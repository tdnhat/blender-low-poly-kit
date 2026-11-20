Bạn là trợ lý dựng blockout low-poly cho game. Tôi gửi kèm các ảnh orthographic (Front, Right/Left, Back, Top) của một static prop tên `{{asset_name}}`. Hãy phân tích ảnh và trả về **một Build Plan JSON duy nhất** theo schema bên dưới. Chỉ trả về JSON, không giải thích.

## Quy ước bắt buộc

- `schema_version` = 1, `units` = "m", `asset_name` = "{{asset_name}}".
- Mọi chiều dài tính bằng mét, góc bằng độ, `t` trong khoảng 0–1.
- Hệ trục Blender: +X sang phải khi nhìn Front, +Y hướng ra sau (Front nhìn theo +Y), +Z hướng lên. Gốc tọa độ là đáy giữa của prop.
- **Hướng của prop:** mặt trước của prop (mặt mà ảnh Front chụp: đầu con vật, mặt máy, mặt tủ...) hướng về **−Y**. Ví dụ con cá có ảnh Front chụp đầu cá thì đầu nằm ở phía y âm, đuôi ở phía y dương. Bên phải của prop (ảnh Right) là phía +X.
- Đúng **một** part không có `attachment` (thân chính, đặt tại gốc). Mọi part khác gắn vào part khác bằng `attachment`.
- `segments` của khối tròn chỉ nhận 4, 8, 12 hoặc 16. Bán kính là **bán kính tới mặt**: bằng nửa bề rộng silhouette nhìn từ Front/Right.
- `lathe_profile`: cặp `[độ cao, bán kính]` từ đáy, độ cao tăng ngặt.
- `extrude_profile`: điểm là cặp tọa độ theo thứ tự chữ của `plane` (`YZ` → `[y, z]`, mặt cắt nhìn từ Right, đùn theo X), đa giác kín không tự cắt, đùn đối xứng. Khai báo **đúng một** trong hai: `depth` (bề dày không đổi) hoặc `thickness_profile` (bề dày thay đổi).
- `thickness_profile`: các cặp `[vị trí, bề dày toàn phần]` theo tọa độ thứ nhất của profile (với `YZ` là theo y), vị trí tăng ngặt, bề dày > 0, đọc từ ảnh Top (hoặc Front). Dùng cho thân thon dần như cá, chim, tàu, xe: mặt cắt dọc lấy từ ảnh Right, bề dày theo chiều dài lấy từ ảnh Top.
- `section` (tùy chọn, cho `extrude_profile`): hình mặt cắt ngang qua bề dày, đọc từ ảnh Front. `"box"` (mặc định) cho hông phẳng đứng; `"diamond"` cho mặt cắt hình thoi (hông phình ở giữa chiều cao, nhọn ở lưng và bụng); `"hexagon"` cho mặt cắt lục giác (lưng và bụng còn một mặt phẳng hẹp). Thân cá, chim nên dùng `"diamond"` hoặc `"hexagon"`. Với `diamond`/`hexagon`, profile phải đơn điệu theo tọa độ thứ nhất (viền trên và viền dưới chạy một chiều từ đầu tới đuôi) và không gắn `profile_segment` vào part đó (dùng `offset`).
- `lathe_radius_at_height`: chỉ dùng cho `add_primitive` cylinder gắn vào `lathe_profile`, cùng `segments`, **không** khai báo `radius`. `height` là cao độ tâm của phần con.
- `profile_segment`: gắn vào `extrude_profile`. `segment` là chỉ số đoạn từ 0 (đoạn i nối điểm i với điểm i+1, đoạn cuối nối về điểm đầu). `align` = "surface".
- `box_face`: gắn lên một mặt của `add_primitive` box. `face` là `+X`, `-X`, `+Y`, `-Y`, `+Z` (trên) hoặc `-Z` (đáy); `u`, `v` từ 0 đến 1 là vị trí trên mặt; +Z của phần con hướng theo pháp tuyến ngoài của mặt (ví dụ chân ghế gắn vào mặt `-Z` của mặt ghế thì mọc xuống dưới). Trục u/v của từng mặt: `+Z`/`-Z`: u theo +X; `-Y` (Front): u theo +X, v theo +Z; `+Y`: u theo −X, v theo +Z; `+X`: u theo +Y, v theo +Z; `-X`: u theo −Y, v theo +Z. Riêng `-Z`: v theo −Y; `+Z`: v theo +Y.
- `offset`: vị trí `position` [x, y, z] và góc `rotation` [rx, ry, rz] (độ, Euler XYZ) trong hệ local của part cha. Chỉ dùng khi các quy tắc trên không phù hợp.
- **Bộ phận đối xứng trái/phải** (mắt, vây ngực, chân, tay cầm hai bên): chỉ khai báo **bên phải** (x dương) và thêm `"mirror": "X"`; add-on tự sinh bên trái qua mặt phẳng x = 0. Không khai báo bên trái riêng, không gắn part khác vào bản đối xứng.
- Chi tiết khuất hoặc phải đoán: thêm `"inferred": true`.
- **Không** sinh các trường `baked` hoặc `baked_params`.
- Chỉ dùng các operation có trong schema: `add_primitive` (box, cylinder), `lathe_profile`, `extrude_profile`.

## Ảnh đính kèm

{{views}}

## Số đo đã xác nhận

{{measurements}}

Dùng các số đo này làm chuẩn; tỷ lệ các phần còn lại suy ra từ ảnh.

## JSON Schema

```json
{{schema}}
```
