"""Sidebar panels (View3D > N > LowPoly Kit)."""

import bpy

from . import adapters, config_ui, prefs, reference, runtime
from .core import messages
from .core.checks import registry

CATEGORY = "LowPoly Kit"
SEVERITY_ICON = {"ERROR": "CANCEL", "WARNING": "ERROR", "INFO": "INFO"}


def tip(layout, context, *lines):
    if prefs.show_tips(context):
        col = layout.column(align=True)
        col.scale_y = 0.8
        for i, line in enumerate(lines):
            col.label(text=line, icon="LIGHT" if i == 0 else "BLANK1")


class _Panel:
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = CATEGORY


class LPK_PT_reference(_Panel, bpy.types.Panel):
    bl_idname = "LPK_PT_reference"
    bl_label = "1. Reference"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        layout.label(text="Thêm ảnh:")
        row = layout.row(align=True)
        for ident, label, _desc in reference.VIEW_ITEMS:
            op = row.operator("lpk.ref_add_image", text=label)
            op.view = ident

        coll = reference.ref_collection(scene, create=False)
        if coll is None or not reference.ref_empties(scene):
            tip(layout, context, "Bắt đầu bằng ảnh Front, rồi Right/Left,", "Back và Top tùy bộ ảnh.")
            return

        layout.prop_search(scene, "lpk_ref_target", coll, "objects", text="Ảnh")
        box = layout.box()
        box.label(text="Căn scale")
        row = box.row(align=True)
        row.prop(scene, "lpk_ref_axis", expand=True)
        box.prop(scene, "lpk_ref_distance")
        op = box.operator("lpk.ref_pick", text="Đặt 2 mốc + mốc gốc", icon="RESTRICT_SELECT_OFF")
        op.mode = "CALIBRATE"
        op.target = scene.lpk_ref_target
        tip(box, context, "Click hai điểm có khoảng cách thật đã biết,", "rồi click mốc gốc (ví dụ đáy giữa vật).")

        box = layout.box()
        box.label(text="Đối chiếu giữa các view")
        row = box.row(align=True)
        op = row.operator("lpk.ref_pick", text="Đo một chiều", icon="DRIVER_DISTANCE")
        op.mode = "MEASURE"
        op.target = scene.lpk_ref_target
        op = row.operator("lpk.ref_clear_measures", text="", icon="TRASH")
        op.target = scene.lpk_ref_target
        for level, line in reference.comparison_lines(scene):
            box.label(text=line, icon="ERROR" if level == "ERROR" else "DOT")

        row = layout.row(align=True)
        row.prop(scene, "lpk_ref_opacity")
        row = layout.row(align=True)
        row.prop(scene, "lpk_ref_locked", icon="LOCKED" if scene.lpk_ref_locked else "UNLOCKED")
        row.prop(scene, "lpk_ref_visible", icon="HIDE_OFF" if scene.lpk_ref_visible else "HIDE_ON")
        row = layout.row(align=True)
        for ident, label, _desc in reference.VIEW_ITEMS:
            op = row.operator("lpk.ref_view", text=label)
            op.view = ident


class LPK_PT_asset(_Panel, bpy.types.Panel):
    bl_idname = "LPK_PT_asset"
    bl_label = "2. Asset"

    def draw(self, context):
        layout = self.layout
        result, _nodes = adapters.find_root_for(context) if context.active_object else (None, None)
        if result is None or result.root is None:
            if result is not None and result.problem != "root_missing":
                layout.label(text=messages.text(result.problem, {"name": result.candidate,
                                                                 "example": config_ui.get_config().get("root_name_example", "")}),
                             icon="ERROR")
            else:
                layout.label(text="Chưa chọn asset", icon="INFO")
            layout.operator("lpk.create_root", icon="EMPTY_AXIS")
            tip(layout, context, "Chọn các mesh rồi bấm Tạo asset root:", "root đặt ở đáy giữa, mesh được parent vào.")
            return
        root = bpy.data.objects[result.root]
        layout.label(text=root.name, icon="EMPTY_AXIS")
        layout.prop(root, "lpk_budget_ui")
        row = layout.row(align=True)
        row.operator("lpk.count_tris", icon="MESH_DATA")
        cache = runtime.tri_cache
        if cache and cache["root"] == result.root:
            st = cache["status"]
            icon = {"OK": "CHECKMARK", "WARNING": "ERROR", "ERROR": "CANCEL"}[st.level]
            layout.label(text=f"{st.total} / {st.limit} tris ({round(st.ratio * 100)}%)", icon=icon)
        tip(layout, context, "Dựng mesh bằng công cụ Blender và parent", "mọi bộ phận vào root.")


class LPK_PT_color(_Panel, bpy.types.Panel):
    bl_idname = "LPK_PT_color"
    bl_label = "3. Tô màu"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        grid = layout.grid_flow(row_major=True, columns=4, even_columns=True, align=True)
        for i, item in enumerate(scene.lpk_palette):
            col = grid.column(align=True)
            col.prop(item, "color", text="")
            op = col.operator("lpk.paint_color", text="", icon="BRUSH_DATA")
            op.index = i
        row = layout.row(align=True)
        row.prop(scene, "lpk_free_color", text="")
        op = row.operator("lpk.paint_color", text="Tô màu tự do")
        op.index = -1
        layout.operator("lpk.setup_vertex_color", icon="NODE_MATERIAL")
        tip(layout, context, "Edit Mode: chọn face rồi bấm ô màu.", "Object Mode: tô toàn bộ mesh đang chọn.")


