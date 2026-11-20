import unittest

from lowpoly_kit.core import config, fixes, vecmath as vm


class Fixes(unittest.TestCase):
    def test_reset_root_keeps_child_world(self):
        root = vm.matmul(vm.translation((2, 0, 1)), vm.matmul(vm.rotation_z(30), vm.scaling((2, 2, 2))))
        child_world = vm.matmul(root, vm.translation((0.5, 0, 0)))
        new_root = fixes.reset_root_world(root)
        self.assertFalse(vm.has_rotation(new_root))
        self.assertTrue(vm.close(vm.get_translation(new_root), (2, 0, 1)))
        local = fixes.rebased_local(child_world, new_root)
        self.assertTrue(vm.matrices_close(vm.matmul(new_root, local), child_world))

    def test_move_root_to_pivot(self):
        root = vm.translation((1, 1, 1))
        new = fixes.move_root_world(root, (0.1, -0.2, -0.3))
        self.assertTrue(vm.close(vm.get_translation(new), (1.1, 0.8, 0.7)))
        self.assertEqual(fixes.bottom_center((-1, -2, 0.5), (1, 4, 3)), (0.0, 1.0, 0.5))

    def test_suggest_root_name(self):
        pat = config.DEFAULT_CONFIG["root_name_pattern"]
        self.assertEqual(fixes.suggest_root_name("Barrel", pat, "PR_X"), "PR_Barrel")
        self.assertEqual(fixes.suggest_root_name("barrel body", pat, "PR_X"), "PR_Barrel_body")
        self.assertEqual(fixes.suggest_root_name("123 body", pat, "PR_X"), "PR_X")
        self.assertEqual(fixes.suggest_root_name("PR_Crate", pat, "PR_X"), "PR_Crate")


if __name__ == "__main__":
    unittest.main()
