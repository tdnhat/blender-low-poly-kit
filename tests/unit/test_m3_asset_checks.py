import unittest

from lowpoly_kit.core import config, messages, scope as sc, vecmath as vm
from lowpoly_kit.core.checks import asset, registry
from lowpoly_kit.core.material_spec import MaterialSummary, built_summary
from tests.unit.fixtures import node

CFG = config.defaults()
GOOD_MAT = built_summary("M_VertexColor", "Color")
GOOD_ATTR = [asset.ColorAttr("Color", "CORNER", "BYTE_COLOR")]


def mesh(key, matrix=None, scale=(1, 1, 1), basis=None, **kw):
    m = vm.as_matrix(matrix or vm.identity())
    defaults = dict(key=key, name=key, data_name=key, basis_matrix=basis or vm.scaling(scale), local_scale=scale,
                    matrix_world=m, modifiers=[], tris=12, color_attributes=GOOD_ATTR, materials=[GOOD_MAT],
                    smooth_faces=[], colors={(1.0, 0.0, 0.0), (0.0, 0.0, 1.0)})
    defaults.update(kw)
    return asset.MeshInfo(**defaults)


def run(meshes, nodes=None, root="PR_Barrel", bounds=((-0.3, -0.3, 0.0), (0.3, 0.3, 0.9)), unit=1.0, group="small", cfg=CFG):
    nodes = nodes or sc.index([node("PR_Barrel", "EMPTY")] + [node(m.key, "MESH", "PR_Barrel", m.matrix_world) for m in meshes])
    rr = sc.find_root(nodes, root, cfg["root_name_pattern"])
    scope = sc.collect(nodes, rr.root) if rr.root else None
    data = asset.AssetData(rr, root, scope, nodes, meshes, group, unit, bounds)
    return asset.run(data, cfg)


def ids(results):
    return [r.check_id for r in results]


class AssetChecks(unittest.TestCase):
    def test_clean_asset(self):
        self.assertEqual(run([mesh("Body")]), [])

    def test_root_problems(self):
        nodes = sc.index([node("Body", "MESH"), node("Band", "MESH", "Body")])
        res = run([], nodes=nodes, root="Band")
        self.assertEqual(ids(res), ["root_not_empty"])
        self.assertEqual(res[0].fix, "reroot")
        nodes = sc.index([node("PR_Barrel", "EMPTY", matrix=vm.rotation_z(15)), node("Body", "MESH", "PR_Barrel")])
        self.assertIn("root_transform", ids(run([mesh("Body")], nodes=nodes)))

    def test_negative_scale_fixture(self):
        a = mesh("A", matrix=vm.scaling((-1, 1, 1)), scale=(-1, 1, 1))
        b = mesh("B", matrix=vm.scaling((-1, -1, 1)), scale=(-1, -1, 1))
        res = [r for r in run([a, b]) if r.check_id == "mesh_negative_scale"]
        by_key = {r.object_key: r.params for r in res}
        self.assertEqual(by_key["A"]["axes_list"], ["X"])
        self.assertEqual(by_key["B"]["axes_list"], ["X", "Y"])
        self.assertEqual(by_key["A"]["sign"], "âm")
        self.assertEqual(by_key["B"]["sign"], "dương")

    def test_budget_and_pivot_and_scale(self):
        res = ids(run([mesh("Body", tris=3001)], bounds=((-0.3, -0.3, 0.1), (0.3, 0.3, 0.9)), unit=0.01))
        for cid in ("budget_over", "pivot_offset", "scene_scale"):
            self.assertIn(cid, res)
        self.assertIn("budget_near", ids(run([mesh("Body", tris=2800)])))

    def test_material_variants(self):
        bad_link = MaterialSummary("M_Old", True, True, "OTHER", None)
        wrong_layer = MaterialSummary("M_V", True, True, "VERTEX_COLOR", "Col")
        self.assertIn("material_not_vertex_color", ids(run([mesh("Body", materials=[bad_link])])))
        self.assertIn("material_not_vertex_color", ids(run([mesh("Body", materials=[wrong_layer])])))
        self.assertIn("material_missing", ids(run([mesh("Body", materials=[])])))
        res = ids(run([mesh("Body", materials=[GOOD_MAT, None, built_summary("M_Two", "Color")])]))
        self.assertIn("material_empty_slot", res)
        self.assertIn("material_count", res)

    def test_color_attribute(self):
        self.assertIn("color_attr_missing", ids(run([mesh("Body", color_attributes=[])])))
        point = [asset.ColorAttr("Color", "POINT", "FLOAT_COLOR")]
        self.assertIn("color_attr_wrong_format", ids(run([mesh("Body", color_attributes=point)])))

    def test_info_and_transform(self):
        res = run([mesh("Body", basis=vm.rotation_z(10), smooth_faces=[0, 1], data_name="Cube.001",
                        colors={(0.5, 0.5, 0.5)}, modifiers=["Mirror"])])
        found = {r.check_id: r for r in res}
        self.assertIn("Mirror", found["mesh_transform"].params["modifiers"])
        self.assertEqual(found["smooth_shading"].indices, (0, 1))
        for cid in ("mesh_data_name", "single_color"):
            self.assertIn(cid, found)

    def test_hidden_and_non_mesh(self):
        nodes = sc.index([node("PR_Barrel", "EMPTY"), node("Pivot", "EMPTY", "PR_Barrel"),
                          node("Door", "MESH", "Pivot", hidden=True), node("Label", "FONT", "PR_Barrel")])
        res = ids(run([mesh("Door")], nodes=nodes))
        self.assertIn("hidden_mesh", res)
        self.assertEqual(res.count("non_mesh_child"), 2)

    def test_severity_override(self):
        cfg = dict(CFG, severity_overrides={"mesh_data_name": "OFF", "pivot_offset": "ERROR"})
        res = run([mesh("Body", data_name="x")], bounds=((0, 0, 0.1), (1, 1, 1)), cfg=cfg)
        self.assertNotIn("mesh_data_name", ids(res))
        self.assertEqual([r.severity for r in res if r.check_id == "pivot_offset"], ["ERROR"])


class Messages(unittest.TestCase):
    def test_every_check_has_text(self):
        for cid in registry.CHECKS:
            self.assertIn(cid, messages.TEXTS)

    def test_format_missing_param_is_safe(self):
        self.assertIn("{name}", messages.text("ngon", {}))


if __name__ == "__main__":
    unittest.main()
