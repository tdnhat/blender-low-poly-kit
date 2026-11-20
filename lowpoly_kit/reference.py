"""Reference Setup: image empties, landmark picking, cross-view comparison."""

import json
import os

import bpy
import gpu
from bpy.props import BoolProperty, EnumProperty, FloatProperty, StringProperty
from bpy_extras import view3d_utils
from gpu_extras.batch import batch_for_shader
from mathutils import Vector
from mathutils.geometry import intersect_line_plane

from . import config_ui
from .core import messages
from .core import reference as core_ref

REF_COLLECTION = "REF"
VIEW_PROP = "lpk_ref_view"
DATA_PROP = "lpk_ref_data"

VIEW_ITEMS = [
    ("FRONT", "Front", "Ảnh nhìn từ trước"),
    ("RIGHT", "Right", "Ảnh nhìn từ bên phải"),
    ("LEFT", "Left", "Ảnh nhìn từ bên trái"),
    ("BACK", "Back", "Ảnh nhìn từ sau"),
    ("TOP", "Top", "Ảnh nhìn từ trên"),
]
AXIS_ITEMS = [
    ("v", "Dọc", "Khoảng cách đo theo chiều dọc của ảnh"),
    ("h", "Ngang", "Khoảng cách đo theo chiều ngang của ảnh"),
]


# ---------------------------------------------------------------- data on empties

def ref_collection(scene, create=True):
    coll = bpy.data.collections.get(REF_COLLECTION)
    if coll is None and create:
        coll = bpy.data.collections.new(REF_COLLECTION)
    if coll is not None and create and coll.name not in scene.collection.children:
        scene.collection.children.link(coll)
    return coll


def ref_empties(scene):
    coll = ref_collection(scene, create=False)
    if coll is None:
        return []
    return [o for o in coll.objects if o.type == "EMPTY" and o.get(VIEW_PROP)]


def read_data(empty):
    try:
        return json.loads(empty.get(DATA_PROP, "{}"))
    except (TypeError, ValueError):
        return {}


def write_data(empty, data):
    empty[DATA_PROP] = json.dumps(data)


def image_geom(empty):
    img = empty.data
    if img is None:
        return None
    w, h = img.size
    if w == 0 or h == 0:
        return None
    return core_ref.ImageGeom(w, h, empty.empty_display_size, tuple(empty.empty_image_offset))


def apply_display(empty, scene):
    empty.empty_display_type = "IMAGE"
    empty.empty_image_depth = "BACK"
    empty.empty_image_side = "FRONT"
    empty.show_empty_image_orthographic = True
    empty.show_empty_image_perspective = False
    empty.show_empty_image_only_axis_aligned = True
    empty.use_empty_image_alpha = True
    empty.color[3] = scene.lpk_ref_opacity
    empty.hide_select = scene.lpk_ref_locked


def measurements(scene):
    """core Measurement list and the set of views present."""
    out, views = [], set()
    for empty in ref_empties(scene):
        view = empty[VIEW_PROP]
        views.add(view)
        data = read_data(empty)
        geom = image_geom(empty)
        cal = data.get("cal")
        if cal:
            out.append(core_ref.Measurement(view, core_ref.dimension(view, cal["axis"]), cal["distance"], False))
        if geom is None:
            continue
        for m in data.get("measures", []):
            meters = core_ref.measure(geom, m["a"], m["b"], m["axis"])
            out.append(core_ref.Measurement(view, core_ref.dimension(view, m["axis"]), meters, True))
    return out, views


def comparison_lines(scene):
    cfg = config_ui.get_config()
    ms, views = measurements(scene)
    mismatches, missing = core_ref.compare(views, ms, cfg["reference_tolerance"])
    lines = []
    for d, va, a, vb, b, delta in mismatches:
        lines.append(("ERROR", messages.text("ref_mismatch", {
            "dimension": messages.DIMENSIONS[d], "view_a": va, "a": round(a, 4), "view_b": vb, "b": round(b, 4),
            "delta": round(delta, 4), "tolerance": cfg["reference_tolerance"]})))
    for view, d in missing:
        lines.append(("INFO", f"{view} · {messages.DIMENSIONS[d]}: {messages.text('ref_not_measured')}"))
    return lines


