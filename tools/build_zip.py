"""Build an installable extension zip (Install from Disk).

Usage: python3 tools/build_zip.py [output_dir]
The manifest ends up at the root of the zip, as Blender 4.2 expects.
"""

import os
import sys
import tomllib
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACKAGE = os.path.join(ROOT, "lowpoly_kit")
EXCLUDE_DIRS = {"__pycache__", ".git"}
EXCLUDE_SUFFIXES = (".pyc", ".blend1")


def iter_package_files(package_dir=PACKAGE):
    for dirpath, dirnames, filenames in os.walk(package_dir):
        dirnames[:] = sorted(d for d in dirnames if d not in EXCLUDE_DIRS)
        for name in sorted(filenames):
            if name.endswith(EXCLUDE_SUFFIXES):
                continue
            full = os.path.join(dirpath, name)
            yield full, os.path.relpath(full, package_dir).replace(os.sep, "/")


def read_manifest(package_dir=PACKAGE):
    with open(os.path.join(package_dir, "blender_manifest.toml"), "rb") as f:
        return tomllib.load(f)


def build(output_dir=None, package_dir=PACKAGE):
    manifest = read_manifest(package_dir)
    output_dir = output_dir or os.path.join(ROOT, "dist")
    os.makedirs(output_dir, exist_ok=True)
    out = os.path.join(output_dir, f"{manifest['id']}-{manifest['version']}.zip")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for full, arc in iter_package_files(package_dir):
            zf.write(full, arc)
    return out


if __name__ == "__main__":
    print(build(sys.argv[1] if len(sys.argv) > 1 else None))
