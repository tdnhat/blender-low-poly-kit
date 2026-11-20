---
name: lowpoly-build-plan
description: Create a LowPoly Kit Build Plan (JSON, schema v1) for a low-poly static game prop from orthographic reference images (Front, Back, Right, Left, Top). Use when the user asks for a Build Plan, a blockout plan, or JSON for the LowPoly Kit Blender add-on, or pastes a LowPoly Kit prompt with an asset name, measurements and notes.
---

# LowPoly Kit Build Plan

Bạn tạo **Build Plan JSON** cho add-on Blender LowPoly Kit. Add-on đọc JSON này và dựng blockout low-poly theo từng bộ phận. Plan phải hợp lệ theo `schema/buildplan.schema.json` (schema v{{schema_version}}) và **phải qua `scripts/validate_plan.py` không lỗi, không cảnh báo** trước khi trả cho user.

## Quy trình

1. **Đọc đầu vào.** Tên asset, các view đã nạp, số đo đã xác nhận, ghi chú của artist (add-on gửi kèm khi user bấm Copy Prompt). Xem ảnh từng view. Ghi chú của artist được ưu tiên hơn suy đoán từ ảnh.
2. **Đo.** Lấy số đo đã xác nhận làm chuẩn. Nếu ảnh có lưới hoặc thước, đo theo lưới. Chi tiết không đo được thì ước lượng và đánh dấu `"inferred": true`.
3. **Lập danh sách bộ phận** (viết ngắn trong đầu hoặc nháp): bộ phận chính (đúng một part không gắn), các bộ phận gắn vào nó, bộ phận đối xứng (khai báo bên phải + `mirror`), chi tiết bỏ qua (màu, cửa sổ, nội thất → tô vertex color hoặc bỏ). Nếu user yêu cầu duyệt trước, trình bày danh sách này và chờ xác nhận.
4. **Chọn op và quy tắc gắn** theo `reference/asset_tips.md` và quy ước bên dưới.
5. **Viết JSON** vào file `plan.json`.
6. **Kiểm tra:** chạy `python3 scripts/validate_plan.py plan.json`. Đọc lỗi và cảnh báo (theo part và trường), đối chiếu bảng khung bao của từng part với số đo và ảnh. Sửa rồi chạy lại cho tới khi kết quả là `OK` (exit code 0). Không trả plan còn lỗi hoặc cảnh báo; nếu một cảnh báo là chủ ý, nói rõ lý do.
7. **Trả kết quả:** một khối ```json chứa toàn bộ plan, sau đó tối đa 5 dòng tóm tắt (số part, tris, các chi tiết `inferred`, giả định quan trọng).

Khi user dán lại lỗi hoặc cảnh báo từ add-on (nút "Copy lỗi cho chatbot"): sửa đúng các mục đó, chạy lại validator, trả lại toàn bộ JSON.

## Quy ước bắt buộc

{{rules}}

## Tài liệu trong skill

- `schema/buildplan.schema.json`: JSON Schema đầy đủ.
- `reference/asset_tips.md`: cách dựng theo loại asset và các lỗi hay gặp.
- `examples/*.json`: plan mẫu đã qua kiểm định (thùng, máy terminal, ghế, cá ngừ, thuyền đánh cá). Dùng làm mẫu cấu trúc, không chép số đo.
- `scripts/validate_plan.py`: chạy đúng các bước của nút **Dán Plan** trong add-on (validator, dựng hình, kiểm tra tiếp xúc). Chỉ cần Python 3 chuẩn.
