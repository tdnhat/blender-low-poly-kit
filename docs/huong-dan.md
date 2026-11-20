# Hướng dẫn sử dụng LowPoly Kit (v0.1)

## Cài đặt

1. Đóng gói: `python3 tools/build_zip.py` → `dist/lowpoly_kit-0.1.0.zip`.
2. Blender 4.2+: **Edit → Preferences → Get Extensions → ⌄ → Install from Disk** → chọn file zip.
3. Trong Preferences của add-on, chọn **Team config** (file `team_config.json` lead đặt ở thư mục chung). Để trống thì dùng bộ mặc định tích hợp (`lowpoly_kit/team_config.example.json`).

Mở sidebar trong viewport 3D bằng phím **N** → tab **LowPoly Kit**.

## Luồng làm việc

### 1. Reference
- Bấm tên view (Front, Right, Left, Back, Top) để nạp ảnh ortho tương ứng. Ảnh nằm trong collection `REF`, chỉ hiện khi nhìn thẳng trục của nó.
- Chọn **Trục** (Dọc/Ngang), nhập **Khoảng cách thật** giữa hai điểm đã biết, bấm **Đặt 2 mốc + mốc gốc** rồi click lần lượt: mốc thứ nhất, mốc thứ hai, mốc gốc (thường là đáy giữa vật). Phải đang ở view ortho thẳng trục của ảnh (dùng các nút view ở cuối panel).
- **Đo một chiều**: click hai đầu của một chiều (cao, rộng, sâu) để đối chiếu giữa các view. Panel báo các cặp lệch quá dung sai và các chiều **Chưa đo**.
- Opacity, khóa chọn, ẩn/hiện ảnh nằm cuối panel.

### 2. Asset
- Chọn các mesh rồi bấm **Tạo asset root**: Empty đặt ở đáy giữa, các mesh được parent vào. Tên root theo quy ước của team (mặc định `PR_TenAsset`).
- Chọn **Nhóm budget**; **Đếm tris** hiện tổng tris sau modifier so với budget.
- Pivot riêng của bộ phận là origin của mesh (ví dụ origin cánh tủ đặt ở bản lề). Empty trung gian không được xuất.

### 3. Tô màu
- Edit Mode: chọn face rồi bấm biểu tượng cọ dưới ô màu. Object Mode: tô toàn bộ mesh đang chọn.
- **Khởi tạo vertex color** tạo attribute `Color` (CORNER/BYTE_COLOR) và material `M_VertexColor`, giữ màu cũ từ material khi có thể.

### 4. Kiểm tra
- **Kiểm tra asset** liệt kê Lỗi / Cảnh báo / Thông tin theo từng object.
- Nút chọn (con trỏ) đưa tới object hoặc vùng mesh có vấn đề; nút sửa (cờ lê) chạy bản sửa của dòng đó. Mọi bản sửa undo được bằng Ctrl+Z; checker tự chạy lại sau khi sửa.

### 5. Export Godot
- **Export Godot** chạy lại kiểm tra, chặn khi còn Lỗi, hỏi xác nhận khi còn Cảnh báo, rồi xuất `<export_dir>/<export_subdir>/<tên root>.glb`.
- Đường dẫn bắt đầu bằng `//` tính theo file `.blend`, nên cần lưu file trước.
- Add-on không sửa object của bạn khi export: nó xuất từ bản sao tạm, đưa root về gốc tọa độ và trả tên node về như cũ.
- Xem nhanh file xuất: `python3 tools/inspect_glb.py path/to/PR_Barrel.glb`.

## Team config

Xem `lowpoly_kit/team_config.example.json` và schema `lowpoly_kit/schemas/team_config.schema.json`. Các khóa chính: `root_name_pattern`, `budget_groups`, `default_budget_group`, `warning_ratio`, `pivot_tolerance`, `max_materials`, `merge_distance`, `reference_tolerance`, `palette`, `export_dir`, `export_subdir`, `severity_overrides` (đặt `"OFF"` để tắt một check). Bấm **Reload Config** sau khi sửa file.
