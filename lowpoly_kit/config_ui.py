"""Loading the team config inside Blender and showing its status."""

import bpy
from bpy.app.handlers import persistent

from . import prefs, runtime
from .core import config as core_config
from .core import messages

_ICONS = {"ERROR": "ERROR", "WARNING": "INFO", "INFO": "DOT"}


def config_path():
    p = prefs.get_prefs()
    raw = p.config_path if p else ""
    return bpy.path.abspath(raw) if raw else ""


def reload_config():
    runtime.config_result = core_config.load(config_path())
    runtime.invalidate_checks()
    return runtime.config_result


def get_config_result():
    if runtime.config_result is None:
        reload_config()
    return runtime.config_result


def get_config():
    return get_config_result().config


def draw_config_status(layout):
    result = get_config_result()
    box = layout.box()
    if result.source == "file":
        box.label(text=f"Đang dùng: {result.path}", icon="CHECKMARK")
    else:
        box.label(text="Đang dùng bộ mặc định tích hợp", icon="INFO")
    for diag in result.diagnostics:
        box.label(text=messages.text(diag.code, diag.params), icon=_ICONS.get(diag.level, "DOT"))


class LPK_OT_reload_config(bpy.types.Operator):
    bl_idname = "lpk.reload_config"
    bl_label = "Reload Config"
    bl_description = "Đọc lại team_config.json"

    def execute(self, context):
        result = reload_config()
        level = {"file": "INFO"}.get(result.source, "WARNING")
        self.report({level}, "Đã nạp team config" if result.source == "file" else "Đang dùng bộ mặc định tích hợp")
        return {"FINISHED"}


@persistent
def _on_load_post(*_args):
    runtime.clear()


classes = (LPK_OT_reload_config,)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.app.handlers.load_post.append(_on_load_post)


def unregister():
    if _on_load_post in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_on_load_post)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    runtime.clear()
