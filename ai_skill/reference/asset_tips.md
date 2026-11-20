# Cách dựng theo loại asset

Rút ra từ các lần thử thật với add-on. Xem plan mẫu tương ứng trong `examples/`.

## Vật tròn xoay: thùng, chai, cột, bình (`examples/barrel.json`)

- Thân: `lathe_profile`, profile `[độ cao, bán kính tới mặt]` lấy nửa bề rộng silhouette ở Front/Right.
- Đai, vành, nắp: `add_primitive` cylinder gắn bằng `lathe_radius_at_height`, cùng `segments` với thân, **không** khai báo `radius`.
- 8 cạnh là đủ cho prop nhỏ; 12–16 cho vật lớn hoặc nhìn gần.

## Máy móc, khối có mặt cắt: terminal, tủ, máy bán hàng (`examples/terminal.json`)

- Thân: `extrude_profile` với mặt cắt nhìn từ Right (`plane: "YZ"`), `depth` không đổi.
- Chi tiết trên mặt nghiêng/mặt phẳng của thân: `profile_segment` (đoạn i nối điểm i → i+1).

## Đồ nội thất: ghế, bàn, kệ (`examples/chair.json`)

- Bộ phận chính là hộp (mặt ghế, mặt bàn, nóc kệ).
- Chân: cylinder/box gắn `box_face` mặt `-Z` của mặt ghế, `u`/`v` ở các góc (ví dụ 0.1 và 0.9); +Z của chân hướng xuống nên chân mọc xuống dưới.
- Tựa lưng: box gắn `box_face` mặt `+Z`, `v` gần 1 (phía sau).
- Chi tiết tự do: `offset` trong hệ của part cha.

## Sinh vật: cá, chim (`examples/tuna.json`)

- Thân: `extrude_profile` `plane: "YZ"` với profile nhìn từ Right, `thickness_profile` lấy bề rộng từ Top, `section: "hexagon"` hoặc `"diamond"`. Đầu hướng về phía mà ảnh Front chụp (−Y).
- Vây phẳng nằm trong mặt phẳng dọc thân (đuôi, vây lưng, vây bụng, hàng vây nhỏ): `extrude_profile` mỏng `plane: "YZ"`, gắn `offset` với `position` = [0, 0, 0] và `rotation` = [0, 0, 0] để vẽ thẳng bằng tọa độ của thân. Cho vây chồng vào thân 1–2 cm để liền khối.
- Mắt, vây ngực, mang: `body_surface` với `side: "+"` và `"mirror": "X"`. Vây ngực của cá nằm **ngay sau mang**, gần đầu, ép sát thân: `size: [dài, rộng, mỏng]`, `normal_offset: 0`, xòe ra bằng `rotation` quanh Y khoảng −10…−20°.

## Thuyền, xe, phương tiện (`examples/boat.json`)

- Thân: `extrude_profile` `plane: "YZ"`, profile là dáng mạn (đáy, mũi/đuôi vát), `thickness_profile` là bề rộng boong từ Top, `section: "hull"` với `chine_height` và `bottom_ratio` đo từ ảnh mũi/đuôi.
- Mọi thứ trên boong (cabin, thùng hàng, tời, chân khung, lan can): `body_surface` với `side: "top"`, `s` là vị trí ngang (phải nằm trong bề rộng thân tại `a`).
- Tầng trên của cabin: `box_face` mặt `+Z` của cabin.
- Khung chữ A: hai chân thẳng đứng (`mirror`), thanh chéo gắn boong rồi xoay quanh Y để gặp đỉnh chân, thanh ngang đặt `offset` sao cho chạm đỉnh hai chân.
- Lan can: vài thanh mảnh dài là đủ; đặt `s` lùi vào trong mép thân vài cm để không thò ra ngoài. Ở mũi thon, rút ngắn hoặc xoay thanh cho khớp mép.

## Lỗi hay gặp (validator bắt được)

| Lỗi | Cách tránh |
| --- | --- |
| `normal_offset` dương ở quy tắc gắn lên mặt | Gốc primitive là tâm đáy; để 0. |
| Part lơ lửng | Part phải chạm part cha hoặc một part khác. Kiểm tra bảng khung bao. |
| Bên trái khai báo riêng và xoay sai | Chỉ khai báo bên phải với `"mirror": "X"`. |
| `section` khác `box` với profile hình chữ C | Viền trên và viền dưới phải chạy một chiều từ đầu tới đuôi. |
| `radius` cùng `lathe_radius_at_height` | Bỏ `radius`, add-on tự tính. |
| `s` ngoài bề rộng thân | Lùi `s` vào trong, nhất là ở mũi/đuôi thon. |

## Lỗi validator không bắt được (tự kiểm bằng mắt và bảng khung bao)

- Vị trí giải phẫu hoặc chức năng sai (vây ngực ở giữa thân, cabin ở đuôi trong khi ảnh ở mũi).
- Hướng sai: đối chiếu ảnh Front (−Y) với phía của part.
- Kích thước lệch số đo: so khung bao của thân với số đo đã xác nhận.
- Chi tiết thò ra ngoài mép thân (lan can, thùng hàng ở mép boong).
