"""Minimal binary glTF (.glb) reader / writer and inspection helpers."""

import json
import math
import struct

from . import vecmath as vm

MAGIC = b"glTF"
CHUNK_JSON = 0x4E4F534A
CHUNK_BIN = 0x004E4942

COMPONENT = {
    5120: ("b", 1, 127.0),
    5121: ("B", 1, 255.0),
    5122: ("h", 2, 32767.0),
    5123: ("H", 2, 65535.0),
    5125: ("I", 4, 4294967295.0),
    5126: ("f", 4, None),
}
TYPE_SIZE = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT2": 4, "MAT3": 9, "MAT4": 16}


class GlbError(ValueError):
    pass


def read(data):
    """Return (gltf dict, bin bytes or None)."""
    if len(data) < 12 or data[:4] != MAGIC:
        raise GlbError("not a binary glTF file")
    version, length = struct.unpack_from("<II", data, 4)
    if version != 2:
        raise GlbError(f"unsupported glTF version {version}")
    if length > len(data):
        raise GlbError("truncated file")
    offset = 12
    gltf, binary = None, None
    while offset + 8 <= length:
        chunk_len, chunk_type = struct.unpack_from("<II", data, offset)
        chunk = data[offset + 8:offset + 8 + chunk_len]
        if chunk_type == CHUNK_JSON:
            gltf = json.loads(chunk.decode("utf-8"))
        elif chunk_type == CHUNK_BIN and binary is None:
            binary = bytes(chunk)
        offset += 8 + chunk_len
    if gltf is None:
        raise GlbError("missing JSON chunk")
    return gltf, binary


def _pad(data, fill):
    return data + fill * ((4 - len(data) % 4) % 4)


def write(gltf, binary=None):
    js = _pad(json.dumps(gltf, ensure_ascii=False, separators=(",", ":")).encode("utf-8"), b" ")
    chunks = struct.pack("<II", len(js), CHUNK_JSON) + js
    if binary is not None:
        b = _pad(bytes(binary), b"\x00")
        chunks += struct.pack("<II", len(b), CHUNK_BIN) + b
    return MAGIC + struct.pack("<II", 2, 12 + len(chunks)) + chunks


def read_file(path):
    with open(path, "rb") as f:
        return read(f.read())


def write_file(path, gltf, binary=None):
    with open(path, "wb") as f:
        f.write(write(gltf, binary))


# ---------------------------------------------------------------- accessors

def read_accessor(gltf, binary, index):
    acc = gltf["accessors"][index]
    fmt, size, norm_div = COMPONENT[acc["componentType"]]
    n_comp = TYPE_SIZE[acc["type"]]
    count = acc["count"]
    if "bufferView" not in acc:
        return [tuple([0.0] * n_comp)] * count
    view = gltf["bufferViews"][acc["bufferView"]]
    base = view.get("byteOffset", 0) + acc.get("byteOffset", 0)
    elem = size * n_comp
    stride = view.get("byteStride", elem)
    normalized = acc.get("normalized", False)
    out = []
    for i in range(count):
        vals = struct.unpack_from("<" + fmt * n_comp, binary, base + i * stride)
        if normalized and norm_div:
            vals = tuple(max(v / norm_div, -1.0) for v in vals)
        out.append(vals)
    return out


# ---------------------------------------------------------------- nodes

def quat_to_matrix(q):
    x, y, z, w = q
    return (
        (1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w), 0.0),
        (2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w), 0.0),
        (2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y), 0.0),
        (0.0, 0.0, 0.0, 1.0),
    )


def node_local_matrix(node):
    if "matrix" in node:
        m = node["matrix"]  # column-major
        return tuple(tuple(m[c * 4 + r] for c in range(4)) for r in range(4))
    t = node.get("translation", [0, 0, 0])
    r = node.get("rotation", [0, 0, 0, 1])
    s = node.get("scale", [1, 1, 1])
    return vm.matmul(vm.translation(t), vm.matmul(quat_to_matrix(r), vm.scaling(s)))


def parents(gltf):
    out = {}
    for i, node in enumerate(gltf.get("nodes", [])):
        for c in node.get("children", []):
            out[c] = i
    return out


def world_matrices(gltf):
    nodes = gltf.get("nodes", [])
    par = parents(gltf)
    cache = {}

    def world(i):
        if i not in cache:
            local = node_local_matrix(nodes[i])
            cache[i] = vm.matmul(world(par[i]), local) if i in par else local
        return cache[i]

    return {i: world(i) for i in range(len(nodes))}


def summary(gltf, binary):
    """Per-node info: name, parent, world matrix, det sign, mesh attrs, world bounds."""
    par = parents(gltf)
    worlds = world_matrices(gltf)
    nodes = gltf.get("nodes", [])
    out = []
    for i, node in enumerate(nodes):
        info = {
            "index": i,
            "name": node.get("name", f"node{i}"),
            "parent": nodes[par[i]].get("name") if i in par else None,
            "world": worlds[i],
            "det": vm.det3(worlds[i]),
            "attributes": [],
            "bounds": None,
            "colors": None,
        }
        if "mesh" in node:
            lo = [math.inf] * 3
            hi = [-math.inf] * 3
            attrs = set()
            for prim in gltf["meshes"][node["mesh"]]["primitives"]:
                attrs.update(prim["attributes"])
                acc = gltf["accessors"][prim["attributes"]["POSITION"]]
                if "min" in acc and "max" in acc:
                    mn, mx = acc["min"], acc["max"]
                    for corner in [(x, y, z) for x in (mn[0], mx[0]) for y in (mn[1], mx[1]) for z in (mn[2], mx[2])]:
                        p = vm.transform_point(worlds[i], corner)
                        lo = [min(a, b) for a, b in zip(lo, p)]
                        hi = [max(a, b) for a, b in zip(hi, p)]
                if "COLOR_0" in prim["attributes"] and binary is not None and info["colors"] is None:
                    info["colors"] = read_accessor(gltf, binary, prim["attributes"]["COLOR_0"])
            info["attributes"] = sorted(attrs)
            info["bounds"] = (tuple(lo), tuple(hi)) if lo[0] != math.inf else None
        out.append(info)
    return out


def blender_to_gltf_point(p):
    """Blender Z-up (x, y, z) -> glTF Y-up (x, z, -y)."""
    return (p[0], p[2], -p[1])
