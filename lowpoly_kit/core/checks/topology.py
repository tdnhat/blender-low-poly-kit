"""Topology checks on plain mesh data (indices match Blender's)."""

import math
from collections import defaultdict, namedtuple

from .. import vecmath as vm
from . import registry

MeshData = namedtuple("MeshData", "verts edges faces det_sign")
# verts: [(x, y, z)] local space; edges: [(a, b)] Blender edge list;
# faces: [(v0, v1, ...)] polygon vertex loops; det_sign: sign of the world
# matrix determinant, kept for reporting only. Normals are judged in local
# space: glTF (and Blender) flip the front-face winding when the global
# determinant is negative, so a locally outward shell stays outward.

AREA_EPS = 1e-12
EDGE_EPS = 1e-7


def edge_key(a, b):
    return (a, b) if a < b else (b, a)


def face_edges(face):
    n = len(face)
    return [(face[i], face[(i + 1) % n]) for i in range(n)]


def newell_normal(verts, face):
    nx = ny = nz = 0.0
    n = len(face)
    for i in range(n):
        x1, y1, z1 = verts[face[i]]
        x2, y2, z2 = verts[face[(i + 1) % n]]
        nx += (y1 - y2) * (z1 + z2)
        ny += (z1 - z2) * (x1 + x2)
        nz += (x1 - x2) * (y1 + y2)
    return (nx, ny, nz)


def face_area(verts, face):
    return 0.5 * vm.length(newell_normal(verts, face))


def ngons(md):
    return [i for i, f in enumerate(md.faces) if len(f) > 4]


def near_duplicates(md, distance):
    """Vertices that have another vertex within ``distance``."""
    if distance <= 0:
        return []
    cell = distance
    grid = defaultdict(list)
    found = set()
    d2 = distance * distance
    for i, (x, y, z) in enumerate(md.verts):
        cx, cy, cz = math.floor(x / cell), math.floor(y / cell), math.floor(z / cell)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    for j in grid.get((cx + dx, cy + dy, cz + dz), ()):
                        px, py, pz = md.verts[j]
                        if (px - x) ** 2 + (py - y) ** 2 + (pz - z) ** 2 <= d2:
                            found.add(i)
                            found.add(j)
        grid[(cx, cy, cz)].append(i)
    return sorted(found)


def edge_usage(md):
    """{edge key: [(face index, directed (a, b))]}."""
    usage = defaultdict(list)
    for fi, face in enumerate(md.faces):
        for a, b in face_edges(face):
            usage[edge_key(a, b)].append((fi, (a, b)))
    return usage


def blender_edge_index(md):
    return {edge_key(a, b): i for i, (a, b) in enumerate(md.edges)}


def loose_verts(md):
    used = set()
    for a, b in md.edges:
        used.add(a)
        used.add(b)
    for f in md.faces:
        used.update(f)
    return [i for i in range(len(md.verts)) if i not in used]


def loose_edges(md, usage):
    return [i for i, (a, b) in enumerate(md.edges) if edge_key(a, b) not in usage]


def degenerate_faces(md):
    out = []
    for i, f in enumerate(md.faces):
        if len(set(f)) < 3 or face_area(md.verts, f) < AREA_EPS:
            out.append(i)
            continue
        if any(vm.distance(md.verts[a], md.verts[b]) < EDGE_EPS for a, b in face_edges(f)):
            out.append(i)
    return out


def _to_edge_indices(keys, index):
    return sorted(index[k] for k in keys if k in index)


def components(md, usage):
    """Connected face groups (through shared edges)."""
    parent = list(range(len(md.faces)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for uses in usage.values():
        first = uses[0][0]
        for fi, _ in uses[1:]:
            ra, rb = find(first), find(fi)
            if ra != rb:
                parent[ra] = rb
    groups = defaultdict(list)
    for i in range(len(md.faces)):
        groups[find(i)].append(i)
    return list(groups.values())


def signed_volume(md, faces):
    vol = 0.0
    for fi in faces:
        f = md.faces[fi]
        a = md.verts[f[0]]
        for k in range(1, len(f) - 1):
            b, c = md.verts[f[k]], md.verts[f[k + 1]]
            vol += vm.dot(a, vm.cross(b, c)) / 6.0
    return vol


def analyse(md, merge_distance):
    usage = edge_usage(md)
    index = blender_edge_index(md)
    nonmanifold = [k for k, u in usage.items() if len(u) > 2]
    boundary = [k for k, u in usage.items() if len(u) == 1]
    inconsistent = [k for k, u in usage.items() if len(u) == 2 and u[0][1] == u[1][1]]
    inconsistent_set = set(inconsistent)
    bad_edges = set(nonmanifold) | set(boundary) | inconsistent_set

    inward_faces = []
    for comp in components(md, usage):
        comp_set = set(comp)
        edges = {edge_key(a, b) for fi in comp for a, b in face_edges(md.faces[fi])}
        if edges & bad_edges:
            continue  # not a closed, consistently wound shell
        if signed_volume(md, comp) < 0:
            inward_faces.extend(sorted(comp_set))

    return {
        "ngon": ngons(md),
        "near_duplicate": near_duplicates(md, merge_distance),
        "loose_vert": loose_verts(md),
        "loose_edge": loose_edges(md, usage),
        "degenerate_face": degenerate_faces(md),
        "nonmanifold_edge": _to_edge_indices(nonmanifold, index),
        "open_boundary": _to_edge_indices(boundary, index),
        "inconsistent_winding": _to_edge_indices(inconsistent, index),
        "inward_normals": sorted(inward_faces),
    }


def run(key, name, md, cfg):
    found = analyse(md, cfg["merge_distance"])
    out = []
    for check_id, indices in found.items():
        if not indices:
            continue
        params = {"name": name, "count": len(indices)}
        if check_id == "near_duplicate":
            params["distance"] = cfg["merge_distance"]
        r = registry.make(check_id, cfg, params, key, indices)
        if r is not None:
            out.append(r)
    return out
