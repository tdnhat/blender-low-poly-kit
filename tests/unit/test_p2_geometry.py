import copy
import json
import math
import os
import unittest

from lowpoly_kit.core import config, vecmath as vm
from lowpoly_kit.core.buildplan import attach, geometry, geometry2d, validate
from lowpoly_kit.core.checks import topology

FIX = os.path.join(os.path.dirname(os.path.dirname(__file__)), "fixtures", "plans")
CFG = config.defaults()


def load(name):
    with open(os.path.join(FIX, name + ".json"), encoding="utf-8") as f:
        return json.load(f)


def as_meshdata(geom):
    edges = sorted({topology.edge_key(a, b) for f in geom.faces for a, b in topology.face_edges(f)})
    return topology.MeshData(geom.verts, edges, geom.faces, 1)


def assert_clean_closed(tc, geom, label):
    md = as_meshdata(geom)
    issues = {k: v for k, v in topology.analyse(md, CFG["merge_distance"]).items() if v}
    tc.assertEqual(issues, {}, label)
    tc.assertGreater(topology.signed_volume(md, range(len(md.faces))), 0, label)


class Generators(unittest.TestCase):
    def test_silhouette_equals_apothem(self):
        for n in (4, 8, 12, 16):
            g = geometry.cylinder(0.31, 1.0, n)
            xs = [v[0] for v in g.verts]
            ys = [v[1] for v in g.verts]
            self.assertAlmostEqual(max(xs), 0.31, places=9, msg=n)   # Front silhouette half-width
            self.assertAlmostEqual(max(ys), 0.31, places=9, msg=n)   # Right silhouette half-depth
            self.assertAlmostEqual(min(ys), -0.31, places=9, msg=n)

    def test_generated_meshes_are_clean_and_outward(self):
        b = load("barrel")["parts"][0]
        assert_clean_closed(self, geometry.build(b), "lathe")
        assert_clean_closed(self, geometry.cylinder(0.2, 0.1, 8), "cylinder")
        assert_clean_closed(self, geometry.box((0.4, 0.12, 0.02)), "box")
        t = load("terminal")["parts"][0]
        assert_clean_closed(self, geometry.build(t), "extrude YZ")
        for plane in ("XZ", "XY"):
            for prof in (t["profile"], list(reversed(t["profile"]))):
                assert_clean_closed(self, geometry.extrude(plane, prof, 0.5, "both"), plane)

    def test_extrude_volume_and_caps_triangulated(self):
        t = load("terminal")["parts"][0]
        g = geometry.build(t)
        md = as_meshdata(g)
        area = abs(geometry2d.signed_area(t["profile"]))
        self.assertAlmostEqual(topology.signed_volume(md, range(len(g.faces))), area * t["depth"])
        self.assertFalse(any(len(f) > 4 for f in g.faces))

    def test_lathe_pole(self):
        g = geometry.lathe([(0.0, 0.0), (0.5, 0.3), (1.0, 0.0)], 8, "both")
        self.assertEqual(len(g.verts), 10)
        assert_clean_closed(self, g, "spindle")


class SpecNumbers(unittest.TestCase):
    def test_barrel_band(self):
        res = {r.id: r for r in attach.resolve(load("barrel"))}
        band = res["upper_band"]
        self.assertAlmostEqual(band.computed["radius"], 0.297778, places=5)
        zs = [vm.transform_point(band.matrix_root, v)[2] for v in band.geom.verts]
        self.assertAlmostEqual(min(zs), 0.695)
        self.assertAlmostEqual(max(zs), 0.745)

    def test_band_follows_body_radius(self):
        plan = load("barrel")
        plan["parts"][0]["profile_z_radius"] = [[0.0, 0.30], [0.45, 0.35], [0.90, 0.30]]
        band = {r.id: r for r in attach.resolve(plan)}["upper_band"]
        self.assertGreater(band.computed["radius"], 0.32)

    def test_terminal_keyboard(self):
        res = {r.id: r for r in attach.resolve(load("terminal"))}
        kb = res["keyboard"]
        self.assertTrue(vm.close(vm.get_translation(kb.matrix_root), (0, -0.125, 0.375)))
        x, y, z = (vm.column(kb.matrix_root, j) for j in range(3))
        self.assertTrue(vm.close(x, (1, 0, 0)))
        s = math.sqrt(0.5)
        self.assertTrue(vm.close(z, (0, -s, s)))          # outward: front and up
        self.assertTrue(vm.close(y, vm.cross(z, x)))
        self.assertGreater(vm.det3(kb.matrix_root), 0)
        # 0.40 m edge along X, 0.12 m along the slope, thickness outward.
        pts = [vm.transform_point(kb.matrix_root, v) for v in kb.geom.verts]
        xs = [p[0] for p in pts]
        self.assertAlmostEqual(max(xs) - min(xs), 0.40)

    def test_chained_attachment(self):
        plan = load("terminal")
        plan["parts"].append({"id": "key", "op": "add_primitive", "shape": "box", "size": [0.02, 0.02, 0.01],
                              "attachment": {"parent_id": "keyboard", "rule": "profile_segment", "segment": 0, "t": 0.5,
                                             "normal_offset": 0, "align": "surface"}})
        # keyboard is a box, not an extrude: invalid by rule, caught by the validator.
        self.assertIn("plan_rule_parent_type", [e.code for e in validate.validate(plan)[1]])

    def test_baked_parent_uses_snapshot(self):
        plan = load("barrel")
        body = {r.id: r for r in attach.resolve(plan)}["body"]
        snap = attach.snapshot(body)
        plan2 = copy.deepcopy(plan)
        plan2["parts"][0]["profile_z_radius"] = [[0.0, 0.5], [0.45, 0.6], [0.90, 0.5]]
        plan2["parts"][0]["baked"] = True
        plan2["parts"][0]["baked_params"] = snap
        res = {r.id: r for r in attach.resolve(plan2)}
        self.assertIsNone(res["body"].geom)
        self.assertAlmostEqual(res["upper_band"].computed["radius"], 0.297778, places=5)


if __name__ == "__main__":
    unittest.main()
