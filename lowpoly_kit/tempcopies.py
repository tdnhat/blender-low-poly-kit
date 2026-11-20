"""Temporary shallow copies of an asset, shared by the checker and the exporter.

Copies share mesh data with the originals, live in a temporary collection
linked to the scene and are always visible, so hidden or excluded meshes are
evaluated with their modifiers. Each copy is parented to the copy of its
nearest kept ancestor (export plan), keeping its world matrix, so nothing in
the user's scene moves. The user's objects are never modified.
"""

import uuid

import bpy

from .core import scope as core_scope

TMP_PREFIX = "LPK_TMP_"


class TempCopies:
    def __init__(self, context, nodes_by_key, scope):
        self.context = context
        self.nodes = nodes_by_key
        self.scope = scope
        self.collection = None
        self.copies = {}          # original key -> copy object
        self.original_names = {}  # copy name -> original name
        self.plan = core_scope.export_plan(nodes_by_key, scope)

    def __enter__(self):
        scene = self.context.scene
        self.collection = bpy.data.collections.new(TMP_PREFIX + uuid.uuid4().hex[:8])
        scene.collection.children.link(self.collection)
        try:
            for item in self.plan:
                original = bpy.data.objects[item.key]
                world = original.matrix_world.copy()
                copy = original.copy()
                copy.animation_data_clear()
                for key in [k for k in copy.keys() if k.startswith("lpk_")]:
                    del copy[key]
                self.collection.objects.link(copy)
                copy.parent = None
                copy.matrix_world = world
                copy.hide_viewport = False
                copy.hide_render = False
                copy.hide_select = False
                self.copies[item.key] = copy
                self.original_names[copy.name] = original.name
            for item in self.plan:
                if item.export_parent is None:
                    continue
                child = self.copies[item.key]
                parent = self.copies[item.export_parent]
                world = child.matrix_world.copy()
                child.parent = parent
                child.matrix_parent_inverse = parent.matrix_world.inverted()
                child.matrix_world = world
            for copy in self.copies.values():
                try:
                    copy.hide_set(False)
                except RuntimeError:
                    pass
            self.context.view_layer.update()
        except Exception:
            self.cleanup()
            raise
        return self

    def __exit__(self, exc_type, exc, tb):
        self.cleanup()
        return False

    def cleanup(self):
        for copy in list(self.copies.values()):
            try:
                bpy.data.objects.remove(copy, do_unlink=True)
            except ReferenceError:
                pass
        self.copies = {}
        if self.collection is not None:
            try:
                bpy.data.collections.remove(self.collection)
            except ReferenceError:
                pass
            self.collection = None

    def layer_collection(self):
        """LayerCollection of the temporary collection in the active view layer."""
        def find(lc):
            if lc.collection == self.collection:
                return lc
            for child in lc.children:
                found = find(child)
                if found is not None:
                    return found
            return None

        return find(self.context.view_layer.layer_collection)


def cleanup_leftovers():
    """Remove temporary collections left by a crash (called on file load)."""
    for coll in [c for c in bpy.data.collections if c.name.startswith(TMP_PREFIX)]:
        for obj in list(coll.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        bpy.data.collections.remove(coll)
