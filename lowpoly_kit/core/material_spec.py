"""What counts as a valid vertex-colour material, and how to build one.

The bpy layer summarises a material's node tree into a MaterialSummary;
the same rule is used by the checker and by the coloring module that
creates ``M_VertexColor``, so a created material always passes.
"""

from collections import namedtuple

MaterialSummary = namedtuple("MaterialSummary", "name uses_nodes principled_to_output base_color_source base_color_layer")
# base_color_source: None | "VERTEX_COLOR" | "OTHER" | "UNLINKED"

# Node graph the coloring module builds (bl_idname, name, location).
BUILD_NODES = (
    ("ShaderNodeOutputMaterial", "Material Output", (300, 0)),
    ("ShaderNodeBsdfPrincipled", "Principled BSDF", (0, 0)),
    ("ShaderNodeVertexColor", "Color Attribute", (-300, 0)),
)
# (from node name, from socket, to node name, to socket)
BUILD_LINKS = (
    ("Color Attribute", "Color", "Principled BSDF", "Base Color"),
    ("Principled BSDF", "BSDF", "Material Output", "Surface"),
)
BUILD_DEFAULTS = {"Roughness": 0.9}


def is_valid(summary, attribute):
    return (
        summary is not None
        and summary.uses_nodes
        and summary.principled_to_output
        and summary.base_color_source == "VERTEX_COLOR"
        and summary.base_color_layer == attribute
    )


def built_summary(name, attribute):
    """Summary of the material produced from BUILD_NODES/BUILD_LINKS."""
    return MaterialSummary(name, True, True, "VERTEX_COLOR", attribute)
