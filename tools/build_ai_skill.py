"""Build the AI skill "lowpoly-build-plan" from the add-on sources.

Usage: python3 tools/build_ai_skill.py [output_dir]

Produces <output_dir>/lowpoly-build-plan/ and lowpoly-build-plan.zip
(folder at the zip root, SKILL.md inside). The rules, schema, examples and
the Python validator all come from this repository, so the skill never
drifts from the add-on's schema.
"""

import json
import os
import re
import shutil
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = os.path.join(ROOT, "lowpoly_kit")
SRC = os.path.join(ROOT, "ai_skill")
SKILL_NAME = "lowpoly-build-plan"
EXAMPLES = ("barrel", "terminal", "chair", "tuna", "boat")
CORE_FILES = (
    "vecmath.py", "strict_json.py", "schema_lite.py", "messages.py",
    "buildplan/__init__.py", "buildplan/validate.py", "buildplan/geometry.py", "buildplan/geometry2d.py",
    "buildplan/attach.py", "buildplan/reconcile.py", "buildplan/contact.py",
)


def rules_from_prompt():
    with open(os.path.join(PKG, "prompts", "buildplan_prompt_v1.md"), encoding="utf-8") as f:
        text = f.read()
    m = re.search(r"## Quy ước bắt buộc\n\n(.*?)\n## ", text, re.S)
    if not m:
        raise RuntimeError("rules section not found in prompt template")
    return m.group(1).strip().replace("{{asset_name}}", "<tên asset>")


def build(output_dir=None):
    output_dir = output_dir or os.path.join(ROOT, "dist")
    out = os.path.join(output_dir, SKILL_NAME)
    if os.path.isdir(out):
        shutil.rmtree(out)
    os.makedirs(out)

    schema_path = os.path.join(PKG, "schemas", "buildplan.schema.json")
    with open(schema_path, encoding="utf-8") as f:
        schema_version = json.load(f)["properties"]["schema_version"]["const"]

    with open(os.path.join(SRC, "SKILL.template.md"), encoding="utf-8") as f:
        skill = f.read()
    skill = skill.replace("{{rules}}", rules_from_prompt()).replace("{{schema_version}}", str(schema_version))
    with open(os.path.join(out, "SKILL.md"), "w", encoding="utf-8") as f:
        f.write(skill)

    for sub in ("schema", "examples", "reference", "scripts/lpk_core/buildplan", "scripts/schemas"):
        os.makedirs(os.path.join(out, sub), exist_ok=True)
    shutil.copy(schema_path, os.path.join(out, "schema", "buildplan.schema.json"))
    shutil.copy(schema_path, os.path.join(out, "scripts", "schemas", "buildplan.schema.json"))
    shutil.copy(os.path.join(SRC, "reference", "asset_tips.md"), os.path.join(out, "reference", "asset_tips.md"))
    shutil.copy(os.path.join(SRC, "scripts", "validate_plan.py"), os.path.join(out, "scripts", "validate_plan.py"))
    for name in EXAMPLES:
        shutil.copy(os.path.join(ROOT, "tests", "fixtures", "plans", name + ".json"), os.path.join(out, "examples", name + ".json"))

    core_dst = os.path.join(out, "scripts", "lpk_core")
    with open(os.path.join(core_dst, "__init__.py"), "w", encoding="utf-8") as f:
        f.write('"""Subset of the LowPoly Kit core used by validate_plan.py (generated)."""\n')
    for rel in CORE_FILES:
        shutil.copy(os.path.join(PKG, "core", rel), os.path.join(core_dst, rel))

    zip_path = os.path.join(output_dir, SKILL_NAME + ".zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for dirpath, dirnames, filenames in os.walk(out):
            dirnames[:] = sorted(d for d in dirnames if d != "__pycache__")
            for name in sorted(filenames):
                if name.endswith(".pyc"):
                    continue
                full = os.path.join(dirpath, name)
                zf.write(full, os.path.relpath(full, output_dir).replace(os.sep, "/"))
    return out, zip_path


if __name__ == "__main__":
    folder, archive = build(sys.argv[1] if len(sys.argv) > 1 else None)
    print(folder)
    print(archive)
