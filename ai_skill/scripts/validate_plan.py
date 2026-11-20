"""Validate a LowPoly Kit Build Plan exactly like the add-on's "Dán Plan".

Usage: python3 scripts/validate_plan.py plan.json [--root-name PR_Name]

Prints errors and warnings (by part and field, with line numbers), then a
table of every part's bounding box in the root frame (metres: X right,
Y back, Z up) and the triangle count. Exit code: 0 OK, 1 errors, 2 warnings.
Standard library only.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lpk_core import messages, vecmath as vm  # noqa: E402
from lpk_core.buildplan import reconcile  # noqa: E402


def bbox(resolved):
    pts = [vm.transform_point(resolved.matrix_root, v) for v in resolved.geom.verts]
    lo = tuple(min(p[i] for p in pts) for i in range(3))
    hi = tuple(max(p[i] for p in pts) for i in range(3))
    return lo, hi


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("plan")
    ap.add_argument("--root-name", default=None, help="asset root name (defaults to the plan's asset_name)")
    args = ap.parse_args(argv)

    with open(args.plan, encoding="utf-8") as f:
        text = f.read()
    root_name = args.root_name
    result = reconcile.reconcile(text, "paste", root_name, [], {})

    if result.errors:
        print(f"ERRORS ({len(result.errors)}):")
        for e in result.errors:
            where = f"line {e.line}, col {e.col}" + (f", {e.pointer}" if e.pointer else "")
            print(f"  - [{e.code}] {where}: {messages.text(e.code, e.params)}")
        print("\nPlan rejected: fix the errors above and run again.")
        return 1

    if result.warnings:
        print(f"WARNINGS ({len(result.warnings)}):")
        for w in result.warnings:
            where = f"line {w.line}" + (f", {w.pointer}" if w.pointer else "")
            print(f"  - [{w.code}] {where}: {messages.text(w.code, w.params)}")
        print()

    total = 0
    print(f"{'part':28s} {'tris':>5s}  {'X min..max':>15s}  {'Y min..max':>15s}  {'Z min..max':>15s}")
    for r in result.resolved:
        if r.geom is None:
            continue
        tris = sum(len(f) - 2 for f in r.geom.faces)
        total += tris
        lo, hi = bbox(r)
        flag = "  (inferred)" if r.part.get("inferred") else ""
        print(f"{r.id:28s} {tris:5d}  {lo[0]:7.3f}..{hi[0]:<7.3f} {lo[1]:7.3f}..{hi[1]:<7.3f} {lo[2]:7.3f}..{hi[2]:<7.3f}{flag}")
    print(f"\nparts: {len(result.resolved)}   triangles: {total}")
    if result.warnings:
        print("Plan builds but has warnings: fix them, or explain why they are intended.")
        return 2
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
