"""Team config loading (pure Python).

Policy (spec, "Giả định triển khai"):
- missing keys fall back to defaults one key at a time;
- a file that does not parse or does not validate falls back to the
  defaults as a whole, and the reason is reported.
"""

import copy
import json
import os
import re
from collections import namedtuple

from . import colors, schema_lite, strict_json

SCHEMA_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "schemas", "team_config.schema.json")

DEFAULT_CONFIG = {
    "schema_version": 1,
    "root_name_pattern": r"^PR_[A-Z][A-Za-z0-9]*(_[A-Za-z0-9]+)*$",
    "root_name_example": "PR_Barrel_Broken",
    "budget_groups": {
        "small": {"label": "Prop nhỏ", "max_tris": 3000},
        "large": {"label": "Prop lớn", "max_tris": 8000},
    },
    "default_budget_group": "small",
    "warning_ratio": 0.9,
    "pivot_tolerance": 0.005,
    "max_materials": 1,
    "merge_distance": 0.0001,
    "reference_tolerance": 0.01,
    "material_name": "M_VertexColor",
    "color_attribute": "Color",
    "default_color": "#C8C8C8",
    "palette": [
        "#2B2D42", "#8D99AE", "#EDF2F4", "#EF233C",
        "#D90429", "#F4A261", "#E9C46A", "#2A9D8F",
        "#264653", "#6A994E", "#A7C957", "#BC6C25",
    ],
    "export_dir": "//export",
    "export_subdir": "props",
    "severity_overrides": {},
}

# (level, code, params). level: ERROR | WARNING | INFO
Diagnostic = namedtuple("Diagnostic", "level code params")
ConfigResult = namedtuple("ConfigResult", "config source path diagnostics")


def load_schema():
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


def defaults():
    return copy.deepcopy(DEFAULT_CONFIG)


def semantic_errors(cfg):
    """Checks JSON Schema cannot express. Returns list of (pointer, code, params)."""
    errors = []
    if "root_name_pattern" in cfg:
        try:
            re.compile(cfg["root_name_pattern"])
        except re.error as exc:
            errors.append(("/root_name_pattern", "config_bad_regex", {"error": str(exc)}))
    groups = cfg.get("budget_groups", DEFAULT_CONFIG["budget_groups"])
    group = cfg.get("default_budget_group", DEFAULT_CONFIG["default_budget_group"])
    if group not in groups:
        errors.append(("/default_budget_group", "config_unknown_group", {"group": group}))
    for i, value in enumerate(cfg.get("palette", [])):
        if not colors.is_hex(value):
            errors.append((f"/palette/{i}", "config_bad_color", {"value": value}))
    return errors


def load_text(text, path="<text>"):
    diags = []
    try:
        data, positions = strict_json.loads_with_positions(text)
    except strict_json.JsonError as exc:
        diags.append(Diagnostic("ERROR", "config_parse_error", {"path": path, "line": exc.line, "col": exc.col, "reason": exc.reason}))
        return ConfigResult(defaults(), "defaults", path, diags)

    errors = schema_lite.validate(data, load_schema())
    problems = [(e.pointer, e.code, e.params) for e in errors]
    if not errors and isinstance(data, dict):
        problems += semantic_errors(data)
    if problems:
        for pointer, code, params in problems:
            line, col = strict_json.position_for(positions, pointer)
            diags.append(Diagnostic("ERROR", "config_invalid", {"path": path, "pointer": pointer or "/", "detail": code, "params": params, "line": line, "col": col}))
        diags.append(Diagnostic("WARNING", "config_using_defaults", {"path": path}))
        return ConfigResult(defaults(), "defaults", path, diags)

    cfg = defaults()
    missing = sorted(k for k in DEFAULT_CONFIG if k not in data)
    cfg.update(copy.deepcopy(data))
    if missing:
        diags.append(Diagnostic("INFO", "config_keys_defaulted", {"keys": missing}))
    return ConfigResult(cfg, "file", path, diags)


def load(path):
    """Load the team config from ``path`` (already absolute)."""
    if not path:
        return ConfigResult(defaults(), "defaults", "", [Diagnostic("INFO", "config_not_set", {})])
    if not os.path.isfile(path):
        return ConfigResult(defaults(), "defaults", path, [Diagnostic("WARNING", "config_missing", {"path": path})])
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except (OSError, UnicodeDecodeError) as exc:
        return ConfigResult(defaults(), "defaults", path, [Diagnostic("ERROR", "config_unreadable", {"path": path, "reason": str(exc)})])
    return load_text(text, path)


def budget_group(cfg, name):
    """Return (group_name, group dict); unknown names fall back to the default group."""
    groups = cfg["budget_groups"]
    if name in groups:
        return name, groups[name]
    default = cfg["default_budget_group"]
    return default, groups[default]
