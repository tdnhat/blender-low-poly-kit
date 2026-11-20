# LowPoly Kit — Plan & Spec

## Tổng quan

LowPoly Kit là Blender add-on giúp artist trong team dựng static prop low-poly từ ảnh orthographic, kiểm tra theo chuẩn chung và xuất `.glb` cho Godot. Build Plan là hướng tự động hóa của dự án: add-on đọc JSON mô tả hình học, dựng blockout theo từng bộ phận và đặt kết quả cạnh ảnh tham chiếu để artist duyệt.

Team có thể dùng luồng dựng tay ngay từ v0.1. PoC Build Plan dùng lại phần căn ảnh và có thể chạy song song với các phần còn lại của v0.1 khi đủ người.

| Người dùng | Nhu cầu |
| --- | --- |
| Artist mới | Biết phải làm gì ở từng bước, thấy lỗi và biết cách sửa. |
| Artist có kinh nghiệm | Căn ảnh, kiểm tra và export nhanh, có thể tắt tip. |
| Lead | Đặt quy ước naming, budget và palette một lần cho team. |

| Hạng mục | Thiết lập cho v0.1 |
| --- | --- |
| Blender và engine | Blender Extension từ 4.2 LTS. Kiểm thử trên bản Blender và Godot 4 mà team sử dụng. |
| Asset | Static prop, tiền tố `PR_`, ví dụ `PR_Barrel_Broken`. |
| Tỷ lệ | 1 đơn vị Blender tương ứng 1 mét trong Godot. |
| Triangle budget | Cấu hình theo nhóm prop. Giá trị thử nghiệm đề xuất là 3.000 tris cho prop nhỏ, có thể cấp budget riêng cho prop lớn. Warning từ 90%, Error khi vượt ngưỡng đã chốt. Nhóm của asset lưu trong custom property `lpk_budget_group` trên root, chọn bằng dropdown ở panel; root chưa chọn nhóm nhận nhóm mặc định trong config. |
| Màu | `Color` attribute theo góc face và một material vertex color chung cho các prop v0.1. |
| Pivot | Root ở đáy giữa của asset theo local bounds. Bộ phận có thể có pivot riêng bằng origin của chính mesh, ví dụ đặt origin cánh tủ tại bản lề. Bản xuất giữ Empty gốc của asset và bỏ qua các Empty trung gian dùng làm pivot. |
| Export | `<export_dir>/props/<tên asset>.glb`. |
| Phạm vi tiếp theo | Nhân vật `CH_`, rig, animation, UV unwrap, texture và sculpt high-poly được xem xét riêng. |

## Luồng sử dụng trong v0.1

1. **Reference.** Chọn Front, Right hoặc Left, Back và Top tùy bộ ảnh. Chọn hướng nhìn, gốc căn và click hai điểm có khoảng cách thực đã biết trên mỗi ảnh, rồi nhập khoảng cách đó. Add-on đặt ảnh ở đúng hướng, căn scale và gom vào collection `REF`. Artist chỉnh opacity, khóa chọn và đổi nhanh giữa các view.
2. **Dựng hình.** Tạo một Empty làm asset root, ví dụ `PR_Barrel`, chọn nhóm budget và dựng mesh bằng công cụ Blender. Parent thân thùng, đai và nắp vào root. Panel hiển thị tên asset, nhóm budget và tổng tris của các mesh sẽ xuất.
3. **Tô màu.** Trong Edit Mode, chọn face và bấm một ô palette. Trong Object Mode, có thể tô toàn bộ object. Add-on tạo hoặc tái sử dụng attribute `Color` và material `M_VertexColor`.
4. **Kiểm tra.** Chọn root hoặc một object con, bấm **Kiểm tra asset** để xem Error, Warning và Info của cả asset. Dùng **Chọn** để tới object hoặc vùng mesh có vấn đề. Dùng **Sửa** với lỗi có bản sửa được hỗ trợ.
5. **Export Godot.** Add-on chạy lại checker với cùng tập object sẽ xuất, chặn khi còn Error rồi xuất một `.glb`. Artist có thể tiếp tục từ scene đang mở sau khi export.

## Tính năng v0.1

### Reference Setup

- Lưu hướng nhìn, mốc gốc và tỷ lệ riêng cho từng view. Khoảng cách mốc có thể dựa vào chiều cao, bề rộng hoặc chiều sâu đã biết, tùy view. Ví dụ, dùng chiều cao thật ở Front và Right, dùng bề rộng thật ở Top nếu hai mốc tương ứng nhìn thấy rõ.
- v0.1 chỉ đặt mốc tay: một modal operator nhận click trong view ortho và chiếu tọa độ lên mặt phẳng ảnh. Cách này hoạt động với mọi kiểu nền và padding. Đề xuất mốc tự động từ đường bao PNG để sau, dùng chung code tách đường bao với `measure.py` của Build Plan.
- Sau khi căn scale, artist có thể đánh dấu thêm hai đầu của mỗi chiều cần đối chiếu. Add-on đo khoảng cách theo trục tương ứng trên ảnh đã căn, bỏ qua phần padding. So chiều cao giữa Front, Back và các view bên (Right/Left), bề rộng giữa Front, Back và Top, chiều sâu giữa các view bên và Top. Chỉ đối chiếu từng cặp view khi cùng một chiều có số đo ở cả hai view và ít nhất một số đo đến từ cặp mốc độc lập với cặp mốc căn scale. Hiển thị **Chưa đo** cho view và chiều còn thiếu mốc, đồng thời chỉ ra các cặp số đo có chênh lệch tuyệt đối vượt dung sai tính bằng mét.
- Ảnh tham chiếu đặt sau geometry, hiển thị ở hướng nhìn tương ứng và có công tắc ẩn/hiện. Bộ ảnh dùng cho PoC cần là ảnh ortho của cùng một prop. Ảnh góc chéo có thể đi kèm để đọc cấu tạo.

