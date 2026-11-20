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
        merged = getattr(self, "merged_mesh", None)
        if merged is not None:
            try:
                bpy.data.meshes.remove(merged)
            except ReferenceError:
                pass
            self.merged_mesh = None
        if self.collection is not None:
            try:
                bpy.data.collections.remove(self.collection)
            except ReferenceError:
                pass
            self.collection = None

    def merge_meshes(self, root_name, merged_name):
        """Replace the mesh copies by one mesh parented to the root copy.

        Each copy is evaluated (modifiers applied), moved into the root frame
        and appended with bmesh; material slots are unified by material.
        Only temporary data is touched: originals keep their meshes.
        """
        import bmesh
        from mathutils import Matrix

        root_key = self.scope.root
        root_copy = self.copies[root_key]
        to_root = root_copy.matrix_world.inverted()
        depsgraph = self.context.evaluated_depsgraph_get()
        materials = []
        bm = bmesh.new()
        temp_meshes = []
        try:
            for key in self.scope.meshes:
                copy = self.copies[key]
                mesh = bpy.data.meshes.new_from_object(copy.evaluated_get(depsgraph), preserve_all_data_layers=True,
                                                       depsgraph=depsgraph)
                temp_meshes.append(mesh)
                m = to_root @ copy.matrix_world
                mesh.transform(m)
                if m.determinant() < 0:
                    mesh.flip_normals()
                remap = []
                for mat in mesh.materials:
                    if mat not in materials:
                        materials.append(mat)
                    remap.append(materials.index(mat))
                if remap:
                    idx = [0] * len(mesh.polygons)
                    mesh.polygons.foreach_get("material_index", idx)
                    mesh.polygons.foreach_set("material_index", [remap[i] if i < len(remap) else 0 for i in idx])
                bm.from_mesh(mesh)
            merged = bpy.data.meshes.new(merged_name)
            bm.to_mesh(merged)
        finally:
            bm.free()
            for mesh in temp_meshes:
                bpy.data.meshes.remove(mesh)
        for mat in materials:
            merged.materials.append(mat)
        from . import config_ui

        attr = config_ui.get_config()["color_attribute"]
        if attr in merged.color_attributes:
            ca = merged.color_attributes
            if hasattr(ca, "active_color_name"):
                ca.active_color_name = attr
            if hasattr(ca, "default_color_name"):
                ca.default_color_name = attr

        for key in list(self.scope.meshes):
            copy = self.copies.pop(key)
            self.original_names.pop(copy.name, None)
            bpy.data.objects.remove(copy, do_unlink=True)
        obj = bpy.data.objects.new(merged_name, merged)
        self.collection.objects.link(obj)
        obj.parent = root_copy
        obj.matrix_parent_inverse = Matrix.Identity(4)
        obj.matrix_world = root_copy.matrix_world.copy()
        self.copies["__merged__"] = obj
        self.original_names[obj.name] = merged_name
        self.merged_mesh = merged
        self.context.view_layer.update()
        return obj

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
