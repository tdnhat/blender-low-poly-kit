"""Build Plan storage on Blender data and execution of reconcile actions."""

import json
import time

import bpy
from mathutils import Matrix

from . import coloring, config_ui
from .core.buildplan import reconcile as core_rc

TEXT_PROP = "lpk_build_plan"
LOG_PROP = "lpk_build_log"
REGISTRY_PROP = "lpk_part_registry"
PART_PROP = "lpk_part_id"
BAKED_PROP = "lpk_baked_params"
INFERRED_COLOR = (1.0, 0.55, 0.15, 1.0)
DEFAULT_COLOR = (1.0, 1.0, 1.0, 1.0)


def uid(obj):
    value = getattr(obj, "session_uid", None)
    return None if value is None else str(value)


def _text(root, prop, suffix, create):
    name = root.get(prop)
    text = bpy.data.texts.get(name) if name else None
    if text is None and create:
        text = bpy.data.texts.new(f"{root.name}{suffix}")
        text.use_fake_user = True
        if hasattr(text, "use_module"):
            text.use_module = False
        root[prop] = text.name  # actual name (may carry .001 or be truncated)
    return text


def plan_text(root, create=False):
    return _text(root, TEXT_PROP, ".buildplan.json", create)


def log_text(root, create=False):
    return _text(root, LOG_PROP, ".buildplan.log.jsonl", create)


def read_registry(root):
    try:
        return json.loads(root.get(REGISTRY_PROP, "{}"))
    except (TypeError, ValueError):
        return {}


def write_registry(root, registry):
    root[REGISTRY_PROP] = json.dumps(registry, sort_keys=True)


def object_states(root, scene):
    states = []
    for obj in root.children_recursive:
        if obj.name not in scene.objects or PART_PROP not in obj:
            continue
        snap = None
        if BAKED_PROP in obj:
            try:
                snap = json.loads(obj[BAKED_PROP])
            except (TypeError, ValueError):
                snap = None
        states.append(core_rc.ObjState(obj.name, str(obj[PART_PROP]), uid(obj), snap))
    return states


def _matrix(m):
    return Matrix([list(row) for row in m])


def build_mesh(name, geom):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata([tuple(v) for v in geom.verts], [], [tuple(f) for f in geom.faces])
    mesh.validate(clean_customdata=False)
    mesh.update()
    return mesh


def _parent_to_root(obj, root, matrix_root):
    obj.parent = root
    obj.matrix_parent_inverse = Matrix.Identity(4)
    obj.matrix_world = root.matrix_world @ _matrix(matrix_root)


def append_log(root, entry):
    text = log_text(root, create=True)
    entry = dict(entry, time=time.strftime("%Y-%m-%dT%H:%M:%S"))
    text.write(json.dumps(entry, ensure_ascii=False) + "\n")


def apply(context, root, result):
    """Apply reconcile actions. Meshes are built first; any failure there
    leaves the scene untouched. Returns list of created object names."""
    cfg = config_ui.get_config()
    new_meshes = {}
    try:
        for a in result.actions:
            if a.kind in ("CREATE", "REPLACE_MESH"):
                new_meshes[a.part_id] = build_mesh(f"{root.name}_{a.part_id}", a.data["geom"])
    except Exception:
        for mesh in new_meshes.values():
            bpy.data.meshes.remove(mesh)
        raise

    created = {}
    collections = list(root.users_collection) or [context.scene.collection]
    for a in result.actions:
        obj = bpy.data.objects.get(a.key) if a.key else None
        if a.kind == "CREATE":
            obj = bpy.data.objects.new(f"{root.name}_{a.part_id}", new_meshes[a.part_id])
            for coll in collections:
                coll.objects.link(obj)
            obj[PART_PROP] = a.part_id
            _parent_to_root(obj, root, a.data["matrix_root"])
            coloring.setup_vertex_color(obj, cfg)
            obj.color = INFERRED_COLOR if a.data.get("inferred") else DEFAULT_COLOR
            created[a.part_id] = obj
        elif a.kind == "REPLACE_MESH" and obj is not None:
            old = obj.data
            old_name = old.name
            old.name = old_name + "_lpk_old"
            obj.data = new_meshes[a.part_id]
            obj.data.name = old_name
            coloring.setup_vertex_color(obj, cfg)
            if old.users == 0:
                bpy.data.meshes.remove(old)
        elif a.kind == "SET_TRANSFORM" and obj is not None:
            _parent_to_root(obj, root, a.data["matrix_root"])
        elif a.kind == "SET_META" and obj is not None:
            obj.color = INFERRED_COLOR if a.data.get("inferred") else DEFAULT_COLOR
        elif a.kind == "DELETE" and obj is not None:
            mesh = obj.data
            bpy.data.objects.remove(obj, do_unlink=True)
            if mesh is not None and mesh.users == 0:
                bpy.data.meshes.remove(mesh)
        elif a.kind == "STRIP" and obj is not None:
            for prop in (PART_PROP, BAKED_PROP):
                if prop in obj:
                    del obj[prop]
            obj.color = DEFAULT_COLOR
        elif a.kind == "WRITE_TEXT":
            plan_text(root, create=True).from_string(a.data["text"])

    registry = {}
    for pid, key in result.registry_parts.items():
        obj = bpy.data.objects.get(key)
        if obj is not None:
            registry[pid] = uid(obj)
    for pid, obj in created.items():
        registry[pid] = uid(obj)
    write_registry(root, registry)
    context.view_layer.update()
    return [o.name for o in created.values()]


def set_baked(obj, snapshot):
    obj[BAKED_PROP] = json.dumps(snapshot, sort_keys=True)