### Dựng hình và tô màu

- Mỗi asset v0.1 dùng một Empty làm root. Toàn bộ hình học của asset nằm trên các mesh con. Root định danh asset, đặt pivot chung và xác định phạm vi checker/export. Cùng một bộ lọc chọn mesh được dùng để đếm tris, chạy checker và xuất file. Ảnh ref nằm ngoài phạm vi asset root.
- Quy tắc của bộ lọc: lấy mọi object con (đệ quy) của root có kiểu Mesh. Mesh đang ẩn trong viewport vẫn được tính và xuất, kèm Info để artist biết. Object con không phải mesh (curve, text, empty khác root) bị bỏ qua khi xuất và báo Warning để artist convert sang mesh hoặc gỡ khỏi root.
- Geometry gốc là nơi chọn face, cạnh hoặc vertex cần sửa. Triangle budget lấy trên mesh đã đánh giá với modifier tương ứng preset export.
- `Color` dùng miền `CORNER`, kiểu `BYTE_COLOR` để các face chung vertex có thể mang màu riêng. Checker xác nhận material thực sự dùng attribute này ở Base Color theo preset glTF. Palette dùng chung cho team và có ô màu tự do.

### Model Checker

| Kiểm tra | Mức mặc định | Cách xử lý |
| --- | --- | --- |
| Root thiếu, sai kiểu hoặc tên sai quy ước | Error | Chỉ ra root cần sửa. Nếu một Mesh đang làm root, hướng dẫn tạo Empty và parent cả cây mesh vào đó trước khi export. |
| Root có scale khác 1 hoặc có rotation | Error | Root phải có scale đơn vị và rotation bằng 0 trước khi chuẩn hóa vị trí cho bản xuất. Hướng dẫn chuyển transform xuống mesh con hoặc reset root. |
| Tổng tris vượt hard budget | Error | Hiện tổng của asset và số tris từng mesh để tìm phần nặng. |
| Tổng tris đạt 90% budget | Warning | Hiện số tris còn lại. |
| Thiếu `Color` hoặc liên kết Base Color sai chuẩn | Error | Cung cấp thao tác khởi tạo hoặc sửa material riêng, giữ màu đã có khi cấu trúc cho phép. |
| Pivot root lệch đáy giữa hoặc scene scale khác chuẩn | Warning | Chỉ rõ chênh lệch. Chỉnh pivot qua thao tác riêng và kiểm lại vị trí bộ phận. |
| Scale hoặc rotation còn trên mesh | Warning | Nêu object và modifier liên quan. Apply là thao tác riêng sau khi xem ảnh hưởng lên geometry, hệ trục và object con. |
| Mesh con có scale âm | Warning | Liệt kê object và các trục có scale âm. Khi kiểm tra thứ tự đỉnh của mặt trong glTF, xét dấu định thức của transform toàn cục, kể cả transform kế thừa từ cha. |
| Object con không phải mesh, mesh con đang ẩn | Warning / Info | Theo quy tắc của bộ lọc asset ở trên. |
| N-gon, vertex gần trùng, phần tử rời, mặt suy biến | Warning | Chọn vùng liên quan. Triangulate, merge, xóa hoặc dissolve chạy riêng khi phù hợp. |
| Normals thiếu nhất quán, cạnh nhiều hơn hai mặt hoặc biên hở | Warning | Chọn vùng liên quan. Biên hở có thể có chủ ý, đánh giá normals theo kiểu mesh. |
| Nhiều material hơn giới hạn | Warning | Liệt kê slot cần duyệt. Thay material là thao tác riêng. |
| Smooth shading, tên mesh data lệch tên object, asset chỉ có một màu | Info | Cho phép chỉnh khi phù hợp. Asset một màu có thể là thiết kế chủ ý. |

v0.1 không có nút **Sửa tất cả**: mỗi fix chạy riêng từ dòng lỗi của nó. Các thao tác đổi topology, màu, transform hay origin cần tác động rõ ràng và undo được. Cân nhắc thêm **Sửa tất cả** khi đã có đủ fix được kiểm thử là an toàn. Nếu geometry do modifier sinh ra gây lỗi, báo tên object hoặc modifier để artist biết nơi xử lý.

### Export Godot

- Export binary glTF với preset Y-up, modifier và vertex color. Checker và exporter dùng cùng danh sách mesh từ asset root, gồm mesh ẩn trong viewport. Bản xuất đặt pivot của root tại `(0, 0, 0)` dù root nằm ở vị trí nào trong Blender. Khi bỏ qua một Empty hoặc object trung gian khác, gắn mesh vào tổ tiên gần nhất còn trong bản xuất và giữ transform của mesh so với root, gồm pivot riêng của nó. Loại các object ngoài asset. Phục hồi cả transform, quan hệ cha–con, visibility, selection và mode nếu có thay đổi tạm, kể cả khi exporter báo lỗi.
- Tùy chọn **Gộp mesh khi export** (lưu trên root, mặc định tắt): bản xuất gộp toàn bộ mesh của asset thành một mesh `<tên root>_mesh` con của root, đã áp modifier và chuyển về hệ của root, giữ material và attribute `Color`. Scene trong Blender vẫn giữ từng part. Nên bật cho prop tĩnh nhiều part để giảm draw call trong Godot; không dùng khi cần pivot riêng của bộ phận (ví dụ cánh tủ mở được).
- Chạy checker trước khi ghi. Chặn Error, trình bày Warning để artist duyệt và thông báo đường dẫn file khi thành công. Dùng file `.blend` đã lưu nếu `export_dir` là đường dẫn tương đối theo project.
- Bài test Godot kiểm tra kích thước thực, trục hướng, pivot ở đáy và màu của hai mặt liền kề dùng cùng material. Dùng fixture có root đặt xa gốc Blender, mesh ẩn làm con của một Empty trung gian có transform và một prop khác nằm ngoài root. Đối chiếu danh sách mesh với checker, xác nhận file chứa mesh ẩn và loại Empty trung gian cùng prop ngoài root. Kiểm tra root ở gốc và mesh giữ vị trí, hướng, tỷ lệ và pivot tương đối sau khi đổi hệ trục.

