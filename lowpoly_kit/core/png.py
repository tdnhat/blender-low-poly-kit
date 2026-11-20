"""Small PNG reader/writer (zlib + struct), for masks and tests.

Reads non-interlaced PNG: greyscale, RGB, palette (with tRNS), grey+alpha,
RGBA; bit depth 8 (palette/greyscale also 1, 2, 4). Writes 8-bit RGBA.
Rows are returned top to bottom.
"""

import struct
import zlib

SIGNATURE = b"\x89PNG\r\n\x1a\n"
CHANNELS = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}


class PngError(ValueError):
    pass


def _paeth(a, b, c):
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    return b if pb <= pc else c


def _unfilter(raw, width, height, bpp, row_bytes):
    rows = []
    prev = bytearray(row_bytes)
    pos = 0
    for _ in range(height):
        ftype = raw[pos]
        line = bytearray(raw[pos + 1:pos + 1 + row_bytes])
        pos += 1 + row_bytes
        for i in range(row_bytes):
            left = line[i - bpp] if i >= bpp else 0
            up = prev[i]
            ul = prev[i - bpp] if i >= bpp else 0
            if ftype == 1:
                line[i] = (line[i] + left) & 0xFF
            elif ftype == 2:
                line[i] = (line[i] + up) & 0xFF
            elif ftype == 3:
                line[i] = (line[i] + ((left + up) >> 1)) & 0xFF
            elif ftype == 4:
                line[i] = (line[i] + _paeth(left, up, ul)) & 0xFF
            elif ftype != 0:
                raise PngError(f"bad filter type {ftype}")
        rows.append(bytes(line))
        prev = line
    return rows


def _unpack_bits(row, bit_depth, count):
    if bit_depth == 8:
        return list(row[:count])
    out = []
    per_byte = 8 // bit_depth
    mask = (1 << bit_depth) - 1
    for byte in row:
        for k in range(per_byte):
            out.append((byte >> (8 - bit_depth * (k + 1))) & mask)
    return out[:count]


def read(data):
    """Return (width, height, rows of RGBA tuples)."""
    if data[:8] != SIGNATURE:
        raise PngError("not a PNG file")
    pos = 8
    idat = b""
    palette, trns = None, None
    header = None
    while pos < len(data):
        length, ctype = struct.unpack(">I4s", data[pos:pos + 8])
        chunk = data[pos + 8:pos + 8 + length]
        pos += 12 + length
        if ctype == b"IHDR":
            header = struct.unpack(">IIBBBBB", chunk)
        elif ctype == b"PLTE":
            palette = [tuple(chunk[i:i + 3]) for i in range(0, len(chunk), 3)]
        elif ctype == b"tRNS":
            trns = chunk
        elif ctype == b"IDAT":
            idat += chunk
        elif ctype == b"IEND":
            break
    if header is None:
        raise PngError("missing IHDR")
    width, height, bit_depth, color_type, _comp, _filt, interlace = header
    if interlace:
        raise PngError("interlaced PNG is not supported")
    if color_type not in CHANNELS or (bit_depth != 8 and color_type not in (0, 3)):
        raise PngError(f"unsupported PNG format (type {color_type}, depth {bit_depth})")
    ch = CHANNELS[color_type]
    row_bytes = (width * ch * bit_depth + 7) // 8
    bpp = max(1, ch * bit_depth // 8)
    rows = _unfilter(zlib.decompress(idat), width, height, bpp, row_bytes)

    out = []
    for row in rows:
        vals = _unpack_bits(row, bit_depth, width * ch)
        pixels = []
        for x in range(width):
            px = vals[x * ch:(x + 1) * ch]
            if color_type == 0:
                g = px[0] * 255 // ((1 << bit_depth) - 1)
                pixels.append((g, g, g, 255))
            elif color_type == 2:
                pixels.append((px[0], px[1], px[2], 255))
            elif color_type == 3:
                r, g, b = palette[px[0]]
                a = trns[px[0]] if trns is not None and px[0] < len(trns) else 255
                pixels.append((r, g, b, a))
            elif color_type == 4:
                pixels.append((px[0], px[0], px[0], px[1]))
            else:
                pixels.append(tuple(px))
        out.append(pixels)
    return width, height, out


def read_file(path):
    with open(path, "rb") as f:
        return read(f.read())


def _chunk(ctype, payload):
    return struct.pack(">I", len(payload)) + ctype + payload + struct.pack(">I", zlib.crc32(ctype + payload) & 0xFFFFFFFF)


def write(width, height, rows):
    """``rows``: top-to-bottom lists of RGBA tuples."""
    raw = b"".join(b"\x00" + bytes(c for px in row for c in px) for row in rows)
    return (SIGNATURE + _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            + _chunk(b"IDAT", zlib.compress(raw)) + _chunk(b"IEND", b""))


def write_file(path, width, height, rows):
    with open(path, "wb") as f:
        f.write(write(width, height, rows))


def mask(rows, use_alpha=None):
    """Boolean rows: alpha > 127, or for opaque images luminance < 128."""
    if use_alpha is None:
        use_alpha = any(px[3] < 255 for row in rows for px in row)
    if use_alpha:
        return [[px[3] > 127 for px in row] for row in rows]
    return [[(px[0] * 299 + px[1] * 587 + px[2] * 114) // 1000 < 128 for px in row] for row in rows]
