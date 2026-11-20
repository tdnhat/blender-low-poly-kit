"""Print the nodes of a .glb: hierarchy, world transform, bounds, vertex colours.

Usage: python3 tools/inspect_glb.py file.glb
Coordinates are glTF (Y-up, metres).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lowpoly_kit.core import glb, vecmath as vm  # noqa: E402


def fmt(v):
    return "(" + ", ".join(f"{x:.4f}" for x in v) + ")"


def main(path):
    gltf, binary = glb.read_file(path)
    for info in glb.summary(gltf, binary):
        t, _rot, s = vm.decompose(info["world"])
        print(f"- {info['name']}  parent={info['parent']}")
        print(f"    world translation {fmt(t)} scale {fmt(s)} det {'+' if info['det'] >= 0 else '-'}")
        if info["attributes"]:
            print(f"    attributes {', '.join(info['attributes'])}")
        if info["bounds"]:
            lo, hi = info["bounds"]
            print(f"    bounds {fmt(lo)} .. {fmt(hi)}  size {fmt(vm.sub(hi, lo))}")
        if info["colors"]:
            distinct = sorted({tuple(round(c, 3) for c in col[:3]) for col in info["colors"]})
            print(f"    COLOR_0 distinct values: {len(distinct)} e.g. {distinct[:4]}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    main(sys.argv[1])
