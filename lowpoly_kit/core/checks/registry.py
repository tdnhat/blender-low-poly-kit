"""Check definitions and results."""

from collections import namedtuple

CheckDef = namedtuple("CheckDef", "id severity fix safe select")
# select: None | "OBJECT" | "VERT" | "EDGE" | "FACE"

CheckResult = namedtuple("CheckResult", "check_id severity code params object_key select indices fix")

SEVERITY_ORDER = {"ERROR": 0, "WARNING": 1, "INFO": 2}

_DEFS = [
    # asset level
    CheckDef("root_missing", "ERROR", "create_root", False, None),
    CheckDef("root_not_empty", "ERROR", "reroot", False, "OBJECT"),
    CheckDef("root_bad_name", "ERROR", None, False, "OBJECT"),
    CheckDef("root_transform", "ERROR", "reset_root_transform", False, "OBJECT"),
    CheckDef("budget_over", "ERROR", None, False, "OBJECT"),
    CheckDef("budget_near", "WARNING", None, False, None),
    CheckDef("color_attr_missing", "ERROR", "setup_vertex_color", False, "OBJECT"),
    CheckDef("color_attr_wrong_format", "ERROR", "setup_vertex_color", False, "OBJECT"),
    CheckDef("material_missing", "ERROR", "setup_vertex_color", False, "OBJECT"),
    CheckDef("material_not_vertex_color", "ERROR", "setup_vertex_color", False, "OBJECT"),
    CheckDef("pivot_offset", "WARNING", "move_root_to_pivot", False, "OBJECT"),
    CheckDef("scene_scale", "WARNING", None, False, None),
    CheckDef("mesh_transform", "WARNING", None, False, "OBJECT"),
    CheckDef("mesh_negative_scale", "WARNING", None, False, "OBJECT"),
    CheckDef("non_mesh_child", "WARNING", None, False, "OBJECT"),
    CheckDef("hidden_mesh", "INFO", None, False, "OBJECT"),
    CheckDef("material_count", "WARNING", None, False, "OBJECT"),
    CheckDef("material_empty_slot", "WARNING", None, False, "OBJECT"),
    CheckDef("smooth_shading", "INFO", "shade_flat", False, "FACE"),
    CheckDef("mesh_data_name", "INFO", "rename_mesh_data", True, "OBJECT"),
    CheckDef("single_color", "INFO", None, False, None),
    # topology
    CheckDef("ngon", "WARNING", "triangulate_ngons", False, "FACE"),
    CheckDef("near_duplicate", "WARNING", "merge_by_distance", False, "VERT"),
    CheckDef("loose_vert", "WARNING", "delete_loose", False, "VERT"),
    CheckDef("loose_edge", "WARNING", "delete_loose", False, "EDGE"),
    CheckDef("degenerate_face", "WARNING", "dissolve_degenerate", False, "FACE"),
    CheckDef("nonmanifold_edge", "WARNING", None, False, "EDGE"),
    CheckDef("open_boundary", "WARNING", None, False, "EDGE"),
    CheckDef("inconsistent_winding", "WARNING", "recalc_normals", False, "EDGE"),
    CheckDef("inward_normals", "WARNING", "recalc_normals", False, "FACE"),
]

CHECKS = {d.id: d for d in _DEFS}


def severity_for(check_id, cfg):
    """Configured severity, or None when the check is turned OFF."""
    override = (cfg or {}).get("severity_overrides", {}).get(check_id)
    if override == "OFF":
        return None
    return override or CHECKS[check_id].severity


def make(check_id, cfg, params, object_key=None, indices=None, code=None):
    """Build a CheckResult, or None when the check is turned off."""
    sev = severity_for(check_id, cfg)
    if sev is None:
        return None
    d = CHECKS[check_id]
    return CheckResult(check_id, sev, code or check_id, params, object_key, d.select,
                       tuple(indices) if indices is not None else None, d.fix)


def sort_results(results):
    return sorted(results, key=lambda r: (SEVERITY_ORDER[r.severity], r.object_key or "", r.check_id))


def error_count(results):
    return sum(1 for r in results if r.severity == "ERROR")


def group_by_object(results):
    """[(object_key or None, [results])], asset-wide results first, order kept."""
    groups = {}
    order = []
    for r in sort_results(results):
        if r.object_key not in groups:
            groups[r.object_key] = []
            order.append(r.object_key)
        groups[r.object_key].append(r)
    order.sort(key=lambda k: (k is not None, min(SEVERITY_ORDER[r.severity] for r in groups[k]), k or ""))
    return [(k, groups[k]) for k in order]


def summary_counts(results):
    counts = {"ERROR": 0, "WARNING": 0, "INFO": 0}
    for r in results:
        counts[r.severity] += 1
    return counts