### Team config

`team_config.json` chứa quy ước tên root, nhóm asset và budget, dung sai căn ảnh và khoảng cách merge, palette, material, color attribute và đường dẫn export. Lead có thể đặt file ở thư mục chung, mỗi máy chọn đường dẫn trong Preferences. Nạp lại khi mở Blender hoặc khi artist chọn **Reload Config**. Nếu file thiếu hoặc lỗi, báo lý do và ghi rõ bộ mặc định nào đang được dùng.

## PoC Build Plan

PoC giới hạn **2 tuần** và có **một người phụ trách** được chỉ định. Hết thời gian thì đánh giá bằng số liệu đang có, không kéo dài. Nếu chỉ có một dev, ưu tiên v0.1 và chạy PoC sau khi luồng Reference xong, vì PoC dùng lại phần căn ảnh.

Ưu tiên dựng và kiểm hai JSON viết tay cho Barrel và Terminal, sau đó chạy phép so sánh với plan từ chatbot. Trong PoC, artist có thể sửa JSON trong Text Editor rồi rebuild, hoặc dùng **Chỉnh part** để đổi tham số của part đang chọn qua hộp thoại (số cạnh, kích thước, hệ số profile, tham số gắn). Khi plan bị từ chối, **Copy lỗi cho chatbot** chép danh sách lỗi kèm JSON đã gửi để hỏi lại. Copy Prompt liệt kê các view đã nạp và view nào chưa căn scale, để artist đính kèm đủ ảnh. Kiểm thử lưu và mở lại `.blend`, giao diện chỉnh tham số riêng và đo profile tự động được xếp sau phép thử chính.

### Hợp đồng dữ liệu

JSON chứa đủ dữ liệu hình học để bộ dựng có thể tạo mesh. Trong PoC, artist xác nhận các số đo từ ảnh và cung cấp chúng khi viết plan hoặc chuẩn bị prompt. Schema có bản máy đọc được `buildplan.schema.json` (JSON Schema), dùng chung cho validator và gửi kèm mẫu prompt v1.

- `schema_version` định danh phiên bản schema. Mỗi phần có `id` duy nhất và ổn định, operation cụ thể và thông số theo operation.
- Schema v1 yêu cầu `units: "m"` cho cả JSON viết tay và JSON từ chatbot. Mọi chiều dài, tọa độ và khoảng dịch tính bằng mét. Góc tính bằng độ và hệ số nội suy `t` là số trong khoảng 0–1. Prompt ghi rõ các số đo và trục tương ứng đã xác nhận. Xem xét `relative` sau khi có quy tắc quy đổi theo từng trường và fixture kiểm chứng.
- `inferred: true` ở cấp part đánh dấu chi tiết khuất hoặc ước lượng. Preview tô màu riêng để artist biết cần duyệt.
- `baked` và `baked_params` là trường do add-on quản lý. JSON đầu vào của **Dán Plan** phải bỏ hai trường này. Trong Text Editor, JSON có thể thiếu chúng hoặc chứa giá trị do add-on đã ghi. Khi rebuild, add-on khôi phục trường thiếu từ object đã bake. Nếu giá trị được khai báo khác trạng thái trên object, hoặc part tự khai đã bake mà chưa có object đã bake tương ứng, báo lỗi theo ID và trường.
- Ba operation của PoC gồm `add_primitive` cho hộp hoặc trụ, `lathe_profile` cho thân tròn và `extrude_profile` cho mặt cắt đùn theo trục. Chưa cần Boolean, Bend, Array hay một DSL tổng quát.
- Part không có `attachment` đặt tại gốc root, theo hệ trục của root. Schema v1 cho phép đúng một part như vậy trong mỗi plan; các part khác phải gắn theo quy tắc.
- Bộ phận gắn theo phần khác khai báo ID cha và quy tắc gắn có cấu trúc. Validator kiểm tra ID trùng, tham chiếu thiếu hoặc vòng lặp, kích thước, `segments` thuộc tập cho phép, số part không gắn, ràng buộc kiểu cha/con của từng quy tắc, trường bị cấm (ví dụ `radius` khi quy tắc tự tính), `segment` nằm trong profile, `t` trong khoảng 0–1 và profile không tự cắt, trước khi tạo object. Báo lỗi theo ID và field để artist sửa ngay hoặc hỏi lại chatbot.

**Quy ước hình học**

