"""2D polygon helpers: area, simplicity, ear-clipping triangulation."""


def signed_area(points):
    n = len(points)
    return 0.5 * sum(points[i][0] * points[(i + 1) % n][1] - points[(i + 1) % n][0] * points[i][1] for i in range(n))


def has_duplicate_points(points, eps=1e-9):
    n = len(points)
    for i in range(n):
        for j in range(i + 1, n):
            if abs(points[i][0] - points[j][0]) <= eps and abs(points[i][1] - points[j][1]) <= eps:
                return True
    return False


def _orient(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _on_segment(a, b, p, eps=1e-12):
    return (min(a[0], b[0]) - eps <= p[0] <= max(a[0], b[0]) + eps
            and min(a[1], b[1]) - eps <= p[1] <= max(a[1], b[1]) + eps)


def segments_intersect(p1, p2, p3, p4, eps=1e-12):
    d1, d2 = _orient(p3, p4, p1), _orient(p3, p4, p2)
    d3, d4 = _orient(p1, p2, p3), _orient(p1, p2, p4)
    if ((d1 > eps and d2 < -eps) or (d1 < -eps and d2 > eps)) and ((d3 > eps and d4 < -eps) or (d3 < -eps and d4 > eps)):
        return True
    if abs(d1) <= eps and _on_segment(p3, p4, p1):
        return True
    if abs(d2) <= eps and _on_segment(p3, p4, p2):
        return True
    if abs(d3) <= eps and _on_segment(p1, p2, p3):
        return True
    if abs(d4) <= eps and _on_segment(p1, p2, p4):
        return True
    return False


def self_intersects(points):
    """True when two non-adjacent edges of the closed polygon touch or cross."""
    n = len(points)
    for i in range(n):
        a1, a2 = points[i], points[(i + 1) % n]
        for j in range(i + 1, n):
            if j == i or (j + 1) % n == i or j == (i + 1) % n:
                continue
            b1, b2 = points[j], points[(j + 1) % n]
            if segments_intersect(a1, a2, b1, b2):
                return True
    return False


def _point_in_triangle(p, a, b, c):
    d1, d2, d3 = _orient(a, b, p), _orient(b, c, p), _orient(c, a, p)
    has_neg = d1 < 0 or d2 < 0 or d3 < 0
    has_pos = d1 > 0 or d2 > 0 or d3 > 0
    return not (has_neg and has_pos)


def triangulate(points):
    """Ear clipping for a simple polygon. Returns index triples with the
    same winding as the input polygon."""
    n = len(points)
    if n < 3:
        return []
    ccw = signed_area(points) > 0
    idx = list(range(n)) if ccw else list(reversed(range(n)))
    tris = []
    guard = 0
    while len(idx) > 3 and guard < 10 * n:
        guard += 1
        m = len(idx)
        for k in range(m):
            i0, i1, i2 = idx[(k - 1) % m], idx[k], idx[(k + 1) % m]
            a, b, c = points[i0], points[i1], points[i2]
            if _orient(a, b, c) <= 1e-15:
                continue
            if any(_point_in_triangle(points[j], a, b, c) for j in idx if j not in (i0, i1, i2)):
                continue
            tris.append((i0, i1, i2))
            idx.pop(k)
            break
        else:
            break
    if len(idx) == 3:
        tris.append(tuple(idx))
    if not ccw:
        tris = [(a, c, b) for a, b, c in tris]
    return tris


def monotone_chains(points, eps=1e-12):
    """Split a polygon into lower and upper chains along the first coordinate.

    Returns (lower, upper) as lists of points ordered by increasing first
    coordinate, or None when the polygon is not monotone in that direction
    (a vertical line would cross its outline more than twice).
    """
    n = len(points)
    i_min = min(range(n), key=lambda i: (points[i][0], points[i][1]))
    i_max = max(range(n), key=lambda i: (points[i][0], -points[i][1]))

    def walk(start, end, step):
        chain = [points[start]]
        i = start
        while i != end:
            i = (i + step) % n
            chain.append(points[i])
        return chain

    c1 = walk(i_min, i_max, 1)
    c2 = walk(i_min, i_max, -1)
    for chain in (c1, c2):
        for k in range(len(chain) - 1):
            if chain[k + 1][0] < chain[k][0] - eps:
                return None
    # Vertical runs are only allowed at the two ends.
    for chain in (c1, c2):
        for k in range(1, len(chain) - 2):
            if abs(chain[k + 1][0] - chain[k][0]) <= eps:
                return None
    mid = lambda c: sum(p[1] for p in c) / len(c)  # noqa: E731
    lower, upper = (c1, c2) if mid(c1) <= mid(c2) else (c2, c1)
    return lower, upper


def chain_value(chain, a, pick=min):
    """Second coordinate of a monotone chain at first coordinate ``a``."""
    values = []
    for p, q in zip(chain, chain[1:]):
        if p[0] <= a <= q[0]:
            if abs(q[0] - p[0]) < 1e-12:
                values += [p[1], q[1]]
            else:
                values.append(p[1] + (q[1] - p[1]) * (a - p[0]) / (q[0] - p[0]))
    if not values:
        raise ValueError("outside chain")
    return pick(values)


def point_in_polygon(p, points):
    """Even-odd test; points on the outline count as outside."""
    x, y = p
    inside = False
    n = len(points)
    for i in range(n):
        (x1, y1), (x2, y2) = points[i], points[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            xc = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if abs(xc - x) < 1e-12:
                return False
            if xc > x:
                inside = not inside
    return inside
