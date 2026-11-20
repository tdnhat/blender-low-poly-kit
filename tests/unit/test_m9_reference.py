import unittest

from lowpoly_kit.core import reference as ref, vecmath as vm


class Views(unittest.TestCase):
    def test_rotations_face_viewer_and_screen_right(self):
        for name, v in ref.VIEWS.items():
            m = vm.euler_xyz(v.rotation)
            self.assertTrue(vm.close(vm.transform_dir(m, (0, 0, 1)), v.normal), name)
            self.assertTrue(vm.close(vm.transform_dir(m, (1, 0, 0)), v.image_x), name)
            self.assertTrue(vm.close(vm.transform_dir(m, (0, 1, 0)), v.image_y), name)
        self.assertEqual(ref.VIEWS["RIGHT"].image_x, tuple(-c for c in ref.VIEWS["LEFT"].image_x))

    def test_alignment(self):
        self.assertTrue(ref.aligned((0, 1, 0), "FRONT"))   # front view looks along +Y
        self.assertFalse(ref.aligned((1, 0, 0), "FRONT"))
        self.assertTrue(ref.aligned((0, 0, -1), "TOP"))


class Geometry(unittest.TestCase):
    def test_uv_local_roundtrip_non_square(self):
        for w, h in ((800, 600), (600, 900)):
            g = ref.ImageGeom(w, h, 2.0, (-0.3, -0.1))
            uv = (0.25, 0.8)
            back = ref.local_to_uv(g, ref.uv_to_local(g, uv))
            self.assertTrue(vm.close(back, uv))

    def test_calibration_ignores_padding(self):
        # 1000x500 image; the 0.9 m tall prop spans v 0.2..0.8 (300 px), padding elsewhere.
        cal = ref.Calibration((0.5, 0.2), (0.5, 0.8), "v", 0.9)
        g, mpp = ref.calibrate(1000, 500, cal, (0.5, 0.2))
        self.assertAlmostEqual(mpp, 0.003)
        self.assertAlmostEqual(g.display_size, 3.0)
        self.assertTrue(vm.close(ref.uv_to_local(g, (0.5, 0.2)), (0, 0)))
        self.assertTrue(vm.close(ref.uv_to_local(g, (0.5, 0.8)), (0, 0.9)))
        self.assertAlmostEqual(ref.measure(g, (0.4, 0.5), (0.6, 0.5), "h"), 0.6)

    def test_calibration_errors(self):
        with self.assertRaises(ValueError):
            ref.calibrate(100, 100, ref.Calibration((0, 0), (0, 0.5), "v", 0), (0, 0))
        with self.assertRaises(ValueError):
            ref.calibrate(100, 100, ref.Calibration((0, 0), (0.001, 0.005), "v", 1), (0, 0))

    def test_dimension_mapping(self):
        self.assertEqual(ref.dimension("RIGHT", "h"), "depth")
        self.assertEqual(ref.dimension("TOP", "v"), "depth")
        self.assertEqual(ref.expected_dimensions("FRONT"), ["height", "width"])


class Compare(unittest.TestCase):
    M = ref.Measurement

    def test_rules(self):
        ms = [self.M("FRONT", "height", 0.90, False), self.M("RIGHT", "height", 0.95, False),
              self.M("FRONT", "width", 0.62, True), self.M("TOP", "width", 0.60, False),
              self.M("RIGHT", "depth", 0.50, True), self.M("TOP", "depth", 0.53, True)]
        mism, missing = ref.compare({"FRONT", "RIGHT", "TOP"}, ms, 0.025)
        # Two calibration pairs are never compared (height), width within tolerance, depth off.
        self.assertEqual([(m[0], m[1], m[3]) for m in mism], [("depth", "RIGHT", "TOP")])
        self.assertEqual(missing, [])
        _, missing = ref.compare({"FRONT", "BACK"}, [self.M("FRONT", "height", 1, False)], 0.01)
        self.assertEqual(missing, [("BACK", "height"), ("BACK", "width"), ("FRONT", "width")])

    def test_tolerance_boundary(self):
        ms = [self.M("FRONT", "width", 0.60, True), self.M("BACK", "width", 0.61, True)]
        self.assertEqual(ref.compare({"FRONT", "BACK"}, ms, 0.0100001)[0], [])
        self.assertEqual(len(ref.compare({"FRONT", "BACK"}, ms, 0.0099)[0]), 1)


if __name__ == "__main__":
    unittest.main()