| Operation | Tham số chính | Quy ước |
| --- | --- | --- |
| `add_primitive` | `shape` (`box` / `cylinder`), `size` hoặc `radius` + `height`, `segments` | Gốc local ở tâm đáy, trục cao là +Z local. |
| `lathe_profile` | `profile_z_radius`, `segments`, `caps` | Xoay quanh trục Z local. Profile là các cặp `[độ cao, bán kính]` tính từ đáy, độ cao tăng dần. `caps` là `"both"`, `"top"`, `"bottom"` hoặc `"none"`. |
| `extrude_profile` | `plane`, `profile`, `depth` hoặc `thickness_profile`, `caps` | `plane` là `"YZ"` (mặt cắt nhìn từ Right, đùn theo X), `"XZ"` (nhìn từ Front, đùn theo Y) hoặc `"XY"` (nhìn từ Top, đùn theo Z). Profile là đa giác kín, không tự cắt; mỗi điểm là cặp tọa độ theo thứ tự chữ của plane (`[y, z]`, `[x, z]` hoặc `[x, y]`). Chiều quay của điểm không bắt buộc: bộ dựng suy ra hướng ngoài từ diện tích có dấu và không đảo thứ tự điểm, nên chỉ số `segment` giữ nguyên. Đùn đối xứng hai phía mặt phẳng gốc. Khai báo đúng một trong hai: `depth` (bề dày không đổi) hoặc `thickness_profile` (các cặp `[vị trí, bề dày]` theo tọa độ thứ nhất của profile, nội suy tuyến tính, giữ giá trị ở hai đầu), để dựng thân thon từ hai ảnh: mặt cắt từ Right, bề dày từ Top. `section` (tùy chọn) chọn mặt cắt ngang: `box` (mặc định, hông phẳng), `diamond` (hình thoi, rộng nhất ở giữa chiều cao), `hexagon` (lục giác, lưng và bụng rộng bằng một nửa) hoặc `hull` (thân thuyền: rộng hết cỡ ở mặt trên, mạn thẳng xuống góc gãy ở `chine_height`, đáy rộng `bottom_ratio`; `bottom_ratio` = 0 là đáy chữ V). Với `diamond`/`hexagon`, mặt tứ giác không phẳng được chia theo đường chéo ngắn hơn để thân đối xứng tuyệt đối hai bên; thân được dựng bằng loft các mặt cắt tại mỗi vị trí điểm profile, nên profile phải đơn điệu theo tọa độ thứ nhất và part không nhận `profile_segment`. |

- Hướng của prop: mặt trước (mặt ảnh Front chụp) hướng về −Y, bên phải (ảnh Right) là +X.
- `"mirror": "X"` trên một part sinh thêm bản đối xứng qua mặt phẳng x = 0 của root, ID `<id>_mirror`. Bản đối xứng dùng matrix `Fx·M·Fx` với hình học đã lật và đảo chiều mặt, nên không có scale âm trong file xuất. Không part nào được gắn vào bản đối xứng, và ID `<id>_mirror` không được trùng ID khác.
- `segments` của khối tròn thuộc tập {4, 8, 12, 16, 24, 32}.
- Góc pha: tâm một mặt nằm trên −Y local, tức hướng Front. Vì số cạnh chia hết cho 4, view Right cũng nhìn thẳng vào một mặt, và các khối tròn cùng số cạnh có mặt thẳng hàng.
- Bán kính trong schema là **bán kính tới mặt**: khoảng cách từ trục đến tâm mỗi mặt phẳng. Nhờ góc pha trên, giá trị này bằng nửa bề rộng silhouette trên ảnh Front và Right, nên số đo từ ảnh ghi thẳng vào JSON. Bộ dựng tự tính bán kính tới đỉnh bằng `r / cos(180°/n)`.
- `height` trong quy tắc gắn là cao độ của **tâm** phần con, đo theo trục cao của phần cha.

**Quy tắc gắn** (`attachment.rule`)

| Rule | Tham số | Ý nghĩa |
| --- | --- | --- |
| `lathe_radius_at_height` | `parent_id`, `height`, `radial_offset` | Cha là `lathe_profile`, con là `add_primitive` cylinder cùng `segments` với cha và không khai báo `radius`. Phần con đồng trục với cha. Bán kính của con bằng bán kính lớn nhất của profile cha trên khoảng chiều cao mà con chiếm, cộng `radial_offset`, để không đầu nào của con chìm vào thân. Dùng cho đai, nắp, vành. |
| `profile_segment` | `parent_id`, `segment`, `t`, `normal_offset`, `align` | Cha là `extrude_profile`. `segment` là chỉ số từ 0, tính cả đoạn từ điểm cuối về điểm đầu. Lấy điểm theo `t` từ đầu đến cuối đoạn, tại giữa bề dày đùn, rồi dịch `normal_offset` theo pháp tuyến ngoài của mặt. Đặt gốc local của phần con tại điểm đó. Với `align: "surface"`, trục +X local của con theo chiều dương của trục đùn, +Z theo pháp tuyến ngoài và +Y = +Z × +X. |
| `box_face` | `parent_id`, `face`, `u`, `v`, `normal_offset`, `align` | Cha là `add_primitive` box. `face` là `+X`, `-X`, `+Y`, `-Y`, `+Z` hoặc `-Z`; `u`, `v` từ 0 đến 1 là vị trí trên mặt. +Z local của con theo pháp tuyến ngoài của mặt, gốc local của con đặt tại điểm (u, v) dịch `normal_offset`. Trục u/v của mặt: `+Z` (u +X, v +Y), `-Z` (u +X, v −Y), `-Y` (u +X, v +Z), `+Y` (u −X, v +Z), `+X` (u +Y, v +Z), `-X` (u −Y, v +Z). Dùng cho chân ghế, tựa lưng, tay cầm. |
| `body_surface` | `parent_id`, `a`, `b`, `side`, `normal_offset`, `align`, `rotation` (tùy chọn) | Cha là `extrude_profile` (mọi `section`). `side` `+`/`-`: từ điểm (a, b) trên mặt phẳng giữa, bắn tia theo trục đùn tới mạn; `top`/`bottom`: từ điểm (a, b) ở vị trí ngang `s`, bắn tia theo trục thứ hai của profile tới mặt trên (boong) hoặc mặt dưới. Gốc local của con đặt tại điểm chạm gốc local của con đặt tại điểm chạm dịch `normal_offset`. +Z theo pháp tuyến mặt, +X dọc thân theo chiều tọa độ thứ nhất tăng, `rotation` (Euler XYZ, độ) xoay thêm trong hệ đó. (a, b) phải nằm trong profile. Dùng cho mắt, vây ngực, mang, tay cầm; kết hợp `mirror` cho chi tiết hai bên. Cha đã bake thì tia bắn vào hình dựng lại từ snapshot. |
| `offset` | `parent_id`, `position`, `rotation` | Vị trí (mét) và góc Euler XYZ (độ) trong hệ local của cha, với mọi kiểu cha. Dùng khi các quy tắc trên không phù hợp. |

