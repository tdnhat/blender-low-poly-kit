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


def _report_errors(op, errors, text=None, draft=""):
    runtime.plan_errors = [(e.code, e.params, e.line, e.col, e.pointer) for e in errors]
    runtime.plan_last_draft = draft
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
        _report_errors(op, result.errors, source_text, text_value)
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
            _report_errors(self, errors, text, text.as_string())
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
        views = [(e[reference.VIEW_PROP], bool(reference.read_data(e).get("cal")))
                 for e in reference.ref_empties(context.scene)]
        context.window_manager.clipboard = core_prompt.build_prompt(asset_name, core_validate.schema_text(), rows, views)
        missing = [v for v, ok in views if not ok]
        msg = f"Đã chép prompt cho {asset_name} ({len(rows)} số đo). Nhớ đính kèm ảnh: {', '.join(v for v, _ in views) or 'các ảnh ortho'}"
        if missing:
            msg += f". Chưa căn scale: {', '.join(missing)}"
        self.report({"INFO"}, msg)
        return {"FINISHED"}


class LPK_OT_plan_copy_errors(bpy.types.Operator):
    bl_idname = "lpk.plan_copy_errors"
    bl_label = "Copy lỗi cho chatbot"
    bl_description = "Chép danh sách lỗi (kèm JSON đã gửi) để dán lại cho chatbot sửa"

    @classmethod
    def poll(cls, context):
        return bool(runtime.plan_errors)

    def execute(self, context):
        rows = [(messages.text(code, params), pointer, line, col) for code, params, line, col, pointer in runtime.plan_errors]
        context.window_manager.clipboard = core_prompt.build_error_prompt(rows, runtime.plan_last_draft)
        self.report({"INFO"}, f"Đã chép {len(rows)} lỗi; dán vào cuộc trò chuyện với chatbot")
        return {"FINISHED"}


SEGMENT_ITEMS = [("4", "4", ""), ("8", "8", ""), ("12", "12", ""), ("16", "16", "")]
CAPS_ITEMS = [("both", "Hai đầu", ""), ("top", "Trên", ""), ("bottom", "Dưới", ""), ("none", "Không", "")]
FACE_ITEMS = [(f, f, "") for f in ("+X", "-X", "+Y", "-Y", "+Z", "-Z")]
PLANE_ITEMS = [("YZ", "YZ (Right)", ""), ("XZ", "XZ (Front)", ""), ("XY", "XY (Top)", "")]