# ---------------------------------------------------------------- scene property callbacks

def _update_opacity(self, context):
    for e in ref_empties(context.scene):
        e.color[3] = self.lpk_ref_opacity


def _update_locked(self, context):
    for e in ref_empties(context.scene):
        e.hide_select = self.lpk_ref_locked


def _update_visible(self, context):
    coll = ref_collection(context.scene, create=False)
    if coll is not None:
        coll.hide_viewport = not self.lpk_ref_visible


# ---------------------------------------------------------------- operators

class LPK_OT_ref_add_image(bpy.types.Operator):
    bl_idname = "lpk.ref_add_image"
    bl_label = "Thêm ảnh tham chiếu"
    bl_description = "Nạp một ảnh ortho và đặt theo hướng nhìn đã chọn"
    bl_options = {"REGISTER", "UNDO"}

    filepath: StringProperty(subtype="FILE_PATH")
    filter_image: BoolProperty(default=True, options={"HIDDEN", "SKIP_SAVE"})
    filter_folder: BoolProperty(default=True, options={"HIDDEN", "SKIP_SAVE"})
    view: EnumProperty(name="Hướng nhìn", items=VIEW_ITEMS, default="FRONT")

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        if not self.filepath or not os.path.isfile(bpy.path.abspath(self.filepath)):
            self.report({"ERROR"}, "Chưa chọn file ảnh")
            return {"CANCELLED"}
        img = bpy.data.images.load(self.filepath, check_existing=True)
        if img.size[0] == 0 or img.size[1] == 0:
            self.report({"ERROR"}, messages.text("ref_image_not_loaded", {"name": img.name}))
            return {"CANCELLED"}
        scene = context.scene
        coll = ref_collection(scene)
        name = f"REF_{self.view.title()}"
        old = bpy.data.objects.get(name)
        if old is not None and old.get(VIEW_PROP):
            bpy.data.objects.remove(old, do_unlink=True)
        empty = bpy.data.objects.new(name, None)
        coll.objects.link(empty)
        empty.empty_display_type = "IMAGE"
        empty.data = img
        empty.empty_display_size = 1.0
        empty.empty_image_offset = (-0.5, -0.5)
        empty.rotation_euler = [v * 3.141592653589793 / 180.0 for v in core_ref.VIEWS[self.view].rotation]
        empty[VIEW_PROP] = self.view
        write_data(empty, {})
        apply_display(empty, scene)
        scene.lpk_ref_target = empty.name
        self.report({"INFO"}, f"Đã thêm {name}. Bước tiếp: đặt mốc căn scale.")
        return {"FINISHED"}


def _window_region_under_mouse(area, event):
    for region in area.regions:
        if region.type != "WINDOW":
            continue
        if region.x <= event.mouse_x < region.x + region.width and region.y <= event.mouse_y < region.y + region.height:
            return region
    return None


_draw_handle = None
_draw_points = []


def _draw_callback():
    if not _draw_points:
        return
    shader = gpu.shader.from_builtin("POINT_UNIFORM_COLOR")
    batch = batch_for_shader(shader, "POINTS", {"pos": _draw_points})
    gpu.state.point_size_set(10.0)
    shader.uniform_float("color", (1.0, 0.2, 0.1, 1.0))
    batch.draw(shader)
    gpu.state.point_size_set(1.0)


