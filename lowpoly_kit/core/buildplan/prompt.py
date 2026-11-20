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


def build_prompt(asset_name, schema_text, measurements, template=None):
    template = load_template() if template is None else template
    return (template
            .replace("{{asset_name}}", asset_name)
            .replace("{{measurements}}", format_measurements(measurements))
            .replace("{{schema}}", schema_text.strip()))
