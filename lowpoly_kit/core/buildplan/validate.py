"""Build Plan validation: strict JSON, schema v1, semantic rules.

Errors are PlanError(code, params, pointer, line, col); ``code`` has a text
in core.messages.
"""

import json
import os
from collections import namedtuple

from .. import schema_lite, strict_json
from . import geometry2d

SCHEMA_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                           "schemas", "buildplan.schema.json")
MANAGED_FIELDS = ("baked", "baked_params")

PlanError = namedtuple("PlanError", "code params pointer line col")

_schema_cache = None


def load_schema():
    global _schema_cache
    if _schema_cache is None:
        with open(SCHEMA_PATH, encoding="utf-8") as f:
            _schema_cache = json.load(f)
    return _schema_cache


def schema_text():
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        return f.read()


class _Collector:
    def __init__(self, positions):
        self.positions = positions
        self.errors = []

    def add(self, code, params, pointer=""):
        line, col = strict_json.position_for(self.positions, pointer)
        self.errors.append(PlanError(code, params, pointer, line, col))


def _part_label(plan, pointer):
    """(' part id' prefix, field path) for a pointer like /parts/1/attachment/t."""
    tokens = pointer.split("/")[1:]
    if len(tokens) >= 2 and tokens[0] == "parts" and tokens[1].isdigit():
        idx = int(tokens[1])
        parts = plan.get("parts") if isinstance(plan, dict) else None
        pid = parts[idx].get("id") if isinstance(parts, list) and idx < len(parts) and isinstance(parts[idx], dict) else None
        label = f"Part '{pid}'" if pid else f"parts[{idx}]"
        field = "/".join(tokens[2:])
        return label, (f" · {field}" if field else "")
    return "Plan", (f" · {'/'.join(tokens)}" if tokens else "")


def parents_of(parts_by_id):
    return {pid: p["attachment"]["parent_id"] for pid, p in parts_by_id.items() if "attachment" in p}


def find_cycle(parent):
    for start in parent:
        seen = []
        node = start
        while node in parent:
            if node in seen:
                return seen[seen.index(node):] + [node]
            seen.append(node)
            node = parent[node]
    return None


def topo_order(parts):
    """Part ids ordered so parents come first (assumes no cycle)."""
    by_id = {p["id"]: p for p in parts}
    parent = parents_of(by_id)
    order, done = [], set()

    def visit(pid):
        if pid in done:
            return
        if pid in parent and parent[pid] in by_id:
            visit(parent[pid])
        done.add(pid)
        order.append(pid)

    for p in parts:
        visit(p["id"])
    return order


