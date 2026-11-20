# Skill AI "lowpoly-build-plan"

Skill đóng gói quy ước, schema, plan mẫu và **script kiểm tra** của add-on, để chatbot tự kiểm Build Plan trước khi trả về. Mọi nội dung được sinh từ repo, nên skill luôn khớp phiên bản schema của add-on.

## Đóng gói

```bash
python3 tools/build_ai_skill.py
# -> dist/lowpoly-build-plan/ và dist/lowpoly-build-plan.zip
```

Đóng gói lại mỗi khi schema, prompt hoặc lõi Build Plan thay đổi.

| File | Nội dung |
| --- | --- |
| `SKILL.md` | Quy trình 7 bước và quy ước bắt buộc (lấy từ prompt của add-on) |
| `schema/buildplan.schema.json` | JSON Schema |
| `reference/asset_tips.md` | Cách dựng theo loại asset, lỗi hay gặp |
| `examples/*.json` | Plan mẫu đã qua kiểm định |
| `scripts/validate_plan.py` | Chạy như nút Dán Plan: validator, dựng hình, kiểm tra tiếp xúc; in bảng khung bao và số tris. Exit code 0 = OK, 1 = lỗi, 2 = cảnh báo |

## Cài đặt

Giao diện của các nhà cung cấp có thể thay đổi; các bước dưới đây theo giao diện hiện tại.

- **Claude (claude.ai):** bật Code execution, rồi tải `lowpoly-build-plan.zip` lên ở phần Skills trong Settings. Cần gói có hỗ trợ custom skill.
- **ChatGPT (Custom GPT):** dán phần thân của `SKILL.md` (bỏ khối `---` đầu file) vào Instructions, tải các file trong thư mục skill lên phần Knowledge (giữ nguyên cấu trúc thư mục `scripts/` bằng cách tải file zip và yêu cầu GPT giải nén khi chạy), bật Code Interpreter.

## Dùng với add-on

Trong panel **Build Plan (PoC)**, chọn **Kiểu prompt → Dùng skill**. **Copy Prompt** lúc đó chỉ chép tên asset, các view, số đo và ghi chú; quy ước và schema đã nằm trong skill. Bật **Duyệt danh sách bộ phận trước** nếu muốn AI liệt kê bộ phận và chờ xác nhận trước khi viết JSON.

Ảnh concept vẫn được gửi lên nhà cung cấp AI như khi dùng prompt đầy đủ; skill chỉ thêm việc chạy script kiểm tra trong sandbox của họ.
