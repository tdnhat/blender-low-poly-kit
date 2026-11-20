"""Vertex colour: attribute setup, material, palette painting."""

import bpy
from bpy.props import CollectionProperty, FloatVectorProperty, IntProperty

from . import config_ui, materials, runtime
from .core import coloring as core_coloring
from .core import colors as core_colors

ATTR_DOMAIN = "CORNER"
ATTR_TYPE = "BYTE_COLOR"


# ---------------------------------------------------------------- attribute

def _read_srgb(attr):
    flat = [0.0] * (len(attr.data) * 4)
    attr.data.foreach_get("color_srgb", flat)
    return core_coloring.unflatten(flat)


def _write_srgb(attr, rgba_list):
    attr.data.foreach_set("color_srgb", core_coloring.flatten(rgba_list))


def _set_active(mesh, name):
    ca = mesh.color_attributes
    if hasattr(ca, "active_color_name"):
        ca.active_color_name = name
    if hasattr(ca, "default_color_name"):
        ca.default_color_name = name
    names = [a.name for a in ca]
    if name in names and hasattr(ca, "render_color_index"):
        ca.render_color_index = names.index(name)


def _initial_corner_colors(obj, cfg):
    """Colours to keep when creating the attribute: old materials, else default."""
    mesh = obj.data
    fallback = core_colors.hex_to_srgb(cfg["default_color"])
    loop_starts = [0] * len(mesh.polygons)
    loop_totals = [0] * len(mesh.polygons)
    mat_index = [0] * len(mesh.polygons)
    mesh.polygons.foreach_get("loop_start", loop_starts)
    mesh.polygons.foreach_get("loop_total", loop_totals)
    mesh.polygons.foreach_get("material_index", mat_index)
    slot_colors = [materials.base_color_srgb(s.material) for s in obj.material_slots]
    return core_coloring.corners_from_face_materials(loop_starts, loop_totals, mat_index, slot_colors, fallback)


def ensure_color_attribute(obj, cfg):
    """Make sure ``obj`` has the CORNER/BYTE_COLOR attribute, keeping existing colours.

    Must run in Object Mode.
    """
    mesh = obj.data
    name = cfg["color_attribute"]
    attr = mesh.color_attributes.get(name)
    if attr is not None and attr.domain == ATTR_DOMAIN and attr.data_type == ATTR_TYPE:
        _set_active(mesh, name)
        return attr

    if attr is not None:
        old = _read_srgb(attr)
        if attr.domain == "POINT":
            loop_vi = [0] * len(mesh.loops)
            mesh.loops.foreach_get("vertex_index", loop_vi)
            corner = core_coloring.corners_from_point_colors(loop_vi, old)
        else:
            corner = old
        mesh.color_attributes.remove(attr)
    else:
        corner = _initial_corner_colors(obj, cfg)

    attr = mesh.color_attributes.new(name=name, type=ATTR_TYPE, domain=ATTR_DOMAIN)
    if len(corner) == len(attr.data):
        _write_srgb(attr, corner)
    _set_active(mesh, name)
    return attr


def setup_vertex_color(obj, cfg):
    """Attribute + single vertex-colour material on every slot of ``obj``."""
    ensure_color_attribute(obj, cfg)
    mat = materials.ensure(cfg["material_name"], cfg["color_attribute"])
    mesh = obj.data
    mesh.materials.clear()
    mesh.materials.append(mat)
    # Faces pointed at removed slots fall back to slot 0.
    mesh.polygons.foreach_set("material_index", [0] * len(mesh.polygons))
    return mat


# ---------------------------------------------------------------- painting

def paint_objects(objects, rgb, cfg, selected_only):
    painted = 0
    for obj in objects:
        if obj.type != "MESH" or obj.data.library is not None:
            continue
        mesh = obj.data
        attr = ensure_color_attribute(obj, cfg)
        if not any(s.material for s in obj.material_slots):
            setup_vertex_color(obj, cfg)
            attr = mesh.color_attributes.get(cfg["color_attribute"])
        n = len(mesh.polygons)
        starts, totals, sel = [0] * n, [0] * n, [False] * n
        mesh.polygons.foreach_get("loop_start", starts)
        mesh.polygons.foreach_get("loop_total", totals)
        mesh.polygons.foreach_get("select", sel)
        faces = [i for i in range(n) if sel[i]] if selected_only else list(range(n))
        if not faces:
            continue
        corners = core_coloring.face_corners(starts, totals, faces)
        colors = core_coloring.fill_corners(_read_srgb(attr), corners, rgb)
        _write_srgb(attr, colors)
        mesh.update()
        painted += len(faces)
    return painted