def _semantic(plan, col, mode):
    parts = plan["parts"]
    by_id, index = {}, {}
    for i, p in enumerate(parts):
        if p["id"] in by_id:
            col.add("plan_duplicate_id", {"id": p["id"]}, f"/parts/{i}/id")
        else:
            by_id[p["id"]] = p
            index[p["id"]] = i

    if mode == "paste":
        for i, p in enumerate(parts):
            for field in MANAGED_FIELDS:
                if field in p:
                    col.add("plan_managed_field", {"id": p["id"], "field": field}, f"/parts/{i}/{field}")

    for i, p in enumerate(parts):
        if p.get("mirror") and p["id"] + "_mirror" in by_id:
            col.add("plan_mirror_id_taken", {"id": p["id"], "mirror_id": p["id"] + "_mirror"}, f"/parts/{i}/mirror")
        att = p.get("attachment")
        if att and att.get("parent_id", "").endswith("_mirror") and att["parent_id"] not in by_id:
            col.add("plan_parent_is_mirror", {"id": p["id"], "parent": att["parent_id"]}, f"/parts/{i}/attachment/parent_id")

    roots = [p["id"] for p in parts if "attachment" not in p]
    if len(roots) != 1:
        col.add("plan_root_count", {"count": len(roots), "ids": roots or ["-"]}, "/parts")

    for i, p in enumerate(parts):
        ptr = f"/parts/{i}"
        if p["op"] == "lathe_profile":
            prof = p["profile_z_radius"]
            if any(prof[k + 1][0] <= prof[k][0] for k in range(len(prof) - 1)):
                col.add("plan_heights_not_increasing", {"id": p["id"]}, ptr + "/profile_z_radius")
            if any(r == 0 for _z, r in prof[1:-1]):
                col.add("plan_profile_degenerate", {"id": p["id"]}, ptr + "/profile_z_radius")
        elif p["op"] == "extrude_profile":
            has_depth, has_thick = "depth" in p, "thickness_profile" in p
            if has_depth == has_thick:
                col.add("plan_depth_or_thickness", {"id": p["id"]}, ptr)
            if has_thick:
                tp = p["thickness_profile"]
                if any(tp[k + 1][0] <= tp[k][0] for k in range(len(tp) - 1)):
                    col.add("plan_thickness_not_increasing", {"id": p["id"]}, ptr + "/thickness_profile")
            prof = [tuple(pt) for pt in p["profile"]]
            if geometry2d.has_duplicate_points(prof) or abs(geometry2d.signed_area(prof)) < 1e-12:
                col.add("plan_profile_degenerate", {"id": p["id"]}, ptr + "/profile")
            elif geometry2d.self_intersects(prof):
                col.add("plan_profile_self_intersect", {"id": p["id"]}, ptr + "/profile")
            elif p.get("section", "box") != "box" and geometry2d.monotone_chains(prof) is None:
                col.add("plan_section_not_monotone", {"id": p["id"], "section": p["section"]}, ptr + "/profile")

    for i, p in enumerate(parts):
        att = p.get("attachment")
        if not att:
            continue
        ptr = f"/parts/{i}/attachment"
        parent = by_id.get(att["parent_id"])
        if parent is None:
            col.add("plan_missing_parent", {"id": p["id"], "parent": att["parent_id"]}, ptr + "/parent_id")
            continue
        rule = att["rule"]
        if rule == "lathe_radius_at_height":
            if parent["op"] != "lathe_profile":
                col.add("plan_rule_parent_type", {"id": p["id"], "rule": rule, "expected": "lathe_profile",
                                                  "parent": parent["id"], "actual": parent["op"]}, ptr + "/parent_id")
                continue
            if not (p["op"] == "add_primitive" and p.get("shape") == "cylinder"):
                col.add("plan_rule_child_type", {"id": p["id"], "rule": rule, "expected": "add_primitive cylinder"}, f"/parts/{i}/op")
                continue
            if p["segments"] != parent["segments"]:
                col.add("plan_segments_mismatch", {"id": p["id"], "parent": parent["id"], "expected": parent["segments"]},
                        f"/parts/{i}/segments")
            if "radius" in p:
                col.add("plan_forbidden_field", {"id": p["id"], "field": "radius", "rule": rule}, f"/parts/{i}/radius")
            prof = parent["profile_z_radius"]
            low, high = att["height"] - p["height"] / 2.0, att["height"] + p["height"] / 2.0
            if low < prof[0][0] - 1e-9 or high > prof[-1][0] + 1e-9:
                col.add("plan_span_outside_parent", {"id": p["id"], "low": round(low, 4), "high": round(high, 4),
                                                     "parent": parent["id"]}, ptr + "/height")
        elif rule == "profile_segment":
            if parent["op"] != "extrude_profile":
                col.add("plan_rule_parent_type", {"id": p["id"], "rule": rule, "expected": "extrude_profile",
                                                  "parent": parent["id"], "actual": parent["op"]}, ptr + "/parent_id")
                continue
            if parent.get("section", "box") != "box":
                col.add("plan_segment_on_section", {"id": p["id"], "parent": parent["id"]}, ptr + "/parent_id")
                continue
            n = len(parent["profile"])
            if att["segment"] >= n:
                col.add("plan_segment_range", {"id": p["id"], "segment": att["segment"], "parent": parent["id"], "max": n - 1},
                        ptr + "/segment")
        elif rule == "box_face":
            if not (parent["op"] == "add_primitive" and parent.get("shape") == "box"):
                col.add("plan_rule_parent_type", {"id": p["id"], "rule": rule, "expected": "add_primitive box",
                                                  "parent": parent["id"], "actual": parent["op"]}, ptr + "/parent_id")

    cycle = find_cycle({pid: q["attachment"]["parent_id"] for pid, q in by_id.items()
                        if "attachment" in q and q["attachment"]["parent_id"] in by_id})
    if cycle:
        col.add("plan_cycle", {"cycle": " → ".join(cycle)}, f"/parts/{index[cycle[0]]}/attachment/parent_id")


def validate_text(text, mode="editor"):
    """Validate plan text. mode: "paste" (managed fields forbidden) or "editor".

    Returns (plan or None, errors).
    """
    try:
        plan, positions = strict_json.loads_with_positions(text)
    except strict_json.JsonError as exc:
        return None, [PlanError("plan_json_error", {"line": exc.line, "col": exc.col, "reason": exc.reason}, "", exc.line, exc.col)]
    return validate(plan, positions, mode)


def validate(plan, positions=None, mode="editor"):
    col = _Collector(positions or {})
    for e in schema_lite.validate(plan, load_schema()):
        label, field = _part_label(plan, e.pointer)
        detail = e.code.replace("schema_", "")
        if e.params:
            detail += " " + ", ".join(f"{k}={v}" for k, v in e.params.items())
        col.add("plan_schema", {"part": label, "field": field, "detail": detail}, e.pointer)
    if col.errors:
        return None, col.errors
    _semantic(plan, col, mode)
    return (plan if not col.errors else None), col.errors
