"""Build Plan operators (PoC): Dán Plan, Rebuild, Bake, Copy Prompt."""

import json

import bpy

from . import adapters, buildplan_store as store, reference, runtime
from .core import messages
from .core.buildplan import prompt as core_prompt
from .core.buildplan import reconcile as core_rc
from .core.buildplan import validate as core_validate


def _active_text_root(context):
    """Root owning the Text shown in the Text Editor, if any."""
    space = context.space_data
    text = getattr(space, "text", None) if space is not None and space.type == "TEXT_EDITOR" else None
    if text is None:
        return None, None
    for obj in context.scene.objects:
        if obj.type == "EMPTY" and obj.get(store.TEXT_PROP) == text.name:
            return obj, text
    return None, text


def _report_errors(op, errors, text=None):
    runtime.plan_errors = [(e.code, e.params, e.line, e.col) for e in errors]
    if text is not None and errors and hasattr(text, "cursor_set"):
        try:
            text.cursor_set(max(0, errors[0].line - 1), character=max(0, errors[0].col - 1))
        except (TypeError, ValueError):
            pass
    first = errors[0]
    op.report({"ERROR"}, messages.text(first.code, first.params) + (f" (+{len(errors) - 1} lỗi)" if len(errors) > 1 else ""))


def _report_notes(op, notes):
    runtime.plan_errors = []
    for code, params in notes:
        op.report({"INFO"}, messages.text(code, params))


def run_plan(op, context, root, text_value, mode, source_text=None):
    """Reconcile and apply; returns Blender operator result set."""
    scene = context.scene
    objects = store.object_states(root, scene) if root else []
    registry = store.read_registry(root) if root else {}
    result = core_rc.reconcile(text_value, mode, root.name if root else None, objects, registry)
    if result.errors:
        _report_errors(op, result.errors, source_text)
        if root is not None:
            store.append_log(root, {"mode": mode, "ok": False, "errors": [e.code for e in result.errors]})
        return {"CANCELLED"}

    if context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    if root is None:
        root = bpy.data.objects.new(result.plan["asset_name"], None)
        root.empty_display_type = "PLAIN_AXES"
        root.empty_display_size = 0.25
        root.location = scene.cursor.location.copy()
        context.collection.objects.link(root)
        context.view_layer.update()
    try:
        store.apply(context, root, result)
    except Exception as exc:  # mesh building failed before scene changes
        op.report({"ERROR"}, messages.text("plan_build_failed", {"reason": str(exc)}))
        store.append_log(root, {"mode": mode, "ok": False, "errors": ["plan_build_failed"], "reason": str(exc)})
        return {"CANCELLED"}
    store.append_log(root, {"mode": mode, "ok": True, "parts": [r.id for r in result.resolved],
                            "plan": result.plan})
    runtime.invalidate_checks()
    _report_notes(op, result.notes)
    return {"FINISHED"}


class LPK_OT_plan_paste(bpy.types.Operator):
    bl_idname = "lpk.plan_paste"
    bl_label = "Dán Plan"
    bl_description = "Dựng blockout từ JSON trong clipboard (bỏ các trường baked, baked_params)"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        value = context.window_manager.clipboard
        if not value.strip():
            self.report({"WARNING"}, messages.text("plan_clipboard_empty"))
            return {"CANCELLED"}
        root = adapters.get_root_object(context) if context.active_object else None
        return run_plan(self, context, root, value, "paste")


class LPK_OT_plan_rebuild(bpy.types.Operator):
    bl_idname = "lpk.plan_rebuild"
    bl_label = "Rebuild"
    bl_description = "Dựng lại blockout từ plan trong Text Editor"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        root, text = _active_text_root(context)
        if root is None and context.active_object is not None:
            root = adapters.get_root_object(context)
            text = store.plan_text(root) if root else None
        if root is None and text is not None:
            # A text not linked yet: build a new asset from it.
            return run_plan(self, context, None, text.as_string(), "editor", text)
        if root is None or text is None:
            self.report({"WARNING"}, "Chọn asset root có plan, hoặc mở file plan trong Text Editor")
            return {"CANCELLED"}
        return run_plan(self, context, root, text.as_string(), "editor", text)


