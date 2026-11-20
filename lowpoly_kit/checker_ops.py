"""Running the checker in Blender and selecting the reported elements."""

import bpy
from bpy.app.handlers import persistent
from bpy.props import IntProperty
from mathutils import Vector

from . import adapters, assets, config_ui, runtime, tempcopies
from .core import scope as core_scope
from .core import vecmath as vm
from .core.checks import asset as asset_checks
from .core.checks import registry
from .core.checks import topology


class ModeGuard:
    """Switch to Object Mode for the duration of a block, then restore."""

    def __init__(self, context):
        self.context = context
        self.mode = context.mode
        self.active = context.view_layer.objects.active

    def __enter__(self):
        if self.mode != "OBJECT" and self.active is not None:
            bpy.ops.object.mode_set(mode="OBJECT")
        return self

    def __exit__(self, exc_type, exc, tb):
        if self.mode == "EDIT_MESH" and self.active is not None:
            try:
                self.context.view_layer.objects.active = self.active
                bpy.ops.object.mode_set(mode="EDIT")
            except (RuntimeError, ReferenceError):
                pass
        return False


def _bounds_in_root(copies, root_key, depsgraph):
    root = copies.copies[root_key]
    to_root = root.matrix_world.inverted()
    lo = [float("inf")] * 3
    hi = [float("-inf")] * 3
    found = False
    for key, copy in copies.copies.items():
        if key == root_key or copy.type != "MESH":
            continue
        eval_obj = copy.evaluated_get(depsgraph)
        m = to_root @ copy.matrix_world
        for corner in eval_obj.bound_box:
            p = m @ Vector(corner)
            lo = [min(a, b) for a, b in zip(lo, p)]
            hi = [max(a, b) for a, b in zip(hi, p)]
            found = True
    return (tuple(lo), tuple(hi)) if found else None


def gather(context, start_obj=None):
    """Collect checker input. Returns (AssetData, {key: MeshData}) or raises."""
    cfg = config_ui.get_config()
    result, nodes = adapters.find_root_for(context, start_obj)
    unit = context.scene.unit_settings.scale_length
    if result.root is None:
        return asset_checks.AssetData(result, None, None, nodes, [], None, unit, None), {}

    scope = core_scope.collect(nodes, result.root)
    root_obj = bpy.data.objects[result.root]
    group = assets.budget_group_of(root_obj, cfg)
    infos, mesh_datas = [], {}
    with tempcopies.TempCopies(context, nodes, scope) as copies:
        depsgraph = context.evaluated_depsgraph_get()
        for key in scope.meshes:
            obj = bpy.data.objects[key]
            tris = adapters.evaluated_tris(copies.copies[key], depsgraph)
            infos.append(adapters.mesh_info(obj, tris, cfg))
            det_sign = 1 if vm.det3(nodes[key].matrix_world) >= 0 else -1
            mesh_datas[key] = adapters.mesh_data(obj, det_sign)
        bounds = _bounds_in_root(copies, result.root, depsgraph)
    data = asset_checks.AssetData(result, root_obj.name, scope, nodes, infos, group, unit, bounds)
    return data, mesh_datas


def run_checks(context, start_obj=None):
    cfg = config_ui.get_config()
    with ModeGuard(context):
        data, mesh_datas = gather(context, start_obj)
    results = asset_checks.run(data, cfg)
    for info in data.meshes:
        results += topology.run(info.key, info.name, mesh_datas[info.key], cfg)
    results = registry.sort_results(results)
    runtime.check_state = {
        "root": data.root_result.root,
        "root_name": data.root_name,
        "results": results,
        "stale": False,
    }
    return results


def current_results():
    state = runtime.check_state
    return state["results"] if state else []


class LPK_OT_check_asset(bpy.types.Operator):
    bl_idname = "lpk.check_asset"
    bl_label = "Kiểm tra asset"
    bl_description = "Kiểm tra asset chứa object đang chọn theo chuẩn của team"

    def execute(self, context):
        results = run_checks(context)
        counts = registry.summary_counts(results)
        level = "ERROR" if counts["ERROR"] else ("WARNING" if counts["WARNING"] else "INFO")
        self.report({level}, f"{counts['ERROR']} lỗi, {counts['WARNING']} cảnh báo, {counts['INFO']} thông tin")
        return {"FINISHED"}