class LPK_PT_check(_Panel, bpy.types.Panel):
    bl_idname = "LPK_PT_check"
    bl_label = "4. Kiểm tra"

    def draw(self, context):
        layout = self.layout
        layout.operator("lpk.check_asset", icon="VIEWZOOM")
        state = runtime.check_state
        if not state:
            return
        results = state["results"]
        if state.get("stale"):
            layout.label(text=messages.text("check_stale"), icon="TIME")
        if not results:
            layout.label(text=messages.text("check_ok"), icon="CHECKMARK")
            return
        counts = registry.summary_counts(results)
        layout.label(text=f"{counts['ERROR']} lỗi · {counts['WARNING']} cảnh báo · {counts['INFO']} thông tin")
        index_of = {id(r): i for i, r in enumerate(results)}
        for key, group in registry.group_by_object(results):
            box = layout.box()
            box.label(text=key or (state.get("root_name") or "Asset"), icon="OBJECT_DATA" if key else "SCENE_DATA")
            for r in group:
                row = box.row(align=True)
                row.label(text=messages.text(r.code, r.params), icon=SEVERITY_ICON[r.severity])
                i = index_of[id(r)]
                if r.object_key and r.select:
                    op = row.operator("lpk.select_issue", text="", icon="RESTRICT_SELECT_OFF")
                    op.index = i
                if r.fix:
                    op = row.operator("lpk.fix_issue", text="", icon="TOOL_SETTINGS")
                    op.index = i


class LPK_PT_export(_Panel, bpy.types.Panel):
    bl_idname = "LPK_PT_export"
    bl_label = "5. Export Godot"

    def draw(self, context):
        layout = self.layout
        cfg = config_ui.get_config()
        layout.label(text=f"Thư mục: {cfg['export_dir']}/{cfg.get('export_subdir', '')}", icon="FILE_FOLDER")
        layout.operator("lpk.export_godot", icon="EXPORT")
        tip(layout, context, "Export chạy lại kiểm tra và bị chặn khi còn lỗi.")


class LPK_PT_buildplan(_Panel, bpy.types.Panel):
    bl_idname = "LPK_PT_buildplan"
    bl_label = "Build Plan (PoC)"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        root = adapters.get_root_object(context) if context.active_object else None
        if root is None:
            layout.prop(scene, "lpk_plan_asset_name")
        layout.prop(scene, "lpk_plan_notes", text="Ghi chú")
        row = layout.row(align=True)
        row.prop(scene, "lpk_detail_level", expand=True)
        if scene.lpk_detail_level == "DETAILED":
            layout.prop(scene, "lpk_target_tris")
        row = layout.row(align=True)
        row.prop(scene, "lpk_prompt_mode", expand=True)
        if scene.lpk_prompt_mode == "SKILL":
            layout.prop(scene, "lpk_prompt_review")
        col = layout.column(align=True)
        col.operator("lpk.plan_copy_prompt", icon="COPYDOWN")
        col.operator("lpk.plan_paste", icon="PASTEDOWN")
        row = layout.row(align=True)
        row.operator("lpk.plan_open", icon="TEXT")
        row.operator("lpk.plan_rebuild", icon="FILE_REFRESH")
        obj = context.active_object
        if obj is not None and "lpk_part_id" in obj:
            box = layout.box()
            state = "đã bake" if "lpk_baked_params" in obj else "preview"
            box.label(text=f"Part '{obj['lpk_part_id']}' ({state})", icon="MESH_CUBE")
            row = box.row(align=True)
            if "lpk_baked_params" not in obj:
                row.operator("lpk.plan_edit_part", icon="PREFERENCES")
            row.operator("lpk.plan_bake", icon="FREEZE")
        box = layout.box()
        box.label(text="Đo PoC")
        box.prop(scene, "lpk_poc_reference_mask")
        box.operator("lpk.plan_render_mask", icon="RENDER_STILL")
        if runtime.plan_errors:
            layout.operator("lpk.plan_copy_errors", icon="COPYDOWN")
        for code, params, line, col_, _pointer in runtime.plan_errors[:6]:
            layout.label(text=f"{line}:{col_} {messages.text(code, params)}", icon="ERROR")
        tip(layout, context, "Copy Prompt → gửi chatbot kèm ảnh → copy JSON", "→ Dán Plan. Part cam là chi tiết ước lượng",
            "(bật Viewport Shading › Color › Object để thấy).")


class LPK_PT_config(_Panel, bpy.types.Panel):
    bl_idname = "LPK_PT_config"
    bl_label = "Team config"
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        layout.operator("lpk.reload_config", icon="FILE_REFRESH")
        config_ui.draw_config_status(layout)


classes = (LPK_PT_reference, LPK_PT_asset, LPK_PT_color, LPK_PT_check, LPK_PT_export, LPK_PT_buildplan,
           LPK_PT_config)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
