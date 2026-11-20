import copy
import json
import os
import unittest

from lowpoly_kit.core import vecmath as vm
from lowpoly_kit.core.buildplan import attach, contact, geometry, validate
from lowpoly_kit.core.checks import topology

FIX = os.path.join(os.path.dirname(os.path.dirname(__file__)), "fixtures", "plans")


def load():
    with open(os.path.join(FIX, "boat_min.json"), encoding="utf-8") as f:
        return json.load(f)


def analyse(geom):
    md = topology.MeshData(geom.verts, sorted({topology.edge_key(a, b) for f in geom.faces for a, b in topology.face_edges(f)}),
                           geom.faces, 1)
    return md, {k: v for k, v in topology.analyse(md, 1e-5).items() if v}


class Hull(unittest.TestCase):
    def setUp(self):
        plan, errors = validate.validate(load())
        self.assertEqual(errors, [])
        self.res = {r.id: r for r in attach.resolve(plan)}

    def test_hull_closed_outward_and_shaped(self):
        g = self.res["hull"].geom
        md, issues = analyse(g)
        self.assertEqual(issues, {})
        self.assertGreater(topology.signed_volume(md, range(len(md.faces))), 0)
        at = [v for v in g.verts if abs(v[1] - 3.0) < 1e-9]
        top = max(v[2] for v in at)
        deck = [v for v in at if abs(v[2] - top) < 1e-9]
        bottom = [v for v in at if abs(v[2]) < 1e-9]
        self.assertAlmostEqual(max(abs(v[0]) for v in deck), 2.8)          # deck full half-beam
        self.assertAlmostEqual(max(abs(v[0]) for v in bottom), 2.8 * 0.35)  # narrow flat bottom

    def test_v_keel(self):
        part = dict(load()["parts"][0], bottom_ratio=0)
        md, issues = analyse(geometry.build(part))
        self.assertEqual(issues, {})

    def test_deck_items_sit_on_deck(self):
        hull = self.res["hull"].geom
        for name, s in (("cabin", 0.0), ("crate", 1.5)):
            origin = vm.get_translation(self.res[name].matrix_root)
            hit = geometry.ray_hit(hull, (s, origin[1], 1.5), (0.0, 0.0, 1.0))
            self.assertAlmostEqual(origin[2], 1.5 + hit[0], places=9, msg=name)
            self.assertAlmostEqual(origin[0], s, msg=name)
            self.assertTrue(vm.close(vm.column(self.res[name].matrix_root, 2), (0, 0, 1), tol=0.05), name)
        self.assertEqual(contact.floating_parts(list(self.res.values())), [])

    def test_validation(self):
        p = load()
        p["parts"][2]["attachment"]["s"] = 3.5
        self.assertIn("plan_surface_lateral_outside", [e.code for e in validate.validate(p)[1]])
        p = load()
        p["parts"][0]["section"] = "box"
        self.assertIn("plan_hull_params", [e.code for e in validate.validate(p)[1]])


if __name__ == "__main__":
    unittest.main()
