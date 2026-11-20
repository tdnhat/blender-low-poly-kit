"""Export path resolution."""

import os
import re


def safe_filename(name):
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .")
    return cleaned or "asset"


def resolve_export_path(export_dir, subdir, asset_name, blend_path):
    """Return (absolute path, error code or None).

    ``//`` and plain relative directories are relative to the saved .blend.
    """
    if export_dir.startswith("//"):
        rel = export_dir[2:]
    elif os.path.isabs(export_dir):
        rel = None
    else:
        rel = export_dir
    if rel is not None:
        if not blend_path:
            return None, "export_unsaved_blend"
        base = os.path.join(os.path.dirname(blend_path), rel)
    else:
        base = export_dir
    folder = os.path.join(base, subdir) if subdir else base
    return os.path.normpath(os.path.join(folder, safe_filename(asset_name) + ".glb")), None


def temp_path_for(target):
    """Temporary file next to the target; must end with .glb for the exporter."""
    folder, name = os.path.split(target)
    return os.path.join(folder, "." + name[:-4] + ".lpk_tmp.glb")