class LPK_OT_ref_pick(bpy.types.Operator):
    bl_idname = "lpk.ref_pick"
    bl_label = "Đặt mốc"
    bl_description = "Click lên ảnh tham chiếu trong view ortho để đặt mốc"
    bl_options = {"REGISTER", "UNDO"}

    mode: EnumProperty(items=[("CALIBRATE", "Căn scale", "Hai mốc căn scale rồi mốc gốc"),
                              ("MEASURE", "Đo đối chiếu", "Hai mốc đo một chiều để đối chiếu")])
    target: StringProperty()

    _points = None

    @classmethod
    def poll(cls, context):
        return context.area is not None and context.area.type == "VIEW_3D"

    def needed(self):
        return 3 if self.mode == "CALIBRATE" else 2

    def prompt(self):
        n = len(self._points)
        if self.mode == "CALIBRATE":
            steps = ["Click mốc căn scale thứ nhất", "Click mốc căn scale thứ hai", "Click mốc gốc (ví dụ đáy giữa vật)"]
        else:
            steps = ["Click đầu thứ nhất của chiều cần đo", "Click đầu thứ hai"]
        return f"{steps[n]}  ·  Chuột phải/Esc: hủy  ·  Chuột giữa/lăn: điều hướng"

    def invoke(self, context, event):
        global _draw_handle, _draw_points
        scene = context.scene
        empty = bpy.data.objects.get(self.target or scene.lpk_ref_target)
        if empty is None or not empty.get(VIEW_PROP):
            self.report({"ERROR"}, "Chưa chọn ảnh tham chiếu")
            return {"CANCELLED"}
        if self.mode == "CALIBRATE" and scene.lpk_ref_distance <= 0:
            self.report({"ERROR"}, messages.text("ref_need_distance"))
            return {"CANCELLED"}
        if self.mode == "MEASURE" and not read_data(empty).get("cal"):
            self.report({"ERROR"}, "Căn scale ảnh này trước khi đo đối chiếu")
            return {"CANCELLED"}
        self.target = empty.name
        self._points = []
        _draw_points = []
        if _draw_handle is None:
            _draw_handle = bpy.types.SpaceView3D.draw_handler_add(_draw_callback, (), "WINDOW", "POST_VIEW")
        context.window_manager.modal_handler_add(self)
        context.area.header_text_set(self.prompt())
        return {"RUNNING_MODAL"}

    def finish(self, context):
        global _draw_handle, _draw_points
        _draw_points = []
        if _draw_handle is not None:
            bpy.types.SpaceView3D.draw_handler_remove(_draw_handle, "WINDOW")
            _draw_handle = None
        if context.area is not None:
            context.area.header_text_set(None)
            context.area.tag_redraw()

    def modal(self, context, event):
        empty = bpy.data.objects.get(self.target)
        if empty is None:
            self.finish(context)
            return {"CANCELLED"}
        if event.type in {"MIDDLEMOUSE", "WHEELUPMOUSE", "WHEELDOWNMOUSE", "TRACKPADPAN", "TRACKPADZOOM",
                          "MOUSEROTATE", "NDOF_MOTION"} or event.type.startswith("NUMPAD"):
            return {"PASS_THROUGH"}
        if event.type in {"RIGHTMOUSE", "ESC"} and event.value == "PRESS":
            self.finish(context)
            return {"CANCELLED"}
        if event.type == "Z" and event.ctrl:
            return {"RUNNING_MODAL"}
        if event.type != "LEFTMOUSE" or event.value != "PRESS":
            return {"RUNNING_MODAL"} if event.type != "MOUSEMOVE" else {"PASS_THROUGH"}

        region = _window_region_under_mouse(context.area, event)
        if region is None:
            return {"RUNNING_MODAL"}
        rv3d = region.data
        view = empty[VIEW_PROP]
        coord = (event.mouse_x - region.x, event.mouse_y - region.y)
        direction = view3d_utils.region_2d_to_vector_3d(region, rv3d, coord)
        if rv3d.is_perspective or not core_ref.aligned(tuple(direction), view):
            self.report({"WARNING"}, messages.text("ref_not_ortho"))
            return {"RUNNING_MODAL"}
        origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, coord)
        plane_co = empty.matrix_world.translation
        plane_no = empty.matrix_world.to_3x3() @ Vector((0.0, 0.0, 1.0))
        hit = intersect_line_plane(origin, origin + direction, plane_co, plane_no)
        if hit is None:
            return {"RUNNING_MODAL"}
        local = empty.matrix_world.inverted() @ hit
        geom = image_geom(empty)
        if geom is None:
            self.report({"ERROR"}, messages.text("ref_image_not_loaded", {"name": empty.name}))
            self.finish(context)
            return {"CANCELLED"}
        self._points.append(core_ref.local_to_uv(geom, (local.x, local.y)))
        _draw_points.append(tuple(hit))
        context.area.tag_redraw()
        if len(self._points) < self.needed():
            context.area.header_text_set(self.prompt())
            return {"RUNNING_MODAL"}

        ok = self.apply(context, empty, geom)
        self.finish(context)
        return {"FINISHED"} if ok else {"CANCELLED"}

    def apply(self, context, empty, geom):
        scene = context.scene
        data = read_data(empty)
        axis = scene.lpk_ref_axis
        if self.mode == "CALIBRATE":
            cal = core_ref.Calibration(self._points[0], self._points[1], axis, scene.lpk_ref_distance)
            try:
                new_geom, _mpp = core_ref.calibrate(geom.width_px, geom.height_px, cal, self._points[2])
            except ValueError as exc:
                self.report({"ERROR"}, messages.text(str(exc)))
                return False
            empty.empty_display_size = new_geom.display_size
            empty.empty_image_offset = new_geom.offset
            empty.location = (0.0, 0.0, 0.0)
            # Landmarks stay valid in uv; earlier extra measurements remain usable.
            data["cal"] = {"a": list(cal.a), "b": list(cal.b), "axis": axis, "distance": cal.distance}
            data["origin"] = list(self._points[2])
            self.report({"INFO"}, f"Đã căn scale {empty.name}")
        else:
            data.setdefault("measures", []).append({"a": list(self._points[0]), "b": list(self._points[1]), "axis": axis})
            meters = core_ref.measure(geom, self._points[0], self._points[1], axis)
            dim = messages.DIMENSIONS[core_ref.dimension(empty[VIEW_PROP], axis)]
            self.report({"INFO"}, f"{empty.name}: {dim} = {meters:.4f} m")
        write_data(empty, data)
        return True


