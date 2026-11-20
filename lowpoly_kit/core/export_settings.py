"""glTF exporter options, filtered against what the installed exporter offers."""

# Option names of the Blender 4.2 glTF exporter.
DESIRED = {
    "export_format": "GLB",
    "export_yup": True,
    "export_apply": True,
    "export_materials": "EXPORT",
    "export_vertex_color": "MATERIAL",
    "export_all_vertex_colors": False,
    "export_normals": True,
    "export_extras": False,
    "export_cameras": False,
    "export_lights": False,
    "export_animations": False,
    "export_skins": False,
    "export_morph": False,
    "export_attributes": False,
    "use_selection": False,
    "use_visible": False,
    "use_renderable": False,
    "use_active_collection": True,
    "use_active_collection_with_nested": True,
    "use_active_scene": True,
    "will_save_settings": False,
    "check_existing": False,
}

# Options without which the export cannot be trusted.
REQUIRED = ("export_format", "export_yup", "export_apply", "use_active_collection", "export_vertex_color")


def filter_options(available, desired=None):
    """``available``: {identifier: enum identifiers list or None for non-enum}.

    Returns (kwargs, dropped, missing_required).
    """
    desired = DESIRED if desired is None else desired
    kwargs, dropped = {}, []
    for key, value in desired.items():
        if key not in available:
            dropped.append(key)
            continue
        enum_items = available[key]
        if enum_items is not None and value not in enum_items:
            dropped.append(key)
            continue
        kwargs[key] = value
    missing_required = [k for k in REQUIRED if k not in kwargs]
    return kwargs, dropped, missing_required
