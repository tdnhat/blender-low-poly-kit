"""Mesh generators for Build Plan operations (local space, metres).

Conventions (spec "Quy ước hình học"):
- primitives and lathes: local origin at the bottom centre, +Z up;
- radii are face (apothem) radii; corner radius = r / cos(180°/n);
- phase: the centre of one face lies on -Y (Front), so for n divisible by 4
  the Front and Right silhouettes are exactly 2r wide;
- extrude profiles are pairs in plane-letter order, extruded symmetrically;
- all faces wind outward; caps with more than four corners are triangulated.
"""

import math
from collections import namedtuple

from .. import vecmath as vm
from . import geometry2d

MeshGeom = namedtuple("MeshGeom", "verts faces")

PLANES = {
    # plane: (axis of first coord, axis of second coord, extrude axis)
    "YZ": (1, 2, 0),
    "XZ": (0, 2, 1),
    "XY": (0, 1, 2),
}


def corner_radius(apothem, n):
    return apothem / math.cos(math.pi / n)


def ring_angles(n):
    """Vertex angles (radians), counter-clockwise from above, face centred on -Y."""
    start = math.radians(270.0) - math.pi / n
    return [start + 2.0 * math.pi * k / n for k in range(n)]


def _cap(ring, outward_up):
    """Cap polygon(s) for a ring listed counter-clockwise from above."""
    order = list(ring) if outward_up else list(reversed(ring))
    if len(order) <= 4:
        return [tuple(order)]
    return [(order[0], order[k], order[k + 1]) for k in range(1, len(order) - 1)]


def lathe(profile, n, caps):
    """``profile``: [(z, apothem radius)] with increasing z."""
    verts, rings = [], []
    angles = ring_angles(n)
    for z, r in profile:
        if r == 0:
            rings.append([len(verts)] * n)
            verts.append((0.0, 0.0, z))
            continue
        R = corner_radius(r, n)
        start = len(verts)
        verts.extend((R * math.cos(a), R * math.sin(a), z) for a in angles)
        rings.append(list(range(start, start + n)))
    faces = []
    for i in range(len(rings) - 1):
        lo, hi = rings[i], rings[i + 1]
        for k in range(n):
            a, b = lo[k], lo[(k + 1) % n]
            c, d = hi[(k + 1) % n], hi[k]
            quad = [a, b, c, d]
            unique = []
            for v in quad:
                if v not in unique:
                    unique.append(v)
            if len(unique) >= 3:
                faces.append(tuple(unique))
    if caps in ("both", "bottom") and profile[0][1] > 0:
        faces += _cap(rings[0], outward_up=False)
    if caps in ("both", "top") and profile[-1][1] > 0:
        faces += _cap(rings[-1], outward_up=True)
    return MeshGeom(verts, faces)


def cylinder(apothem, height, n):
    return lathe([(0.0, apothem), (height, apothem)], n, "both")


def box(size):
    sx, sy, sz = size[0] / 2.0, size[1] / 2.0, size[2]
    verts = [(-sx, -sy, 0.0), (sx, -sy, 0.0), (sx, sy, 0.0), (-sx, sy, 0.0),
             (-sx, -sy, sz), (sx, -sy, sz), (sx, sy, sz), (-sx, sy, sz)]
    faces = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    return MeshGeom(verts, faces)


def _handedness(plane):
    a, b, e = PLANES[plane]
    ua, ub, ue = [0, 0, 0], [0, 0, 0], [0, 0, 0]
    ua[a], ub[b], ue[e] = 1, 1, 1
    return 1 if vm.dot(vm.cross(ua, ub), ue) > 0 else -1


def profile_point_3d(plane, pt, s):
    a, b, e = PLANES[plane]
    p = [0.0, 0.0, 0.0]
    p[a], p[b], p[e] = float(pt[0]), float(pt[1]), float(s)
    return tuple(p)


def extrude_axis(plane):
    e = PLANES[plane][2]
    axis = [0.0, 0.0, 0.0]
    axis[e] = 1.0
    return tuple(axis)


def ccw_about_axis(plane, profile):
    """True when the profile runs counter-clockwise seen from the +extrude axis."""
    return geometry2d.signed_area(profile) * _handedness(plane) > 0