class LPK_OT_plan_open(bpy.types.Operator):
    bl_idname = "lpk.plan_open"
    bl_label = "Mở plan"
    bl_description = "Hiện plan của asset trong Text Editor (tạo mới nếu chưa có)"

    def execute(self, context):
        root = adapters.get_root_object(context) if context.active_object else None
        if root is None:
            self.report({"WARNING"}, "Chọn asset root trước")
            return {"CANCELLED"}
        text = store.plan_text(root, create=True)
        if not text.as_string().strip():
            starter = {"schema_version": 1, "asset_name": root.name, "units": "m", "parts": []}
            text.from_string(json.dumps(starter, ensure_ascii=False, indent=2) + "\n")
        for area in context.screen.areas:
            if area.type == "TEXT_EDITOR":
                area.spaces.active.text = text
                break
        else:
            self.report({"INFO"}, f"Plan nằm trong Text '{text.name}'; mở một Text Editor để sửa")
        return {"FINISHED"}


class LPK_OT_plan_bake(bpy.types.Operator):
    bl_idname = "lpk.plan_bake"
    bl_label = "Bake part"
    bl_description = "Đóng băng part đang chọn: giữ mesh và transform, rebuild không ghi đè"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        obj = context.active_object
        if obj is None or store.PART_PROP not in obj:
            self.report({"WARNING"}, "Chọn một object do Build Plan tạo")
            return {"CANCELLED"}
        root = adapters.get_root_object(context, obj)
        text = store.plan_text(root) if root else None
        if text is None:
            self.report({"ERROR"}, "Không tìm thấy plan của asset")
            return {"CANCELLED"}
        plan, errors = core_validate.validate_text(text.as_string(), mode="editor")
        if errors:
            _report_errors(self, errors, text)
            return {"CANCELLED"}
        part_id = str(obj[store.PART_PROP])
        try:
            baked_plan, snap = core_rc.bake_part(plan, part_id)
        except KeyError:
            self.report({"ERROR"}, f"Plan không có part '{part_id}'")
            return {"CANCELLED"}
        store.set_baked(obj, snap)
        text.from_string(core_rc.dump_plan(baked_plan))
        self.report({"INFO"}, f"Đã bake '{part_id}'. Phần con gắn vào part này sẽ dựng theo snapshot lúc bake.")
        return {"FINISHED"}


class LPK_OT_plan_copy_prompt(bpy.types.Operator):
    bl_idname = "lpk.plan_copy_prompt"
    bl_label = "Copy Prompt"
    bl_description = "Chép prompt (schema + số đo đã xác nhận) vào clipboard để gửi chatbot kèm ảnh"

    def execute(self, context):
        root = adapters.get_root_object(context) if context.active_object else None
        asset_name = root.name if root else context.scene.lpk_plan_asset_name
        if not asset_name:
            self.report({"WARNING"}, "Chọn asset root hoặc nhập tên asset")
            return {"CANCELLED"}
        ms, _views = reference.measurements(context.scene)
        rows = [(m.view, m.dimension, m.meters) for m in ms]
        context.window_manager.clipboard = core_prompt.build_prompt(asset_name, core_validate.schema_text(), rows)
        self.report({"INFO"}, f"Đã chép prompt cho {asset_name} ({len(rows)} số đo)")
        return {"FINISHED"}


class LPK_OT_plan_clear_registry(bpy.types.Operator):
    bl_idname = "lpk.plan_clear_registry"
    bl_label = "Xóa bảng tham chiếu part"
    bl_description = "Gỡ bảng part → object của root (dùng để thử trường hợp trùng ID)"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        root = adapters.get_root_object(context) if context.active_object else None
        if root is None or store.REGISTRY_PROP not in root:
            return {"CANCELLED"}
        del root[store.REGISTRY_PROP]
        return {"FINISHED"}


