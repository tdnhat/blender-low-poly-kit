"""Export the active asset to .glb for Godot.

Flow: checker on the same scope -> block on Error -> temporary copies in a
temporary collection -> glTF export of that collection to a temp file ->
post-process (root at origin, original names, node check) -> replace target.
The user's objects are never modified; state is restored in ``finally``.
"""

import os

import bpy

from . import checker_ops, config_ui, runtime, tempcopies
from .core import export_post, export_settings, glb, messages, paths
from .core.checks import registry


def exporter_options():
    """{identifier: enum items or None} of the installed glTF exporter."""
    rna = bpy.ops.export_scene.gltf.get_rna_type()
    out = {}
    for prop in rna.properties:
        if prop.identifier == "rna_type":
            continue
        out[prop.identifier] = [e.identifier for e in prop.enum_items] if prop.type == "ENUM" else None
    return out


def export_asset(context):
    """Export the asset of the active object. Returns (ok, message)."""
    cfg = config_ui.get_config()
    results = checker_ops.run_checks(context)
    state = runtime.check_state
    if registry.error_count(results):
        return False, messages.text("export_blocked", {"count": registry.error_count(results)})

    root_name = state["root_name"]
    target, err = paths.resolve_export_path(cfg["export_dir"], cfg.get("export_subdir", ""), root_name, bpy.data.filepath)
    if err:
        return False, messages.text(err)

    try:
        available = exporter_options()
    except (AttributeError, RuntimeError) as exc:
        return False, messages.text("export_failed", {"reason": f"glTF exporter không khả dụng ({exc})"})
    kwargs, dropped, missing_required = export_settings.filter_options(available)
    if missing_required:
        return False, messages.text("export_failed", {"reason": "thiếu tùy chọn exporter: " + ", ".join(missing_required)})

    os.makedirs(os.path.dirname(target), exist_ok=True)
    tmp = paths.temp_path_for(target)
    view_layer = context.view_layer
    prev_layer_collection = view_layer.active_layer_collection
    prev_active = view_layer.objects.active

    from . import adapters
    from .core import scope as core_scope

    nodes = adapters.scene_index(context)
    scope = core_scope.collect(nodes, state["root"])
    expected = [root_name] + [nodes[k].name for k in scope.meshes]

    with checker_ops.ModeGuard(context):
        try:
            with tempcopies.TempCopies(context, nodes, scope) as copies:
                layer = copies.layer_collection()
                if layer is None:
                    return False, messages.text("export_failed", {"reason": "không tìm thấy collection tạm"})
                view_layer.active_layer_collection = layer
                try:
                    result = bpy.ops.export_scene.gltf(filepath=tmp, **kwargs)
                except RuntimeError as exc:
                    return False, messages.text("export_failed", {"reason": str(exc)})
                finally:
                    view_layer.active_layer_collection = prev_layer_collection
                if "FINISHED" not in result or not os.path.isfile(tmp):
                    return False, messages.text("export_failed", {"reason": str(result)})
                original_names = dict(copies.original_names)

            gltf, binary = glb.read_file(tmp)
            post = export_post.postprocess(gltf, root_name, original_names, expected)
            if post.missing or post.extra:
                return False, messages.text("export_node_mismatch", {"missing": post.missing or "-", "extra": post.extra or "-"})
            glb.write_file(tmp, post.gltf, binary)
            os.replace(tmp, target)
        finally:
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass
            try:
                view_layer.objects.active = prev_active
            except (ReferenceError, RuntimeError):
                pass

    msg = messages.text("export_done", {"path": target})
    if dropped:
        msg += " " + messages.text("export_dropped_options", {"options": dropped})
    return True, msg


class LPK_OT_export_godot(bpy.types.Operator):
    bl_idname = "lpk.export_godot"
    bl_label = "Export Godot"
    bl_description = "Kiểm tra rồi xuất asset đang chọn thành .glb cho Godot"

    def invoke(self, context, event):
        results = checker_ops.run_checks(context)
        errors = registry.error_count(results)
        if errors:
            self.report({"ERROR"}, messages.text("export_blocked", {"count": errors}))
            return {"CANCELLED"}
        warnings = registry.summary_counts(results)["WARNING"]
        if warnings:
            try:
                return context.window_manager.invoke_confirm(
                    self, event, title="Export Godot",
                    message=f"Còn {warnings} cảnh báo. Vẫn export?", confirm_text="Export")
            except TypeError:
                return context.window_manager.invoke_confirm(self, event)
        return self.execute(context)

    def execute(self, context):
        ok, message = export_asset(context)
        self.report({"INFO"} if ok else {"ERROR"}, message)
        return {"FINISHED"} if ok else {"CANCELLED"}


classes = (LPK_OT_export_godot,)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
