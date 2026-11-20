"""Small vector / matrix helpers (no mathutils).

Matrices are 4x4, row-major, column vectors: a point p maps to M @ p and the
translation lives in ``m[i][3]`` -- the same indexing as mathutils.Matrix.
Matrices are returned as tuples of tuples; inputs may be any 4x4 sequence.
"""

import math

EPS = 1e-9


# ---------------------------------------------------------------- vectors

def add(a, b):
    return tuple(x + y for x, y in zip(a, b))


def sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def mul(a, s):
    return tuple(x * s for x in a)


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def length(a):
    return math.sqrt(dot(a, a))


def normalize(a):
    n = length(a)
    if n < EPS:
        raise ValueError("cannot normalize a zero-length vector")
    return mul(a, 1.0 / n)


def lerp(a, b, t):
    return tuple(x + (y - x) * t for x, y in zip(a, b))


def distance(a, b):
    return length(sub(a, b))


def close(a, b, tol=1e-6):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


# ---------------------------------------------------------------- matrices

def identity():
    return ((1.0, 0.0, 0.0, 0.0), (0.0, 1.0, 0.0, 0.0), (0.0, 0.0, 1.0, 0.0), (0.0, 0.0, 0.0, 1.0))


def as_matrix(m):
    return tuple(tuple(float(v) for v in row) for row in m)


def matmul(a, b):
    return tuple(tuple(sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)) for i in range(4))


def transform_point(m, p):
    x, y, z = p
    return tuple(m[i][0] * x + m[i][1] * y + m[i][2] * z + m[i][3] for i in range(3))


def transform_dir(m, d):
    x, y, z = d
    return tuple(m[i][0] * x + m[i][1] * y + m[i][2] * z for i in range(3))


def translation(t):
    x, y, z = t
    return ((1.0, 0.0, 0.0, x), (0.0, 1.0, 0.0, y), (0.0, 0.0, 1.0, z), (0.0, 0.0, 0.0, 1.0))


def scaling(s):
    x, y, z = s
    return ((x, 0.0, 0.0, 0.0), (0.0, y, 0.0, 0.0), (0.0, 0.0, z, 0.0), (0.0, 0.0, 0.0, 1.0))


def rotation_x(deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return ((1.0, 0.0, 0.0, 0.0), (0.0, c, -s, 0.0), (0.0, s, c, 0.0), (0.0, 0.0, 0.0, 1.0))


def rotation_y(deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return ((c, 0.0, s, 0.0), (0.0, 1.0, 0.0, 0.0), (-s, 0.0, c, 0.0), (0.0, 0.0, 0.0, 1.0))


def rotation_z(deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return ((c, -s, 0.0, 0.0), (s, c, 0.0, 0.0), (0.0, 0.0, 1.0, 0.0), (0.0, 0.0, 0.0, 1.0))


def euler_xyz(deg_xyz):
    """Blender 'XYZ' Euler: X applied first, so M = Rz @ Ry @ Rx."""
    rx, ry, rz = deg_xyz
    return matmul(rotation_z(rz), matmul(rotation_y(ry), rotation_x(rx)))


def from_axes(x_axis, y_axis, z_axis, origin=(0.0, 0.0, 0.0)):
    """Matrix whose columns are the given axes and origin."""
    return (
        (x_axis[0], y_axis[0], z_axis[0], origin[0]),
        (x_axis[1], y_axis[1], z_axis[1], origin[1]),
        (x_axis[2], y_axis[2], z_axis[2], origin[2]),
        (0.0, 0.0, 0.0, 1.0),
    )


def column(m, j):
    return (m[0][j], m[1][j], m[2][j])


def get_translation(m):
    return column(m, 3)


def det3(m):
    """Determinant of the upper-left 3x3 block."""
    return (
        m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
        - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
        + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0])
    )


def inverse_affine(m):
    """Inverse of an affine matrix (last row 0 0 0 1)."""
    d = det3(m)
    if abs(d) < EPS:
        raise ValueError("matrix is singular")
    a = m
    inv3 = (
        ((a[1][1] * a[2][2] - a[1][2] * a[2][1]) / d,
         (a[0][2] * a[2][1] - a[0][1] * a[2][2]) / d,
         (a[0][1] * a[1][2] - a[0][2] * a[1][1]) / d),
        ((a[1][2] * a[2][0] - a[1][0] * a[2][2]) / d,
         (a[0][0] * a[2][2] - a[0][2] * a[2][0]) / d,
         (a[0][2] * a[1][0] - a[0][0] * a[1][2]) / d),
        ((a[1][0] * a[2][1] - a[1][1] * a[2][0]) / d,
         (a[0][1] * a[2][0] - a[0][0] * a[2][1]) / d,
         (a[0][0] * a[1][1] - a[0][1] * a[1][0]) / d),
    )
    t = get_translation(m)
    it = tuple(-sum(inv3[i][k] * t[k] for k in range(3)) for i in range(3))
    return (
        (inv3[0][0], inv3[0][1], inv3[0][2], it[0]),
        (inv3[1][0], inv3[1][1], inv3[1][2], it[1]),
        (inv3[2][0], inv3[2][1], inv3[2][2], it[2]),
        (0.0, 0.0, 0.0, 1.0),
    )


def decompose(m):
    """Return (translation, rotation 3x3 as rows, scale) with sign folded into X scale.

    The rotation is orthonormal and right-handed; a negative determinant is
    represented by a negative X scale (same convention as mathutils).
    """
    t = get_translation(m)
    cols = [column(m, j) for j in range(3)]
    sx, sy, sz = (length(c) for c in cols)
    if det3(m) < 0:
        sx = -sx
    scale = (sx, sy, sz)
    rot_cols = []
    for c, s in zip(cols, scale):
        rot_cols.append(mul(c, 1.0 / s) if abs(s) > EPS else (0.0, 0.0, 0.0))
    rot = tuple(tuple(rot_cols[j][i] for j in range(3)) for i in range(3))
    return t, rot, scale


def is_unit_scale(m, tol=1e-5):
    _, _, s = decompose(m)
    return all(abs(v - 1.0) <= tol for v in s)


def has_rotation(m, tol=1e-5):
    _, rot, _ = decompose(m)
    for i in range(3):
        for j in range(3):
            if abs(rot[i][j] - (1.0 if i == j else 0.0)) > tol:
                return True
    return False


def negative_scale_axes(local_scale):
    """Axis names whose basis scale is negative (from the object's own scale)."""
    return [name for name, v in zip("XYZ", local_scale) if v < 0]


def matrices_close(a, b, tol=1e-6):
    return all(abs(a[i][j] - b[i][j]) <= tol for i in range(4) for j in range(4))
