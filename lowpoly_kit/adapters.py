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
