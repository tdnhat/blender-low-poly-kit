"""PoC metrics: changed-field count and normalised outline (Hausdorff) error."""

import math

from .buildplan.validate import MANAGED_FIELDS

IGNORED_KEYS = set(MANAGED_FIELDS) | {"inferred", "id"}


# ---------------------------------------------------------------- field counting

def numeric_fields(plan):
    """{(part_id, json path): number} for every numeric leaf of every part."""
    out = {}

    def walk(pid, value, path):
        if isinstance(value, bool) or isinstance(value, str) or value is None:
            return
        if isinstance(value, (int, float)):
            out[(pid, path)] = value
        elif isinstance(value, list):
            for i, v in enumerate(value):
                walk(pid, v, f"{path}/{i}")
        elif isinstance(value, dict):
            for k, v in value.items():
                if k not in IGNORED_KEYS:
                    walk(pid, v, f"{path}/{k}")

    for part in plan.get("parts", []):
        walk(part.get("id"), {k: v for k, v in part.items() if k not in IGNORED_KEYS}, "")
    return out


def changed_fields(plans):
    """Union of numeric fields that differ between consecutive successful plans.

    ``plans``: successful builds in order; the first is the baseline.
    Adding or removing a part counts all its numeric fields. Inserting a
    profile point shifts later indices, which then count as changed.
    """
    changed = set()
    for before, after in zip(plans, plans[1:]):
        a, b = numeric_fields(before), numeric_fields(after)
        for key in set(a) | set(b):
            if a.get(key) != b.get(key):
                changed.add(key)
    return changed


# ---------------------------------------------------------------- outline error

def boundary(mask):
    """Inside pixels touching an outside pixel or the image edge (4-neighbour)."""
    h = len(mask)
    w = len(mask[0]) if h else 0
    pts = []
    for y in range(h):
        row = mask[y]
        for x in range(w):
            if not row[x]:
                continue
            if (x == 0 or y == 0 or x == w - 1 or y == h - 1 or not row[x - 1] or not row[x + 1]
                    or not mask[y - 1][x] or not mask[y + 1][x]):
                pts.append((x, y))
    return pts


def bbox(mask):
    xs, ys = [], []
    for y, row in enumerate(mask):
        for x, v in enumerate(row):
            if v:
                xs.append(x)
                ys.append(y)
    if not xs:
        return None
    return min(xs), min(ys), max(xs), max(ys)


class _Grid:
    def __init__(self, points, cell=8):
        self.cell = cell
        self.cells = {}
        for p in points:
            self.cells.setdefault((p[0] // cell, p[1] // cell), []).append(p)
        self.empty = not points

    def nearest(self, p):
        if self.empty:
            return math.inf
        cx, cy = p[0] // self.cell, p[1] // self.cell
        best = math.inf
        r = 0
        while True:
            for gx in range(cx - r, cx + r + 1):
                for gy in (cy - r, cy + r) if r else (cy,):
                    for q in self.cells.get((gx, gy), ()):
                        best = min(best, (q[0] - p[0]) ** 2 + (q[1] - p[1]) ** 2)
            if r:
                for gy in range(cy - r + 1, cy + r):
                    for gx in (cx - r, cx + r):
                        for q in self.cells.get((gx, gy), ()):
                            best = min(best, (q[0] - p[0]) ** 2 + (q[1] - p[1]) ** 2)
            if best < math.inf and (r * self.cell) ** 2 >= best:
                return math.sqrt(best)
            r += 1
            if r > 100000:
                return math.sqrt(best)


def hausdorff(points_a, points_b):
    ga, gb = _Grid(points_a), _Grid(points_b)
    d_ab = max((gb.nearest(p) for p in points_a), default=0.0)
    d_ba = max((ga.nearest(p) for p in points_b), default=0.0)
    return max(d_ab, d_ba)


def outline_error(reference_mask, model_mask):
    """Hausdorff distance between outlines / longer side of the reference bbox."""
    box = bbox(reference_mask)
    if box is None:
        raise ValueError("reference mask is empty")
    longest = max(box[2] - box[0] + 1, box[3] - box[1] + 1)
    model_pts = boundary(model_mask)
    if not model_pts:
        return math.inf
    return hausdorff(boundary(reference_mask), model_pts) / longest
