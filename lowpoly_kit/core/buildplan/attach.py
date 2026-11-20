"""Attachment rules and plan resolution (geometry + transforms in root space)."""

from collections import namedtuple

from .. import vecmath as vm
from . import geometry
from .validate import topo_order

ResolvedPart = namedtuple("ResolvedPart", "id op part geom matrix_root computed baked")

NON_PARAM_KEYS = ("id", "attachment", "baked", "baked_params", "inferred")
MIRROR_SUFFIX = "_mirror"
_FLIP_X = vm.scaling((-1.0, 1.0, 1.0))


def mirror_id(part_id):
    return part_id + MIRROR_SUFFIX


def mirrored(resolved):
    """Copy of a resolved part reflected across the root's YZ plane.

    The object matrix stays right-handed: M' = Fx @ M @ Fx, with the local
    geometry reflected and its faces reversed, so world points are Fx @ M @ v
    and no negative scale reaches the export.
    """
    matrix = vm.matmul(_FLIP_X, vm.matmul(resolved.matrix_root, _FLIP_X))
    geom = None if resolved.geom is None else geometry.mirror_x(resolved.geom)
    return ResolvedPart(mirror_id(resolved.id), resolved.op, resolved.part, geom, matrix, resolved.computed, resolved.baked)


def part_params(part):
    return {k: v for k, v in part.items() if k not in NON_PARAM_KEYS}


def snapshot(resolved):
    """Bake snapshot ``{op, params, computed, attachment, matrix_root}``."""
    params = part_params(resolved.part)
    params.pop("op", None)
    snap = {
        "op": resolved.op,
        "params": params,
        "computed": dict(resolved.computed),
        "matrix_root": [list(row) for row in resolved.matrix_root],
    }
    if "attachment" in resolved.part:
        snap["attachment"] = resolved.part["attachment"]
    return snap


def part_from_snapshot(part_id, snap):
    """Plan part (as declared, without computed values) rebuilt from a snapshot."""
    part = {"id": part_id, "op": snap["op"]}
    part.update(snap.get("params", {}))
    if snap.get("attachment"):
        part["attachment"] = snap["attachment"]
    return part


def _effective(part):
    """Parameters used for geometry: the bake snapshot when baked."""
    if part.get("baked") and isinstance(part.get("baked_params"), dict):
        snap = part["baked_params"]
        eff = part_from_snapshot(part["id"], snap)
        eff.update(snap.get("computed", {}))
        return eff, vm.as_matrix(snap["matrix_root"]) if "matrix_root" in snap else None
    return part, None


def attach_matrix(child, parent_eff, parent_computed):
    """(child local matrix in the parent frame, computed child params)."""
    att = child["attachment"]
    rule = att["rule"]
    if rule == "lathe_radius_at_height":
        profile = [tuple(p) for p in parent_eff["profile_z_radius"]]
        low = att["height"] - child["height"] / 2.0
        high = att["height"] + child["height"] / 2.0
        radius = geometry.lathe_max_radius(profile, low, high) + att["radial_offset"]
        return vm.translation((0.0, 0.0, low)), {"radius": radius}
    if rule == "profile_segment":
        frame = geometry.segment_frame(parent_eff["plane"], parent_eff["profile"], att["segment"], att["t"],
                                       att["normal_offset"])
        return frame, {}
    if rule == "box_face":
        frame = geometry.box_face_frame(parent_eff["size"], att["face"], att["u"], att["v"], att["normal_offset"])
        return frame, {}
    if rule == "body_surface":
        parent_geom = geometry.build(parent_eff, parent_computed)
        frame = geometry.body_surface_frame(parent_geom, parent_eff["plane"], att["a"], att["b"], att["side"],
                                            att["normal_offset"], att.get("s", 0.0))
        if att.get("rotation"):
            frame = vm.matmul(frame, vm.euler_xyz(att["rotation"]))
        return frame, {}
    if rule == "offset":
        local = vm.matmul(vm.translation(att["position"]), vm.euler_xyz(att["rotation"]))
        return local, {}
    raise ValueError(f"unsupported rule {rule}")


def resolve(plan):
    """Resolve every part in dependency order. The plan must be valid."""
    parts = {p["id"]: p for p in plan["parts"]}
    out = {}
    for pid in topo_order(plan["parts"]):
        part = parts[pid]
        eff, frozen = _effective(part)
        baked = bool(part.get("baked"))
        computed = {}
        if frozen is not None:
            matrix = frozen
        elif "attachment" not in part:
            matrix = vm.identity()
        else:
            parent = out[part["attachment"]["parent_id"]]
            parent_eff, _ = _effective(parent.part)
            local, computed = attach_matrix(eff, parent_eff, parent.computed)
            matrix = vm.matmul(parent.matrix_root, local)
        geom = None if baked else geometry.build(eff, computed)
        out[pid] = ResolvedPart(pid, eff["op"], part, geom, matrix, computed, baked)
    result = []
    for pid in topo_order(plan["parts"]):
        result.append(out[pid])
        if parts[pid].get("mirror") == "X":
            result.append(mirrored(out[pid]))
    return result
