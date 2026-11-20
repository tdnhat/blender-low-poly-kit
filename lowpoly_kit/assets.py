"""Asset root creation, budget group selection and the cached tri summary."""

import bpy
from bpy.props import EnumProperty, StringProperty
from mathutils import Vector

from . import adapters, config_ui, runtime
from .core import budget as core_budget
from .core import scope as core_scope

BUDGET_PROP = "lpk_budget_group"

# Keep a module-level reference: Blender does not keep dynamic enum items alive.
_group_items = []


def _budget_items(self, context):
    global _group_items
    cfg = config_ui.get_config()
    _group_items = [
        (name, f"{info.get('label', name)} ({info['max_tris']} tris)", f"Budget {info['max_tris']} tris", i)
        for i, (name, info) in enumerate(cfg["budget_groups"].items())
    ]
    return _group_items


def _budget_get(self):
    cfg = config_ui.get_config()
    names = list(cfg["budget_groups"])
    current = self.get(BUDGET_PROP, cfg["default_budget_group"])
    if current not in names:
        current = cfg["default_budget_group"]
    return names.index(current)


def _budget_set(self, value):
    names = list(config_ui.get_config()["budget_groups"])
    if 0 <= value < len(names):
        # Stored as a plain string custom property, never as an RNA property.
        self[BUDGET_PROP] = names[value]
        runtime.invalidate_checks()


def budget_group_of(root_obj, cfg):
    return root_obj.get(BUDGET_PROP, cfg["default_budget_group"]) if root_obj else cfg["default_budget_group"]


def world_bounds(objects, depsgraph):
    """Axis-aligned world bounds of evaluated meshes, or None."""
    lo = Vector((float("inf"),) * 3)
    hi = Vector((float("-inf"),) * 3)
    found = False
    for obj in objects:
        if obj.type != "MESH":
            continue
        eval_obj = obj.evaluated_get(depsgraph)
        for corner in eval_obj.bound_box:
            p = obj.matrix_world @ Vector(corner)
            lo = Vector(map(min, lo, p))
            hi = Vector(map(max, hi, p))
            found = True
    return (lo, hi) if found else None


class LPK_OT_create_root(bpy.types.Operator):
    bl_idname = "lpk.create_root"
    bl_label = "Tạo asset root"
    bl_description = "Tạo Empty làm asset root; nếu đang chọn mesh, đặt root ở đáy giữa và parent các mesh vào root"
    bl_options = {"REGISTER", "UNDO"}

    name: StringProperty(name="Tên asset", default="PR_NewAsset")

    def invoke(self, context, event):
        self.name = config_ui.get_config().get("root_name_example", "PR_NewAsset")
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        selected = [o for o in context.selected_objects if o.type == "MESH"]
        depsgraph = context.evaluated_depsgraph_get()
        bounds = world_bounds(selected, depsgraph)
        if bounds:
            lo, hi = bounds
            location = Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z))
        else:
            location = context.scene.cursor.location.copy()

        root = bpy.data.objects.new(self.name, None)
        root.empty_display_type = "PLAIN_AXES"
        root.empty_display_size = 0.25
        root.location = location
        context.collection.objects.link(root)
        root[BUDGET_PROP] = config_ui.get_config()["default_budget_group"]
        context.view_layer.update()

        # Parent only the top-most selected meshes, keeping world transforms.
        selected_set = set(selected)
        for obj in selected:
            if obj.parent in selected_set:
                continue
            world = obj.matrix_world.copy()
            obj.parent = root
            obj.matrix_parent_inverse = root.matrix_world.inverted()
            obj.matrix_world = world

        for obj in context.selected_objects:
            obj.select_set(False)
        root.select_set(True)
        context.view_layer.objects.active = root
        runtime.invalidate_checks()
        self.report({"INFO"}, f"Đã tạo root '{root.name}'")
        return {"FINISHED"}


def asset_summary(context):
    """(root RootResult, scope or None, BudgetStatus or None) for the active object."""
    cfg = config_ui.get_config()
    result, nodes = adapters.find_root_for(context)
    if result.root is None:
        return result, None, None
    scope = core_scope.collect(nodes, result.root)
    tris = adapters.scope_tris(context, scope, nodes)
    root_obj = bpy.data.objects.get(result.root)
    status = core_budget.evaluate(tris, budget_group_of(root_obj, cfg), cfg)
    return result, scope, status


classes = (LPK_OT_create_root,)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Object.lpk_budget_ui = EnumProperty(
        name="Nhóm budget",
        description="Nhóm triangle budget của asset (lưu trong custom property lpk_budget_group)",
        items=_budget_items,
        get=_budget_get,
        set=_budget_set,
    )


def unregister():
    del bpy.types.Object.lpk_budget_ui
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
