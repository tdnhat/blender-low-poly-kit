"""Asset-level checks on plain data gathered by the bpy adapter."""

from collections import namedtuple

from .. import budget as core_budget
from .. import colors as core_colors
from .. import material_spec
from .. import vecmath as vm
from . import registry

ColorAttr = namedtuple("ColorAttr", "name domain data_type")

MeshInfo = namedtuple(
    "MeshInfo",
    "key name data_name basis_matrix local_scale matrix_world modifiers tris "
    "color_attributes materials smooth_faces colors",
)
# basis_matrix: object's own transform (matrix_basis); local_scale: obj.scale
# materials: list of MaterialSummary or None (empty slot), in slot order
# colors: set of quantised sRGB tuples found in the colour attribute (may be capped)

AssetData = namedtuple("AssetData", "root_result root_name scope nodes meshes budget_group unit_scale bounds_root")
# bounds_root: (lo, hi) of the evaluated meshes in root space, or None


def _mesh_transform_problem(m):
    rot = vm.has_rotation(m.basis_matrix)
    scale = not vm.is_unit_scale(m.basis_matrix)
    if rot and scale:
        return "scale và rotation"
    if scale:
        return "scale"
    if rot:
        return "rotation"
    return None


def run(data, cfg):
    out = []

    def add(check_id, params, key=None, indices=None):
        r = registry.make(check_id, cfg, params, key, indices)
        if r is not None:
            out.append(r)

    example = cfg.get("root_name_example", "")
    rr = data.root_result
    if rr.root is None:
        if rr.problem == "root_missing":
            add("root_missing", {"example": example})
        elif rr.problem == "root_not_empty":
            add("root_not_empty", {"name": data.nodes[rr.candidate].name}, rr.candidate)
        else:
            add("root_bad_name", {"name": data.nodes[rr.candidate].name, "example": example}, rr.candidate)
        return registry.sort_results(out)

    root = data.nodes[rr.root]
    if vm.has_rotation(root.matrix_world) or not vm.is_unit_scale(root.matrix_world):
        add("root_transform", {"name": root.name}, root.key)

    # Budget
    status = core_budget.evaluate({m.name: m.tris for m in data.meshes}, data.budget_group, cfg)
    if status.level == "ERROR":
        heavy = ", ".join(f"{n} ({t})" for n, t in status.heaviest[:3])
        add("budget_over", {"tris": status.total, "limit": status.limit, "group": status.group, "heaviest": heavy}, root.key)
    elif status.level == "WARNING":
        add("budget_near", {"tris": status.total, "limit": status.limit, "percent": round(status.ratio * 100),
                            "remaining": status.remaining})

    # Pivot and scene scale
    if data.bounds_root is not None:
        lo, hi = data.bounds_root
        bottom_center = ((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, lo[2])
        offset = vm.length(bottom_center)
        if offset > cfg["pivot_tolerance"]:
            add("pivot_offset", {"offset_mm": round(offset * 1000, 1), "tolerance_mm": round(cfg["pivot_tolerance"] * 1000, 1),
                                 "target": bottom_center}, root.key)
    if abs(data.unit_scale - 1.0) > 1e-6:
        add("scene_scale", {"scale": data.unit_scale})

    for key in data.scope.non_mesh:
        n = data.nodes[key]
        add("non_mesh_child", {"name": n.name, "type": n.type}, key)

    attr = cfg["color_attribute"]
    all_colors = set()
    colors_known = True
    for m in data.meshes:
        if m.key in data.scope.hidden_meshes:
            add("hidden_mesh", {"name": m.name}, m.key)

        what = _mesh_transform_problem(m)
        if what:
            mods = f" (modifier: {', '.join(m.modifiers)})" if m.modifiers else ""
            add("mesh_transform", {"name": m.name, "what": what, "modifiers": mods}, m.key)
        axes = vm.negative_scale_axes(m.local_scale)
        if axes:
            sign = "âm" if vm.det3(m.matrix_world) < 0 else "dương"
            add("mesh_negative_scale", {"name": m.name, "axes": "".join(axes), "axes_list": axes, "sign": sign}, m.key)

        found = [c for c in m.color_attributes if c.name == attr]
        if not found:
            add("color_attr_missing", {"name": m.name, "attribute": attr}, m.key)
            colors_known = False
        elif (found[0].domain, found[0].data_type) != ("CORNER", "BYTE_COLOR"):
            add("color_attr_wrong_format", {"name": m.name, "attribute": attr, "domain": found[0].domain,
                                            "data_type": found[0].data_type}, m.key)

        mats = [s for s in m.materials if s is not None]
        if not mats:
            add("material_missing", {"name": m.name}, m.key)
        else:
            for s in mats:
                if not material_spec.is_valid(s, attr):
                    add("material_not_vertex_color", {"name": m.name, "material": s.name, "attribute": attr}, m.key)
                    break
        if any(s is None for s in m.materials):
            add("material_empty_slot", {"name": m.name}, m.key)
        names = sorted({s.name for s in mats})
        if len(names) > cfg["max_materials"]:
            add("material_count", {"name": m.name, "count": len(names), "limit": cfg["max_materials"], "materials": names}, m.key)

        if m.smooth_faces:
            add("smooth_shading", {"name": m.name, "count": len(m.smooth_faces)}, m.key, m.smooth_faces)
        if m.data_name != m.name:
            add("mesh_data_name", {"name": m.name, "data": m.data_name}, m.key)
        if m.colors is None:
            colors_known = False
        else:
            all_colors |= set(m.colors)

    if data.meshes and colors_known and len(all_colors) == 1:
        add("single_color", {"color": core_colors.srgb_to_hex(next(iter(all_colors)))})

    return registry.sort_results(out)
