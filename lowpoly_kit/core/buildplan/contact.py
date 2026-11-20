"""Contact check: does each attached part touch its parent?

Two meshes (root space) are in contact when one has a vertex inside or
within ``tol`` of the other, or an edge of one crosses a face of the other.
The last test catches a band wrapped around a body, where no vertex of
either mesh lies inside the other.
"""

from .. import vecmath as vm

TOL = 0.001
_RAY_DIR = vm.normalize((0.5773, 0.4999, 0.6453))  # skewed to avoid hitting edges exactly


def world_mesh(resolved):
    verts = [vm.transform_point(resolved.matrix_root, v) for v in resolved.geom.verts]
    tris = []
    for f in resolved.geom.faces:
        for k in range(1, len(f) - 1):
            tris.append((verts[f[0]], verts[f[k]], verts[f[k + 1]]))
    edges = set()
    for f in resolved.geom.faces:
        for i in range(len(f)):
            a, b = f[i], f[(i + 1) % len(f)]
            edges.add((min(a, b), max(a, b)))
    return verts, tris, [(verts[a], verts[b]) for a, b in edges]


def _bbox(points):
    return tuple(min(p[i] for p in points) for i in range(3)), tuple(max(p[i] for p in points) for i in range(3))


def _bbox_overlap(a, b, tol):
    return all(a[0][i] - tol <= b[1][i] and b[0][i] - tol <= a[1][i] for i in range(3))


def _ray_tri(origin, direction, tri):
    a, b, c = tri
    e1, e2 = vm.sub(b, a), vm.sub(c, a)
    pv = vm.cross(direction, e2)
    det = vm.dot(e1, pv)
    if abs(det) < 1e-14:
        return None
    tv = vm.sub(origin, a)
    u = vm.dot(tv, pv) / det
    if u < 0 or u > 1:
        return None
    qv = vm.cross(tv, e1)
    v = vm.dot(direction, qv) / det
    if v < 0 or u + v > 1:
        return None
    return vm.dot(e2, qv) / det


def point_inside(p, tris):
    hits = 0
    for tri in tris:
        t = _ray_tri(p, _RAY_DIR, tri)
        if t is not None and t > 1e-12:
            hits += 1
    return hits % 2 == 1


def segment_crosses(seg, tri):
    a, b = seg
    d = vm.sub(b, a)
    length = vm.length(d)
    if length < 1e-12:
        return False
    t = _ray_tri(a, vm.mul(d, 1.0 / length), tri)
    return t is not None and 0.0 <= t <= length


def point_tri_distance(p, tri):
    a, b, c = tri
    n = vm.cross(vm.sub(b, a), vm.sub(c, a))
    nl = vm.length(n)
    if nl < 1e-15:
        return min(vm.distance(p, a), vm.distance(p, b), vm.distance(p, c))
    n = vm.mul(n, 1.0 / nl)
    dist = vm.dot(vm.sub(p, a), n)
    proj = vm.sub(p, vm.mul(n, dist))
    # Inside test with barycentric signs.
    inside = True
    for x, y in ((a, b), (b, c), (c, a)):
        if vm.dot(vm.cross(vm.sub(y, x), vm.sub(proj, x)), n) < 0:
            inside = False
            break
    if inside:
        return abs(dist)

    def seg_dist(x, y):
        d = vm.sub(y, x)
        t = max(0.0, min(1.0, vm.dot(vm.sub(p, x), d) / max(vm.dot(d, d), 1e-30)))
        return vm.distance(p, vm.add(x, vm.mul(d, t)))

    return min(seg_dist(a, b), seg_dist(b, c), seg_dist(c, a))


def in_contact(mesh_a, mesh_b, tol=TOL):
    va, ta, ea = mesh_a
    vb, tb, eb = mesh_b
    box_a, box_b = _bbox(va), _bbox(vb)
    if not _bbox_overlap(box_a, box_b, tol):
        return False
    if any(point_inside(p, tb) for p in va) or any(point_inside(p, ta) for p in vb):
        return True
    if any(segment_crosses(s, t) for s in ea for t in tb) or any(segment_crosses(s, t) for s in eb for t in ta):
        return True
    near = lambda pts, tris: any(point_tri_distance(p, t) <= tol for p in pts for t in tris)  # noqa: E731
    return near(va, tb) or near(vb, ta)


def floating_parts(resolved_parts, tol=TOL):
    """[(part id, parent id)] for attached parts that touch no other part.

    The parent is tested first; a part that misses its parent but touches
    another part (a crossbar resting on frame legs, stairs between deck and
    roof) is not floating.
    """
    by_id = {r.id: r for r in resolved_parts}
    meshes = {}

    def mesh(r):
        if r.id not in meshes:
            meshes[r.id] = world_mesh(r)
        return meshes[r.id]

    out = []
    for r in resolved_parts:
        att = r.part.get("attachment")
        if not att or r.geom is None:
            continue
        parent = by_id.get(att["parent_id"])
        if parent is None or parent.geom is None:
            continue
        if in_contact(mesh(r), mesh(parent), tol):
            continue
        box = _bbox(mesh(r)[0])
        others = (o for o in resolved_parts if o.id not in (r.id, parent.id) and o.geom is not None)
        if any(_bbox_overlap(box, _bbox(mesh(o)[0]), tol) and in_contact(mesh(r), mesh(o), tol) for o in others):
            continue
        out.append((r.id, parent.id))
    return out