def _select_object(context, obj):
    for o in context.selected_objects:
        o.select_set(False)
    try:
        obj.select_set(True)
    except RuntimeError:
        return False
    context.view_layer.objects.active = obj
    return True


def _select_elements(context, obj, kind, indices):
    """Enter Edit Mode on ``obj`` with exactly ``indices`` selected."""
    if context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    if not _select_object(context, obj):
        return False
    mesh = obj.data
    nv, ne, nf = len(mesh.vertices), len(mesh.edges), len(mesh.polygons)
    vsel, esel, fsel = [False] * nv, [False] * ne, [False] * nf
    wanted = set(indices or ())
    if kind == "VERT":
        for i in wanted:
            if i < nv:
                vsel[i] = True
    elif kind == "EDGE":
        ev = [0] * (ne * 2)
        mesh.edges.foreach_get("vertices", ev)
        for i in wanted:
            if i < ne:
                esel[i] = True
                vsel[ev[2 * i]] = vsel[ev[2 * i + 1]] = True
    elif kind == "FACE":
        for i in wanted:
            if i < nf:
                fsel[i] = True
                poly = mesh.polygons[i]
                for v in poly.vertices:
                    vsel[v] = True
        # Edges of selected faces: an edge is selected when both its verts are.
        ev = [0] * (ne * 2)
        mesh.edges.foreach_get("vertices", ev)
        face_verts = vsel
        for i in range(ne):
            esel[i] = face_verts[ev[2 * i]] and face_verts[ev[2 * i + 1]]
    mesh.vertices.foreach_set("select", vsel)
    mesh.edges.foreach_set("select", esel)
    mesh.polygons.foreach_set("select", fsel)
    mesh.update()
    bpy.ops.object.mode_set(mode="EDIT")
    context.tool_settings.mesh_select_mode = (kind == "VERT", kind == "EDGE", kind == "FACE")
    return True


class LPK_OT_select_issue(bpy.types.Operator):
    bl_idname = "lpk.select_issue"
    bl_label = "Chọn"
    bl_description = "Chọn object hoặc vùng mesh liên quan tới dòng kiểm tra"
    bl_options = {"REGISTER", "UNDO"}

    index: IntProperty(default=-1)

    def execute(self, context):
        results = current_results()
        if not 0 <= self.index < len(results):
            self.report({"WARNING"}, "Kết quả kiểm tra đã cũ, hãy kiểm tra lại")
            return {"CANCELLED"}
        r = results[self.index]
        obj = bpy.data.objects.get(r.object_key) if r.object_key else None
        if obj is None:
            self.report({"WARNING"}, "Không tìm thấy object")
            return {"CANCELLED"}
        if adapters.is_hidden(obj, context.view_layer):
            self.report({"WARNING"}, f"'{obj.name}' đang ẩn; hiện object để chọn được")
            try:
                context.view_layer.objects.active = obj
            except RuntimeError:
                pass
            return {"FINISHED"}
        if r.select in ("VERT", "EDGE", "FACE") and r.indices and obj.type == "MESH":
            ok = _select_elements(context, obj, r.select, r.indices)
        else:
            if context.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")
            ok = _select_object(context, obj)
        if not ok:
            self.report({"WARNING"}, f"Không chọn được '{obj.name}'")
        return {"FINISHED"}


@persistent
def _on_undo_redo(*_args):
    runtime.invalidate_checks()


@persistent
def _on_load(*_args):
    tempcopies.cleanup_leftovers()


classes = (LPK_OT_check_asset, LPK_OT_select_issue)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.app.handlers.undo_post.append(_on_undo_redo)
    bpy.app.handlers.redo_post.append(_on_undo_redo)
    bpy.app.handlers.load_post.append(_on_load)


def unregister():
    for handlers, fn in ((bpy.app.handlers.undo_post, _on_undo_redo), (bpy.app.handlers.redo_post, _on_undo_redo),
                         (bpy.app.handlers.load_post, _on_load)):
        if fn in handlers:
            handlers.remove(fn)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