class LPK_OT_plan_edit_part(bpy.types.Operator):
    bl_idname = "lpk.plan_edit_part"
    bl_label = "Chỉnh part"
    bl_description = "Chỉnh tham số của part đang chọn rồi dựng lại (ghi vào plan)"
    bl_options = {"REGISTER", "UNDO"}

    part_id: bpy.props.StringProperty()
    kind: bpy.props.StringProperty(options={"HIDDEN"})
    rule: bpy.props.StringProperty(options={"HIDDEN"})
    segments: bpy.props.EnumProperty(name="Số cạnh", items=SEGMENT_ITEMS)
    caps: bpy.props.EnumProperty(name="Nắp", items=CAPS_ITEMS)
    plane: bpy.props.EnumProperty(name="Mặt phẳng", items=PLANE_ITEMS)
    size: bpy.props.FloatVectorProperty(name="Kích thước", size=3, min=0.0001, unit="LENGTH")
    radius: bpy.props.FloatProperty(name="Bán kính (tới mặt)", min=0.0001, unit="LENGTH")
    height: bpy.props.FloatProperty(name="Chiều cao", min=0.0001, unit="LENGTH")
    depth: bpy.props.FloatProperty(name="Bề dày đùn", min=0.0001, unit="LENGTH")
    radius_scale: bpy.props.FloatProperty(name="Hệ số bán kính", default=1.0, min=0.01)
    height_scale: bpy.props.FloatProperty(name="Hệ số chiều cao", default=1.0, min=0.01)
    profile_scale: bpy.props.FloatVectorProperty(name="Hệ số profile", size=2, default=(1.0, 1.0), min=0.01)
    att_height: bpy.props.FloatProperty(name="Cao độ gắn", unit="LENGTH")
    att_radial_offset: bpy.props.FloatProperty(name="Khoảng nhô", unit="LENGTH")
    att_segment: bpy.props.IntProperty(name="Đoạn profile", min=0)
    att_t: bpy.props.FloatProperty(name="Vị trí t", min=0.0, max=1.0)
    att_normal_offset: bpy.props.FloatProperty(name="Khoảng nhô", unit="LENGTH")
    att_face: bpy.props.EnumProperty(name="Mặt", items=FACE_ITEMS)
    att_u: bpy.props.FloatProperty(name="u", min=0.0, max=1.0)
    att_v: bpy.props.FloatProperty(name="v", min=0.0, max=1.0)
    att_position: bpy.props.FloatVectorProperty(name="Vị trí", size=3, unit="LENGTH")
    att_rotation: bpy.props.FloatVectorProperty(name="Góc (độ)", size=3)

    _fields = ()
    _att_fields = ()
    _scales = ()

    def _load(self, context):
        obj = context.active_object
        if obj is None or store.PART_PROP not in obj:
            return None, None, "Chọn một object do Build Plan tạo"
        if store.BAKED_PROP in obj:
            return None, None, "Part đã bake; chỉnh trực tiếp trong Edit Mode"
        root = adapters.get_root_object(context, obj)
        text = store.plan_text(root) if root else None
        if text is None:
            return None, None, "Không tìm thấy plan của asset"
        plan, errors = core_validate.validate_text(text.as_string(), mode="editor")
        if errors:
            return None, None, "Plan trong Text Editor đang lỗi; sửa rồi Rebuild trước"
        return root, plan, None

    def invoke(self, context, event):
        from .core.buildplan import edit as core_edit

        root, plan, err = self._load(context)
        if err:
            self.report({"WARNING"}, err)
            return {"CANCELLED"}
        self.part_id = str(context.active_object[store.PART_PROP])
        try:
            part = core_edit.find_part(plan, self.part_id)
        except KeyError:
            self.report({"WARNING"}, "Đây là bản đối xứng; chọn part gốc để chỉnh")
            return {"CANCELLED"}
        self.kind = core_edit.part_kind(part)
        self.rule = part.get("attachment", {}).get("rule", "")
        fields, att_fields, _scales = core_edit.editable_fields(part)
        for f in fields:
            value = part[f] if f in part else None
            if value is None:
                continue
            setattr(self, f, str(value) if f == "segments" else value)
        for f in att_fields:
            setattr(self, "att_" + f, part["attachment"][f])
        self.radius_scale = self.height_scale = 1.0
        self.profile_scale = (1.0, 1.0)
        return context.window_manager.invoke_props_dialog(self, width=360)

    def draw(self, context):
        from .core.buildplan import edit as core_edit

        layout = self.layout
        layout.label(text=f"Part '{self.part_id}' ({self.kind})")
        fake = {"op": "add_primitive" if self.kind in ("box", "cylinder") else self.kind, "shape": self.kind}
        if self.rule:
            fake["attachment"] = {"rule": self.rule}
        fields, att_fields, scales = core_edit.editable_fields(fake)
        for f in fields + scales:
            layout.prop(self, f)
        if att_fields:
            box = layout.box()
            box.label(text=f"Gắn: {self.rule}")
            for f in att_fields:
                box.prop(self, "att_" + f)

    def execute(self, context):
        from .core.buildplan import edit as core_edit

        root, plan, err = self._load(context)
        if err:
            self.report({"WARNING"}, err)
            return {"CANCELLED"}
        part = core_edit.find_part(plan, self.part_id)
        fields, att_fields, scales = core_edit.editable_fields(part)
        changes = {}
        for f in fields:
            value = getattr(self, f)
            changes[f] = int(value) if f == "segments" else (list(value) if f == "size" else value)
        for f in att_fields:
            value = getattr(self, "att_" + f)
            changes["att." + f] = list(value) if f in ("position", "rotation") else value
        for f in scales:
            value = getattr(self, f)
            changes[f] = list(value) if f == "profile_scale" else value
        new_plan = core_edit.edit_part(plan, self.part_id, changes)
        return run_plan(self, context, root, core_rc.dump_plan(new_plan), "editor")


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
        if runtime.plan_errors:
            layout.operator("lpk.plan_copy_errors", icon="COPYDOWN")
        for code, params, line, col, _pointer in runtime.plan_errors[:8]:
            layout.label(text=f"{line}:{col} {messages.text(code, params)}", icon="ERROR")


classes = (LPK_OT_plan_paste, LPK_OT_plan_rebuild, LPK_OT_plan_open, LPK_OT_plan_bake, LPK_OT_plan_copy_prompt,
           LPK_OT_plan_copy_errors, LPK_OT_plan_edit_part, LPK_OT_plan_clear_registry, LPK_OT_plan_render_mask, LPK_PT_plan_text)


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
