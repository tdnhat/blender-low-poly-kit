import json
import os
import tempfile
import unittest

from lowpoly_kit.core import colors, config, schema_lite, strict_json, vecmath as vm


class VecMath(unittest.TestCase):
    def test_euler_and_inverse(self):
        m = vm.matmul(vm.translation((1, 2, 3)), vm.matmul(vm.euler_xyz((30, 45, 60)), vm.scaling((2, 3, 4))))
        inv = vm.inverse_affine(m)
        self.assertTrue(vm.matrices_close(vm.matmul(m, inv), vm.identity()))
        t, rot, s = vm.decompose(m)
        self.assertTrue(vm.close(t, (1, 2, 3)))
        self.assertTrue(vm.close(s, (2, 3, 4)))

    def test_rotation_direction(self):
        # +90 deg about Z maps +X to +Y (right-handed).
        self.assertTrue(vm.close(vm.transform_dir(vm.rotation_z(90), (1, 0, 0)), (0, 1, 0)))
        # Blender Front empty rotation (90,0,0) maps local +Z to -Y.
        self.assertTrue(vm.close(vm.transform_dir(vm.euler_xyz((90, 0, 0)), (0, 0, 1)), (0, -1, 0)))

    def test_determinant_and_negative_scale(self):
        self.assertLess(vm.det3(vm.scaling((-1, 1, 1))), 0)
        self.assertGreater(vm.det3(vm.scaling((-1, -1, 1))), 0)
        self.assertEqual(vm.negative_scale_axes((-1, -1, 1)), ["X", "Y"])
        self.assertFalse(vm.has_rotation(vm.scaling((2, 2, 2))))
        self.assertTrue(vm.has_rotation(vm.rotation_x(10)))
        self.assertFalse(vm.is_unit_scale(vm.scaling((1, 1, 2))))


class StrictJson(unittest.TestCase):
    def test_positions(self):
        text = '{\n  "a": [1, 2.5],\n  "b": {"c": true}\n}'
        value, pos = strict_json.loads_with_positions(text)
        self.assertEqual(value, json.loads(text))
        self.assertEqual(pos["/a/1"], (2, 12))
        self.assertEqual(pos["/b/c"], (3, 14))
        self.assertEqual(strict_json.position_for(pos, "/b/missing"), pos["/b"])

    def test_rejects_duplicates_and_nan(self):
        with self.assertRaises(strict_json.JsonError) as ctx:
            strict_json.loads('{"a": 1,\n "a": 2}')
        self.assertEqual(ctx.exception.code, "json_duplicate_key")
        self.assertEqual(ctx.exception.line, 2)
        for bad in ('{"a": NaN}', '[Infinity]', '[1,]', '{"a" 1}', '"\\x"', '01'):
            with self.assertRaises(strict_json.JsonError):
                strict_json.loads(bad)

    def test_types(self):
        self.assertIsInstance(strict_json.loads("1"), int)
        self.assertIsInstance(strict_json.loads("1.0"), float)
        self.assertEqual(strict_json.loads('"\\u00e1\\ud83d\\ude00"'), "á\U0001F600")


class SchemaLite(unittest.TestCase):
    def codes(self, instance, schema):
        return [e.code for e in schema_lite.validate(instance, schema)]

    def test_types_and_bool(self):
        self.assertEqual(self.codes(True, {"type": "integer"}), ["schema_type"])
        self.assertEqual(self.codes(1, {"type": "number"}), [])
        self.assertEqual(self.codes(True, {"const": 1}), ["schema_const"])
        self.assertEqual(self.codes(1, {"enum": [True, 2]}), ["schema_enum"])

    def test_object_and_array(self):
        schema = {"type": "object", "required": ["a"], "additionalProperties": False,
                  "properties": {"a": {"type": "array", "minItems": 2, "items": {"minimum": 0}}}}
        errs = schema_lite.validate({"a": [-1], "b": 1}, schema)
        self.assertEqual(sorted(e.code for e in errs), ["schema_additional_property", "schema_min_items", "schema_minimum"])
        self.assertIn("/a/0", [e.pointer for e in errs])

    def test_one_of_discriminator_and_ref(self):
        schema = {"$defs": {
            "box": {"type": "object", "properties": {"op": {"const": "box"}, "size": {"type": "number"}}, "required": ["size"]},
            "cyl": {"type": "object", "properties": {"op": {"const": "cyl"}, "r": {"type": "number"}}, "required": ["r"]}},
            "oneOf": [{"$ref": "#/$defs/box"}, {"$ref": "#/$defs/cyl"}]}
        self.assertEqual(self.codes({"op": "cyl", "r": 1}, schema), [])
        self.assertEqual(self.codes({"op": "cyl"}, schema), ["schema_required"])
        self.assertEqual(self.codes({"op": "x"}, schema), ["schema_one_of"])

    def test_shipped_schemas_use_supported_keywords(self):
        base = os.path.join(os.path.dirname(config.SCHEMA_PATH))
        for name in os.listdir(base):
            with open(os.path.join(base, name), encoding="utf-8") as f:
                self.assertEqual(schema_lite.unsupported_keywords(json.load(f)), [], name)


class Colors(unittest.TestCase):
    def test_roundtrip(self):
        self.assertEqual(colors.srgb_to_hex(colors.hex_to_srgb("#2a9d8f")), "#2A9D8F")
        lin = colors.srgb_to_linear((0.5, 0.5, 0.5))
        self.assertAlmostEqual(colors.linear_to_srgb(lin)[0], 0.5, places=6)
        self.assertFalse(colors.is_hex("#12345"))


class Config(unittest.TestCase):
    def load(self, data):
        text = data if isinstance(data, str) else json.dumps(data)
        return config.load_text(text, "test.json")

    def test_defaults_valid_and_example_matches(self):
        self.assertEqual(schema_lite.validate(config.DEFAULT_CONFIG, config.load_schema()), [])
        example = os.path.join(os.path.dirname(os.path.dirname(config.SCHEMA_PATH)), "team_config.example.json")
        with open(example, encoding="utf-8") as f:
            self.assertEqual(json.load(f), config.DEFAULT_CONFIG)

    def test_partial_file_fills_missing_keys(self):
        r = self.load({"schema_version": 1, "max_materials": 2})
        self.assertEqual(r.source, "file")
        self.assertEqual(r.config["max_materials"], 2)
        self.assertEqual(r.config["palette"], config.DEFAULT_CONFIG["palette"])
        self.assertIn("config_keys_defaulted", [d.code for d in r.diagnostics])

    def test_invalid_files_fall_back_whole(self):
        cases = ['{"schema_version": 1,', {"schema_version": 1, "max_materials": "2"},
                 {"schema_version": 1, "root_name_pattern": "("}, {"schema_version": 1, "palette": ["red"]},
                 {"schema_version": 1, "default_budget_group": "huge"}, {"schema_version": 1, "unknown": 1}]
        for case in cases:
            r = self.load(case)
            self.assertEqual(r.source, "defaults", case)
            self.assertTrue(any(d.level == "ERROR" for d in r.diagnostics), case)

    def test_missing_and_unset(self):
        self.assertEqual(config.load("").diagnostics[0].code, "config_not_set")
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(config.load(os.path.join(tmp, "nope.json")).diagnostics[0].code, "config_missing")

    def test_budget_group_fallback(self):
        cfg = config.defaults()
        self.assertEqual(config.budget_group(cfg, "large")[0], "large")
        self.assertEqual(config.budget_group(cfg, "zzz")[0], "small")


if __name__ == "__main__":
    unittest.main()