def render_mask(context, root, empty, filepath):
    """Render the asset silhouette for a calibrated reference view (Workbench,
    transparent film, no anti-aliasing) into ``filepath``. The user's scene
    and objects are not modified: copies are rendered in a temporary scene."""
    from mathutils import Matrix

    from .core import reference as core_ref
    from .core import scope as core_scope

    geom = reference.image_geom(empty)
    if geom is None:
        raise ValueError(messages.text("ref_image_not_loaded", {"name": empty.name}))
    lw, lh = core_ref.local_size(geom)
    cx, cy = core_ref.uv_to_local(geom, (0.5, 0.5))

    nodes = adapters.scene_index(context)
    scope = core_scope.collect(nodes, root.name)
    tmp = bpy.data.scenes.new("LPK_MASK_TMP")
    cam_data = bpy.data.cameras.new("LPK_MASK_CAM")
    cam = bpy.data.objects.new("LPK_MASK_CAM", cam_data)
    copies = []
    try:
        for key in scope.meshes:
            src = bpy.data.objects[key]
            copy = src.copy()
            copy.parent = None
            copy.matrix_world = src.matrix_world.copy()
            copy.hide_render = False
            tmp.collection.objects.link(copy)
            copies.append(copy)
        cam_data.type = "ORTHO"
        cam_data.ortho_scale = max(lw, lh)
        cam_data.sensor_fit = "AUTO"
        cam_data.clip_start = 0.01
        cam_data.clip_end = 1000.0
        tmp.collection.objects.link(cam)
        cam.matrix_world = empty.matrix_world @ Matrix.Translation((cx, cy, 100.0))
        tmp.camera = cam
        r = tmp.render
        r.engine = "BLENDER_WORKBENCH"
        r.resolution_x, r.resolution_y = geom.width_px, geom.height_px
        r.resolution_percentage = 100
        r.pixel_aspect_x = r.pixel_aspect_y = 1.0
        r.film_transparent = True
        r.image_settings.file_format = "PNG"
        r.image_settings.color_mode = "RGBA"
        r.filepath = filepath
        tmp.display.render_aa = "OFF"
        tmp.display.shading.light = "FLAT"
        tmp.display.shading.color_type = "SINGLE"
        bpy.ops.render.render(write_still=True, scene=tmp.name)
    finally:
        for copy in copies:
            bpy.data.objects.remove(copy, do_unlink=True)
        bpy.data.objects.remove(cam, do_unlink=True)
        bpy.data.cameras.remove(cam_data)
        bpy.data.scenes.remove(tmp)
    return filepath


class LPK_OT_plan_render_mask(bpy.types.Operator):
    bl_idname = "lpk.plan_render_mask"
    bl_label = "Render mask"
    bl_description = "Render silhouette của asset theo view tham chiếu đang chọn và đo sai số đường bao"

    def execute(self, context):
        import os
        import tempfile

        from .core import metrics, png

        root = adapters.get_root_object(context) if context.active_object else None
        empty = bpy.data.objects.get(context.scene.lpk_ref_target)
        if root is None or empty is None or not empty.get(reference.VIEW_PROP):
            self.report({"WARNING"}, "Chọn asset root và ảnh tham chiếu đã căn scale")
            return {"CANCELLED"}
        view = empty[reference.VIEW_PROP]
        folder = bpy.path.abspath("//poc") if bpy.data.filepath else tempfile.gettempdir()
        os.makedirs(folder, exist_ok=True)
        out = os.path.join(folder, f"{root.name}_{view}_mask.png")
        try:
            render_mask(context, root, empty, out)
        except (ValueError, RuntimeError) as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        ref_path = bpy.path.abspath(context.scene.lpk_poc_reference_mask)
        if ref_path and os.path.isfile(ref_path):
            _w, _h, ref_rows = png.read_file(ref_path)
            _w2, _h2, model_rows = png.read_file(out)
            err = metrics.outline_error(png.mask(ref_rows), png.mask(model_rows, use_alpha=True))
            self.report({"INFO"}, f"{view}: sai số đường bao {err * 100:.2f}% · mask: {out}")
        else:
            self.report({"INFO"}, f"Đã render mask: {out}")
        return {"FINISHED"}


class LPK_PT_plan_text(bpy.types.Panel):
    bl_idname = "LPK_PT_plan_text"
    bl_label = "LowPoly Kit"
    bl_space_type = "TEXT_EDITOR"
    bl_region_type = "UI"
    bl_category = "LowPoly Kit"

    def draw(self, context):
        layout = self.layout
        layout.operator("lpk.plan_rebuild", icon="FILE_REFRESH")
        for code, params, line, col in runtime.plan_errors[:8]:
            layout.label(text=f"{line}:{col} {messages.text(code, params)}", icon="ERROR")


classes = (LPK_OT_plan_paste, LPK_OT_plan_rebuild, LPK_OT_plan_open, LPK_OT_plan_bake, LPK_OT_plan_copy_prompt,
           LPK_OT_plan_clear_registry, LPK_OT_plan_render_mask, LPK_PT_plan_text)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.lpk_plan_asset_name = bpy.props.StringProperty(
        name="Tên asset", description="Tên asset cho Copy Prompt khi chưa có root")
    bpy.types.Scene.lpk_poc_reference_mask = bpy.props.StringProperty(
        name="Mask tham chiếu", subtype="FILE_PATH", description="PNG mask đã duyệt của view đang chọn (đo PoC)")


def unregister():
    del bpy.types.Scene.lpk_poc_reference_mask
    del bpy.types.Scene.lpk_plan_asset_name
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
