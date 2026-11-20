"""Edit one part of a plan from the parameter panel (pure Python)."""

import copy

# Direct part fields per kind of part.
PART_FIELDS = {
    "lathe_profile": ("segments", "caps"),
    "extrude_profile": ("depth", "caps", "plane"),
    "box": ("size",),
    "cylinder": ("segments", "radius", "height"),
}
# Attachment fields per rule.
ATTACH_FIELDS = {
    "lathe_radius_at_height": ("height", "radial_offset"),
    "profile_segment": ("segment", "t", "normal_offset"),
    "box_face": ("face", "u", "v", "normal_offset"),
    "offset": ("position", "rotation"),
}


def part_kind(part):
    if part["op"] == "add_primitive":
        return part.get("shape")
    return part["op"]


def editable_fields(part):
    """(part field names, attachment field names, scale knobs) for the UI."""
    kind = part_kind(part)
    fields = list(PART_FIELDS.get(kind, ()))
    if kind == "cylinder" and part.get("attachment", {}).get("rule") == "lathe_radius_at_height":
        fields.remove("radius")  # computed by the rule
    att = part.get("attachment")
    att_fields = list(ATTACH_FIELDS.get(att["rule"], ())) if att else []
    scales = {"lathe_profile": ["radius_scale", "height_scale"], "extrude_profile": ["profile_scale"]}.get(kind, [])
    return fields, att_fields, scales


def find_part(plan, part_id):
    for part in plan["parts"]:
        if part["id"] == part_id:
            return part
    raise KeyError(part_id)


def edit_part(plan, part_id, changes):
    """Return a copy of ``plan`` with ``changes`` applied to ``part_id``.

    ``changes`` keys: part fields, ``att.<field>`` for attachment fields,
    ``radius_scale`` / ``height_scale`` (lathe) and ``profile_scale`` [sa, sb]
    (extrude). Keys that do not apply to the part are ignored.
    """
    out = copy.deepcopy(plan)
    part = find_part(out, part_id)
    if part.get("baked"):
        raise ValueError("baked")
    fields, att_fields, scales = editable_fields(part)
    for key, value in changes.items():
        if key in fields:
            part[key] = list(value) if isinstance(value, (list, tuple)) else value
        elif key.startswith("att.") and key[4:] in att_fields:
            part["attachment"][key[4:]] = list(value) if isinstance(value, (list, tuple)) else value
        elif key == "radius_scale" and "radius_scale" in scales and value != 1.0:
            part["profile_z_radius"] = [[z, r * value] for z, r in part["profile_z_radius"]]
        elif key == "height_scale" and "height_scale" in scales and value != 1.0:
            part["profile_z_radius"] = [[z * value, r] for z, r in part["profile_z_radius"]]
        elif key == "profile_scale" and "profile_scale" in scales and tuple(value) != (1.0, 1.0):
            part["profile"] = [[a * value[0], b * value[1]] for a, b in part["profile"]]
    return out