class LPK_OT_ref_clear_measures(bpy.types.Operator):
    bl_idname = "lpk.ref_clear_measures"
    bl_label = "Xóa số đo đối chiếu"
    bl_options = {"REGISTER", "UNDO"}

    target: StringProperty()

    def execute(self, context):
        empty = bpy.data.objects.get(self.target or context.scene.lpk_ref_target)
        if empty is None:
            return {"CANCELLED"}
        data = read_data(empty)
        data["measures"] = []
        write_data(empty, data)
        return {"FINISHED"}


class LPK_OT_ref_view(bpy.types.Operator):
    bl_idname = "lpk.ref_view"
    bl_label = "Đổi view"
    bl_description = "Chuyển sang view ortho tương ứng với ảnh"

    view: EnumProperty(items=VIEW_ITEMS)

    @classmethod
    def poll(cls, context):
        return context.area is not None and context.area.type == "VIEW_3D"

    def execute(self, context):
        bpy.ops.view3d.view_axis(type=self.view)
        rv3d = context.region_data
        if rv3d is None:
            rv3d = context.area.spaces.active.region_3d
        if rv3d is not None:
            rv3d.view_perspective = "ORTHO"
        empty = bpy.data.objects.get(f"REF_{self.view.title()}")
        if empty is not None:
            context.scene.lpk_ref_target = empty.name
        return {"FINISHED"}


classes = (LPK_OT_ref_add_image, LPK_OT_ref_pick, LPK_OT_ref_clear_measures, LPK_OT_ref_view)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    S = bpy.types.Scene
    S.lpk_ref_target = StringProperty(name="Ảnh đang căn")
    S.lpk_ref_axis = EnumProperty(name="Trục", items=AXIS_ITEMS, default="v")
    S.lpk_ref_distance = FloatProperty(name="Khoảng cách thật", unit="LENGTH", min=0.0, default=1.0,
                                       description="Khoảng cách thật giữa hai mốc căn scale, theo trục đã chọn")
    S.lpk_ref_opacity = FloatProperty(name="Opacity", min=0.0, max=1.0, default=0.5, subtype="FACTOR",
                                      update=_update_opacity)
    S.lpk_ref_locked = BoolProperty(name="Khóa chọn", default=True, update=_update_locked)
    S.lpk_ref_visible = BoolProperty(name="Hiện ảnh", default=True, update=_update_visible)


def unregister():
    global _draw_handle
    if _draw_handle is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_draw_handle, "WINDOW")
        _draw_handle = None
    S = bpy.types.Scene
    for name in ("lpk_ref_visible", "lpk_ref_locked", "lpk_ref_opacity", "lpk_ref_distance", "lpk_ref_axis",
                 "lpk_ref_target"):
        delattr(S, name)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