**Kiểm tra tiếp xúc.** Sau khi dựng, add-on cảnh báo (không chặn) khi một part không chạm part cha và cũng không chạm part nào khác trong asset (ví dụ thanh ngang tựa trên hai chân khung, cầu thang nối boong với mái thì không bị cảnh báo). Hai part được coi là chạm nhau khi có đỉnh nằm trong hoặc cách mặt part kia dưới 1 mm, hoặc có cạnh cắt mặt của part kia. Cách kiểm cạnh cắt mặt bắt được cả trường hợp đai ôm quanh thân. Add-on cũng cảnh báo `normal_offset` dương ở các quy tắc gắn lên mặt, vì gốc của primitive là tâm đáy nên giá trị dương làm part rời khỏi mặt. Cảnh báo hiện theo dòng trong JSON và được **Copy lỗi cho chatbot** chép kèm.

Ví dụ rút gọn với hai phần của `PR_Barrel`. Bán kính trong profile là bán kính tới mặt, đo trực tiếp từ nửa bề rộng thân trên ảnh Front. Đai đặc trong PoC là khối đại diện, bán kính lấy từ tiết diện lớn nhất của thân trong khoảng chiều cao của đai, cộng khoảng nhô.

```json
{
  "schema_version": 1,
  "asset_name": "PR_Barrel",
  "units": "m",
  "parts": [
    {
      "id": "body",
      "op": "lathe_profile",
      "segments": 8,
      "caps": "both",
      "profile_z_radius": [[0.0, 0.26], [0.45, 0.31], [0.90, 0.26]]
    },
    {
      "id": "upper_band",
      "op": "add_primitive",
      "shape": "cylinder",
      "segments": 8,
      "height": 0.05,
      "inferred": false,
      "attachment": {
        "parent_id": "body",
        "rule": "lathe_radius_at_height",
        "height": 0.72,
        "radial_offset": 0.015
      }
    }
  ]
}
```

Ví dụ rút gọn với hai phần của `PR_Terminal`. Thân là mặt cắt Right đùn theo X, đoạn 3 là mặt nghiêng phía trước. Tâm đáy bàn phím đặt giữa mặt nghiêng. Cạnh `0.40 m` chạy theo trục đùn, cạnh `0.12 m` chạy dọc mặt nghiêng và chiều dày `0.02 m` hướng ra ngoài.

```json
{
  "schema_version": 1,
  "asset_name": "PR_Terminal",
  "units": "m",
  "parts": [
    {
      "id": "body",
      "op": "extrude_profile",
      "plane": "YZ",
      "depth": 0.50,
      "caps": "both",
      "profile": [[-0.20, 0.0], [0.20, 0.0], [0.20, 0.45], [-0.05, 0.45], [-0.20, 0.30]]
    },
    {
      "id": "keyboard",
      "op": "add_primitive",
      "shape": "box",
      "size": [0.40, 0.12, 0.02],
      "attachment": {
        "parent_id": "body",
        "rule": "profile_segment",
        "segment": 3,
        "t": 0.5,
        "normal_offset": 0.0,
        "align": "surface"
      }
    }
  ]
}
```

### Lưu plan và rebuild

- Plan lưu trong Text datablock `<tên root>.buildplan.json`. Root giữ tên datablock trong custom property `lpk_build_plan`, mỗi object sinh ra mang `lpk_part_id`.
- **Dán Plan** và **Rebuild** từ Text Editor dùng chung quy trình dưới đây. Nội dung artist đang sửa là bản nháp cho tới khi dựng thành công.

1. Đọc bản nháp, kiểm tra cấu trúc đầu vào và tính duy nhất của part ID. Trong phạm vi root, xác định object gốc của từng ID bằng tham chiếu object đã lưu từ lần dựng thành công trong phiên. Tham chiếu vẫn nhận diện được bản gốc sau khi đổi tên. Nếu nhiều object mang cùng ID và chưa xác định được bản gốc, dừng trước khi sửa mesh hoặc gỡ property, liệt kê các object để artist xử lý. Tên object chỉ dùng để hiển thị.
2. Với mỗi ID còn tồn tại và đã bake, lấy operation, thông số và quan hệ gắn đã lưu khi bake để lập plan dùng cho lần dựng. Khôi phục `baked` và `baked_params` theo trạng thái của object, báo các thay đổi trong bản nháp bị bỏ qua. Kiểm tra lại toàn bộ plan sau bước ghép, gồm kiểu cha/con, tham chiếu, chu trình và các ràng buộc hình học. Nếu liên kết sai, báo ID con, ID cha và trường liên quan.
3. Dựng thử các preview cần cập nhật. Chỉ khi toàn bộ bước dựng thành công mới cập nhật scene, bảng tham chiếu object và Text datablock. Khi có lỗi, giữ bản dựng đã thành công gần nhất. Nếu artist đang sửa trong Text Editor, giữ bản nháp và vị trí lỗi để họ sửa tiếp.
4. Khi áp dụng kết quả, cập nhật preview còn ID, dọn preview có ID bị xóa và xử lý đổi ID như xóa ID cũ rồi thêm ID mới. Với part đã bake bị xóa khỏi plan, giữ mesh trong asset, gỡ thông tin quản lý Build Plan và báo cho artist. Với bản sao đã xác định được object gốc, cũng gỡ thông tin quản lý khỏi bản sao. Các mesh đã gỡ liên kết vẫn thuộc phạm vi checker và export khi còn nằm dưới root.

