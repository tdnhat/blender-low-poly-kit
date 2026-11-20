"""Reference image maths: view orientation, calibration, cross-view checks.

Image coordinates are normalised (u, v) in [0, 1] from the bottom-left
corner (Blender's image convention). An image empty with display size S
shows the image's longer side as S local units; ``empty_image_offset``
(ox, oy) is in fractions of the image (default -0.5, -0.5 = centred).
"""

from collections import namedtuple

from . import vecmath as vm

# rotation (Euler XYZ degrees), image +X / +Y in world, dimension per image axis
ViewDef = namedtuple("ViewDef", "rotation image_x image_y normal dims")

VIEWS = {
    "FRONT": ViewDef((90.0, 0.0, 0.0), (1, 0, 0), (0, 0, 1), (0, -1, 0), {"h": "width", "v": "height"}),
    "BACK": ViewDef((90.0, 0.0, 180.0), (-1, 0, 0), (0, 0, 1), (0, 1, 0), {"h": "width", "v": "height"}),
    "RIGHT": ViewDef((90.0, 0.0, 90.0), (0, 1, 0), (0, 0, 1), (1, 0, 0), {"h": "depth", "v": "height"}),
    "LEFT": ViewDef((90.0, 0.0, -90.0), (0, -1, 0), (0, 0, 1), (-1, 0, 0), {"h": "depth", "v": "height"}),
    "TOP": ViewDef((0.0, 0.0, 0.0), (1, 0, 0), (0, 1, 0), (0, 0, 1), {"h": "width", "v": "depth"}),
}

# Image geometry of an empty: pixel size, display size, offset.
ImageGeom = namedtuple("ImageGeom", "width_px height_px display_size offset")

Calibration = namedtuple("Calibration", "a b axis distance")   # a, b: (u, v); axis: "h" | "v"
Measurement = namedtuple("Measurement", "view dimension meters independent")


def local_size(geom):
    """(width, height) of the displayed image in empty-local units."""
    w, h, s = geom.width_px, geom.height_px, geom.display_size
    if w <= 0 or h <= 0:
        raise ValueError("image has no size")
    if w >= h:
        return s, s * h / w
    return s * w / h, s


def uv_to_local(geom, uv):
    lw, lh = local_size(geom)
    return ((uv[0] + geom.offset[0]) * lw, (uv[1] + geom.offset[1]) * lh)


def local_to_uv(geom, local_xy):
    lw, lh = local_size(geom)
    return (local_xy[0] / lw - geom.offset[0], local_xy[1] / lh - geom.offset[1])


def pixel_delta(geom, a, b, axis):
    if axis == "h":
        return abs(b[0] - a[0]) * geom.width_px
    return abs(b[1] - a[1]) * geom.height_px


def calibrate(width_px, height_px, calibration, origin_uv):
    """New ImageGeom so that the two landmarks are ``distance`` metres apart
    along the axis and ``origin_uv`` sits at the empty's local origin.

    Returns (ImageGeom, metres per pixel). Raises ValueError when invalid.
    """
    if calibration.distance <= 0:
        raise ValueError("ref_need_distance")
    geom0 = ImageGeom(width_px, height_px, 1.0, (-0.5, -0.5))
    delta = pixel_delta(geom0, calibration.a, calibration.b, calibration.axis)
    if delta < 2.0:
        raise ValueError("ref_points_too_close")
    mpp = calibration.distance / delta
    size = max(width_px, height_px) * mpp
    offset = (-origin_uv[0], -origin_uv[1])
    return ImageGeom(width_px, height_px, size, offset), mpp


def measure(geom, a, b, axis):
    """Metres between two landmarks along an image axis of a calibrated image."""
    lw, lh = local_size(geom)
    if axis == "h":
        return abs(b[0] - a[0]) * lw
    return abs(b[1] - a[1]) * lh


def dimension(view, axis):
    return VIEWS[view].dims[axis]


def expected_dimensions(view):
    return sorted(set(VIEWS[view].dims.values()))


def compare(views, measurements, tolerance):
    """Cross-view comparison.

    ``views``: views present; ``measurements``: list of Measurement.
    Returns (mismatches, not_measured) where mismatches are
    (dimension, view_a, a, view_b, b, delta) and not_measured are
    (view, dimension) without any measurement.
    A pair is compared only when at least one of its two measurements comes
    from landmarks independent of the scale calibration.
    """
    by = {}
    for m in measurements:
        by.setdefault((m.view, m.dimension), []).append(m)
    not_measured = [(v, d) for v in sorted(views) for d in expected_dimensions(v) if (v, d) not in by]

    mismatches = []
    dims = sorted({m.dimension for m in measurements})
    for d in dims:
        views_with = sorted({v for (v, dd) in by if dd == d})
        for i in range(len(views_with)):
            for j in range(i + 1, len(views_with)):
                va, vb = views_with[i], views_with[j]
                best = None
                for ma in by[(va, d)]:
                    for mb in by[(vb, d)]:
                        if not (ma.independent or mb.independent):
                            continue
                        delta = abs(ma.meters - mb.meters)
                        if best is None or delta < best[5]:
                            best = (d, va, ma.meters, vb, mb.meters, delta)
                if best is not None and best[5] > tolerance:
                    mismatches.append(best)
    return mismatches, not_measured


def view_matrix(view, location=(0.0, 0.0, 0.0)):
    return vm.matmul(vm.translation(location), vm.euler_xyz(VIEWS[view].rotation))


def aligned(view_direction, view):
    """True when looking straight at the image (view_direction points into the screen)."""
    n = VIEWS[view].normal
    return vm.dot(vm.normalize(view_direction), n) < -0.999
