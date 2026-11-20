"""Validator for a subset of JSON Schema (draft 2020-12 keywords).

Only the keywords in SUPPORTED_KEYWORDS are understood; schema files shipped
with the add-on may use nothing else (enforced by a unit test), so the subset
never silently ignores a constraint.

``oneOf`` picks its branch by ``const`` discriminators when possible (e.g.
``"op": {"const": "lathe_profile"}``), so error messages talk about the
branch the author meant instead of listing every branch.

Errors are ``SchemaError(pointer, code, params)``.
"""

import re
from collections import namedtuple

from .strict_json import join_pointer

SchemaError = namedtuple("SchemaError", "pointer code params")

ANNOTATIONS = {"$schema", "$id", "$comment", "title", "description", "default", "examples"}
SUPPORTED_KEYWORDS = ANNOTATIONS | {
    "$defs", "$ref", "type", "properties", "required", "additionalProperties",
    "enum", "const", "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum",
    "minItems", "maxItems", "items", "prefixItems", "minLength", "maxLength", "pattern",
    "oneOf", "minProperties", "uniqueItems",
}


def json_type(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def _type_matches(value, expected):
    actual = json_type(value)
    if expected == "number":
        return actual in ("number", "integer")
    if expected == "integer" and actual == "number":
        return float(value).is_integer()
    return actual == expected


def json_equal(a, b):
    """Equality that does not treat True as 1."""
    if isinstance(a, bool) or isinstance(b, bool):
        return isinstance(a, bool) and isinstance(b, bool) and a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return a == b
    if type(a) is not type(b):
        return False
    if isinstance(a, list):
        return len(a) == len(b) and all(json_equal(x, y) for x, y in zip(a, b))
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(json_equal(a[k], b[k]) for k in a)
    return a == b


def _is_number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


class Validator:
    def __init__(self, schema):
        self.root = schema

    def resolve(self, ref):
        if not ref.startswith("#/"):
            raise ValueError(f"only local $ref is supported: {ref}")
        node = self.root
        for token in ref[2:].split("/"):
            token = token.replace("~1", "/").replace("~0", "~")
            node = node[token]
        return node

    def validate(self, instance):
        errors = []
        self._validate(instance, self.root, "", errors)
        return errors

    def _validate(self, value, schema, ptr, errors):
        if schema is True:
            return
        if schema is False:
            errors.append(SchemaError(ptr, "schema_not_allowed", {}))
            return
        if "$ref" in schema:
            self._validate(value, self.resolve(schema["$ref"]), ptr, errors)

        if "type" in schema:
            types = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
            if not any(_type_matches(value, t) for t in types):
                errors.append(SchemaError(ptr, "schema_type", {"expected": "|".join(types), "actual": json_type(value)}))
                return

        if "const" in schema and not json_equal(value, schema["const"]):
            errors.append(SchemaError(ptr, "schema_const", {"expected": schema["const"], "actual": value}))
        if "enum" in schema and not any(json_equal(value, e) for e in schema["enum"]):
            errors.append(SchemaError(ptr, "schema_enum", {"allowed": schema["enum"], "actual": value}))

        if _is_number(value):
            if "minimum" in schema and value < schema["minimum"]:
                errors.append(SchemaError(ptr, "schema_minimum", {"limit": schema["minimum"], "actual": value}))
            if "maximum" in schema and value > schema["maximum"]:
                errors.append(SchemaError(ptr, "schema_maximum", {"limit": schema["maximum"], "actual": value}))
            if "exclusiveMinimum" in schema and value <= schema["exclusiveMinimum"]:
                errors.append(SchemaError(ptr, "schema_exclusive_minimum", {"limit": schema["exclusiveMinimum"], "actual": value}))
            if "exclusiveMaximum" in schema and value >= schema["exclusiveMaximum"]:
                errors.append(SchemaError(ptr, "schema_exclusive_maximum", {"limit": schema["exclusiveMaximum"], "actual": value}))

        if isinstance(value, str):
            if "minLength" in schema and len(value) < schema["minLength"]:
                errors.append(SchemaError(ptr, "schema_min_length", {"limit": schema["minLength"]}))
            if "maxLength" in schema and len(value) > schema["maxLength"]:
                errors.append(SchemaError(ptr, "schema_max_length", {"limit": schema["maxLength"]}))
            if "pattern" in schema and not re.search(schema["pattern"], value):
                errors.append(SchemaError(ptr, "schema_pattern", {"pattern": schema["pattern"], "actual": value}))

        if isinstance(value, list):
            self._validate_array(value, schema, ptr, errors)
        if isinstance(value, dict):
            self._validate_object(value, schema, ptr, errors)

        if "oneOf" in schema:
            self._validate_one_of(value, schema["oneOf"], ptr, errors)

    def _validate_array(self, value, schema, ptr, errors):
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append(SchemaError(ptr, "schema_min_items", {"limit": schema["minItems"], "actual": len(value)}))
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            errors.append(SchemaError(ptr, "schema_max_items", {"limit": schema["maxItems"], "actual": len(value)}))
        prefix = schema.get("prefixItems", [])
        for i, item_schema in enumerate(prefix[:len(value)]):
            self._validate(value[i], item_schema, join_pointer(ptr, i), errors)
        if "items" in schema:
            for i in range(len(prefix), len(value)):
                self._validate(value[i], schema["items"], join_pointer(ptr, i), errors)
        if schema.get("uniqueItems"):
            for i in range(len(value)):
                for j in range(i):
                    if json_equal(value[i], value[j]):
                        errors.append(SchemaError(join_pointer(ptr, i), "schema_unique_items", {}))

    def _validate_object(self, value, schema, ptr, errors):
        if "minProperties" in schema and len(value) < schema["minProperties"]:
            errors.append(SchemaError(ptr, "schema_min_properties", {"limit": schema["minProperties"]}))
        for key in schema.get("required", []):
            if key not in value:
                errors.append(SchemaError(join_pointer(ptr, key), "schema_required", {"field": key}))
        props = schema.get("properties", {})
        additional = schema.get("additionalProperties", True)
        for key, item in value.items():
            child = join_pointer(ptr, key)
            if key in props:
                self._validate(item, props[key], child, errors)
            elif additional is False:
                errors.append(SchemaError(child, "schema_additional_property", {"field": key}))
            elif isinstance(additional, dict):
                self._validate(item, additional, child, errors)

    def _discriminated_branch(self, value, branches):
        if not isinstance(value, dict):
            return None
        for branch in branches:
            b = self.resolve(branch["$ref"]) if "$ref" in branch else branch
            consts = {k: p["const"] for k, p in b.get("properties", {}).items()
                      if isinstance(p, dict) and "const" in p}
            if consts and all(k in value and json_equal(value[k], c) for k, c in consts.items()):
                return branch
        return None

    def _validate_one_of(self, value, branches, ptr, errors):
        chosen = self._discriminated_branch(value, branches)
        if chosen is not None:
            self._validate(value, chosen, ptr, errors)
            return
        passing = 0
        for branch in branches:
            sub = []
            self._validate(value, branch, ptr, sub)
            if not sub:
                passing += 1
        if passing != 1:
            errors.append(SchemaError(ptr, "schema_one_of", {"matched": passing}))


def validate(instance, schema):
    return Validator(schema).validate(instance)


def unsupported_keywords(schema, path="#"):
    """List keywords in ``schema`` outside the supported subset (for tests)."""
    found = []
    if isinstance(schema, dict):
        for key, sub in schema.items():
            if key not in SUPPORTED_KEYWORDS:
                found.append(f"{path}/{key}")
            if key in ("properties", "$defs"):
                for name, s in sub.items():
                    found += unsupported_keywords(s, f"{path}/{key}/{name}")
            elif key in ("items", "additionalProperties") and isinstance(sub, dict):
                found += unsupported_keywords(sub, f"{path}/{key}")
            elif key in ("oneOf", "prefixItems"):
                for i, s in enumerate(sub):
                    found += unsupported_keywords(s, f"{path}/{key}/{i}")
    return found
