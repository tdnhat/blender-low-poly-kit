"""Static guardrails that replace running Blender during development."""

import ast
import os
import re
import tomllib
import unittest
import zipfile
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PKG = os.path.join(ROOT, "lowpoly_kit")
CORE = os.path.join(PKG, "core")

FORBIDDEN_IN_CORE = {"bpy", "bmesh", "mathutils", "gpu", "blf", "bpy_extras", "gpu_extras", "numpy"}

# APIs removed or deprecated in Blender 4.x that must not appear in the add-on.
DENY_PATTERNS = [
    r"use_auto_smooth",
    r"calc_normals_split",
    r"\.vertex_colors\b",
    r"\bimport bgl\b",
    r"3D_UNIFORM_COLOR",
    r"\bexport_colors\b",
    r"bpy\.ops\.[a-z_]+\.[a-z_]+\(\s*\{",  # dict context override (removed in 4.0)
]


def py_files(base):
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for name in filenames:
            if name.endswith(".py"):
                yield os.path.join(dirpath, name)


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


class CoreIsolation(unittest.TestCase):
    def test_core_imports_only_stdlib_or_core(self):
        for path in py_files(CORE):
            tree = ast.parse(read(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        top = alias.name.split(".")[0]
                        self.assertNotIn(top, FORBIDDEN_IN_CORE, f"{path}: import {alias.name}")
                        self.assertNotEqual(top, "lowpoly_kit", f"{path}: absolute package import")
                elif isinstance(node, ast.ImportFrom):
                    if node.level == 0:
                        top = (node.module or "").split(".")[0]
                        self.assertNotIn(top, FORBIDDEN_IN_CORE, f"{path}: from {node.module}")
                        self.assertNotEqual(top, "lowpoly_kit", f"{path}: absolute package import")
                    else:
                        # Relative imports must stay inside core.
                        rel = os.path.relpath(os.path.dirname(path), CORE)
                        depth = 0 if rel == "." else len(rel.split(os.sep))
                        self.assertLessEqual(node.level - 1, depth, f"{path}: relative import leaves core")

    def test_package_init_has_no_toplevel_bpy(self):
        tree = ast.parse(read(os.path.join(PKG, "__init__.py")))
        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
                for n in names:
                    self.assertNotEqual(n.split(".")[0], "bpy")


class PythonCompat(unittest.TestCase):
    def test_parses_as_python_311(self):
        for path in py_files(PKG):
            ast.parse(read(path), filename=path, feature_version=(3, 11))

    def test_no_312_only_features(self):
        for path in py_files(PKG):
            src = read(path)
            self.assertNotIn("itertools.batched", src, path)
            self.assertNotIn("typing.override", src, path)
            self._check_fstring_quotes(path, src)

    def _check_fstring_quotes(self, path, src):
        """Strings nested in an f-string with the same quote are 3.12-only (PEP 701)."""
        import io
        import tokenize

        def quote_of(tok_string):
            s = tok_string.lstrip("rRbBuUfF")
            return s[:3] if s[:3] in ('"""', "'''") else s[:1]

        stack = []
        for tok in tokenize.generate_tokens(io.StringIO(src).readline):
            name = tokenize.tok_name.get(tok.type, "")
            if name == "FSTRING_START":
                q = quote_of(tok.string)
                self.assertNotIn(q, stack, f"{path}:{tok.start[0]} nested f-string reuses quote")
                stack.append(q)
            elif name == "FSTRING_END":
                stack.pop()
            elif name == "STRING" and stack:
                self.assertNotIn(quote_of(tok.string), stack, f"{path}:{tok.start[0]} string in f-string reuses quote")


class DeniedApis(unittest.TestCase):
    def test_no_removed_blender_apis(self):
        for path in py_files(PKG):
            src = read(path)
            for pat in DENY_PATTERNS:
                self.assertIsNone(re.search(pat, src), f"{path}: matches {pat}")


class Manifest(unittest.TestCase):
    def test_manifest_fields(self):
        with open(os.path.join(PKG, "blender_manifest.toml"), "rb") as f:
            m = tomllib.load(f)
        for key in ("schema_version", "id", "version", "name", "tagline", "maintainer", "type",
                    "blender_version_min", "license"):
            self.assertIn(key, m)
        self.assertRegex(m["version"], r"^\d+\.\d+\.\d+$")
        self.assertLessEqual(len(m["tagline"]), 64)
        self.assertFalse(m["tagline"].endswith((".", "!", "?")))
        self.assertEqual(m["type"], "add-on")
        self.assertTrue(m["blender_version_min"].startswith("4.2"))


class BuildZip(unittest.TestCase):
    def test_zip_layout(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("build_zip", os.path.join(ROOT, "tools", "build_zip.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        with tempfile.TemporaryDirectory() as tmp:
            out = mod.build(tmp)
            with zipfile.ZipFile(out) as zf:
                names = zf.namelist()
        self.assertIn("blender_manifest.toml", names)
        self.assertIn("__init__.py", names)
        self.assertFalse(any("__pycache__" in n or n.endswith(".pyc") for n in names))
        self.assertFalse(any(n.startswith("tests/") for n in names))


if __name__ == "__main__":
    unittest.main()
