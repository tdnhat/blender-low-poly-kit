"""box_face / offset rules, part editing, prompt views and error prompt."""

import copy
import json
import os
import unittest

from lowpoly_kit.core import config, vecmath as vm
from lowpoly_kit.core.buildplan import attach, edit, geometry, prompt, reconcile, validate

FIX = os.path.join(os.path.dirname(os.path.dirname(__file__)), "fixtures", "plans")


def load(name):
    with open(os.path.join(FIX, name + ".json"), encoding="utf-8") as f:
        return json.load(f)


def world_points(r):
    return [vm.transform_point(r.matrix_root, v) for v in r.geom.verts]


class BoxFace(unittest.TestCase):
    def test_frames_are_right_handed_and_outward(self):
        size = (0.4, 0.6, 0.2)
        for face, (normal, _x) in geometry.BOX_FACES.items():
            m = geometry.box_face_frame(size, face, 0.5, 0.5, 0.0)
            self.assertGreater(vm.det3(m), 0, face)
            self.assertTrue(vm.close(vm.column(m, 2), normal), face)
            origin = vm.get_translation(m)
            # The face centre lies on the box surface.
            self.assertTrue(vm.close(origin, (normal[0] * 0.2, normal[1] * 0.3, 0.1 + normal[2] * 0.1)), face)

    def test_chair(self):
        plan, errors = validate.validate(load("chair"))
        self.assertEqual(errors, [])
        res = {r.id: r for r in attach.resolve(plan)}
        leg = world_points(res["leg_fl"])
        self.assertAlmostEqual(max(p[2] for p in leg), 0.0)          # hangs from the seat bottom
        self.assertAlmostEqual(min(p[2] for p in leg), -0.45)
        cx = sum(p[0] for p in leg) / len(leg)
        cy = sum(p[1] for p in leg) / len(leg)
        self.assertAlmostEqual(cx, -0.18, places=6)                  # u = 0.1 along +X
        self.assertAlmostEqual(cy, 0.18, places=6)                   # v = 0.1 along -Y on the -Z face
        back = world_points(res["back"])
        self.assertAlmostEqual(min(p[2] for p in back), 0.05)        # stands on the seat top
        self.assertAlmostEqual(max(p[2] for p in back), 0.45)
        knob = res["knob"]
        self.assertTrue(vm.close(vm.get_translation(knob.matrix_root),
                                 vm.transform_point(res["back"].matrix_root, (0.1, 0, 0.3))))

    def test_box_face_requires_box_parent(self):
        p = load("chair")
        p["parts"][0] = {"id": "seat", "op": "add_primitive", "shape": "cylinder", "segments": 8, "radius": 0.2, "height": 0.05}
        self.assertIn("plan_rule_parent_type", [e.code for e in validate.validate(p)[1]])

    def test_reconcile_chair(self):
        r = reconcile.reconcile(json.dumps(load("chair")), "paste", "PR_Chair", [], {})
        self.assertEqual(r.errors, [])
        self.assertEqual(sum(1 for a in r.actions if a.kind == "CREATE"), 5)


class EditPart(unittest.TestCase):
    def test_fields_and_scales(self):
        barrel = load("barrel")
        fields, att, scales = edit.editable_fields(barrel["parts"][1])
        self.assertEqual((fields, att), (["segments", "height"], ["height", "radial_offset"]))
        out = edit.edit_part(barrel, "body", {"radius_scale": 2.0, "segments": 12, "size": [1, 1, 1]})
        self.assertEqual(out["parts"][0]["segments"], 12)
        self.assertNotIn("size", out["parts"][0])
        self.assertAlmostEqual(out["parts"][0]["profile_z_radius"][1][1], 0.62)
        self.assertAlmostEqual(barrel["parts"][0]["profile_z_radius"][1][1], 0.31)  # input untouched

    def test_attachment_edit_and_rebuild(self):
        chair = load("chair")
        out = edit.edit_part(chair, "leg_fl", {"att.u": 0.2, "att.face": "-Z", "height": 0.5})
        self.assertEqual(out["parts"][1]["attachment"]["u"], 0.2)
        self.assertEqual(validate.validate(out)[1], [])
        t = edit.edit_part(load("terminal"), "body", {"profile_scale": [2.0, 1.0]})
        self.assertEqual(t["parts"][0]["profile"][0], [-0.4, 0.0])

    def test_baked_refused(self):
        plan, _ = reconcile.bake_part(load("barrel"), "body")
        with self.assertRaises(ValueError):
            edit.edit_part(plan, "body", {"segments": 4})


class Prompts(unittest.TestCase):
    def test_views_listed(self):
        text = prompt.build_prompt("PR_Chair", validate.schema_text(), [], [("TOP", True), ("FRONT", True), ("RIGHT", False)])
        self.assertIn("- FRONT\n- RIGHT (chưa căn scale", text)
        self.assertIn("box_face", text)

    def test_error_prompt(self):
        p = copy.deepcopy(load("barrel"))
        p["parts"][1]["segments"] = 12
        draft = json.dumps(p, indent=2)
        _plan, errors = validate.validate_text(draft)
        from lowpoly_kit.core import messages
        rows = [(messages.text(e.code, e.params), e.pointer, e.line, e.col) for e in errors]
        text = prompt.build_error_prompt(rows, draft)
        self.assertIn("/parts/1/segments", text)
        self.assertIn("upper_band", text)
        self.assertIn("```json", text)


if __name__ == "__main__":
    unittest.main()
