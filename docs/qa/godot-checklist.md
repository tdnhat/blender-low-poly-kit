# Checklist kiểm file .glb trong Godot 4

Dùng cho nghiệm thu v0.1. Trước khi mở Godot, chạy `python3 tools/inspect_glb.py <file>.glb` để xem nhanh node, transform, bounds và `COLOR_0`.

## Fixture cần chuẩn bị trong Blender

| Fixture | Cách dựng |
| --- | --- |
| Root xa gốc | Root `PR_Cabinet` đặt ở (10, −5, 2). Thân là mesh con. |
| Mesh ẩn dưới Empty trung gian | Empty `HingePivot` có transform (dời + xoay 90° quanh Z), con là mesh `Door` đang ẩn. |
| Prop ngoài root | Một prop khác nằm cạnh, không thuộc `PR_Cabinet`. |
| Scale âm | Hai mesh con scale `(-1, 1, 1)` và `(-1, -1, 1)`. |
| Màu liền kề | Hai mặt chung cạnh, cùng material, tô hai màu khác nhau. |

## Kiểm tra trong file (inspect_glb)

- [ ] Node gốc tên đúng tên root, translation `(0, 0, 0)`.
- [ ] Có `Door` (mesh ẩn), không có `HingePivot` và prop ngoài root.
- [ ] `Door` giữ vị trí, hướng, tỷ lệ so với root như trong Blender (Blender (x, y, z) ↔ glTF (x, z, −y)).
- [ ] Mỗi mesh có `COLOR_0`, không có `COLOR_1`.
- [ ] Kích thước bounds khớp kích thước thật (mét).

## Kiểm tra trong Godot

- [ ] Import không cảnh báo; root nằm ở gốc, pivot ở đáy.
- [ ] Kích thước thực đúng (so với một khối 1 m).
- [ ] Trục hướng đúng: mặt Front của prop nhìn về −Z của Godot... *(ghi lại hướng thực tế khi nghiệm thu)*.
- [ ] Màu hiển thị đúng; hai mặt liền kề giữ hai màu riêng.
- [ ] Nếu màu không hiện: bật **Vertex Color → Use as Albedo** trong material và ghi lại để chỉnh preset.
- [ ] Scale âm: bật backface culling, nhìn cùng một mặt từ ngoài và từ trong. Mặt ngoài hiển thị, mặt trong bị loại ở cả hai fixture.
