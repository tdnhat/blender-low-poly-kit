import copy
import json
import os
import unittest

from lowpoly_kit.core import vecmath as vm
from lowpoly_kit.core.buildplan import attach, geometry, reconcile, validate

FIX = os.path.join(os.path.dirname(os.path.dirname(__file__)), "fixtures", "plans")


def load():
    with open(os.path.join(FIX, "tuna.json"), encoding="utf-8") as f:
        return json.load(f)


class BodySurface(unittest.TestCase):
    def setUp(self):
        self.plan = load()
        plan, errors = validate.validate(copy.deepcopy(self.plan), mode="paste")
        self.assertEqual(errors, [])
        self.res = {r.id: r for r in attach.resolve(plan)}

    def surface_x(self, y, z, sign=1):
        body = self.res["body"].geom
        hit = geometry.ray_hit(body, (0.0, y, z), (float(sign), 0.0, 0.0))
        return sign * hit[0]

    def test_eye_touches_body(self):
        eye = self.res["eye"]
        origin = vm.get_translation(eye.matrix_root)
        self.assertAlmostEqual(origin[0], self.surface_x(-0.243, 0.16), places=9)
        self.assertAlmostEqual(origin[1], -0.243)
        self.assertAlmostEqual(origin[2], 0.16)
        normal = vm.column(eye.matrix_root, 2)
        self.assertGreater(normal[0], 0.7)                    # faces outward (+X), tilted by the hexagon
        self.assertGreater(vm.det3(eye.matrix_root), 0)

    def test_mirrored_eye_touches_other_side(self):
        left = self.res["eye_mirror"]
        origin = vm.get_translation(left.matrix_root)
        self.assertAlmostEqual(origin[0], self.surface_x(-0.243, 0.16, sign=-1), places=9)
        self.assertGreater(vm.det3(left.matrix_root), 0)

    def test_pectoral_on_surface_and_sweeps_back(self):
        fin = self.res["pectoral_fin"]
        origin = vm.get_translation(fin.matrix_root)
        self.assertAlmostEqual(origin[0], self.surface_x(-0.17, 0.12), places=9)
        x_axis = vm.column(fin.matrix_root, 0)
        self.assertGreater(x_axis[1], 0.5)                    # length runs toward the tail (+Y)

    def test_errors(self):
        p = copy.deepcopy(self.plan)
        eye = [q for q in p["parts"] if q["id"] == "eye"][0]
        eye["attachment"]["b"] = 0.5
        self.assertIn("plan_surface_point_outside", [e.code for e in validate.validate(p)[1]])
        eye["attachment"]["b"] = 0.16
        eye["attachment"]["parent_id"] = "pectoral_fin"
        self.assertIn("plan_rule_parent_type", [e.code for e in validate.validate(p)[1]])

    def test_baked_body_still_supports_surface_parts(self):
        baked, snap = reconcile.bake_part(self.plan, "body")
        state = reconcile.ObjState("Body", "body", "u", snap)
        r = reconcile.reconcile(json.dumps(self.plan), "paste", "PR_Tuna", [state], {"body": "u"})
        self.assertEqual(r.errors, [])
        eye = {x.id: x for x in r.resolved}["eye"]
        self.assertTrue(vm.matrices_close(eye.matrix_root, self.res["eye"].matrix_root))


if __name__ == "__main__":
    unittest.main()
