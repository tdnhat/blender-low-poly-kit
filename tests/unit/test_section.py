import copy
import unittest

from lowpoly_kit.core import vecmath as vm
from lowpoly_kit.core.buildplan import attach, geometry, geometry2d, validate
from lowpoly_kit.core.checks import topology
from tests.unit.test_thickness_mirror import FISH


def analyse(geom):
    md = topology.MeshData(geom.verts, sorted({topology.edge_key(a, b) for f in geom.faces for a, b in topology.face_edges(f)}),
                           geom.faces, 1)
    return md, {k: v for k, v in topology.analyse(md, 1e-5).items() if v}


class Section(unittest.TestCase):
    def body(self, section, plane="YZ"):
        part = copy.deepcopy(FISH["parts"][0])
        part["section"] = section
        part["plane"] = plane
        return geometry.build(part)

    def test_closed_outward_for_all_sections_and_planes(self):
        for section in ("diamond", "hexagon"):
            for plane in ("YZ", "XZ", "XY"):
                g = self.body(section, plane)
                md, issues = analyse(g)
                self.assertEqual(issues, {}, (section, plane))
                self.assertGreater(topology.signed_volume(md, range(len(md.faces))), 0, (section, plane))

    def test_silhouettes(self):
        g = self.body("diamond")
        prof = FISH["parts"][0]["profile"]
        # Side view (YZ) keeps the profile's height range; nose is a single tip vertex.
        self.assertAlmostEqual(max(v[2] for v in g.verts), max(p[1] for p in prof))
        self.assertAlmostEqual(min(v[2] for v in g.verts), min(p[1] for p in prof))
        nose = [v for v in g.verts if abs(v[1] + 0.34) < 1e-9]
        self.assertEqual(len(nose), 1)
        # Top view: widest at mid-height equals half the thickness profile.
        at = [v for v in g.verts if abs(v[1] + 0.06) < 1e-9]
        half = geometry.thickness_at(FISH["parts"][0]["thickness_profile"], -0.06) / 2
        self.assertAlmostEqual(max(v[0] for v in at), half)
        # Diamond: top and bottom ridge on x = 0.
        self.assertEqual(sorted(round(abs(v[0]), 6) for v in at), [0.0, 0.0, round(half, 6), round(half, 6)])
        hexa = [v for v in self.body("hexagon").verts if abs(v[1] + 0.06) < 1e-9]
        self.assertEqual(len(hexa), 6)

    def test_tris_stay_low(self):
        g = self.body("hexagon")
        self.assertLess(sum(len(f) - 2 for f in g.faces), 120)

    def test_validation(self):
        p = copy.deepcopy(FISH)
        p["parts"][0]["section"] = "diamond"
        p["parts"][0]["profile"] = [[0, 0], [1, 0], [1, 1], [0.5, 0.3], [0, 1]]   # notch: not monotone in y? (it is)
        self.assertEqual(validate.validate(p)[1], [])
        p["parts"][0]["profile"] = [[0, 0], [1, 0], [0.6, 0.5], [1, 1], [0, 1]]   # C shape
        self.assertIn("plan_section_not_monotone", [e.code for e in validate.validate(p)[1]])
        self.assertIsNone(geometry2d.monotone_chains([(0, 0), (1, 0), (0.6, 0.5), (1, 1), (0, 1)]))
        q = copy.deepcopy(FISH)
        q["parts"][0]["section"] = "hexagon"
        q["parts"].append({"id": "fin", "op": "add_primitive", "shape": "box", "size": [0.01, 0.05, 0.05],
                           "attachment": {"parent_id": "body", "rule": "profile_segment", "segment": 1, "t": 0.5,
                                          "normal_offset": 0, "align": "surface"}})
        self.assertIn("plan_segment_on_section", [e.code for e in validate.validate(q)[1]])

    def test_box_default_unchanged(self):
        a = geometry.build(FISH["parts"][0])
        part = dict(FISH["parts"][0], section="box")
        self.assertEqual(geometry.build(part), a)


if __name__ == "__main__":
    unittest.main()
