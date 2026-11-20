"""Asset root, asset scope and export plan on plain scene nodes.

A Node describes one object of the current scene. ``key`` is any stable,
unique identifier (the bpy layer uses the object name).
"""

import re
from collections import namedtuple

from . import vecmath as vm

Node = namedtuple("Node", "key name type parent matrix_world hidden")
Node.__new__.__defaults__ = (None, None, None, False)

RootResult = namedtuple("RootResult", "root problem candidate")
# problem: None | "root_missing" | "root_not_empty" | "root_bad_name"

Scope = namedtuple("Scope", "root meshes non_mesh hidden_meshes intermediates")
ExportItem = namedtuple("ExportItem", "key name export_parent matrix_local")


def index(nodes):
    return {n.key: n for n in nodes}


def children_map(nodes_by_key):
    kids = {k: [] for k in nodes_by_key}
    for n in nodes_by_key.values():
        if n.parent is not None and n.parent in kids:
            kids[n.parent].append(n.key)
    for k in kids:
        kids[k].sort(key=lambda c: nodes_by_key[c].name)
    return kids


def ancestors(nodes_by_key, key):
    """Yield key, parent, grandparent... (stops on cycles or unknown parents)."""
    seen = set()
    while key is not None and key in nodes_by_key and key not in seen:
        seen.add(key)
        yield key
        key = nodes_by_key[key].parent


def find_root(nodes_by_key, start_key, name_pattern):
    """Nearest ancestor (or self) that is an EMPTY with a valid name.

    Otherwise report the topmost ancestor as candidate with the problem found.
    """
    if start_key is None or start_key not in nodes_by_key:
        return RootResult(None, "root_missing", None)
    pattern = re.compile(name_pattern)
    chain = list(ancestors(nodes_by_key, start_key))
    for key in chain:
        node = nodes_by_key[key]
        if node.type == "EMPTY" and pattern.search(node.name):
            return RootResult(key, None, key)
    top = nodes_by_key[chain[-1]]
    if top.type != "EMPTY":
        return RootResult(None, "root_not_empty", top.key)
    return RootResult(None, "root_bad_name", top.key)


def collect(nodes_by_key, root_key):
    """Depth-first scope of an asset root (children ordered by name)."""
    kids = children_map(nodes_by_key)
    meshes, non_mesh, hidden, intermediates = [], [], [], []
    stack = list(reversed(kids.get(root_key, [])))
    while stack:
        key = stack.pop()
        node = nodes_by_key[key]
        if node.type == "MESH":
            meshes.append(key)
            if node.hidden:
                hidden.append(key)
        else:
            non_mesh.append(key)
            intermediates.append(key)
        stack.extend(reversed(kids.get(key, [])))
    return Scope(root_key, meshes, non_mesh, hidden, intermediates)


def export_parent(nodes_by_key, key, kept):
    """Nearest ancestor of ``key`` that is kept in the export."""
    parent = nodes_by_key[key].parent
    while parent is not None and parent not in kept:
        parent = nodes_by_key[parent].parent
    return parent


def export_plan(nodes_by_key, scope):
    """Objects to export with their parent in the export and local matrix.

    The root comes first with an identity local matrix: the export places the
    root pivot at the origin. Each mesh keeps its transform relative to its
    nearest kept ancestor, so the transform relative to the root (including
    its own pivot) is preserved when intermediate empties are dropped.
    """
    kept = {scope.root} | set(scope.meshes)
    items = [ExportItem(scope.root, nodes_by_key[scope.root].name, None, vm.identity())]
    for key in scope.meshes:
        parent = export_parent(nodes_by_key, key, kept)
        parent_world = nodes_by_key[parent].matrix_world
        local = vm.matmul(vm.inverse_affine(parent_world), nodes_by_key[key].matrix_world)
        items.append(ExportItem(key, nodes_by_key[key].name, parent, local))
    return items


def matrix_relative_to_root(nodes_by_key, root_key, key):
    root_world = nodes_by_key[root_key].matrix_world
    return vm.matmul(vm.inverse_affine(root_world), nodes_by_key[key].matrix_world)
