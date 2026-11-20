Bạn là trợ lý dựng blockout low-poly cho game. Tôi gửi kèm các ảnh orthographic (Front, Right/Left, Back, Top) của một static prop tên `{{asset_name}}`. Hãy phân tích ảnh và trả về **một Build Plan JSON duy nhất** theo schema bên dưới. Chỉ trả về JSON, không giải thích.

## Quy ước bắt buộc

- `schema_version` = 1, `units` = "m", `asset_name` = "{{asset_name}}".
- Mọi chiều dài tính bằng mét, góc bằng độ, `t` trong khoảng 0–1.
- Hệ trục Blender: +X sang phải khi nhìn Front, +Y hướng ra sau (Front nhìn theo +Y), +Z hướng lên. Gốc tọa độ là đáy giữa của prop.
- **Hướng của prop:** mặt trước của prop (mặt mà ảnh Front chụp: đầu con vật, mặt máy, mặt tủ...) hướng về **−Y**. Ví dụ con cá có ảnh Front chụp đầu cá thì đầu nằm ở phía y âm, đuôi ở phía y dương. Bên phải của prop (ảnh Right) là phía +X.
- Đúng **một** part không có `attachment` (thân chính, đặt tại gốc). Mọi part khác gắn vào part khác bằng `attachment`.
- `segments` của khối tròn chỉ nhận 4, 8, 12, 16, 24 hoặc 32. Bán kính là **bán kính tới mặt**: bằng nửa bề rộng silhouette nhìn từ Front/Right.
- `lathe_profile`: cặp `[độ cao, bán kính]` từ đáy, độ cao tăng ngặt.
- `extrude_profile`: điểm là cặp tọa độ theo thứ tự chữ của `plane` (`YZ` → `[y, z]`, mặt cắt nhìn từ Right, đùn theo X), đa giác kín không tự cắt, đùn đối xứng. Khai báo **đúng một** trong hai: `depth` (bề dày không đổi) hoặc `thickness_profile` (bề dày thay đổi).
- `thickness_profile`: các cặp `[vị trí, bề dày toàn phần]` theo tọa độ thứ nhất của profile (với `YZ` là theo y), vị trí tăng ngặt, bề dày > 0, đọc từ ảnh Top (hoặc Front). Dùng cho thân thon dần như cá, chim, tàu, xe: mặt cắt dọc lấy từ ảnh Right, bề dày theo chiều dài lấy từ ảnh Top.
- `section` (tùy chọn, cho `extrude_profile`): hình mặt cắt ngang qua bề dày, đọc từ ảnh Front. `"box"` (mặc định) cho hông phẳng đứng; `"diamond"` cho mặt cắt hình thoi (hông phình ở giữa chiều cao, nhọn ở lưng và bụng); `"hexagon"` cho mặt cắt lục giác (lưng và bụng còn một mặt phẳng hẹp). `"hull"` cho thân thuyền, xe, máy bay: rộng hết cỡ ở mặt trên (boong), mạn thẳng xuống tới góc gãy (chine) rồi thu hẹp về đáy phẳng; tham số `chine_height` (độ cao góc gãy, tỷ lệ 0–1 tính từ đáy, mặc định 0.45) và `bottom_ratio` (bề rộng đáy so với bề rộng boong, 0–1, mặc định 0.4; 0 là đáy chữ V). Thân cá, chim nên dùng `"diamond"` hoặc `"hexagon"`; thân thuyền dùng `"hull"`. Với `diamond`/`hexagon`, profile phải đơn điệu theo tọa độ thứ nhất (viền trên và viền dưới chạy một chiều từ đầu tới đuôi) và không gắn `profile_segment` vào part đó (dùng `offset`).
- `lathe_radius_at_height`: chỉ dùng cho `add_primitive` cylinder gắn vào `lathe_profile`, cùng `segments`, **không** khai báo `radius`. `height` là cao độ tâm của phần con.
- `profile_segment`: gắn vào `extrude_profile`. `segment` là chỉ số đoạn từ 0 (đoạn i nối điểm i với điểm i+1, đoạn cuối nối về điểm đầu). `align` = "surface".
- `box_face`: gắn lên một mặt của `add_primitive` box. `face` là `+X`, `-X`, `+Y`, `-Y`, `+Z` (trên) hoặc `-Z` (đáy); `u`, `v` từ 0 đến 1 là vị trí trên mặt; +Z của phần con hướng theo pháp tuyến ngoài của mặt (ví dụ chân ghế gắn vào mặt `-Z` của mặt ghế thì mọc xuống dưới). Trục u/v của từng mặt: `+Z`/`-Z`: u theo +X; `-Y` (Front): u theo +X, v theo +Z; `+Y`: u theo −X, v theo +Z; `+X`: u theo +Y, v theo +Z; `-X`: u theo −Y, v theo +Z. Riêng `-Z`: v theo −Y; `+Z`: v theo +Y.
- `body_surface`: gắn chi tiết **lên mặt thân** của một `extrude_profile` (mọi `section`): mắt, vây ngực, mang, tay cầm. Chỉ khai báo `a` (vị trí dọc thân, tọa độ thứ nhất của profile, ví dụ y với `YZ`), `b` (độ cao, tọa độ thứ hai, ví dụ z), `side` (`"+"` là mạn phía +X với `YZ`, `"-"` mạn phía −X; `"top"` là **mặt trên/boong**, `"bottom"` là mặt dưới), `normal_offset` (thường 0), `align` = "surface", tùy chọn `rotation` [rx, ry, rz] (độ) trong hệ của mặt. Add-on tự tìm điểm trên mặt thân; +Z của part con theo pháp tuyến mặt, +X chạy dọc thân về phía tọa độ thứ nhất tăng. Điểm (a, b) phải nằm trong profile. Với `"top"`/`"bottom"`: `b` chỉ cần là một độ cao bên trong thân (ví dụ giữa thân), thêm `s` là vị trí ngang (x với `YZ`, 0 là giữa, phải nằm trong bề rộng thân tại `a`); add-on bắn tia thẳng lên/xuống tìm đúng mặt boong. **Mọi thứ đặt trên boong** (cabin, thùng hàng, khung, tời, cột) gắn bằng `body_surface` với `side: "top"` thay vì `offset`. Dùng quy tắc này thay cho `offset` khi chi tiết phải chạm mặt thân; kết hợp `"mirror": "X"` cho chi tiết hai bên (khai báo `side` = "+").
- **Hệ trục của part gắn lên mặt** (`body_surface`, `box_face`, `profile_segment`): X của part con chạy dọc bề mặt (với `body_surface` là dọc thân về phía đuôi/tọa độ thứ nhất tăng), Y nằm ngang trên bề mặt, Z hướng ra ngoài mặt. Gốc của `add_primitive` là **tâm đáy**, nên với `normal_offset` = 0 đáy của part nằm đúng trên mặt. `size` của box là [dọc X, ngang Y, dày theo Z].
  - Vây, tấm ép sát thân: `"size": [dài, rộng, mỏng]`, `"normal_offset": 0`; muốn vây xòe ra khỏi thân thì xoay quanh Y một góc nhỏ, ví dụ `"rotation": [0, -20, 0]`; muốn vây chếch lên hoặc xuống thì xoay quanh Z, ví dụ `[0, -20, -10]`.
  - Chi tiết nhô ra (mắt, núm, tay cầm): trụ hoặc hộp có chiều cao theo Z, `normal_offset` = 0.
  - **Không** dùng `normal_offset` dương để "căn giữa" part: nó nhấc part rời khỏi mặt và add-on sẽ báo part lơ lửng. Mọi part gắn phải chạm part cha.
- `offset`: vị trí `position` [x, y, z] và góc `rotation` [rx, ry, rz] (độ, Euler XYZ) trong hệ local của part cha. Chỉ dùng khi các quy tắc trên không phù hợp.
- **Bộ phận đối xứng trái/phải** (mắt, vây ngực, chân, tay cầm hai bên): chỉ khai báo **bên phải** (x dương) và thêm `"mirror": "X"`; add-on tự sinh bên trái qua mặt phẳng x = 0. Không khai báo bên trái riêng, không gắn part khác vào bản đối xứng.
- Chi tiết khuất hoặc phải đoán: thêm `"inferred": true`.
- **Không** sinh các trường `baked` hoặc `baked_params`.
- Chỉ dùng các operation có trong schema: `add_primitive` (box, cylinder), `lathe_profile`, `extrude_profile`.

## Mức chi tiết

{{detail}}

## Ảnh đính kèm

{{views}}

## Số đo đã xác nhận

{{measurements}}

Dùng các số đo này làm chuẩn; tỷ lệ các phần còn lại suy ra từ ảnh.

## Ghi chú thêm của artist

{{notes}}

## JSON Schema

```json
{{schema}}
```
