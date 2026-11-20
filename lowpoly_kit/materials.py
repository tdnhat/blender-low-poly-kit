"""Vertex-colour material: summarise existing node trees, build new ones."""

import bpy

from .core import colors as core_colors
from .core import material_spec


def _output_surface_node(mat):
    nt = mat.node_tree
    outputs = [n for n in nt.nodes if n.bl_idname == "ShaderNodeOutputMaterial"]
    active = [n for n in outputs if getattr(n, "is_active_output", False)] or outputs
    if not active:
        return None
    surface = active[0].inputs.get("Surface")
    if surface is None or not surface.is_linked:
        return None
    return surface.links[0].from_node


def summarize(mat):
    """MaterialSummary for the checker, or None for an empty slot."""
    if mat is None:
        return None
    if not mat.use_nodes or mat.node_tree is None:
        return material_spec.MaterialSummary(mat.name, False, False, "UNLINKED", None)
    shader = _output_surface_node(mat)
    if shader is None or shader.bl_idname != "ShaderNodeBsdfPrincipled":
        return material_spec.MaterialSummary(mat.name, True, False, "UNLINKED", None)
    base = shader.inputs.get("Base Color")
    if base is None or not base.is_linked:
        return material_spec.MaterialSummary(mat.name, True, True, "UNLINKED", None)
    src = base.links[0].from_node
    if src.bl_idname == "ShaderNodeVertexColor":
        return material_spec.MaterialSummary(mat.name, True, True, "VERTEX_COLOR", src.layer_name)
    return material_spec.MaterialSummary(mat.name, True, True, "OTHER", None)


def base_color_srgb(mat):
    """Best-effort Base Color of a material as sRGB, or None."""
    if mat is None:
        return None
    if mat.use_nodes and mat.node_tree is not None:
        shader = _output_surface_node(mat)
        if shader is not None and shader.bl_idname == "ShaderNodeBsdfPrincipled":
            base = shader.inputs.get("Base Color")
            if base is not None and not base.is_linked:
                return core_colors.linear_to_srgb(tuple(base.default_value)[:3])
    return core_colors.linear_to_srgb(tuple(mat.diffuse_color)[:3])


def build(name, attribute):
    """Create a new vertex-colour material following material_spec."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    nodes = {}
    for idname, node_name, location in material_spec.BUILD_NODES:
        node = nt.nodes.new(idname)
        node.name = node_name
        node.label = node_name
        node.location = location
        nodes[node_name] = node
    nodes["Color Attribute"].layer_name = attribute
    for from_node, from_socket, to_node, to_socket in material_spec.BUILD_LINKS:
        nt.links.new(nodes[from_node].outputs[from_socket], nodes[to_node].inputs[to_socket])
    for socket, value in material_spec.BUILD_DEFAULTS.items():
        inp = nodes["Principled BSDF"].inputs.get(socket)
        if inp is not None:
            inp.default_value = value
    return mat


def ensure(name, attribute):
    """Reuse ``name`` when it is a valid vertex-colour material, else build one."""
    existing = bpy.data.materials.get(name)
    if existing is not None and existing.library is None and material_spec.is_valid(summarize(existing), attribute):
        return existing
    return build(name, attribute)
