"""Reconcile a draft plan with the objects of an asset root (pure Python).

Shared by **Dán Plan** (mode "paste") and **Rebuild** from the Text Editor
(mode "editor"). Nothing is decided by the bpy layer: it gathers ObjState
values, calls ``reconcile`` and applies the returned actions only when there
are no errors (spec "Lưu plan và rebuild", steps 1–4).
"""

import json
from collections import namedtuple

from . import attach
from .validate import MANAGED_FIELDS, PlanError, validate, validate_text

ObjState = namedtuple("ObjState", "key part_id uid baked_snapshot")
# key: object name; uid: session identifier (string) or None;
# baked_snapshot: dict stored on the object when baked, else None

Action = namedtuple("Action", "kind key part_id data")
# kinds: CREATE, REPLACE_MESH, SET_TRANSFORM, SET_META, DELETE, STRIP, WRITE_TEXT

ReconcileResult = namedtuple("ReconcileResult", "errors plan resolved actions notes registry_parts")


def _err(code, params):
    return PlanError(code, params, "", 1, 1)


def identify_originals(objects, registry):
    """Map part_id -> original ObjState, plus duplicates to strip and errors."""
    by_id = {}
    for o in objects:
        by_id.setdefault(o.part_id, []).append(o)
    originals, duplicates, errors = {}, [], []
    for pid, cands in sorted(by_id.items()):
        if len(cands) == 1:
            originals[pid] = cands[0]
            continue
        uid = registry.get(pid)
        match = [c for c in cands if uid is not None and c.uid == uid]
        if len(match) == 1:
            originals[pid] = match[0]
            duplicates.extend(c for c in cands if c is not match[0])
        else:
            errors.append(_err("plan_duplicate_objects", {"id": pid, "objects": sorted(c.key for c in cands)}))
    return originals, duplicates, errors


def _changed_fields(declared, snap_part):
    keys = sorted(set(declared) | set(snap_part))
    return [k for k in keys if k not in ("id",) + MANAGED_FIELDS and declared.get(k) != snap_part.get(k)]


def merge_baked(draft, originals, mode):
    """Return (merged plan, errors, notes). Baked parts take their snapshot."""
    errors, notes = [], []
    merged = {k: v for k, v in draft.items() if k != "parts"}
    merged_parts = []
    for part in draft["parts"]:
        pid = part["id"]
        obj = originals.get(pid)
        snap = obj.baked_snapshot if obj is not None else None
        if snap is None:
            if part.get("baked") or "baked_params" in part:
                errors.append(_err("plan_baked_without_object", {"id": pid}))
            merged_parts.append(part)
            continue
        if mode == "editor":
            if "baked" in part and part["baked"] is not True:
                errors.append(_err("plan_baked_mismatch", {"id": pid, "field": "baked"}))
            if "baked_params" in part and part["baked_params"] != snap:
                errors.append(_err("plan_baked_mismatch", {"id": pid, "field": "baked_params"}))
        snap_part = attach.part_from_snapshot(pid, snap)
        changed = _changed_fields(part, snap_part)
        if changed:
            notes.append(("plan_ignored_baked_change", {"id": pid, "fields": changed}))
        new_part = dict(snap_part)
        if "inferred" in part:
            new_part["inferred"] = part["inferred"]
        new_part["baked"] = True
        new_part["baked_params"] = snap
        merged_parts.append(new_part)
    merged["parts"] = merged_parts
    return merged, errors, notes


def reconcile(text, mode, root_name, objects, registry):
    """``objects``: ObjState of every object under the root carrying a part id.
    ``registry``: {part_id: uid} recorded at the last successful build.
    """
    draft, errors = validate_text(text, mode=mode)
    if errors:
        return ReconcileResult(errors, None, None, [], [], {})
    if root_name and draft["asset_name"] != root_name:
        return ReconcileResult([_err("plan_asset_name", {"plan": draft["asset_name"], "root": root_name})],
                               None, None, [], [], {})

    originals, duplicates, errors = identify_originals(objects, registry)
    if errors:
        return ReconcileResult(errors, None, None, [], [], {})

    merged, errors, notes = merge_baked(draft, originals, mode)
    if errors:
        return ReconcileResult(errors, None, None, [], notes, {})

    # Re-validate after merging snapshots: parent/child types may now differ.
    _, errors = validate(merged, mode="editor")
    if errors:
        return ReconcileResult(errors, None, None, [], notes, {})
    try:
        resolved = attach.resolve(merged)
    except (ValueError, ZeroDivisionError) as exc:
        return ReconcileResult([_err("plan_build_failed", {"reason": str(exc)})], None, None, [], notes, {})

    actions = []
    plan_ids = {r.id for r in resolved}
    for r in resolved:
        obj = originals.get(r.id)
        meta = {"inferred": bool(r.part.get("inferred", False))}
        if r.baked:
            if obj is not None:
                actions.append(Action("SET_META", obj.key, r.id, meta))
            continue
        if obj is None:
            actions.append(Action("CREATE", None, r.id, {"geom": r.geom, "matrix_root": r.matrix_root, **meta}))
        else:
            actions.append(Action("REPLACE_MESH", obj.key, r.id, {"geom": r.geom}))
            actions.append(Action("SET_TRANSFORM", obj.key, r.id, {"matrix_root": r.matrix_root}))
            actions.append(Action("SET_META", obj.key, r.id, meta))
    for pid, obj in sorted(originals.items()):
        if pid in plan_ids:
            continue
        if obj.baked_snapshot is not None:
            actions.append(Action("STRIP", obj.key, pid, {}))
            notes.append(("plan_stripped", {"name": obj.key}))
        else:
            actions.append(Action("DELETE", obj.key, pid, {}))
    for dup in duplicates:
        actions.append(Action("STRIP", dup.key, dup.part_id, {}))
        notes.append(("plan_stripped", {"name": dup.key}))
    actions.append(Action("WRITE_TEXT", None, None, {"text": dump_plan(merged)}))

    registry_parts = {pid: originals[pid].key for pid in plan_ids if pid in originals}
    notes.append(("plan_built", {"count": len(resolved)}))
    return ReconcileResult([], merged, resolved, actions, notes, registry_parts)


def dump_plan(plan):
    return json.dumps(plan, ensure_ascii=False, indent=2) + "\n"


def bake_part(plan, part_id):
    """Plan with ``part_id`` marked baked (snapshot of its resolved state)."""
    resolved = {r.id: r for r in attach.resolve(plan)}
    if part_id not in resolved:
        raise KeyError(part_id)
    snap = attach.snapshot(resolved[part_id])
    out = json.loads(json.dumps(plan))
    for part in out["parts"]:
        if part["id"] == part_id:
            part["baked"] = True
            part["baked_params"] = snap
    return out, snap
