"""Triangle budget evaluation."""

from collections import namedtuple

from . import config as core_config

BudgetStatus = namedtuple("BudgetStatus", "group label limit total ratio level heaviest remaining")


def evaluate(per_mesh_tris, group_name, cfg):
    """``per_mesh_tris``: {mesh name: tris}. level: OK | WARNING | ERROR.

    Warning from ``warning_ratio`` of the limit, Error only when exceeding it.
    """
    group, info = core_config.budget_group(cfg, group_name)
    limit = info["max_tris"]
    total = sum(per_mesh_tris.values())
    ratio = total / limit if limit else float("inf")
    if total > limit:
        level = "ERROR"
    elif ratio >= cfg["warning_ratio"]:
        level = "WARNING"
    else:
        level = "OK"
    heaviest = sorted(per_mesh_tris.items(), key=lambda kv: (-kv[1], kv[0]))
    return BudgetStatus(group, info.get("label", group), limit, total, ratio, level, heaviest, limit - total)
