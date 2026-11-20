"""Post-process an exported .glb: root at origin, original names, node check."""

from collections import namedtuple

PostResult = namedtuple("PostResult", "gltf node_names missing extra")

MERGED_SUFFIX = "_mesh"


def merged_node_name(root_name):
    """Name of the single mesh node when the asset is merged on export."""
    return root_name + MERGED_SUFFIX


def expected_names(root_name, mesh_names, merged):
    return [root_name, merged_node_name(root_name)] if merged else [root_name] + list(mesh_names)


def postprocess(gltf, root_name, original_names, expected_names):
    """Return a PostResult with a modified copy of ``gltf``.

    - nodes named after temporary copies get their original names back;
    - the root node's translation is set to zero (its rotation/scale are
      identity, enforced by the checker), so the root pivot is at the origin;
    - ``missing`` / ``extra`` compare the node names with ``expected_names``.
    """
    import copy

    out = copy.deepcopy(gltf)
    names = []
    for node in out.get("nodes", []):
        name = node.get("name")
        if name in original_names:
            node["name"] = original_names[name]
        names.append(node.get("name"))

    for node in out.get("nodes", []):
        if node.get("name") == root_name:
            if "matrix" in node:
                m = list(node["matrix"])
                m[12] = m[13] = m[14] = 0.0
                node["matrix"] = m
            else:
                node.pop("translation", None)

    expected = set(expected_names)
    present = set(names)
    return PostResult(out, names, sorted(expected - present), sorted(present - expected))