def thickness_at(thickness_profile, a):
    """Full thickness at first-coordinate ``a`` (linear, clamped at the ends)."""
    pts = sorted((float(p), float(t)) for p, t in thickness_profile)
    if a <= pts[0][0]:
        return pts[0][1]
    for (p0, t0), (p1, t1) in zip(pts, pts[1:]):
        if a <= p1:
            return t0 + (t1 - t0) * ((a - p0) / (p1 - p0) if p1 > p0 else 0.0)
    return pts[-1][1]


def extrude(plane, profile, depth, caps, thickness_profile=None):
    """Symmetric extrusion; with ``thickness_profile`` each profile point gets
    its own thickness, read along the first profile coordinate (for a body
    seen from Right/Front, the thickness comes from the Top view)."""
    profile = [tuple(p) for p in profile]
    m = len(profile)
    if thickness_profile:
        halves = [thickness_at(thickness_profile, p[0]) / 2.0 for p in profile]
    else:
        halves = [depth / 2.0] * m
    verts = ([profile_point_3d(plane, p, -h) for p, h in zip(profile, halves)]
             + [profile_point_3d(plane, p, h) for p, h in zip(profile, halves)])
    ccw = ccw_about_axis(plane, profile)
    faces = []
    for i in range(m):
        j = (i + 1) % m
        bi, bj, fi, fj = i, j, m + i, m + j
        faces.append((bi, bj, fj, fi) if ccw else (fi, fj, bj, bi))
    if caps == "both":
        hand = _handedness(plane)
        for tri in geometry2d.triangulate(profile):
            pts = [profile[k] for k in tri]
            about_axis = geometry2d.signed_area(pts) * hand > 0
            front = tri if about_axis else (tri[0], tri[2], tri[1])
            faces.append(tuple(m + k for k in front))                # normal +axis
            faces.append(tuple(front[k] for k in (0, 2, 1)))         # normal -axis
    return MeshGeom(verts, faces)


HEX_TOP = 0.5  # hexagon: half-width at top/bottom relative to mid-height


def _quad_or_tris(verts, quad, eps=1e-9):
    """Keep a planar quad; split a non-planar one along its shorter diagonal.

    Mirror-image quads have equal diagonal lengths, so the split stays
    symmetric across the body (and does not depend on how a later
    triangulation would pick the diagonal).
    """
    a, b, c, d = (verts[i] for i in quad)
    n = vm.cross(vm.sub(b, a), vm.sub(c, a))
    if vm.length(n) < 1e-15 or abs(vm.dot(vm.normalize(n), vm.sub(d, a))) <= eps:
        return [quad]
    if vm.distance(a, c) <= vm.distance(b, d):
        return [(quad[0], quad[1], quad[2]), (quad[0], quad[2], quad[3])]
    return [(quad[0], quad[1], quad[3]), (quad[1], quad[2], quad[3])]