### Bake

- Bake đánh dấu part `baked: true` và lưu snapshot gồm operation, thông số hình học, quan hệ gắn và hệ trục của part so với root lúc bake. Add-on ghi snapshot vào `baked_params` và lưu bản đối chiếu trên object. Object giữ mesh hiện tại, rebuild không ghi đè.
- Phần con gắn vào phần đã bake tiếp tục đọc `baked_params` của cha và dùng gốc của cha tại thời điểm bake để dựng lại. Nếu artist sửa hình phần cha trong Edit Mode sau khi bake, điểm gắn vẫn tính từ snapshot. Hiển thị lưu ý khi bake để artist biết lúc nào cần bake phần con hoặc chỉnh tay.
- Thao tác bỏ bake chưa có trong PoC.

### Trải nghiệm và phép thử

1. Chạy bộ dựng bằng JSON viết tay, dùng ảnh Front, Right, Top của `PR_Barrel` và `PR_Terminal`. Terminal dùng mặt cắt Right để dựng thân và gắn bàn phím lên mặt nghiêng.
2. Thử cùng bộ ảnh với JSON từ ChatGPT hoặc Claude. **Copy Prompt** cung cấp schema, danh mục thao tác và số đo đã xác nhận, artist gửi prompt với ảnh đã được phép dùng, rồi **Dán Plan** vào add-on. Có thể chuẩn bị prompt từ mẫu và dán JSON vào Text Editor để chạy phép thử trước khi có các nút trên. Add-on hoạt động offline.
3. Dựng preview từng phần, chiếu đường bao model trở lại các view đã căn và đánh dấu chi tiết ước lượng. Chỉnh bán kính thân Barrel để kiểm tra đai cập nhật theo. Với Terminal, kiểm tâm đáy bàn phím và hướng của cả ba trục theo quy tắc gắn.
4. Với mỗi prop, chạy ít nhất hai lượt so sánh theo cặp. Trong mỗi lượt, cùng một artist thực hiện cả hai luồng từ scene có cùng bộ ảnh đã căn, dùng cùng danh sách bộ phận bắt buộc và tiêu chí duyệt. Đảo thứ tự hai luồng giữa các lượt. Ghi thời gian, số thông số đã chỉnh, phần còn thiếu và sai số đường bao theo từng view.

5. Với luồng chatbot, lead duyệt bản preview dựng từ JSON trước khi bake hoặc chỉnh mesh tay. Dùng chính bản preview đó để đo đường bao, chốt thời gian và số thông số đã chỉnh. Nếu phải chỉnh mesh tay mới đủ điều kiện duyệt, ghi lượt đó là chưa đạt. Sau khi ghi kết quả, artist có thể bake, chỉnh trong Edit Mode hoặc gộp mesh để bàn giao.

**Cách đo**

- **Thời gian.** Bắt đầu khi artist mở scene đã căn ảnh và nhận yêu cầu dựng. Dừng ở lần đầu có blockout được lead duyệt. Luồng chatbot tính cả chuẩn bị prompt, gửi ảnh, chờ phản hồi, gửi lại yêu cầu, dán, dựng và chỉnh. Mỗi cặp lượt tính tỷ lệ tiết kiệm bằng `(thời gian dựng tay - thời gian dùng chatbot) / thời gian dựng tay`.
- **Đường bao.** Chuẩn bị một mask tham chiếu đã được lead duyệt cho mỗi view, có thể tạo tay trong PoC. Chiếu mesh trên cùng gốc, scale và lưới pixel đã căn. Với mỗi điểm trên đường bao của một mask, đo khoảng cách đến điểm gần nhất trên đường bao kia. Đo theo cả hai chiều, lấy khoảng cách lớn nhất và chia cho cạnh dài hơn của khung bao vật thể tham chiếu trong view đó. Dùng khung bao của vật thể để padding không ảnh hưởng kết quả. Mask của mesh có thể lấy bằng render Workbench nền trong suốt với camera ortho khớp gốc, scale và lưới pixel của view đã căn; tính khoảng cách đường bao bằng numpy vì Blender không đóng gói sẵn scipy.
- **Số thông số chỉnh.** Sau lần dựng thành công đầu tiên, đếm các trường giá trị khác nhau đã đổi trên toàn bộ các lần dựng tiếp theo, gồm thay đổi do yêu cầu chatbot làm lại. Định danh trường theo part ID và đường dẫn trong JSON, tính riêng từng thành phần vector hoặc điểm profile. Một trường sửa nhiều lần chỉ tính một lần. Khi thêm hoặc xóa part, tính các trường giá trị tương ứng của part đó. Các lần thử JSON lỗi trước lần dựng đầu tiên được tính vào thời gian.

**Mức chi tiết.** Copy Prompt có hai mức: **Blockout** (mặc định, khối chính và tỷ lệ) và **Chi tiết** kèm số tris mục tiêu (chấp nhận 70–130%), khi đó AI dùng profile nhiều điểm hơn, khối tròn 12–16 cạnh, tách chi tiết lặp lại (cột lan can, bậc thang) và khung viền thành part riêng. Schema chưa có vát cạnh. Phép thử PoC đo ở mức Blockout.

