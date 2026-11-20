"""Shared plain-data fixtures."""

from lowpoly_kit.core import scope as sc
from lowpoly_kit.core import vecmath as vm


def node(key, type_, parent=None, matrix=None, hidden=False):
    return sc.Node(key, key, type_, parent, vm.as_matrix(matrix or vm.identity()), hidden)


def export_fixture():
    """Spec fixture: root far from origin, hidden mesh under a transformed
    intermediate Empty, and a prop outside the root."""
    root_m = vm.translation((10, -5, 2))
    pivot_m = vm.matmul(root_m, vm.matmul(vm.translation((0.3, 0, 0.5)), vm.rotation_z(90)))
    hidden_m = vm.matmul(pivot_m, vm.translation((0.2, 0, 0)))
    nodes = [
        node("PR_Cabinet", "EMPTY", matrix=root_m),
        node("Body", "MESH", "PR_Cabinet", vm.matmul(root_m, vm.translation((0, 0, 0.4)))),
        node("HingePivot", "EMPTY", "PR_Cabinet", pivot_m),
        node("Door", "MESH", "HingePivot", hidden_m, hidden=True),
        node("PR_Other", "EMPTY", matrix=vm.translation((-3, 0, 0))),
        node("OtherMesh", "MESH", "PR_Other"),
    ]
    return sc.index(nodes)


def cube_mesh(det_sign=1, flip_face=None, open_face=None, size=1.0):
    """Unit cube with outward winding (Blender default vertex order)."""
    from lowpoly_kit.core.checks.topology import MeshData, edge_key, face_edges

    s = size / 2
    verts = [(-s, -s, -s), (-s, -s, s), (-s, s, -s), (-s, s, s), (s, -s, -s), (s, -s, s), (s, s, -s), (s, s, s)]
    faces = [(0, 1, 3, 2), (2, 3, 7, 6), (6, 7, 5, 4), (4, 5, 1, 0), (2, 6, 4, 0), (7, 3, 1, 5)]
    if flip_face is not None:
        faces[flip_face] = tuple(reversed(faces[flip_face]))
    if open_face is not None:
        faces.pop(open_face)
    edges = sorted({edge_key(a, b) for f in faces for a, b in face_edges(f)})
    return MeshData(verts, edges, faces, det_sign)