def sectioned_body(plane, profile, depth, caps, thickness_profile, section):
    """Loft of cross-sections along the profile's first coordinate.

    The side silhouette follows ``profile`` (monotone along its first
    coordinate), the thickness follows ``thickness_profile`` (or ``depth``)
    and each station gets a diamond or hexagon cross-section.
    """
    profile = [tuple(map(float, p)) for p in profile]
    lower, upper = geometry2d.monotone_chains(profile)
    stations = sorted({p[0] for p in profile} | {float(p) for p, _t in (thickness_profile or [])
                                                 if lower[0][0] < p < lower[-1][0]})
    verts, rings = [], []
    for k, a in enumerate(stations):
        # At the ends take the full vertical extent of the end edge.
        lo = geometry2d.chain_value(lower, a, min)
        hi = geometry2d.chain_value(upper, a, max)
        lo = min(lo, geometry2d.chain_value(upper, a, min))
        hi = max(hi, geometry2d.chain_value(lower, a, max))
        h = (thickness_at(thickness_profile, a) if thickness_profile else depth) / 2.0
        if hi - lo < 1e-9:
            rings.append([len(verts)])
            verts.append(profile_point_3d(plane, (a, lo), 0.0))
            continue
        mid = (lo + hi) / 2.0
        if section == "diamond":
            pts = [(a, hi, 0.0), (a, mid, h), (a, lo, 0.0), (a, mid, -h)]
        else:
            pts = [(a, hi, h * HEX_TOP), (a, mid, h), (a, lo, h * HEX_TOP),
                   (a, lo, -h * HEX_TOP), (a, mid, -h), (a, hi, -h * HEX_TOP)]
        start = len(verts)
        verts.extend(profile_point_3d(plane, (pa, pb), ps) for pa, pb, ps in pts)
        rings.append(list(range(start, start + len(pts))))

    faces = []
    for r0, r1 in zip(rings, rings[1:]):
        if len(r0) == 1 and len(r1) == 1:
            continue
        if len(r0) == 1:
            faces += [(r0[0], r1[(i + 1) % len(r1)], r1[i]) for i in range(len(r1))]
        elif len(r1) == 1:
            faces += [(r0[i], r0[(i + 1) % len(r0)], r1[0]) for i in range(len(r0))]
        else:
            m = len(r0)
            for i in range(m):
                faces += _quad_or_tris(verts, (r0[i], r0[(i + 1) % m], r1[(i + 1) % m], r1[i]))
    if caps == "both":
        # Caps traverse each end ring opposite to the side faces sharing it.
        for ring in (list(reversed(rings[0])), rings[-1]):
            if len(ring) > 2:
                faces += [tuple(ring)] if len(ring) <= 4 else [
                    (ring[0], ring[k], ring[k + 1]) for k in range(1, len(ring) - 1)]
    geom = MeshGeom(verts, faces)
    # Make the shell outward whatever the plane handedness.
    vol = 0.0
    for f in faces:
        a0 = verts[f[0]]
        for k in range(1, len(f) - 1):
            vol += vm.dot(a0, vm.cross(verts[f[k]], verts[f[k + 1]]))
    if vol < 0:
        geom = MeshGeom(verts, [tuple(reversed(f)) for f in faces])
    return geom


def segment_frame(plane, profile, segment, t, normal_offset):
    """Attachment frame on the face generated by profile edge ``segment``."""
    profile = [tuple(p) for p in profile]
    m = len(profile)
    p0 = profile_point_3d(plane, profile[segment], 0.0)
    p1 = profile_point_3d(plane, profile[(segment + 1) % m], 0.0)
    axis = extrude_axis(plane)
    d = vm.normalize(vm.sub(p1, p0))
    outward = vm.cross(d, axis) if ccw_about_axis(plane, profile) else vm.cross(axis, d)
    outward = vm.normalize(outward)
    origin = vm.add(vm.lerp(p0, p1, t), vm.mul(outward, normal_offset))
    x_axis = axis
    z_axis = outward
    y_axis = vm.cross(z_axis, x_axis)
    return vm.from_axes(x_axis, y_axis, z_axis, origin)


# face: (outward normal Z, in-plane X); Y = Z x X
BOX_FACES = {
    "+Z": ((0, 0, 1), (1, 0, 0)),
    "-Z": ((0, 0, -1), (1, 0, 0)),
    "+X": ((1, 0, 0), (0, 1, 0)),
    "-X": ((-1, 0, 0), (0, -1, 0)),
    "+Y": ((0, 1, 0), (-1, 0, 0)),
    "-Y": ((0, -1, 0), (1, 0, 0)),
}


def box_face_frame(size, face, u, v, normal_offset):
    """Attachment frame on a box face. ``u``/``v`` run 0..1 along the face's
    local X / Y; +Z of the frame is the face's outward normal."""
    sx, sy, sz = size
    z_axis, x_axis = (tuple(float(c) for c in a) for a in BOX_FACES[face])
    y_axis = vm.cross(z_axis, x_axis)
    center = (z_axis[0] * sx / 2.0, z_axis[1] * sy / 2.0, sz / 2.0 + z_axis[2] * sz / 2.0)
    extent = lambda axis: abs(axis[0]) * sx + abs(axis[1]) * sy + abs(axis[2]) * sz  # noqa: E731
    origin = vm.add(center, vm.add(vm.mul(x_axis, (u - 0.5) * extent(x_axis)),
                                   vm.add(vm.mul(y_axis, (v - 0.5) * extent(y_axis)), vm.mul(z_axis, normal_offset))))
    return vm.from_axes(x_axis, y_axis, z_axis, origin)


