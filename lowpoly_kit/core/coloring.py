"""Vertex-colour data transforms (pure Python).

Colours are sRGB float triples; the bpy layer writes them through the
attribute's ``color_srgb`` property, so no colour-space guessing happens here.
"""

from . import colors


def palette(cfg):
    """Team palette as list of (hex, sRGB triple)."""
    return [(h.upper(), colors.hex_to_srgb(h)) for h in cfg.get("palette", [])]


def face_corners(loop_starts, loop_totals, face_indices):
    """Corner (loop) indices of the given faces."""
    out = []
    for f in face_indices:
        start = loop_starts[f]
        out.extend(range(start, start + loop_totals[f]))
    return out


def fill_corners(corner_colors, corners, rgb):
    """Return a copy of ``corner_colors`` (list of RGBA) with ``corners`` set to rgb."""
    out = list(corner_colors)
    rgba = (rgb[0], rgb[1], rgb[2], 1.0)
    for c in corners:
        out[c] = rgba
    return out


def corners_from_face_materials(loop_starts, loop_totals, face_material_index, material_colors, fallback):
    """Per-corner colours from each face's material Base Color (sRGB).

    ``material_colors``: list indexed by slot; None for empty/unknown slots.
    """
    total = sum(loop_totals)
    out = [None] * total
    for f, (start, count) in enumerate(zip(loop_starts, loop_totals)):
        idx = face_material_index[f]
        rgb = material_colors[idx] if 0 <= idx < len(material_colors) and material_colors[idx] is not None else fallback
        rgba = (rgb[0], rgb[1], rgb[2], 1.0)
        for c in range(start, start + count):
            out[c] = rgba
    return out


def corners_from_point_colors(loop_vertex_index, point_colors):
    """Per-corner colours from a POINT-domain attribute."""
    return [tuple(point_colors[v]) for v in loop_vertex_index]


def unique_colors(corner_colors, cap=2):
    """Distinct quantised RGB values, stopping once ``cap`` are found."""
    seen = set()
    for c in corner_colors:
        seen.add(colors.quantize_byte(c[:3]))
        if len(seen) >= cap:
            break
    return seen


def flatten(rgba_list):
    flat = []
    for c in rgba_list:
        flat.extend(c[:4] if len(c) >= 4 else (c[0], c[1], c[2], 1.0))
    return flat


def unflatten(flat):
    return [tuple(flat[i:i + 4]) for i in range(0, len(flat), 4)]
