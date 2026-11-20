# LowPoly Kit

Blender add-on (Extension, Blender 4.2 LTS trở lên) giúp artist dựng static prop low-poly từ ảnh orthographic, kiểm tra theo chuẩn của team và xuất `.glb` cho Godot 4. Spec: [docs/plan-spec.md](docs/plan-spec.md).

## Cấu trúc

| Đường dẫn | Vai trò |
| --- | --- |
| `lowpoly_kit/core/` | Lõi Python thuần (không import `bpy`), chứa toàn bộ logic: phạm vi asset, checker, toán căn ảnh, đọc/ghi glTF, Build Plan. |
| `lowpoly_kit/*.py` | Lớp Blender: adapter đọc scene, operator, panel. Chỉ thực thi kết quả lõi trả về. |
| `lowpoly_kit/schemas/` | JSON Schema cho `team_config.json` và Build Plan. |
| `lowpoly_kit/prompts/` | Mẫu prompt cho chatbot (Build Plan). |
| `tests/unit/` | Test lõi bằng `unittest`, chạy được với Python hệ thống. |
| `tools/` | Đóng gói zip, đọc `.glb`, đo PoC. |

## Phát triển

```bash
# Test lõi (Python 3.11+ stdlib, không cần Blender)
python3 -m unittest discover -s tests/unit -t .

# Đóng gói extension để Install from Disk
python3 tools/build_zip.py

# Xem nội dung một file .glb
python3 tools/inspect_glb.py path/to/PR_Barrel.glb
```

Quy tắc:
- `lowpoly_kit/__init__.py` không import `bpy` ở cấp module; module Blender chỉ import trong `register()`.
- `core/` chỉ dùng thư viện chuẩn và import nội bộ `core`.
- Code phải chạy trên Python 3.11 (Python của Blender 4.2).

Hướng dẫn sử dụng: [docs/huong-dan.md](docs/huong-dan.md). Checklist Godot: [docs/qa/godot-checklist.md](docs/qa/godot-checklist.md).

## Trạng thái

- v0.1 (Reference, asset root, tô màu, checker, export Godot) và PoC Build Plan đã có code.
- Lõi `core/` có unit test chạy bằng Python hệ thống. Lớp Blender được kiểm tĩnh (import với module giả lập, đăng ký operator/panel) nhưng **chưa chạy trong Blender**; test trong Blender và kiểm file trong Godot sẽ được quyết định sau.
