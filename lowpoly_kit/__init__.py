"""LowPoly Kit: Blender add-on for low-poly static props.

This file must not import bpy at module level, so that ``lowpoly_kit.core``
can be imported and unit-tested with a plain Python interpreter.
"""

_registered_modules = []


def _bpy_modules():
    # Imported lazily: these modules depend on bpy.
    from . import (
        prefs,
        config_ui,
        assets,
        checker_ops,
        fix_ops,
        coloring,
        export,
        reference,
        buildplan_ops,
        ui,
    )

    return [prefs, config_ui, assets, checker_ops, fix_ops, coloring, export, reference, buildplan_ops, ui]


def register():
    global _registered_modules
    _registered_modules = []
    for module in _bpy_modules():
        module.register()
        _registered_modules.append(module)


def unregister():
    global _registered_modules
    for module in reversed(_registered_modules):
        module.unregister()
    _registered_modules = []
