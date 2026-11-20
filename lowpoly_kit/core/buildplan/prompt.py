"""Copy Prompt: fill the prompt template with schema and confirmed measurements."""

import os

from .. import messages

TEMPLATE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                             "prompts", "buildplan_prompt_v1.md")


def load_template():
    with open(TEMPLATE_PATH, encoding="utf-8") as f:
        return f.read()


def format_measurements(measurements):
    """``measurements``: iterable of (view, dimension, metres)."""
    lines = []
    for view, dim, meters in sorted(measurements):
        lines.append(f"- {view} · {messages.DIMENSIONS.get(dim, dim)} ({dim}): {meters:.4f} m")
    return "\n".join(lines) if lines else "- (chưa có số đo đã xác nhận; hãy ước lượng và đánh dấu inferred)"


def format_views(views):
    """``views``: iterable of (view, calibrated)."""
    views = sorted(views)
    if not views:
        return "- (chưa nạp ảnh tham chiếu trong add-on; đính kèm các ảnh ortho bạn có)"
    lines = [f"- {v}{'' if ok else ' (chưa căn scale, chỉ dùng để đọc hình dạng)'}" for v, ok in views]
    return "\n".join(lines)


def build_prompt(asset_name, schema_text, measurements, views=(), template=None):
    template = load_template() if template is None else template
    return (template
            .replace("{{asset_name}}", asset_name)
            .replace("{{views}}", format_views(views))
            .replace("{{measurements}}", format_measurements(measurements))
            .replace("{{schema}}", schema_text.strip()))


def build_error_prompt(errors, plan_text=None, rejected=True):
    """Follow-up message asking the chatbot to fix a plan.

    ``errors``: iterable of (message, pointer, line, col). ``rejected`` False
    means the plan was built but has warnings (for example floating parts).
    """
    header = ("Build Plan bạn vừa trả về bị add-on từ chối với các lỗi sau:" if rejected
              else "Build Plan bạn vừa trả về dựng được nhưng add-on phát hiện các vấn đề sau:")
    lines = [header, ""]
    for message, pointer, line, col in errors:
        where = f"dòng {line}, cột {col}" + (f", trường {pointer}" if pointer else "")
        lines.append(f"- {where}: {message}")
    lines += ["", "Hãy sửa đúng các lỗi trên, giữ nguyên các phần khác và trả về lại **toàn bộ** JSON hợp lệ theo schema. "
              "Chỉ trả về JSON."]
    if plan_text:
        lines += ["", "JSON đã gửi:", "```json", plan_text.strip(), "```"]
    return "\n".join(lines)