def mirror_x(geom):
    """Geometry reflected across local x = 0, faces reversed to stay outward."""
    verts = [(-x, y, z) for x, y, z in geom.verts]
    faces = [tuple(reversed(f)) for f in geom.faces]
    return MeshGeom(verts, faces)


def ray_hit(geom, origin, direction):
    """Nearest hit of a ray with the mesh: (distance, unit face normal) or None."""
    best = None
    for f in geom.faces:
        a = geom.verts[f[0]]
        for k in range(1, len(f) - 1):
            b, c = geom.verts[f[k]], geom.verts[f[k + 1]]
            e1, e2 = vm.sub(b, a), vm.sub(c, a)
            pv = vm.cross(direction, e2)
            det = vm.dot(e1, pv)
            if abs(det) < 1e-14:
                continue
            tv = vm.sub(origin, a)
            u = vm.dot(tv, pv) / det
            if u < -1e-9 or u > 1 + 1e-9:
                continue
            qv = vm.cross(tv, e1)
            v = vm.dot(direction, qv) / det
            if v < -1e-9 or u + v > 1 + 1e-9:
                continue
            dist = vm.dot(e2, qv) / det
            if dist > 1e-9 and (best is None or dist < best[0]):
                best = (dist, vm.normalize(vm.cross(e1, e2)))
    return best


def body_surface_frame(parent_geom, plane, a, b, side, normal_offset):
    """Frame on the body surface hit by a ray from the mid-plane point (a, b)
    along the extrude axis. +Z = surface normal, +X = along the body's first
    profile axis projected on the surface."""
    axis = extrude_axis(plane)
    direction = axis if side == "+" else vm.mul(axis, -1.0)
    origin = profile_point_3d(plane, (a, b), 0.0)
    hit = ray_hit(parent_geom, origin, direction)
    if hit is None:
        raise ValueError(f"body_surface: no surface at ({a}, {b})")
    dist, normal = hit
    if vm.dot(normal, direction) < 0:
        normal = vm.mul(normal, -1.0)
    point = vm.add(origin, vm.mul(direction, dist))
    first = [0.0, 0.0, 0.0]
    first[PLANES[plane][0]] = 1.0
    x_axis = vm.sub(first, vm.mul(normal, vm.dot(first, normal)))
    if vm.length(x_axis) < 1e-6:
        second = [0.0, 0.0, 0.0]
        second[PLANES[plane][1]] = 1.0
        x_axis = vm.sub(second, vm.mul(normal, vm.dot(second, normal)))
    x_axis = vm.normalize(x_axis)
    y_axis = vm.cross(normal, x_axis)
    return vm.from_axes(x_axis, y_axis, normal, vm.add(point, vm.mul(normal, normal_offset)))


def lathe_radius_at(profile, z):
    for (z0, r0), (z1, r1) in zip(profile, profile[1:]):
        if z0 <= z <= z1:
            return r0 + (r1 - r0) * ((z - z0) / (z1 - z0) if z1 > z0 else 0.0)
    raise ValueError("height outside profile")


def lathe_max_radius(profile, low, high):
    candidates = [lathe_radius_at(profile, low), lathe_radius_at(profile, high)]
    candidates += [r for z, r in profile if low < z < high]
    return max(candidates)


def build(part, computed=None):
    """MeshGeom for a plan part; ``computed`` may supply rule-derived params."""
    computed = computed or {}
    op = part["op"]
    if op == "lathe_profile":
        return lathe([tuple(p) for p in part["profile_z_radius"]], part["segments"], part["caps"])
    if op == "extrude_profile":
        section = part.get("section", "box")
        if section != "box":
            return sectioned_body(part["plane"], part["profile"], part.get("depth"), part["caps"],
                                  part.get("thickness_profile"), section)
        return extrude(part["plane"], part["profile"], part.get("depth"), part["caps"], part.get("thickness_profile"))
    if op == "add_primitive" and part["shape"] == "box":
        return box(part["size"])
    if op == "add_primitive" and part["shape"] == "cylinder":
        radius = computed.get("radius", part.get("radius"))
        return cylinder(radius, part["height"], part["segments"])
    raise ValueError(f"unsupported op {op}")