class LPK_PaletteColor(bpy.types.PropertyGroup):
    color: FloatVectorProperty(name="Màu", subtype="COLOR_GAMMA", size=3, min=0.0, max=1.0)


def sync_palette(scene, cfg):
    scene.lpk_palette.clear()
    for _hex, rgb in core_coloring.palette(cfg):
        item = scene.lpk_palette.add()
        item.color = rgb


def _sync_palette_timer():
    cfg = config_ui.get_config()
    wanted = [h for h, _rgb in core_coloring.palette(cfg)]
    for scene in bpy.data.scenes:
        current = [core_colors.srgb_to_hex(item.color) for item in scene.lpk_palette]
        if current != wanted:
            sync_palette(scene, cfg)
    return None


def schedule_palette_sync():
    if not bpy.app.timers.is_registered(_sync_palette_timer):
        bpy.app.timers.register(_sync_palette_timer, first_interval=0.1)


class LPK_OT_paint_color(bpy.types.Operator):
    bl_idname = "lpk.paint_color"
    bl_label = "Tô màu"
    bl_description = "Edit Mode: tô các face đang chọn. Object Mode: tô toàn bộ mesh đang chọn"
    bl_options = {"REGISTER", "UNDO"}

    index: IntProperty(name="Ô palette", default=-1, description="-1 = màu tự do")

    @classmethod
    def poll(cls, context):
        return any(o.type == "MESH" for o in (context.selected_objects or [])) or (
            context.active_object is not None and context.active_object.type == "MESH")

    def execute(self, context):
        cfg = config_ui.get_config()
        scene = context.scene
        if self.index >= 0:
            if self.index >= len(scene.lpk_palette):
                sync_palette(scene, cfg)
            if self.index >= len(scene.lpk_palette):
                self.report({"ERROR"}, "Ô palette không tồn tại")
                return {"CANCELLED"}
            rgb = tuple(scene.lpk_palette[self.index].color)
        else:
            rgb = tuple(scene.lpk_free_color)

        edit = context.mode == "EDIT_MESH"
        objects = list(context.objects_in_mode) if edit else [o for o in context.selected_objects if o.type == "MESH"]
        if edit:
            # Write through the attribute API in Object Mode; selection is kept.
            bpy.ops.object.mode_set(mode="OBJECT")
        try:
            count = paint_objects(objects, rgb, cfg, selected_only=edit)
        finally:
            if edit:
                bpy.ops.object.mode_set(mode="EDIT")
        runtime.invalidate_checks()
        self.report({"INFO"}, f"Đã tô {count} face ({core_colors.srgb_to_hex(rgb)})")
        return {"FINISHED"}


class LPK_OT_setup_vertex_color(bpy.types.Operator):
    bl_idname = "lpk.setup_vertex_color"
    bl_label = "Khởi tạo vertex color"
    bl_description = "Tạo attribute Color (CORNER/BYTE_COLOR) và material vertex color, giữ màu đã có khi có thể"
    bl_options = {"REGISTER", "UNDO"}

    object_name: bpy.props.StringProperty(default="")

    def execute(self, context):
        cfg = config_ui.get_config()
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        if self.object_name:
            objs = [bpy.data.objects.get(self.object_name)]
        else:
            objs = [o for o in context.selected_objects if o.type == "MESH"]
        done = 0
        for obj in objs:
            if obj is None or obj.type != "MESH" or obj.data.library is not None:
                continue
            setup_vertex_color(obj, cfg)
            done += 1
        runtime.invalidate_checks()
        self.report({"INFO"}, f"Đã khởi tạo vertex color cho {done} mesh")
        return {"FINISHED"}


classes = (LPK_PaletteColor, LPK_OT_paint_color, LPK_OT_setup_vertex_color)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.lpk_palette = CollectionProperty(type=LPK_PaletteColor)
    bpy.types.Scene.lpk_free_color = FloatVectorProperty(
        name="Màu tự do", subtype="COLOR_GAMMA", size=3, min=0.0, max=1.0, default=(0.8, 0.8, 0.8))
    schedule_palette_sync()


def unregister():
    if bpy.app.timers.is_registered(_sync_palette_timer):
        bpy.app.timers.unregister(_sync_palette_timer)
    del bpy.types.Scene.lpk_free_color
    del bpy.types.Scene.lpk_palette
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
