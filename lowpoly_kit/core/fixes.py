"""Transform maths for root / pivot fixes (children keep their world transform)."""

import re

from . import vecmath as vm


def reset_root_world(root_world):
    """Root keeps its location, loses rotation and scale."""
    return vm.translation(vm.get_translation(root_world))


def move_root_world(root_world, target_in_root):
    """Root moved so its pivot lands on ``target_in_root`` (root space)."""
    return vm.matmul(root_world, vm.translation(target_in_root))


def rebased_local(child_world, new_parent_world):
    """Local matrix that keeps ``child_world`` under a parent at ``new_parent_world``."""
    return vm.matmul(vm.inverse_affine(new_parent_world), child_world)


def bottom_center(lo, hi):
    return ((lo[0] + hi[0]) / 2.0, (lo[1] + hi[1]) / 2.0, lo[2])


def suggest_root_name(mesh_name, pattern, example):
    """Root name for a mesh that wrongly acts as root."""
    candidates = [mesh_name, "PR_" + mesh_name, "PR_" + mesh_name[:1].upper() + mesh_name[1:]]
    for c in candidates:
        cleaned = re.sub(r"[^A-Za-z0-9_]", "_", c)
        if re.search(pattern, cleaned):
            return cleaned
    return example
