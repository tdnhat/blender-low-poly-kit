import copy
import json
import os
import unittest

from lowpoly_kit.core.buildplan import geometry2d, validate as v

FIX = os.path.join(os.path.dirname(os.path.dirname(__file__)), "fixtures", "plans")


def load(name):
    with open(os.path.join(FIX, name + ".json"), encoding="utf-8") as f:
        return json.load(f)


def codes(plan, mode="editor"):
    return [e.code for e in v.validate(plan, mode=mode)[1]]


class SpecExamples(unittest.TestCase):
    def test_examples_valid(self):
        for name in ("barrel", "terminal"):
            with open(os.path.join(FIX, name + ".json"), encoding="utf-8") as f:
                plan, errors = v.validate_text(f.read(), mode="paste")
            self.assertEqual(errors, [], name)
            self.assertIsNotNone(plan)

    def test_topo_order(self):
        self.assertEqual(v.topo_order(load("barrel")["parts"]), ["body", "upper_band"])


class Invalid(unittest.TestCase):
    def test_json_errors(self):
        for text in ('{"a": NaN}', '{"a": 1, "a": 2}', '{"parts": [}'):
            plan, errors = v.validate_text(text)
            self.assertIsNone(plan)
            self.assertEqual(errors[0].code, "plan_json_error")

    def test_schema_errors_point_at_field(self):
        p = load("barrel")
        p["units"] = "cm"
        p["parts"][0]["segments"] = 6
        text = json.dumps(p, indent=2)
        _, errors = v.validate_text(text)
        self.assertEqual({e.code for e in errors}, {"plan_schema"})
        seg = [e for e in errors if e.pointer == "/parts/0/segments"][0]
        self.assertIn("body", seg.params["part"])
        self.assertGreater(seg.line, 1)

    def test_semantic_cases(self):
        base = load("barrel")
        cases = []
        p = copy.deepcopy(base); p["parts"][1]["id"] = "body"; cases.append((p, "plan_duplicate_id"))
        p = copy.deepcopy(base); del p["parts"][1]["attachment"]; cases.append((p, "plan_root_count"))
        p = copy.deepcopy(base); p["parts"][1]["attachment"]["parent_id"] = "lid"; cases.append((p, "plan_missing_parent"))
        p = copy.deepcopy(base); p["parts"][1]["segments"] = 12; cases.append((p, "plan_segments_mismatch"))
        p = copy.deepcopy(base); p["parts"][1]["radius"] = 0.3; cases.append((p, "plan_forbidden_field"))
        p = copy.deepcopy(base); p["parts"][1]["attachment"]["height"] = 0.89; cases.append((p, "plan_span_outside_parent"))
        p = copy.deepcopy(base); p["parts"][0]["profile_z_radius"][1][0] = 0.0; cases.append((p, "plan_heights_not_increasing"))
        p = copy.deepcopy(base); p["parts"][1]["baked"] = True; cases.append((p, "plan_managed_field"))
        for plan, code in cases:
            self.assertIn(code, codes(plan, mode="paste"), code)

    def test_rule_types_and_segment_range(self):
        t = load("terminal")
        p = copy.deepcopy(t); p["parts"][1]["attachment"]["segment"] = 5
        self.assertIn("plan_segment_range", codes(p))
        b = load("barrel")
        # Keyboard attached with profile_segment to a lathe parent.
        mixed = copy.deepcopy(b)
        mixed["parts"].append(copy.deepcopy(t["parts"][1]))
        self.assertIn("plan_rule_parent_type", codes(mixed))
        p = copy.deepcopy(b)
        p["parts"][1] = {"id": "lid", "op": "add_primitive", "shape": "box", "size": [0.1, 0.1, 0.1],
                         "attachment": b["parts"][1]["attachment"]}
        self.assertIn("plan_rule_child_type", codes(p))

    def test_cycle(self):
        t = load("terminal")
        t["parts"].append({"id": "a", "op": "add_primitive", "shape": "box", "size": [1, 1, 1],
                           "attachment": {"parent_id": "b", "rule": "profile_segment", "segment": 0, "t": 0.5,
                                          "normal_offset": 0, "align": "surface"}})
        t["parts"].append({"id": "b", "op": "add_primitive", "shape": "box", "size": [1, 1, 1],
                           "attachment": {"parent_id": "a", "rule": "profile_segment", "segment": 0, "t": 0.5,
                                          "normal_offset": 0, "align": "surface"}})
        self.assertIn("plan_cycle", codes(t))

    def test_profiles(self):
        t = load("terminal")
        p = copy.deepcopy(t); p["parts"][0]["profile"] = [[0, 0], [2, 2], [2, 0], [0, 1]]
        self.assertIn("plan_profile_self_intersect", codes(p))
        p = copy.deepcopy(t); p["parts"][0]["profile"] = [[0, 0], [1, 0], [2, 0]]
        self.assertIn("plan_profile_degenerate", codes(p))


class Polygon(unittest.TestCase):
    def test_triangulate_keeps_winding(self):
        prof = [(-0.2, 0.0), (0.2, 0.0), (0.2, 0.45), (-0.05, 0.45), (-0.2, 0.3)]
        for pts in (prof, list(reversed(prof))):
            tris = geometry2d.triangulate(pts)
            self.assertEqual(len(tris), 3)
            area = sum(geometry2d.signed_area([pts[a], pts[b], pts[c]]) for a, b, c in tris)
            self.assertAlmostEqual(area, geometry2d.signed_area(pts))

    def test_concave(self):
        l_shape = [(0, 0), (2, 0), (2, 1), (1, 1), (1, 2), (0, 2)]
        tris = geometry2d.triangulate(l_shape)
        self.assertEqual(len(tris), 4)
        self.assertAlmostEqual(sum(geometry2d.signed_area([l_shape[i] for i in t]) for t in tris), 3.0)


if __name__ == "__main__":
    unittest.main()
