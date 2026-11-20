"""One undoable operator per fix; the checker re-runs afterwards."""

import bmesh
import bpy
from bpy.props import IntProperty
from mathutils import Matrix

from . import adapters, assets, checker_ops, coloring, config_ui, runtime
from .core import fixes as core_fixes

TOPOLOGY_FIXES = {"triangulate_ngons", "merge_by_distance", "delete_loose", "dissolve_degenerate", "recalc_normals"}


def _matrix(m):
    return Matrix([list(row) for row in m])


def _set_world_keep_children(context, obj, new_world):
    children = [(c, c.matrix_world.copy()) for c in obj.children]
    obj.matrix_world = new_world
    context.view_layer.update()
    for child, world in children:
        child.matrix_world = world
    context.view_layer.update()


def _editable_mesh(obj):
    mesh = obj.data
    if mesh.library is not None:
        return None, f"Mesh '{mesh.name}' là dữ liệu liên kết từ thư viện"
    if mesh.users > 1:
        return None, f"Mesh '{mesh.name}' đang được {mesh.users} object dùng chung; tách dữ liệu (Make Single User) trước"
    return mesh, None


def _bmesh_fix(obj, fix, cfg):
    mesh, err = _editable_mesh(obj)
    if err:
        return err
    bm = bmesh.new()
    try:
        bm.from_mesh(mesh)
        if fix == "triangulate_ngons":
            bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4])
        elif fix == "merge_by_distance":
            bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=cfg["merge_distance"])
        elif fix == "delete_loose":
            loose_edges = [e for e in bm.edges if not e.link_faces]
            if loose_edges:
                bmesh.ops.delete(bm, geom=loose_edges, context="EDGES")
            loose_verts = [v for v in bm.verts if not v.link_edges]
            if loose_verts:
                bmesh.ops.delete(bm, geom=loose_verts, context="VERTS")
        elif fix == "dissolve_degenerate":
            bmesh.ops.dissolve_degenerate(bm, dist=1e-6, edges=list(bm.edges))
        elif fix == "recalc_normals":
            bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        bm.to_mesh(mesh)
    finally:
        bm.free()
    mesh.update()
    return None


def _reroot(context, obj, cfg):
    subtree = [obj] + [o for o in obj.children_recursive if o.name in context.scene.objects]
    bounds = assets.world_bounds(subtree, context.evaluated_depsgraph_get())
    lo, hi = bounds if bounds else (obj.matrix_world.translation, obj.matrix_world.translation)
    name = core_fixes.suggest_root_name(obj.name, cfg["root_name_pattern"], cfg.get("root_name_example", "PR_Asset"))
    root = bpy.data.objects.new(name, None)
    root.empty_display_type = "PLAIN_AXES"
    root.empty_display_size = 0.25
    root.location = core_fixes.bottom_center(tuple(lo), tuple(hi))
    for coll in obj.users_collection:
        coll.objects.link(root)
    if obj.parent is not None:
        world = root.matrix_world.copy()
        root.parent = obj.parent
        root.matrix_parent_inverse = obj.parent.matrix_world.inverted()
        root.matrix_world = world
    context.view_layer.update()
    world = obj.matrix_world.copy()
    obj.parent = root
    obj.matrix_parent_inverse = root.matrix_world.inverted()
    obj.matrix_world = world
    root["lpk_budget_group"] = cfg["default_budget_group"]
    return root


def apply_fix(context, fix, obj, result, cfg):
    """Run one fix. Returns (ok, message, object to re-check from)."""
    if fix == "create_root":
        bpy.ops.lpk.create_root("INVOKE_DEFAULT")
        return True, "", None
    if obj is None:
        return False, "Không tìm thấy object", None
    if fix == "reroot":
        root = _reroot(context, obj, cfg)
        return True, f"Đã tạo root '{root.name}'", root
    if fix == "reset_root_transform":
        new = core_fixes.reset_root_world(adapters.matrix_tuple(obj.matrix_world))
        _set_world_keep_children(context, obj, _matrix(new))
        return True, f"Đã reset transform của '{obj.name}'", obj
    if fix == "move_root_to_pivot":
        target = result.params.get("target")
        new = core_fixes.move_root_world(adapters.matrix_tuple(obj.matrix_world), target)
        _set_world_keep_children(context, obj, _matrix(new))
        return True, f"Đã dời pivot của '{obj.name}' về đáy giữa", obj
    if obj.type != "MESH":
        return False, f"'{obj.name}' không phải mesh", obj
    if fix == "setup_vertex_color":
        coloring.setup_vertex_color(obj, cfg)
        return True, f"Đã khởi tạo vertex color cho '{obj.name}'", obj
    if fix == "rename_mesh_data":
        mesh, err = _editable_mesh(obj)
        if err:
            return False, err, obj
        mesh.name = obj.name
        return True, f"Đã đổi tên mesh data thành '{mesh.name}'", obj
    if fix == "shade_flat":
        mesh, err = _editable_mesh(obj)
        if err:
            return False, err, obj
        mesh.polygons.foreach_set("use_smooth", [False] * len(mesh.polygons))
        mesh.update()
        return True, f"Đã shade flat '{obj.name}'", obj
    if fix in TOPOLOGY_FIXES:
        err = _bmesh_fix(obj, fix, cfg)
        if err:
            return False, err, obj
        return True, f"Đã chạy {fix} trên '{obj.name}'", obj
    return False, f"Chưa hỗ trợ fix '{fix}'", obj


class LPK_OT_fix_issue(bpy.types.Operator):
    bl_idname = "lpk.fix_issue"
    bl_label = "Sửa"
    bl_description = "Chạy bản sửa cho dòng kiểm tra này (undo được bằng Ctrl+Z)"
    bl_options = {"REGISTER", "UNDO"}

    index: IntProperty(default=-1)

    def execute(self, context):
        results = checker_ops.current_results()
        if not 0 <= self.index < len(results) or runtime.check_state.get("stale"):
            self.report({"WARNING"}, "Kết quả kiểm tra đã cũ, hãy kiểm tra lại")
            return {"CANCELLED"}
        r = results[self.index]
        if not r.fix:
            return {"CANCELLED"}
        cfg = config_ui.get_config()
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        obj = bpy.data.objects.get(r.object_key) if r.object_key else None
        ok, message, recheck_from = apply_fix(context, r.fix, obj, r, cfg)
        if message:
            self.report({"INFO"} if ok else {"WARNING"}, message)
        if r.fix != "create_root":
            start = recheck_from or (bpy.data.objects.get(runtime.check_state["root"]) if runtime.check_state.get("root") else None)
            checker_ops.run_checks(context, start)
        return {"FINISHED"}


classes = (LPK_OT_fix_issue,)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
