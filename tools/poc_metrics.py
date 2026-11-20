"""PoC Build Plan metrics.

Outline error between a reference mask and a rendered model mask:
    python3 tools/poc_metrics.py outline reference.png model.png

Changed numeric fields across successful builds in a build log (JSONL,
exported from the Text datablock "<root>.buildplan.log.jsonl"):
    python3 tools/poc_metrics.py fields build_log.jsonl
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lowpoly_kit.core import metrics, png  # noqa: E402


def outline(ref_path, model_path):
    _w1, _h1, ref_rows = png.read_file(ref_path)
    _w2, _h2, model_rows = png.read_file(model_path)
    err = metrics.outline_error(png.mask(ref_rows), png.mask(model_rows))
    print(f"outline error: {err * 100:.2f}% of the reference bbox long side")


def fields(log_path):
    plans = []
    with open(log_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            if entry.get("ok") and "plan" in entry:
                plans.append(entry["plan"])
    changed = metrics.changed_fields(plans)
    print(f"successful builds: {len(plans)}; changed fields after the first: {len(changed)}")
    for pid, path in sorted(changed, key=lambda k: (str(k[0]), k[1])):
        print(f"  {pid}{path}")


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "outline":
        outline(sys.argv[2], sys.argv[3])
    elif len(sys.argv) == 3 and sys.argv[1] == "fields":
        fields(sys.argv[2])
    else:
        print(__doc__)
        sys.exit(1)
