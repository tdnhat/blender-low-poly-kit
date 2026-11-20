"""Session state kept in Python (never bpy object references).

Imported by bpy modules; contains no bpy import itself.
"""

# core.config.ConfigResult, loaded lazily by config_ui.get_config()
config_result = None

# Last checker run: dict with keys
#   root_key, results (list of core.checks.registry.CheckResult), stale (bool)
check_state = None

# Last tri count shown in the asset panel: dict root_name, status (BudgetStatus)
tri_cache = None

# Last Build Plan errors shown in the UI: list of (code, params, line, col, pointer)
plan_errors = []
# Draft text of the last rejected plan (for "Copy lỗi cho chatbot")
plan_last_draft = ""
# True when plan_errors are warnings of a successful build
plan_errors_are_warnings = False


def invalidate_checks():
    global check_state
    if check_state is not None:
        check_state["stale"] = True


def clear():
    global config_result, check_state, plan_errors, tri_cache, plan_last_draft, plan_errors_are_warnings
    plan_errors_are_warnings = False
    config_result = None
    check_state = None
    plan_errors = []
    plan_last_draft = ""
    tri_cache = None
