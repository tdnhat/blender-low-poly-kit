"""Colour helpers: hex <-> sRGB floats <-> linear."""

import re

_HEX = re.compile(r"^#?([0-9a-fA-F]{6})$")


def is_hex(value):
    return isinstance(value, str) and bool(_HEX.match(value))


def hex_to_srgb(value):
    m = _HEX.match(value or "")
    if not m:
        raise ValueError(f"invalid hex colour: {value!r}")
    h = m.group(1)
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def srgb_to_hex(rgb):
    return "#" + "".join(f"{max(0, min(255, round(c * 255))):02X}" for c in rgb[:3])


def srgb_to_linear_channel(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def linear_to_srgb_channel(c):
    c = max(0.0, c)
    return c * 12.92 if c <= 0.0031308 else 1.055 * (c ** (1.0 / 2.4)) - 0.055


def srgb_to_linear(rgb):
    return tuple(srgb_to_linear_channel(c) for c in rgb)


def linear_to_srgb(rgb):
    return tuple(linear_to_srgb_channel(c) for c in rgb)


def quantize_byte(rgb):
    """Round sRGB floats to the 8-bit values a BYTE_COLOR attribute stores."""
    return tuple(round(max(0.0, min(1.0, c)) * 255) / 255.0 for c in rgb)
