import struct
import unittest
import zlib

from lowpoly_kit.core import metrics, png


def rect_mask(w, h, x0, y0, x1, y1):
    return [[x0 <= x <= x1 and y0 <= y <= y1 for x in range(w)] for y in range(h)]


def chunk(t, p):
    return struct.pack(">I", len(p)) + t + p + struct.pack(">I", zlib.crc32(t + p) & 0xFFFFFFFF)


def png_bytes(width, height, color_type, bit_depth, rows_raw, filter_types, extra=b""):
    raw = b"".join(bytes([f]) + r for f, r in zip(filter_types, rows_raw))
    return (png.SIGNATURE + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, bit_depth, color_type, 0, 0, 0))
            + extra + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


class Png(unittest.TestCase):
    def test_roundtrip_rgba(self):
        rows = [[(255, 0, 0, 255), (0, 0, 0, 0)], [(0, 255, 0, 128), (1, 2, 3, 4)]]
        w, h, back = png.read(png.write(2, 2, rows))
        self.assertEqual((w, h, back), (2, 2, rows))

    def test_filters_1_to_4(self):
        # RGB 2x1 rows encoded with each filter type; decoded rows must match the plain row.
        plain = bytes([10, 20, 30, 40, 50, 60])
        for f in range(5):
            if f == 0:
                enc = plain
            elif f == 1:
                enc = bytes([plain[i] - (plain[i - 3] if i >= 3 else 0) & 0xFF for i in range(6)])
            elif f == 2:
                enc = plain  # previous row is zero for the first row
            elif f == 3:
                enc = bytes([(plain[i] - ((plain[i - 3] if i >= 3 else 0) >> 1)) & 0xFF for i in range(6)])
            else:
                enc = bytes([(plain[i] - (plain[i - 3] if i >= 3 else 0)) & 0xFF for i in range(6)])
            _, _, rows = png.read(png_bytes(2, 1, 2, 8, [enc], [f]))
            self.assertEqual(rows[0], [(10, 20, 30, 255), (40, 50, 60, 255)], f)

    def test_palette_with_transparency(self):
        plte = chunk(b"PLTE", bytes([0, 0, 0, 255, 255, 255]))
        trns = chunk(b"tRNS", bytes([0, 255]))
        # 4 pixels, 1 bit per pixel: 0,1,1,0 -> 0b01100000
        data = png_bytes(4, 1, 3, 1, [bytes([0b01100000])], [0], plte + trns)
        _, _, rows = png.read(data)
        self.assertEqual([px[3] for px in rows[0]], [0, 255, 255, 0])
        self.assertEqual(png.mask(rows), [[False, True, True, False]])

    def test_luminance_mask(self):
        rows = [[(0, 0, 0, 255), (255, 255, 255, 255)]]
        self.assertEqual(png.mask(rows), [[True, False]])


class Outline(unittest.TestCase):
    def test_shift_of_k_pixels(self):
        ref = rect_mask(100, 100, 20, 20, 59, 79)        # 40 x 60 box
        model = rect_mask(100, 100, 23, 20, 62, 79)      # shifted 3 px
        self.assertAlmostEqual(metrics.outline_error(ref, model), 3 / 60)
        self.assertEqual(metrics.outline_error(ref, ref), 0.0)

    def test_padding_does_not_matter(self):
        ref_small = rect_mask(60, 80, 10, 10, 49, 69)
        model_small = rect_mask(60, 80, 12, 10, 51, 69)
        ref_big = rect_mask(200, 200, 10, 10, 49, 69)
        model_big = rect_mask(200, 200, 12, 10, 51, 69)
        self.assertAlmostEqual(metrics.outline_error(ref_small, model_small), metrics.outline_error(ref_big, model_big))

    def test_missing_part_is_large(self):
        ref = rect_mask(100, 100, 10, 10, 89, 89)
        model = rect_mask(100, 100, 10, 10, 49, 89)
        self.assertGreater(metrics.outline_error(ref, model), 0.4)


class Fields(unittest.TestCase):
    def test_counting_rules(self):
        base = {"parts": [{"id": "body", "op": "lathe_profile", "segments": 8, "caps": "both",
                           "profile_z_radius": [[0, 0.26], [0.45, 0.31], [0.9, 0.26]]}]}
        v2 = {"parts": [dict(base["parts"][0], profile_z_radius=[[0, 0.26], [0.45, 0.33], [0.9, 0.26]], inferred=True,
                             caps="none")]}
        v3 = {"parts": [dict(v2["parts"][0], profile_z_radius=[[0, 0.26], [0.45, 0.34], [0.9, 0.26]]),
                        {"id": "lid", "op": "add_primitive", "shape": "box", "size": [0.5, 0.5, 0.05]}]}
        changed = metrics.changed_fields([base, v2, v3])
        # same field edited twice counts once; strings and inferred ignored; new part counts its 3 numbers
        self.assertEqual(changed, {("body", "/profile_z_radius/1/1"), ("lid", "/size/0"), ("lid", "/size/1"),
                                   ("lid", "/size/2")})


if __name__ == "__main__":
    unittest.main()
