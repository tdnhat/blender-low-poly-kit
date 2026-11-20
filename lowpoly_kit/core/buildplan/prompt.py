"""Copy Prompt: fill the prompt template with schema and confirmed measurements."""

import os

from .. import messages

PROMPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "prompts")
TEMPLATE_PATH = os.path.join(PROMPTS_DIR, "buildplan_prompt_v1.md")
SKILL_TEMPLATE_PATH = os.path.join(PROMPTS_DIR, "buildplan_prompt_skill.md")
REVIEW_STEP = ("\n## Duyệt trước\n\nTrước khi viết JSON, liệt kê các bộ phận (id, op, quy tắc gắn, kích thước chính, "
               "chi tiết inferred) và chờ tôi xác nhận.")


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


def format_notes(notes):
    lines = [ln.strip() for ln in (notes or "").replace(";", "\n").splitlines() if ln.strip()]
    return "\n".join(ln if ln.startswith("-") else f"- {ln}" for ln in lines) if lines else "- (không có)"


DETAIL_TEXT = {
    "BLOCKOUT": ("**Blockout.** Chỉ dựng khối chính và tỷ lệ: ít part, khối tròn 8 cạnh, lan can và cầu thang "
                 "giản lược thành tấm hoặc thanh liền, cửa sổ để tô màu. Không cần đạt số tris nào."),
    "DETAILED": ("**Chi tiết**, mục tiêu khoảng **{target} tris** (chấp nhận 70–130%). Thân và khối chính dùng profile nhiều "
                 "điểm hơn để đường cong mượt; khối tròn 12–16 cạnh (24–32 cho chi tiết lớn nhìn gần); tách chi tiết lặp "
                 "lại thành part riêng (cột lan can, bậc thang, đinh, tay cầm); khung cửa sổ và viền bằng hộp mỏng gắn "
                 "lên mặt; thêm chi tiết nhỏ có trong ảnh (đèn, móc, ống, phao). Không thêm chi tiết không có trong ảnh."),
}


def format_detail(level="BLOCKOUT", target_tris=0):
    if level == "DETAILED":
        return DETAIL_TEXT["DETAILED"].format(target=target_tris or 2500)
    return DETAIL_TEXT["BLOCKOUT"]


def build_prompt(asset_name, schema_text, measurements, views=(), template=None, notes="",
                 detail="BLOCKOUT", target_tris=0):
    template = load_template() if template is None else template
    return (template
            .replace("{{asset_name}}", asset_name)
            .replace("{{views}}", format_views(views))
            .replace("{{notes}}", format_notes(notes))
            .replace("{{detail}}", format_detail(detail, target_tris))
            .replace("{{measurements}}", format_measurements(measurements))
            .replace("{{schema}}", schema_text.strip()))


def build_skill_prompt(asset_name, measurements, views=(), notes="", review=False, detail="BLOCKOUT", target_tris=0):
    """Short prompt for use with the lowpoly-build-plan skill (rules live in the skill)."""
    with open(SKILL_TEMPLATE_PATH, encoding="utf-8") as f:
        template = f.read()
    return (template
            .replace("{{asset_name}}", asset_name)
            .replace("{{views}}", format_views(views))
            .replace("{{measurements}}", format_measurements(measurements))
            .replace("{{notes}}", format_notes(notes))
            .replace("{{detail}}", format_detail(detail, target_tris))
            .replace("{{target_arg}}", f" --target-tris {target_tris or 2500}" if detail == "DETAILED" else "")
            .replace("{{review}}", REVIEW_STEP if review else "")).rstrip() + "\n"


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
