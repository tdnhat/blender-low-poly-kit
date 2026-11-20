import unittest

from lowpoly_kit.core import budget, config, scope as sc, vecmath as vm
from tests.unit.fixtures import export_fixture, node

PATTERN = config.DEFAULT_CONFIG["root_name_pattern"]


class FindRoot(unittest.TestCase):
    def test_from_child_and_root(self):
        nodes = export_fixture()
        self.assertEqual(sc.find_root(nodes, "Door", PATTERN).root, "PR_Cabinet")
        self.assertEqual(sc.find_root(nodes, "PR_Cabinet", PATTERN).root, "PR_Cabinet")

    def test_problems(self):
        nodes = sc.index([node("BarrelBody", "MESH"), node("Band", "MESH", "BarrelBody"),
                          node("badname", "EMPTY"), node("Child", "MESH", "badname")])
        r = sc.find_root(nodes, "Band", PATTERN)
        self.assertEqual((r.root, r.problem, r.candidate), (None, "root_not_empty", "BarrelBody"))
        self.assertEqual(sc.find_root(nodes, "Child", PATTERN).problem, "root_bad_name")
        self.assertEqual(sc.find_root(nodes, None, PATTERN).problem, "root_missing")

    def test_nearest_valid_root_below_organizer(self):
        nodes = sc.index([node("Props", "EMPTY"), node("PR_Barrel", "EMPTY", "Props"), node("Body", "MESH", "PR_Barrel")])
        self.assertEqual(sc.find_root(nodes, "Body", PATTERN).root, "PR_Barrel")


class ScopeAndExport(unittest.TestCase):
    def test_scope(self):
        nodes = export_fixture()
        s = sc.collect(nodes, "PR_Cabinet")
        self.assertEqual(s.meshes, ["Body", "Door"])
        self.assertEqual(s.hidden_meshes, ["Door"])
        self.assertEqual(s.non_mesh, ["HingePivot"])
        self.assertNotIn("OtherMesh", s.meshes)

    def test_export_plan_reparents_and_keeps_relative_transform(self):
        nodes = export_fixture()
        s = sc.collect(nodes, "PR_Cabinet")
        items = {i.key: i for i in sc.export_plan(nodes, s)}
        self.assertEqual(set(items), {"PR_Cabinet", "Body", "Door"})
        self.assertIsNone(items["PR_Cabinet"].export_parent)
        self.assertEqual(items["Door"].export_parent, "PR_Cabinet")
        expected = sc.matrix_relative_to_root(nodes, "PR_Cabinet", "Door")
        self.assertTrue(vm.matrices_close(items["Door"].matrix_local, expected))
        # Door pivot sits at hinge (0.3, 0, 0.5) + rotated (0.2, 0, 0) -> (0.3, 0.2, 0.5)
        self.assertTrue(vm.close(vm.get_translation(expected), (0.3, 0.2, 0.5)))

    def test_mesh_under_mesh_keeps_mesh_parent(self):
        nodes = sc.index([node("PR_A", "EMPTY"), node("Body", "MESH", "PR_A", vm.translation((0, 0, 1))),
                          node("Lid", "MESH", "Body", vm.translation((0, 0, 2)))])
        items = {i.key: i for i in sc.export_plan(nodes, sc.collect(nodes, "PR_A"))}
        self.assertEqual(items["Lid"].export_parent, "Body")
        self.assertTrue(vm.close(vm.get_translation(items["Lid"].matrix_local), (0, 0, 1)))


class Budget(unittest.TestCase):
    def test_levels(self):
        cfg = config.defaults()
        for total, level in ((2699, "OK"), (2700, "WARNING"), (3000, "WARNING"), (3001, "ERROR")):
            self.assertEqual(budget.evaluate({"a": total}, "small", cfg).level, level, total)
        st = budget.evaluate({"a": 100, "b": 300}, "nope", cfg)
        self.assertEqual(st.group, "small")
        self.assertEqual(st.heaviest[0], ("b", 300))
        self.assertEqual(st.remaining, 2600)


if __name__ == "__main__":
    unittest.main()