**Ngưỡng quyết định.** Lead xác nhận ngưỡng trước khi chạy. Đề xuất tích hợp Build Plan khi cả Barrel và Terminal có đủ lượt so sánh và trung vị tỷ lệ tiết kiệm của từng prop đạt ít nhất 30%. Mỗi lượt chatbot phải có blockout được duyệt, sai số đường bao tối đa 5% ở từng view và số thông số chỉnh nằm trong ngưỡng đã chốt (đề xuất 5). Hiệu chỉnh ngưỡng 5 thông số bằng hai plan viết tay trước khi lead chốt, vì cách đếm theo từng thành phần khiến một lần nắn profile có thể tốn 3–6 trường. Nếu hết hai tuần mà thiếu lượt hoặc còn lượt chưa được duyệt, ghi kết quả và lý do. Lead đánh giá từ dữ liệu đã thu được trong khung hai tuần.

## Lộ trình và tiêu chí nghiệm thu

| Mốc | Phạm vi | Điều kiện hoàn thành |
| --- | --- | --- |
| PoC Build Plan, tối đa 2 tuần, chạy song song v0.1 nếu đủ người | Barrel và Terminal, ba phép dựng, quy tắc gắn cho đai và bàn phím, schema v1 kèm `buildplan.schema.json`, mẫu prompt v1, preview, sửa JSON và rebuild, bake từng phần | JSON viết tay dựng ra mesh thực và khớp tỷ lệ các view. Kiểm được quan hệ phụ thuộc, kể cả sau khi bake phần cha, và cách rebuild xử lý part bị xóa. Báo cáo kết quả phép so sánh theo ngưỡng quyết định hoặc ghi rõ dữ liệu còn thiếu khi hết hai tuần. |
| v0.1 | Reference, dựng tay, palette, checker thiết yếu, config và export static prop | Hai bạn mới tự làm xong một prop từ ảnh ref đến `.glb` mà không cần senior thao tác hộ. Lead xác nhận kích thước, hướng, pivot, màu và đủ bộ phận trong Godot. |
| v0.2 | Cải thiện theo feedback v0.1. Ưu tiên primitive low-poly, preset Mirror/flat shade và tip. | Các lỗi trong bài dùng thử được xử lý. Build Plan vào sidebar khi PoC đạt ngưỡng quyết định. |
| Backlog | Contours theo cảm hứng RetopoFlow, collision cho prop, xuất Empty thành Node3D cho bản lề và điểm gắn, bỏ bake, preview Decimate, nhân vật và rig, shape key, batch export, báo cáo checker, tích hợp API | Đánh giá khi có asset và nhu cầu cụ thể. Với Decimate, thử silhouette, cạnh sắc và ranh giới vertex color trước khi đưa ra preset. |

## Kiến trúc và kiểm thử

- Một package Python với `blender_manifest.toml`, phân phối qua zip **Install from Disk** trước. Các module chính là `config.py`, `reference.py`, `modeling.py`, `coloring.py`, `checks.py`, `export.py` và `ui.py`. PoC thêm `buildplan.py` cho validator (đọc `buildplan.schema.json` cộng các ràng buộc ngữ nghĩa), bộ dựng bằng `bmesh` và quản lý plan trong phiên làm việc. Khi triển khai đo profile tự động và đề xuất mốc căn, dùng chung `measure.py` để tách đường bao và đọc pixel theo lô bằng `image.pixels.foreach_get`.
- Dùng chung bộ chọn phạm vi asset cho checker và export. Registry của checker chứa ID, severity, hàm kiểm tra, thao tác chọn và cờ an toàn (dự phòng cho **Sửa tất cả** sau này). Dùng mesh data hoặc `bmesh` cho check/fix, gọi operator cho các thao tác cần context như export hoặc chuyển mode.
- Dùng `blender -b` để kiểm ảnh có padding khác nhau, mốc đo bổ sung bị thiếu hoặc lệch dung sai, root nhiều mesh với modifier, mặt hở chủ ý, budget tổng vượt giới hạn, fix/undo và trạng thái scene sau khi export thất bại. Thử root có rotation hoặc scale khác chuẩn, mesh con có scale âm và fixture export có mesh ẩn dưới Empty trung gian. Thử schema với đơn vị sai, ID trùng, cha bị thiếu, tham chiếu vòng, `segment` ngoài profile, profile tự cắt, `segments` ngoài tập cho phép, hơn một part không gắn, quy tắc gắn sai kiểu cha/con, `radius` khai báo cùng `lathe_radius_at_height` và plan dán vào có trường do add-on quản lý. Thử rebuild khi xóa hoặc đổi ID của part preview, xóa part đã bake, sửa `baked_params` bằng tay, nhân bản object của một part, dán plan mới lên plan có part đã bake và khi lần dựng mới thất bại. Kiểm silhouette của khối tròn 8 cạnh trên view Front và Right khớp bán kính tới mặt trong JSON. Test UI trong Blender và smoke test file xuất trong Godot 4 trên phiên bản team đã chốt.
- Các bài test dưới đây bổ sung kết quả mong đợi cho các tình huống dễ làm sai hình học hoặc ghi đè mesh.

