"""Static checks of the Blender layer without Blender.

- every bpy module imports against permissive stub modules (catches typos,
  missing imports and bad module-level code);
- operator / panel ids are well-formed and unique;
- every Operator / Panel / PropertyGroup class is listed in its module's
  ``classes`` tuple so it gets registered.
"""

import ast
import importlib
import os
import sys
import types
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PKG = os.path.join(ROOT, "lowpoly_kit")
BPY_MODULES = [f[:-3] for f in sorted(os.listdir(PKG)) if f.endswith(".py") and f != "__init__.py"]
STUBBED = ["bpy", "bpy.props", "bpy.types", "bpy.app", "bpy.app.handlers", "bpy.utils", "bpy.ops", "bpy.path",
           "bmesh", "mathutils", "mathutils.geometry", "gpu", "gpu_extras", "gpu_extras.batch",
           "bpy_extras", "bpy_extras.view3d_utils"]


class _Dummy:
    """Accepts any attribute access, call, or use as a base class."""

    def __init__(self, *args, **kwargs):
        pass

    def __getattr__(self, name):
        return _Dummy()

    def __call__(self, *args, **kwargs):
        if len(args) == 1 and callable(args[0]) and not kwargs:
            return args[0]  # decorator such as @persistent
        return _Dummy()

    def __mro_entries__(self, bases):
        return (object,)

    def __iter__(self):
        return iter(())


class _StubModule(types.ModuleType):
    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return _Dummy()


def install_stubs():
    saved = {name: sys.modules.get(name) for name in STUBBED}
    for name in STUBBED:
        sys.modules[name] = _StubModule(name)
    for name in STUBBED:
        if "." in name:
            parent, child = name.rsplit(".", 1)
            setattr(sys.modules[parent], child, sys.modules[name])
    return saved


def restore(saved):
    for name, mod in saved.items():
        if mod is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = mod
    for name in list(sys.modules):
        if name.startswith("lowpoly_kit.") and not name.startswith("lowpoly_kit.core"):
            sys.modules.pop(name, None)


class ImportSmoke(unittest.TestCase):
    def test_bpy_modules_import_with_stubs(self):
        saved = install_stubs()
        try:
            for mod in BPY_MODULES:
                with self.subTest(module=mod):
                    m = importlib.import_module(f"lowpoly_kit.{mod}")
                    if hasattr(m, "classes"):
                        self.assertTrue(callable(getattr(m, "register", None)), mod)
                        self.assertTrue(callable(getattr(m, "unregister", None)), mod)
        finally:
            restore(saved)


def _class_info():
    """(module, class name, bases, attributes) for classes deriving from bpy.types.*."""
    out = []
    for mod in BPY_MODULES:
        with open(os.path.join(PKG, mod + ".py"), encoding="utf-8") as f:
            tree = ast.parse(f.read())
        listed = set()
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "classes" for t in node.targets):
                if isinstance(node.value, ast.Tuple):
                    listed = {e.id for e in node.value.elts if isinstance(e, ast.Name)}
        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            bases = [ast.unparse(b) for b in node.bases]
            attrs = {}
            for stmt in node.body:
                if isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.Constant):
                    for t in stmt.targets:
                        if isinstance(t, ast.Name):
                            attrs[t.id] = stmt.value.value
            out.append((mod, node.name, bases, attrs, listed))
    return out


class Registration(unittest.TestCase):
    def test_ids_and_listing(self):
        seen = {}
        for mod, name, bases, attrs, listed in _class_info():
            kind = next((b.split(".")[-1] for b in bases if b.startswith("bpy.types.")), None)
            if kind is None:
                continue
            if kind in ("Operator", "Panel", "PropertyGroup", "AddonPreferences"):
                self.assertIn(name, listed, f"{mod}.{name} not in classes tuple")
            if kind == "Operator":
                idname = attrs.get("bl_idname", "")
                self.assertRegex(idname, r"^lpk\.[a-z_]+$", f"{mod}.{name}")
                self.assertRegex(name, r"^LPK_OT_[a-z_]+$")
                self.assertTrue(attrs.get("bl_label"), f"{mod}.{name} has no bl_label")
            if kind == "Panel":
                idname = attrs.get("bl_idname", "")
                self.assertRegex(idname, r"^LPK_PT_[a-z_]+$", f"{mod}.{name}")
            if "bl_idname" in attrs and kind in ("Operator", "Panel"):
                self.assertNotIn(attrs["bl_idname"], seen, f"duplicate id {attrs['bl_idname']}")
                seen[attrs["bl_idname"]] = name

    def test_ui_operator_references_exist(self):
        defined = {attrs.get("bl_idname") for _m, _n, _b, attrs, _l in _class_info()}
        builtin = {"view3d.view_axis"}
        for mod in BPY_MODULES:
            with open(os.path.join(PKG, mod + ".py"), encoding="utf-8") as f:
                tree = ast.parse(f.read())
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "operator":
                    if node.args and isinstance(node.args[0], ast.Constant):
                        op = node.args[0].value
                        self.assertTrue(op in defined or op in builtin, f"{mod}: unknown operator {op}")

    def test_init_lists_every_registering_module(self):
        with open(os.path.join(PKG, "__init__.py"), encoding="utf-8") as f:
            src = f.read()
        for mod, _name, _bases, _attrs, listed in _class_info():
            if listed:
                self.assertIn(mod, src, f"{mod} has classes but is not registered in __init__")


if __name__ == "__main__":
    unittest.main()
