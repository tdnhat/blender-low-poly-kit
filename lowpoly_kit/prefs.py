"""Add-on preferences: team config path and tips toggle."""

import bpy
from bpy.props import BoolProperty, StringProperty

# Top-level package; at runtime this is "bl_ext.<repo>.lowpoly_kit".
ADDON_ID = __package__


def _on_config_path(self, context):
    from . import config_ui

    config_ui.reload_config()


class LPK_AddonPreferences(bpy.types.AddonPreferences):
    bl_idname = ADDON_ID

    config_path: StringProperty(
        name="Team config",
        description="Đường dẫn tới team_config.json (có thể đặt ở thư mục chung của team)",
        subtype="FILE_PATH",
        update=_on_config_path,
    )
    show_tips: BoolProperty(
        name="Hiện tip",
        description="Hiện gợi ý ngắn trong các panel",
        default=True,
    )

    def draw(self, context):
        from . import config_ui

        layout = self.layout
        layout.prop(self, "config_path")
        layout.prop(self, "show_tips")
        row = layout.row()
        row.operator("lpk.reload_config", icon="FILE_REFRESH")
        config_ui.draw_config_status(layout)


def get_prefs(context=None):
    """Preferences, or None when the add-on is loaded from source without being enabled."""
    context = context or bpy.context
    addon = context.preferences.addons.get(ADDON_ID)
    return addon.preferences if addon else None


def show_tips(context=None):
    prefs = get_prefs(context)
    return True if prefs is None else prefs.show_tips


classes = (LPK_AddonPreferences,)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