| Tình huống | Kết quả mong đợi |
| --- | --- |
| Thân thùng kiểu Mesh làm root, đai là con | Checker báo Error, export dừng trước khi ghi file. Sau khi parent cả thân và đai vào Empty root hợp lệ, chọn đai vẫn kiểm và xuất đủ hai mesh. |
| Hai mesh có scale `(-1, 1, 1)` và `(-1, -1, 1)`, cha có transform đơn vị | Checker chỉ đúng các trục âm của từng mesh. Dấu định thức toàn cục lần lượt là âm và dương. Với material bật backface culling, đối chiếu cùng một mặt từ phía ngoài và phía trong sau khi import vào Godot. Mặt ngoài phải hiển thị, mặt trong bị loại ở cả hai fixture. |
| Hai JSON mẫu ở trên | Đai Barrel trải từ Z = 0.695 đến 0.745 m, bán kính tới mặt xấp xỉ 0.29778 m theo nội suy tuyến tính của profile. Tâm đáy bàn phím Terminal ở `(0, -0.125, 0.375) m` trong hệ local của thân. Cạnh dài 0.40 m song song trục X của thân. |
| Bake thân Barrel, sửa một đỉnh trong Edit Mode, thay toàn bộ JSON bằng bản cùng ID thiếu các trường bake | Thử riêng qua **Dán Plan** và Text Editor. Cả hai lần rebuild đều khôi phục trạng thái bake và giữ tọa độ đỉnh artist đã sửa. |
| Giữ thân đã bake kiểu `lathe_profile`, dán plan mới dùng cùng ID cho thân Terminal và gắn bàn phím bằng `profile_segment` | Sau khi ghép snapshot, validator báo liên kết `keyboard → body` sai kiểu cha. Mesh, liên kết quản lý và bản dựng đã thành công vẫn nguyên vẹn. |
| Nhân bản một part, đổi tên bản gốc rồi đặt tên cũ cho bản sao | Rebuild vẫn nhận đúng bản gốc qua tham chiếu trong phiên. Khi bỏ tham chiếu để mô phỏng trường hợp mơ hồ, rebuild báo các object trùng ID và dừng trước khi sửa cả hai. |

- Tài liệu kỹ thuật tham khảo cho export và tối ưu mesh: [Blender 4.2 — glTF 2.0](https://docs.blender.org/manual/en/4.2/addons/import_export/scene_gltf2.html) · [Blender 4.2 — Decimate Modifier](https://docs.blender.org/manual/en/4.2/modeling/modifiers/generate/decimate.html) · [Godot — Available 3D formats](https://docs.godotengine.org/en/stable/tutorials/assets_pipeline/importing_3d_scenes/available_formats.html)

## Giả định triển khai

Các điểm spec chưa chốt được triển khai theo mặc định dưới đây. Lead có thể đổi; phần lớn chỉnh được trong `team_config.json`.

| Chủ đề | Mặc định |
| --- | --- |
| Profile đùn | Cặp tọa độ theo thứ tự chữ của plane, chiều quay tự do (xem Quy ước hình học). `caps` của extrude là `"both"` hoặc `"none"`; mặt cap được chia tam giác. |
| Lathe | Độ cao tăng ngặt. Điểm có bán kính 0 thu về một đỉnh. Khoảng chiều cao của phần gắn nằm ngoài profile cha là lỗi. |
| Trường bắt buộc | `align` chỉ nhận `"surface"`. `align`, `radial_offset`, `normal_offset` bắt buộc trong schema v1. |
| Bake | Transform của object đã bake cũng được đóng băng. Snapshot có dạng `{op, params, attachment, matrix_root}`. |
| Part sinh ra | Parent phẳng dưới root. **Dán Plan** khi chưa có root thì tạo root từ `asset_name`; `asset_name` khác tên root là lỗi. Part `inferred` được đánh dấu bằng object color, không đụng attribute `Color`. Màu mặc định ghi vào `Color` là xám nhạt. |
| Reference | Mốc gốc là click thứ ba, sau hai điểm căn scale. Khoảng cách đo theo trục đã chọn. Có thể dùng đồng thời Right và Left. |
| Tìm root | Từ object đang chọn, lấy tổ tiên gần nhất (kể cả chính nó) là Empty có tên khớp quy ước. Không có thì lấy tổ tiên cao nhất để báo lỗi root. |
| Team config | Thêm dung sai pivot, số material tối đa (1), tỷ lệ Warning (0.9), override severity. Quy ước tên là regex, palette là mã hex sRGB. Thiếu key dùng mặc định từng key; file không hợp lệ dùng mặc định cả file. |
| Material | Hợp lệ khi Base Color của Principled BSDF nối trực tiếp từ node Color Attribute có `layer_name = "Color"`. Không bắt buộc tên `M_VertexColor`. Slot rỗng là Warning. "Giữ màu đã có" là quy đổi màu Base Color của material cũ và attribute POINT/FLOAT sang `Color` CORNER/BYTE. |
| Normals, merge | Winding được kiểm mọi nơi; kiểm normal hướng vào trong chỉ với mesh kín manifold. Khoảng cách merge tính trong không gian local. |
| Đo PoC | Mask theo kênh alpha, đường bao 4-láng giềng. Số thông số chỉnh là hợp các trường đổi giữa các lần dựng liên tiếp, không tính trường chuỗi và `inferred`. |
| Prompt | Tiếng Việt; số đo lấy từ các mốc Reference đã xác nhận. |

## Việc cần chốt trước khi bắt đầu

- [ ] Lead chọn chuẩn tên root, danh sách nhóm budget và nhóm mặc định, palette và dung sai căn ảnh.
- [ ] Lead duyệt ngưỡng quyết định của PoC (30% thời gian, 5% đường bao, tối đa 5 thông số đã hiệu chỉnh bằng plan viết tay) trước khi chạy thử so sánh.
- [ ] Chỉ định người phụ trách PoC và ngày bắt đầu khung 2 tuần.
- [ ] Chốt phiên bản Blender/Godot dùng để nghiệm thu và UI tiếng Việt với thuật ngữ Blender bằng tiếng Anh.
- [ ] Chuẩn bị hai bộ ảnh ortho cho Barrel và Terminal, kèm kích thước thật, mốc căn và mask tham chiếu đã duyệt cho từng view. Dùng ảnh team cho phép gửi nếu thử qua chatbot.
- [ ] Chạy hai plan viết tay trước, sau đó ghi kết quả các lượt so sánh chatbot và dựng tay theo cặp.
- [ ] Mời hai artist mới chạy luồng v0.1 và duyệt file trong Godot trước khi chốt phạm vi bản tiếp theo.
