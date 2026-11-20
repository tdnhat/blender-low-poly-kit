import copy
import json
import os
import unittest

from lowpoly_kit.core import config, vecmath as vm
from lowpoly_kit.core.buildplan import attach, geometry, prompt, reconcile, validate
from lowpoly_kit.core.checks import topology

CFG = config.defaults()
FISH = {
    "schema_version": 1, "asset_name": "PR_Fish", "units": "m",
    "parts": [
        {"id": "body", "op": "extrude_profile", "plane": "YZ", "caps": "both",
         "profile": [[-0.34, 0.14], [-0.24, 0.18], [-0.06, 0.225], [0.29, 0.162], [0.29, 0.118], [0.1, 0.07],
                     [-0.08, 0.05], [-0.27, 0.09]],
         "thickness_profile": [[-0.34, 0.04], [-0.1, 0.16], [0.29, 0.03]]},
        {"id": "eye", "op": "add_primitive", "shape": "cylinder", "segments": 8, "radius": 0.012, "height": 0.008,
         "mirror": "X",
         "attachment": {"parent_id": "body", "rule": "offset", "position": [0.06, -0.243, 0.16], "rotation": [0, 90, 0]}},
    ],
}


def clean(tc, geom, label):
    md = topology.MeshData(geom.verts, sorted({topology.edge_key(a, b) for f in geom.faces for a, b in topology.face_edges(f)}),
                           geom.faces, 1)
    tc.assertEqual({k: v for k, v in topology.analyse(md, 1e-5).items() if v}, {}, label)
    tc.assertGreater(topology.signed_volume(md, range(len(md.faces))), 0, label)


class Thickness(unittest.TestCase):
    def test_tapered_body(self):
        plan, errors = validate.validate(copy.deepcopy(FISH))
        self.assertEqual(errors, [])
        body = attach.resolve(plan)[0]
        clean(self, body.geom, "tapered body")
        by_y = {}
        for x, y, z in body.geom.verts:
            by_y.setdefault(round(y, 3), set()).add(round(abs(x), 4))
        self.assertEqual(by_y[-0.34], {0.02})          # thin nose
        self.assertEqual(by_y[0.29], {0.015})          # thin tail
        widest = max(abs(v[0]) for v in body.geom.verts)
        self.assertTrue(0.07 < widest <= 0.08)
        self.assertAlmostEqual(geometry.thickness_at([[0, 0.1], [1, 0.3]], 0.5), 0.2)
        self.assertAlmostEqual(geometry.thickness_at([[0, 0.1], [1, 0.3]], 5), 0.3)

    def test_depth_xor_thickness(self):
        p = copy.deepcopy(FISH)
        p["parts"][0]["depth"] = 0.16
        self.assertIn("plan_depth_or_thickness", [e.code for e in validate.validate(p)[1]])
        p = copy.deepcopy(FISH)
        del p["parts"][0]["thickness_profile"]
        self.assertIn("plan_depth_or_thickness", [e.code for e in validate.validate(p)[1]])
        p = copy.deepcopy(FISH)
        p["parts"][0]["thickness_profile"] = [[0, 0.1], [0, 0.2]]
        self.assertIn("plan_thickness_not_increasing", [e.code for e in validate.validate(p)[1]])


class Mirror(unittest.TestCase):
    def test_mirrored_eye(self):
        plan, _ = validate.validate(copy.deepcopy(FISH))
        res = {r.id: r for r in attach.resolve(plan)}
        self.assertIn("eye_mirror", res)
        right, left = res["eye"], res["eye_mirror"]
        self.assertGreater(vm.det3(left.matrix_root), 0)
        clean(self, left.geom, "mirrored eye")
        rp = sorted(vm.transform_point(right.matrix_root, v) for v in right.geom.verts)
        lp = sorted((-x, y, z) for x, y, z in (vm.transform_point(left.matrix_root, v) for v in left.geom.verts))
        for a, b in zip(rp, lp):
            self.assertTrue(vm.close(a, b))
        # The right eye sticks out of +X, the mirrored one out of -X.
        left_world = [vm.transform_point(left.matrix_root, v) for v in left.geom.verts]
        self.assertGreater(min(p[0] for p in rp), 0.059)
        self.assertLess(max(p[0] for p in left_world), -0.059)

    def test_validation_and_reconcile(self):
        p = copy.deepcopy(FISH)
        p["parts"].append({"id": "eye_mirror", "op": "add_primitive", "shape": "box", "size": [1, 1, 1],
                           "attachment": {"parent_id": "body", "rule": "offset", "position": [0, 0, 0], "rotation": [0, 0, 0]}})
        self.assertIn("plan_mirror_id_taken", [e.code for e in validate.validate(p)[1]])
        p = copy.deepcopy(FISH)
        p["parts"].append({"id": "pupil", "op": "add_primitive", "shape": "box", "size": [0.01, 0.01, 0.01],
                           "attachment": {"parent_id": "eye_mirror", "rule": "offset", "position": [0, 0, 0], "rotation": [0, 0, 0]}})
        self.assertIn("plan_parent_is_mirror", [e.code for e in validate.validate(p)[1]])
        r = reconcile.reconcile(json.dumps(FISH), "paste", "PR_Fish", [], {})
        self.assertEqual(r.errors, [])
        self.assertEqual(sorted(a.part_id for a in r.actions if a.kind == "CREATE"), ["body", "eye", "eye_mirror"])


class PromptText(unittest.TestCase):
    def test_prompt_mentions_new_rules(self):
        text = prompt.build_prompt("PR_Tuna", validate.schema_text(), [], [("FRONT", False)])
        for needle in ("−Y", "thickness_profile", '"mirror": "X"'):
            self.assertIn(needle, text)


if __name__ == "__main__":
    unittest.main()
