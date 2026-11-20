"""User-facing Vietnamese texts, keyed by code.

Core modules return codes + params; only this module holds wording.
A unit test checks every code produced by the core has a text here.
"""


class _SafeDict(dict):
    def __missing__(self, key):
        return "{" + key + "}"


TEXTS = {
    # ---------------------------------------------------------------- config
    "config_not_set": "Chưa chọn file team config, đang dùng bộ mặc định tích hợp.",
    "config_missing": "Không tìm thấy file team config: {path}. Đang dùng bộ mặc định tích hợp.",
    "config_unreadable": "Không đọc được file team config {path}: {reason}. Đang dùng bộ mặc định tích hợp.",
    "config_parse_error": "File team config lỗi cú pháp tại dòng {line}, cột {col}: {reason}.",
    "config_invalid": "Team config không hợp lệ tại {pointer} (dòng {line}): {detail}.",
    "config_using_defaults": "Team config {path} không hợp lệ nên đang dùng bộ mặc định tích hợp.",
    "config_keys_defaulted": "Team config thiếu {keys}; các mục này dùng giá trị mặc định.",
    "config_bad_regex": "Regex tên root không hợp lệ: {error}.",
    "config_unknown_group": "Nhóm budget mặc định '{group}' không có trong budget_groups.",
    "config_bad_color": "Màu palette không hợp lệ: {value}.",
    # ---------------------------------------------------------------- asset checks
    "root_missing": "Không tìm thấy asset root. Chọn một Empty có tên theo quy ước (ví dụ {example}) hoặc một object con của nó.",
    "root_not_empty": "'{name}' đang làm root nhưng không phải Empty. Tạo Empty root và parent cả cây mesh vào đó.",
    "root_bad_name": "Tên root '{name}' không khớp quy ước (ví dụ {example}).",
    "root_transform": "Root '{name}' có scale khác 1 hoặc có rotation. Đưa transform xuống mesh con hoặc reset root.",
    "budget_over": "Tổng {tris} tris vượt budget {limit} của nhóm '{group}'. Mesh nặng nhất: {heaviest}.",
    "budget_near": "Tổng {tris}/{limit} tris ({percent}%), còn {remaining} tris.",
    "color_attr_missing": "Mesh '{name}' thiếu color attribute '{attribute}'.",
    "color_attr_wrong_format": "Color attribute '{attribute}' của '{name}' là {domain}/{data_type}, cần CORNER/BYTE_COLOR.",
    "material_not_vertex_color": "Material '{material}' trên '{name}' không lấy Base Color từ attribute '{attribute}'.",
    "material_missing": "Mesh '{name}' chưa có material vertex color.",
    "material_empty_slot": "Mesh '{name}' có slot material rỗng.",
    "material_count": "Mesh '{name}' dùng {count} material, giới hạn là {limit}: {materials}.",
    "pivot_offset": "Pivot root lệch đáy giữa của asset {offset_mm} mm (dung sai {tolerance_mm} mm).",
    "scene_scale": "Unit scale của scene là {scale}, cần 1.0 (1 đơn vị = 1 mét).",
    "mesh_transform": "Mesh '{name}' còn {what}{modifiers}.",
    "mesh_negative_scale": "Mesh '{name}' có scale âm trên trục {axes}; định thức toàn cục {sign}.",
    "non_mesh_child": "'{name}' ({type}) nằm dưới root nhưng không phải mesh nên sẽ không được xuất.",
    "hidden_mesh": "Mesh '{name}' đang ẩn trong viewport nhưng vẫn được tính và xuất.",
    "smooth_shading": "Mesh '{name}' có {count} face dùng smooth shading.",
    "mesh_data_name": "Mesh data '{data}' khác tên object '{name}'.",
    "single_color": "Asset chỉ có một màu ({color}). Bỏ qua nếu đây là chủ ý.",
    "modifier_geometry": "Lỗi có thể do modifier '{modifier}' trên '{name}' sinh ra.",
    # ---------------------------------------------------------------- topology
    "ngon": "Mesh '{name}' có {count} n-gon.",
    "near_duplicate": "Mesh '{name}' có {count} vertex gần trùng (≤ {distance} m).",
    "loose_vert": "Mesh '{name}' có {count} vertex rời.",
    "loose_edge": "Mesh '{name}' có {count} cạnh rời.",
    "degenerate_face": "Mesh '{name}' có {count} mặt suy biến.",
    "nonmanifold_edge": "Mesh '{name}' có {count} cạnh dùng chung bởi hơn hai mặt.",
    "open_boundary": "Mesh '{name}' có {count} cạnh biên hở. Bỏ qua nếu mặt hở là chủ ý.",
    "inconsistent_winding": "Mesh '{name}' có {count} cạnh nối hai mặt ngược chiều normal.",
    "inward_normals": "Normal của mesh kín '{name}' đang hướng vào trong.",
    # ---------------------------------------------------------------- checker ui
    "check_ok": "Không có lỗi. Asset sẵn sàng export.",
    "check_stale": "Kết quả kiểm tra đã cũ, hãy kiểm tra lại.",
    # ---------------------------------------------------------------- export
    "export_blocked": "Export bị chặn: còn {count} lỗi Error.",
    "export_done": "Đã xuất {path}.",
    "export_failed": "Export thất bại: {reason}.",
    "export_unsaved_blend": "Lưu file .blend trước khi export vì export_dir là đường dẫn tương đối.",
    "export_dropped_options": "Exporter glTF của bản Blender này không có tùy chọn: {options}.",
    "export_node_mismatch": "File xuất không khớp danh sách mesh: thiếu {missing}, thừa {extra}.",
    # ---------------------------------------------------------------- reference
    "ref_not_ortho": "Chuyển sang view orthographic thẳng trục của ảnh trước khi đặt mốc.",
    "ref_need_distance": "Nhập khoảng cách thật (> 0) trước khi đặt mốc.",
    "ref_points_too_close": "Hai mốc quá gần nhau theo trục đã chọn.",
    "ref_not_measured": "Chưa đo",
    "ref_mismatch": "{dimension}: {view_a} đo {a} m, {view_b} đo {b} m, lệch {delta} m (dung sai {tolerance} m).",
    "ref_image_not_loaded": "Ảnh '{name}' chưa nạp được hoặc có kích thước 0.",
    # ---------------------------------------------------------------- build plan
    "plan_json_error": "JSON lỗi tại dòng {line}, cột {col}: {reason}.",
    "plan_schema": "{part}{field}: {detail}.",
    "plan_duplicate_id": "ID '{id}' bị trùng.",
    "plan_root_count": "Plan phải có đúng một part không gắn (đang có {count}: {ids}).",
    "plan_missing_parent": "Part '{id}' tham chiếu cha '{parent}' không tồn tại.",
    "plan_cycle": "Quan hệ gắn tạo vòng: {cycle}.",
    "plan_rule_parent_type": "Part '{id}': rule {rule} cần cha kiểu {expected}, cha '{parent}' là {actual}.",
    "plan_rule_child_type": "Part '{id}': rule {rule} cần phần con kiểu {expected}.",
    "plan_segments_mismatch": "Part '{id}' phải có cùng số cạnh với cha '{parent}' ({expected}).",
    "plan_forbidden_field": "Part '{id}' không được khai báo '{field}' khi dùng rule {rule}.",
    "plan_segment_range": "Part '{id}': segment {segment} ngoài profile của '{parent}' (0–{max}).",
    "plan_profile_self_intersect": "Part '{id}': profile tự cắt.",
    "plan_profile_degenerate": "Part '{id}': profile suy biến (diện tích bằng 0 hoặc điểm trùng).",
    "plan_heights_not_increasing": "Part '{id}': độ cao profile phải tăng ngặt.",
    "plan_span_outside_parent": "Part '{id}': khoảng cao {low}–{high} m nằm ngoài profile của '{parent}'.",
    "plan_depth_or_thickness": "Part '{id}': khai báo đúng một trong hai trường depth hoặc thickness_profile.",
    "plan_thickness_not_increasing": "Part '{id}': vị trí trong thickness_profile phải tăng ngặt.",
    "plan_mirror_id_taken": "Part '{id}' dùng mirror nhưng ID '{mirror_id}' đã có trong plan.",
    "plan_parent_is_mirror": "Part '{id}' không gắn được vào bản đối xứng '{parent}'; gắn vào part gốc và dùng mirror.",
    "plan_managed_field": "Part '{id}': plan dán vào không được chứa trường '{field}' (do add-on quản lý).",
    "plan_baked_mismatch": "Part '{id}': '{field}' khác trạng thái bake đang lưu trên object.",
    "plan_baked_without_object": "Part '{id}' khai đã bake nhưng không có object đã bake tương ứng.",
    "plan_asset_name": "asset_name '{plan}' khác tên root '{root}'.",
    "plan_duplicate_objects": "Nhiều object cùng part ID '{id}': {objects}. Xử lý trùng lặp trước khi dựng.",
    "plan_ignored_baked_change": "Part '{id}' đã bake nên bỏ qua thay đổi ở: {fields}.",
    "plan_stripped": "Đã gỡ liên kết Build Plan khỏi '{name}'.",
    "plan_built": "Đã dựng {count} part.",
    "plan_build_failed": "Dựng thất bại, giữ bản dựng gần nhất: {reason}.",
    "plan_clipboard_empty": "Clipboard trống. Dán JSON vào Text Editor rồi dùng Rebuild.",
}

# Display names for structural wording.
DIMENSIONS = {"height": "Chiều cao", "width": "Bề rộng", "depth": "Chiều sâu"}
SEVERITY_LABELS = {"ERROR": "Lỗi", "WARNING": "Cảnh báo", "INFO": "Thông tin"}


def text(code, params=None):
    template = TEXTS.get(code)
    if template is None:
        return code
    return template.format_map(_SafeDict({k: _fmt(v) for k, v in (params or {}).items()}))


def _fmt(value):
    if isinstance(value, float):
        return f"{value:.4g}"
    if isinstance(value, (list, tuple)):
        return ", ".join(_fmt(v) for v in value)
    return value
