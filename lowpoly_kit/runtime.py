"""Session state kept in Python (never bpy object references).

Imported by bpy modules; contains no bpy import itself.
"""

# core.config.ConfigResult, loaded lazily by config_ui.get_config()
config_result = None

# Last checker run: dict with keys
#   root_key, results (list of core.checks.registry.CheckResult), stale (bool)
check_state = None

# Last Build Plan errors shown in the UI: list of (code, params, line, col)
plan_errors = []


def invalidate_checks():
    global check_state
    if check_state is not None:
        check_state["stale"] = True


def clear():
    global config_result, check_state, plan_errors
    config_result = None
    check_state = None
    plan_errors = []
