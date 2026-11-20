"""Read Blender data into plain core structures (no scene changes here)."""

import bpy

from .core import scope as core_scope


def matrix_tuple(m):
    """mathutils.Matrix -> tuple of tuples (copied, so it never aliases bpy data)."""
    return tuple(tuple(float(m[i][j]) for j in range(4)) for i in range(4))


def is_hidden(obj, view_layer=None):
    """True when the object is not visible in the viewport of the view layer.

    ``visible_get`` raises RuntimeError for objects outside the view layer
    (for example in an excluded collection); those count as hidden.
    """
    try:
        return not obj.visible_get(view_layer=view_layer) if view_layer else not obj.visible_get()
    except RuntimeError:
        return True


def scene_nodes(scene, view_layer=None):
    nodes = []
    for obj in scene.objects:
        parent = obj.parent.name if obj.parent is not None and obj.parent.name in scene.objects else None
        nodes.append(core_scope.Node(
            key=obj.name,
            name=obj.name,
            type=obj.type,
            parent=parent,
            matrix_world=matrix_tuple(obj.matrix_world),
            hidden=is_hidden(obj, view_layer),
        ))
    return nodes


def scene_index(context):
    return core_scope.index(scene_nodes(context.scene, context.view_layer))


def find_root_for(context, obj=None, name_pattern=None):
    from . import config_ui

    obj = obj if obj is not None else context.active_object
    nodes = scene_index(context)
    pattern = name_pattern or config_ui.get_config()["root_name_pattern"]
    result = core_scope.find_root(nodes, obj.name if obj else None, pattern)
    return result, nodes


def get_root_object(context, obj=None):
    result, _nodes = find_root_for(context, obj)
    return bpy.data.objects.get(result.root) if result.root else None


def evaluated_tris(obj, depsgraph):
    """Triangle count of the evaluated mesh (modifiers as shown in the viewport)."""
    if obj.type != "MESH":
        return 0
    eval_obj = obj.evaluated_get(depsgraph)
    mesh = eval_obj.to_mesh()
    try:
        mesh.calc_loop_triangles()
        return len(mesh.loop_triangles)
    finally:
        eval_obj.to_mesh_clear()


def scope_tris(context, scope, nodes_by_key):
    depsgraph = context.evaluated_depsgraph_get()
    result = {}
    for key in scope.meshes:
        obj = bpy.data.objects.get(key)
        if obj is not None:
            result[nodes_by_key[key].name] = evaluated_tris(obj, depsgraph)
    return result


# ---------------------------------------------------------------- mesh data

def mesh_data(obj, det_sign):
    """Plain topology of the object's own mesh (not evaluated), local space."""
    from .core.checks.topology import MeshData

    if obj.mode == "EDIT":
        obj.update_from_editmode()
    mesh = obj.data
    nv, ne, np_, nl = len(mesh.vertices), len(mesh.edges), len(mesh.polygons), len(mesh.loops)
    co = [0.0] * (nv * 3)
    mesh.vertices.foreach_get("co", co)
    ev = [0] * (ne * 2)
    mesh.edges.foreach_get("vertices", ev)
    starts, totals = [0] * np_, [0] * np_
    mesh.polygons.foreach_get("loop_start", starts)
    mesh.polygons.foreach_get("loop_total", totals)
    lv = [0] * nl
    mesh.loops.foreach_get("vertex_index", lv)
    verts = [tuple(co[i:i + 3]) for i in range(0, len(co), 3)]
    edges = [(ev[i], ev[i + 1]) for i in range(0, len(ev), 2)]
    faces = [tuple(lv[s:s + t]) for s, t in zip(starts, totals)]
    return MeshData(verts, edges, faces, det_sign)


def smooth_faces(mesh):
    flags = [False] * len(mesh.polygons)
    mesh.polygons.foreach_get("use_smooth", flags)
    return [i for i, f in enumerate(flags) if f]


def color_attributes(mesh):
    from .core.checks.asset import ColorAttr

    return [ColorAttr(a.name, a.domain, a.data_type) for a in mesh.color_attributes]


def unique_colors(mesh, attribute, cap=2):
    from .core import coloring as core_coloring

    attr = mesh.color_attributes.get(attribute)
    if attr is None:
        return None
    flat = [0.0] * (len(attr.data) * 4)
    attr.data.foreach_get("color_srgb", flat)
    return core_coloring.unique_colors(core_coloring.unflatten(flat), cap)


def mesh_info(obj, tris, cfg):
    from . import materials
    from .core.checks.asset import MeshInfo

    mesh = obj.data
    return MeshInfo(
        key=obj.name,
        name=obj.name,
        data_name=mesh.name,
        basis_matrix=matrix_tuple(obj.matrix_basis),
        local_scale=tuple(obj.scale),
        matrix_world=matrix_tuple(obj.matrix_world),
        modifiers=[m.name for m in obj.modifiers],
        tris=tris,
        color_attributes=color_attributes(mesh),
        materials=[materials.summarize(slot.material) for slot in obj.material_slots],
        smooth_faces=smooth_faces(mesh),
        colors=unique_colors(mesh, cfg["color_attribute"]),
    )
