import time
import unittest

from lowpoly_kit.core import config
from lowpoly_kit.core.checks import topology as topo
from tests.unit.fixtures import cube_mesh

CFG = config.defaults()


def found(md):
    return {k: v for k, v in topo.analyse(md, CFG["merge_distance"]).items() if v}


class Topology(unittest.TestCase):
    def test_clean_cube(self):
        md = cube_mesh()
        self.assertGreater(topo.signed_volume(md, range(6)), 0)
        self.assertEqual(found(md), {})

    def test_open_box(self):
        f = found(cube_mesh(open_face=0))
        self.assertEqual(set(f), {"open_boundary"})
        self.assertEqual(len(f["open_boundary"]), 4)

    def test_flipped_face(self):
        f = found(cube_mesh(flip_face=2))
        self.assertEqual(set(f), {"inconsistent_winding"})
        self.assertEqual(len(f["inconsistent_winding"]), 4)

    def test_inside_out_and_negative_determinant(self):
        md = cube_mesh()
        inverted = topo.MeshData(md.verts, md.edges, [tuple(reversed(x)) for x in md.faces], 1)
        self.assertEqual(found(inverted).get("inward_normals"), list(range(6)))
        mirrored = topo.MeshData(md.verts, md.edges, md.faces, -1)
        self.assertEqual(found(mirrored).get("inward_normals"), list(range(6)))
        # Inverted winding under a negative determinant looks correct after export.
        both = topo.MeshData(inverted.verts, inverted.edges, inverted.faces, -1)
        self.assertEqual(found(both), {})

    def test_three_face_edge_and_loose_and_ngon(self):
        md = cube_mesh()
        verts = md.verts + [(0, 0, 2), (5, 5, 5), (6, 5, 5), (7, 5, 5)]
        faces = md.faces + [(1, 3, 8)]  # fin sharing edge 1-3 -> 3 faces
        edges = md.edges + [(1, 8), (3, 8), (9, 10)]
        f = found(topo.MeshData(verts, edges, faces, 1))
        self.assertEqual(len(f["nonmanifold_edge"]), 1)
        self.assertEqual(f["loose_vert"], [11])
        self.assertEqual(len(f["loose_edge"]), 1)
        ngon = topo.MeshData([(0, 0, 0), (1, 0, 0), (2, 1, 0), (1, 2, 0), (0, 1, 0)],
                             [(0, 1), (1, 2), (2, 3), (3, 4), (0, 4)], [(0, 1, 2, 3, 4)], 1)
        self.assertEqual(found(ngon)["ngon"], [0])

    def test_near_duplicates_threshold(self):
        d = CFG["merge_distance"]
        base = [(0, 0, 0), (1, 0, 0), (0, 1, 0)]
        near = topo.MeshData(base + [(d * 0.9, 0, 0)], [], [], 1)
        far = topo.MeshData(base + [(d * 1.1, 0, 0)], [], [], 1)
        self.assertEqual(topo.near_duplicates(near, d), [0, 3])
        self.assertEqual(topo.near_duplicates(far, d), [])

    def test_degenerate_sliver(self):
        md = topo.MeshData([(0, 0, 0), (1, 0, 0), (2, 0, 0)], [(0, 1), (1, 2), (0, 2)], [(0, 1, 2)], 1)
        self.assertEqual(topo.degenerate_faces(md), [0])

    def test_run_results(self):
        res = topo.run("Box", "Box", cube_mesh(open_face=0), CFG)
        self.assertEqual([r.check_id for r in res], ["open_boundary"])
        self.assertEqual(res[0].select, "EDGE")

    def test_performance_20k_tris(self):
        n = 70
        verts = [(x, y, 0.0) for y in range(n + 1) for x in range(n + 1)]
        faces = []
        for y in range(n):
            for x in range(n):
                a = y * (n + 1) + x
                faces += [(a, a + 1, a + n + 2), (a, a + n + 2, a + n + 1)]
        edges = sorted({topo.edge_key(a, b) for f in faces for a, b in topo.face_edges(f)})
        start = time.time()
        topo.analyse(topo.MeshData(verts, edges, faces, 1), CFG["merge_distance"])
        self.assertLess(time.time() - start, 5.0)


if __name__ == "__main__":
    unittest.main()
