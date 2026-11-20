import unittest

from lowpoly_kit.core import coloring, config, material_spec


class Coloring(unittest.TestCase):
    def test_palette(self):
        pal = coloring.palette(config.defaults())
        self.assertEqual(len(pal), 12)
        self.assertEqual(pal[0][0], "#2B2D42")

    def test_face_corners_and_fill(self):
        starts, totals = [0, 4, 7], [4, 3, 4]
        corners = coloring.face_corners(starts, totals, [1, 2])
        self.assertEqual(corners, [4, 5, 6, 7, 8, 9, 10])
        base = [(0, 0, 0, 1)] * 11
        out = coloring.fill_corners(base, corners, (1, 0, 0))
        self.assertEqual(out[3], (0, 0, 0, 1))
        self.assertEqual(out[4], (1, 0, 0, 1.0))

    def test_from_materials_and_points(self):
        out = coloring.corners_from_face_materials([0, 3], [3, 3], [1, 5], [None, (0, 1, 0)], (0.5, 0.5, 0.5))
        self.assertEqual(out[0], (0, 1, 0, 1.0))
        self.assertEqual(out[3], (0.5, 0.5, 0.5, 1.0))
        self.assertEqual(coloring.corners_from_point_colors([2, 0], [(1, 1, 1, 1), (0, 0, 0, 1), (1, 0, 0, 1)]),
                         [(1, 0, 0, 1), (1, 1, 1, 1)])

    def test_unique_and_flatten(self):
        self.assertEqual(len(coloring.unique_colors([(0.5, 0.5, 0.5, 1)] * 5)), 1)
        flat = coloring.flatten([(1, 0, 0, 1), (0, 1, 0)])
        self.assertEqual(coloring.unflatten(flat), [(1, 0, 0, 1), (0, 1, 0, 1.0)])

    def test_built_material_passes_rule(self):
        self.assertTrue(material_spec.is_valid(material_spec.built_summary("M_VertexColor", "Color"), "Color"))
        links = {(a, b, c, d) for a, b, c, d in material_spec.BUILD_LINKS}
        self.assertIn(("Color Attribute", "Color", "Principled BSDF", "Base Color"), links)


if __name__ == "__main__":
    unittest.main()
