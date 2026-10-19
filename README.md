# BỔ SUNG v4.3.5 — Giao diện thống kê, QR và nghiệm thu

- **Thống kê khai thác:** hiển thị “Tên sinh viên (Mã)” với ba chữ số cuối mã SV, tên học liệu số; bỏ cột mã QR. Bộ lọc chọn học liệu bằng tên, không cho lọc tự do theo mã sinh viên. Bảng phiên xem lấy tên video thực tế, kể cả khi phát từ playlist. Mã SV đầy đủ vẫn lưu trong CSDL và vẫn dùng để đối chiếu.
- **Mã QR động:** số lượng playlist/QR hiển thị dạng số nguyên tự nhiên; chuẩn hóa nhãn nút; kho mã QR dạng bảng gồm học liệu, loại, môn học, trạng thái, ngày tạo và thao tác. Các hành động đổi video đích, mở thử và xóa QR vẫn giữ nguyên nghiệp vụ.
- **Giảng viên:** bỏ ghi chú dài về xóa GV; đổi nút chuẩn hóa dữ liệu dùng chung thành “Lưu”.
- **Đánh giá nghiệm thu:** giản lược lời dẫn; tăng chữ ở bốn ô tổng hợp; bảng kết quả tự ghi 10 dòng/trang, phân trang số, lọc thời gian/chức năng/kết quả và tìm tên người thực hiện/học liệu. Tổng hợp số liệu trên toàn bộ bản ghi khớp bộ lọc. Mã SV trên giao diện chỉ còn ba chữ số cuối; dữ liệu gốc không thay đổi.
- Bản này **không thêm cột hay bảng PostgreSQL**.

---

# BỔ SUNG v4.3.4 — Sửa nguồn video lẫn từ kênh YouTube khác

- Khi đồng bộ YouTube, xác định kênh **thực sự đăng tải** theo trường `snippet.channelId` của YouTube Data API, không coi video xuất hiện trong playlist là video của chủ playlist.
- Kho video học liệu, bộ chọn tạo QR và các chỉ số số video chỉ tính video đã xác minh thuộc các kênh giảng viên thực sự kết nối. Video của kênh thứ hai đã kết nối hợp lệ vẫn được sử dụng.
- Video bị nhập nhầm trước đây sẽ không còn xuất hiện sau khi triển khai và đồng bộ lại. Các liên kết playlist-video không hợp lệ được tự loại khỏi playlist; bản ghi video, mã QR, lịch sử quét/xem **không bị xóa**.
- Mã QR video cũ liên quan đến video sai nguồn được đánh dấu cần rà soát nếu gắn với môn học; không tự ngừng hoạt động hoặc thay đích.
- Thêm cột PostgreSQL `videos.uploader_channel_id` (tự cập nhật schema khi Web App khởi động). **Không xóa database**. Các video cũ chỉ có thông tin kiểm chứng sau khi bấm **Đồng bộ lại**.
- Kiểm thử độc lập tại `tests/test_youtube_playlist_ownership.py` (chạy không cần OAuth/DB).

---

# Bổ sung v4.3.1 — hiệu chỉnh giao diện và bổ sung lớp đang dạy

- Trang **Lớp chủ nhiệm** bỏ các câu giải thích dài đã được yêu cầu loại bỏ; giữ các thao tác Excel, thêm SV, sửa tên, trạng thái và xóa nhập nhầm.
- Trang **Kênh YouTube** thay mô tả kết nối thêm kênh thành: **“Liên kết với tài khoản Google khác để tích hợp thêm video học liệu”**.
- Thanh menu có trạng thái chọn **độc lập** cho Lớp chủ nhiệm, Danh sách lớp đang dạy và Quản lý lớp; Kho video học liệu vẫn dùng trạng thái riêng.
- Trang **Danh sách lớp đang dạy** có thêm biểu mẫu chọn môn học/mô đun đang phụ trách, chọn lớp đã lưu hoặc nhập lớp mới. Khi lớp chưa có danh sách sinh viên, GV bộ môn được tải tệp Excel hoặc thêm SV ban đầu trực tiếp trong trang này. Khi lớp đã có SV, chỉ GVCN được tiếp tục cập nhật.
- Không đổi cấu trúc cơ sở dữ liệu PostgreSQL; nâng cấp trực tiếp từ v4.3.0, không yêu cầu xóa dữ liệu hoặc tạo lại mã GV/lớp.

---

# TẠO MÃ QR TỰ ĐỘNG TỪ VIDEO YOUTUBE — v4.1

## Điểm mới v4.1
- Với tài khoản giảng viên kiêm GVCN, menu **Lớp chủ nhiệm** được đưa lên vị trí thứ 2, ngay sau **Kênh YouTube**.
- Trong **Lớp chủ nhiệm**, bỏ dòng hướng dẫn và tiêu đề cột “Xóa nhập nhầm”; chức năng xóa sinh viên nhập sai vẫn được giữ dưới cột **Thao tác**.
- Trong **Đánh giá nghiệm thu**, các mục tiêu 100% hiển thị trực tiếp **100%**, không có dấu “=” phía trước.
- Đổi chỉ tiêu **Số đơn vị/khoa/bộ môn** thành **Số bộ môn** và đếm theo tên bộ môn duy nhất của các môn học/mô đun thực nghiệm.
- Chỉ tiêu **Số giảng viên tham gia** hiển thị mục tiêu **>= 3 (GV CN khác CNTT: >= 1)**; số thực tế theo dạng `5 (2)`, trong đó số trong ngoặc là giảng viên thuộc nhóm chuyên môn khác CNTT.
- Giao diện **Giảng viên** bổ sung trường **Nhóm chuyên môn** (Công nghệ thông tin / Khác CNTT) để quản trị viên xác định chính xác số liệu trong ngoặc của chỉ tiêu nghiệm thu.


## Bổ sung v3.9.2
- GVCN có thể xóa một sinh viên bị nhập nhầm/nhập thừa khỏi chính lớp mình chủ nhiệm.
- Khi xóa, hệ thống đồng thời xóa lượt quét, phiên xem và sự kiện xem phát sinh của sinh viên đó trong lớp, nên các thống kê được tính lại theo dữ liệu còn lại.
- Nếu sinh viên không còn thuộc lớp nào khác, hồ sơ sinh viên và dữ liệu nhận diện cũ còn sót lại cũng được xóa.
- Nút Xóa được tách rõ khỏi chức năng Thay đổi trạng thái; bảo lưu/nghỉ học/chuyển lớp phải dùng thay đổi trạng thái để bảo toàn lịch sử.

# TẠO MÃ QR TỰ ĐỘNG TỪ VIDEO YOUTUBE — v3.7

Ứng dụng web phục vụ đề tài tại **Trường Cao đẳng Sơn La**.

## Điểm mới v3.7
- **Lớp và sinh viên được quản lý dùng chung toàn hệ thống**, không tạo lại danh sách theo từng học phần.
- Quản trị viên tạo lớp và giao **giảng viên chủ nhiệm (GVCN)**; GVCN quản lý danh sách sinh viên của lớp mình.
- Mã sinh viên dùng **đúng mã do Nhà trường cấp**, không sinh thêm mã nội bộ cho sinh viên.
- GVCN có thể tải danh sách ban đầu hoặc bổ sung nhiều sinh viên bằng Excel; có thể thêm một sinh viên riêng lẻ.
- Khi sinh viên bảo lưu, nghỉ học, chuyển trường/chuyển lớp..., GVCN chỉ thay đổi trạng thái và **ngày có hiệu lực**; dữ liệu lịch sử trước đó không bị sửa.
- Lịch sử lớp lưu theo khoảng thời gian, nhờ đó lượt quét cũ vẫn giữ đúng lớp tại thời điểm phát sinh, còn sĩ số hiện tại thay đổi theo biến động mới.
- Giảng viên bộ môn chỉ chọn lớp dùng chung cho học phần; không tải lại danh sách sinh viên.
- Sinh viên quét QR **nhập tên lớp và chọn họ tên kèm mã SV** từ danh sách SV đang học của lớp đó. Hệ thống kiểm tra quan hệ lớp–môn học/mô đun của QR trước khi ghi lượt quét; mỗi lượt mở QR của SV cần xác nhận lại danh tính để tránh nhầm trên thiết bị dùng chung.
- Giao diện **Quản lý học phần** được thu gọn: chỉ giữ số video/QR, playlist/QR, số lớp và khu vực chọn lớp áp dụng.
- Giao diện **Mã QR động** đưa hai chức năng tạo QR một video/một playlist xuống khu vực **Tạo QR riêng lẻ**; quy trình chính ưu tiên tạo theo học phần.
- Thông báo đăng nhập và lỗi quyền truy cập được chuẩn hóa bằng tiếng Việt; tài khoản giảng viên truy cập nhầm trang quản trị được đưa về giao diện phù hợp thay vì hiện trang lỗi 403 thô.
- Sao lưu/khôi phục bổ sung dữ liệu lớp dùng chung, sinh viên, lịch sử biến động và liên kết lớp-học phần.

## Nhóm tác giả
Nguyễn Thị Thúy Tươi (Chủ nhiệm đề tài); Hoàng Thị Nhất; Nguyễn Thu Huyền; Tường Thị Phương Thảo; Nguyễn Hữu Thọ.

## Điểm mới v3.6
- **Kho video học liệu:** bỏ mã kỹ thuật YouTube (dạng `PL...`) hiển thị dưới tên playlist; giảng viên chỉ thấy tên playlist cần dùng.
- **Mã QR động:** mỗi học phần hiển thị rõ số video, số QR video đã có/chưa có; dòng playlist hiển thị số lượng kèm tên playlist và số QR playlist đã có/chưa có.
- Nút **Mở thử** chuyển sang chế độ xem thử dành cho giảng viên: không yêu cầu nhập mã GV/SV và không ghi lượt quét/thời lượng xem vào thống kê.
- Bổ sung **Mã GV thực nghiệm** cho tài khoản giảng viên. Quản trị viên cấp mã tại trang **Đánh giá nghiệm thu**; sau khi cấp, mã hiển thị trên giao diện khi giảng viên đăng nhập.
- Khi giảng viên đã đăng nhập và thực sự quét QR, hệ thống tự dùng Mã GV đã cấp, không yêu cầu nhập lại.
- Sinh viên **không cần đăng nhập Web App**. Khi quét QR do giảng viên cung cấp, sinh viên chỉ nhập **Mã sinh viên do Nhà trường cấp**; hệ thống tự xác định lớp theo dữ liệu GVCN và thời điểm quét.
- Trang nhận diện công khai không yêu cầu chọn vai trò hoặc chọn lớp; luồng công khai mặc định là sinh viên.
- PostgreSQL được nâng cấp nhẹ bằng cột `users.lecturer_code`; dữ liệu hiện có được giữ nguyên.

## Các chức năng chính
- Giao diện tiếng Việt, có logo Trường Cao đẳng Sơn La.
- Bỏ tên hiển thị “SLC QR Learning Hub”.
- “YouTube & Hub/WebSub” được đổi thành giao diện dễ hiểu: **Kết nối và đồng bộ kênh YouTube**.
- Có **Kho video học liệu**; giảng viên có thể lọc video theo playlist, xem playlist của từng video, chọn nhiều video hoặc nhiều playlist và gán trực tiếp vào học phần.
- Quan hệ Video ↔ Học phần là nhiều–nhiều thông qua bảng `course_videos`.
- Tạo mã QR động hàng loạt theo học phần: chỉ tạo cho video chưa có mã, chống tạo trùng.
- Tên mã QR tự lấy theo tên video YouTube.
- QR chốt theo mẫu chính thức: **mã đen trên nền trắng, mức sửa lỗi H, logo Trường Cao đẳng Sơn La ở giữa và có viền trắng tròn bảo vệ logo**.
- Tải PNG từng mã; tải ZIP theo học phần; tải ZIP toàn bộ.
- Focus Viewer, trang nhận diện GV/SV và trang lỗi học liệu đều có logo trường.
- Giữ nguyên theo dõi lượt quét, phiên xem, thống kê, nghiệm thu, sao lưu/khôi phục.

## Luồng sử dụng chính
1. Đăng nhập bằng Google.
2. Vào **Học phần** để tạo/kiểm tra học phần cần sử dụng.
3. Vào **Kênh YouTube** → **Đồng bộ dữ liệu từ YouTube** khi cần cập nhật học liệu.
4. Vào **Kho video học liệu** → lọc theo playlist nếu cần → chọn video hoặc playlist → chọn học phần → gán vào học phần.
5. Vào **Học phần** hoặc **Mã QR động** → tạo QR cho video/playlist chưa có mã.
6. Tải PNG/ZIP. QR đã tạo là QR động nên có thể cập nhật đích mà không phải phát hành lại mã.




## Điểm mới v3.5.1
- Hiệu chỉnh nội dung **Hướng dẫn gán học liệu vào học phần** trong Kho video học liệu theo nội dung đã chốt:
  - Nếu kênh YouTube đã tổ chức video theo playlist, ưu tiên gán playlist cho học phần; các video trong playlist tự động được gán vào học phần tương ứng.
  - Nếu không muốn gán toàn bộ video trong playlist cho học phần, chọn từng video cần sử dụng và gán video đó vào học phần tương ứng.
- Không thay đổi logic, cơ sở dữ liệu hoặc schema PostgreSQL của v3.5.

## Điểm mới v3.5
- Trong **Kho video học liệu**, phần **Danh sách playlist** được đưa lên trước **Danh sách video** để giảng viên ưu tiên phân loại học liệu theo playlist.
- Bổ sung khung hướng dẫn ngắn: nếu kênh YouTube đã tổ chức video theo playlist thì gán playlist cho học phần; nếu không muốn dùng cả playlist hoặc video chưa thuộc playlist phù hợp thì chọn video riêng và gán cho học phần.
- Cột **Học phần áp dụng** của từng playlist chuyển từ danh sách checkbox hiển thị thường trực sang **danh sách thả xuống chọn nhiều học phần**. Giao diện không còn kéo dài khi có nhiều học phần.
- Bộ chọn hiển thị số học phần đã chọn; giảng viên có thể mở lại danh sách, bỏ học phần cũ, chọn học phần mới và bấm **Lưu** để hiệu chỉnh.
- Không thay đổi cơ chế dữ liệu v3.4: video trong playlist tự kế thừa các học phần của playlist; video gán riêng vẫn được giữ theo quy tắc an toàn.
- Không thay đổi schema PostgreSQL.

## Điểm mới v3.4
- **Học phần** được đưa lên vị trí thứ 2 trên menu, ngay sau **Kênh YouTube**.
- **Kho video học liệu** bổ sung bộ lọc **Playlist** cho danh sách video.
- Mỗi video hiển thị các playlist đang chứa video đó.
- Bổ sung khu vực **Danh sách playlist** ngay trong Kho video học liệu.
- Có thể tìm kiếm playlist, lọc playlist đã/chưa gán học phần, chọn nhiều playlist và gán trực tiếp vào học phần.
- Không thay đổi schema PostgreSQL.

## Nâng cấp từ v1.0 trên Render
Bản v2.1 kế thừa cấu trúc dữ liệu của v2.0; các bảng dữ liệu cũ được giữ nguyên. Khi Web Service khởi động, `db.create_all()` sẽ tự tạo bảng mới nếu `AUTO_CREATE_DB=1`.

Các biến môi trường cũ tiếp tục dùng:
- `DATABASE_URL`
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `ADMIN_EMAILS`
- `SECRET_KEY`
- `RECONCILE_KEY`
- `COMPLETION_THRESHOLD`
- `HEARTBEAT_SECONDS`
- `COOKIE_SECURE`
- `AUTO_CREATE_DB`

Không đưa `.env` hoặc Client Secret lên GitHub.

## Logo thương hiệu
Logo chính thức nằm tại:

`static/branding/logo_truong.png`

Logo được dùng cho header, trang đăng nhập, Focus Viewer, trang nhận diện người học và mã QR.

## Cấu trúc chính
- `app.py`: route, gán video vào học phần, tạo QR hàng loạt, QR có logo.
- `models.py`: mô hình dữ liệu; v2.0 có thêm `CourseVideo` / `course_videos`.
- `templates/`: giao diện tiếng Việt.
- `static/app.css`: nhận diện giao diện.
- `static/branding/logo_truong.png`: logo trường.
- `static/viewer.js`: theo dõi trạng thái xem bằng YouTube IFrame Player API.
- `render.yaml`: triển khai Render + PostgreSQL.

## Kiểm tra sau khi deploy
- `/health` phải trả trạng thái database `ok`.
- Đăng nhập Google thành công.
- Đồng bộ được video.
- Tạo được học phần.
- Chọn nhiều video và gán vào học phần.
- Tạo QR hàng loạt, bấm lần hai không sinh QR trùng.
- PNG tải về có logo trường và quét được.
- Mở QR → nhận diện GV/SV → Focus Viewer.
- Đổi video đích nhưng slug/QR không đổi.
- Lịch sử quét và quá trình xem xuất CSV được.

## Lưu ý dữ liệu nghiên cứu
Thời lượng xem là giá trị ước tính từ trạng thái trình phát. Không dùng log xem để khẳng định mức độ chú ý, mức độ hiểu bài hoặc kết quả học tập.


## Mẫu QR chính thức v2.1
- Mã QR màu đen, nền trắng.
- Error correction H.
- Logo trường đặt chính giữa, kích thước khoảng 23% chiều rộng ảnh QR.
- Có vòng trắng mỏng quanh logo.
- PNG/ZIP và QR tạo hàng loạt đều gọi chung một hàm sinh QR để bảo đảm đồng nhất.

## Hiệu chỉnh v2.2
- Tên mã QR và tên tệp PNG luôn đúng bằng **tên video YouTube**, giữ nguyên tiếng Việt có dấu; không thêm mã học phần/slug.
- Tạo mã hàng loạt từ trang **Quản lý mã QR động** giữ nguyên tại trang này, không chuyển sang trang Học phần.
- Trang xem video thay thông tin kỹ thuật bằng nhắc nhở người học xem đầy đủ, không tua nhanh/bỏ qua hướng dẫn.
- Footer: **Sản phẩm nghiên cứu khoa học cấp trường phục vụ giảng dạy**.
- Trang chờ đăng nhập bỏ dòng tên trường bị lặp và giữ tiêu đề **TẠO MÃ QR TỰ ĐỘNG TỪ VIDEO YOUTUBE** trên một dòng.

## Hiệu chỉnh v2.3
- **Mã học phần được hệ thống tự động sinh**, giảng viên không còn phải nhập mã. Khi tạo mới, chỉ nhập **Tên học phần** và **Tên khoa/bộ môn**.
- Tên học phần không dùng danh sách gợi ý từ dữ liệu đã nhập trước; trường nhập được đặt `autocomplete=off` và đổi tên trường dữ liệu để hạn chế lịch sử gợi ý cũ của trình duyệt.
- **Tên khoa/bộ môn vẫn được gợi ý từ các dữ liệu đã dùng trước đây** để giảng viên có thể chọn lại nhanh mà không phải gõ lại.
- **Mã lớp được hệ thống tự động sinh**; khi thêm lớp, giảng viên chỉ nhập **Tên lớp**.
- Các mã tự động được tạo từ ID nội bộ của cơ sở dữ liệu theo dạng `HPxxxxxx` và `Lxxxxxx`, bảo đảm ổn định và tránh trùng khi nhiều giảng viên cùng sử dụng.
- Giao diện thường ngày ưu tiên hiển thị **tên học phần** và **tên lớp**, giảm thuật ngữ kỹ thuật không cần thiết đối với giảng viên không chuyên CNTT.
- Không thay đổi cấu trúc bảng dữ liệu, nên có thể cập nhật trực tiếp từ v2.2 lên Render mà không xóa PostgreSQL hiện tại.

## Hiệu chỉnh v2.4 — Chính sách quyền riêng tư
- Bổ sung trang công khai `/privacy` dạng HTML cho ứng dụng.
- Công bố rõ dữ liệu Google/YouTube được truy cập, dữ liệu hệ thống lưu, mục đích sử dụng, nguyên tắc chia sẻ, bảo vệ, lưu giữ và quyền của người dùng.
- Công bố phạm vi `youtube.readonly`: chỉ đọc dữ liệu kênh/video, không đăng/sửa/xóa video.
- Nêu rõ token OAuth được mã hóa trước khi lưu và lịch sử quét không lưu IP thô.
- Bổ sung cam kết tuân thủ Google API Services User Data Policy và Limited Use.
- Thêm liên kết **Chính sách quyền riêng tư** tại trang đăng nhập và footer toàn hệ thống để người dùng truy cập dễ dàng.
- URL dùng để điền trong Google Auth Platform sau khi deploy: `https://<ten-mien-cua-web-app>/privacy`.

## Hiệu chỉnh v2.5 — phân quyền giảng viên, khoa/bộ môn và menu đang chọn
- Tài khoản không nằm trong `ADMIN_EMAILS` luôn được xác định là **Giảng viên** khi đăng nhập. Tài khoản giảng viên chỉ đồng bộ kênh/video của chính họ; chỉ quản lý học phần, QR và thống kê thuộc dữ liệu họ phụ trách.
- Các chức năng quản trị/nghiệm thu (**Đánh giá nghiệm thu, Nhật ký lỗi, Sao lưu dữ liệu, Khôi phục dữ liệu**) chỉ hiển thị và cho phép truy cập với tài khoản **Quản trị viên**.
- Trang **Học phần** tách rõ **Tên khoa** và **Bộ môn quản lý học phần** để hỗ trợ thực nghiệm với giảng viên thuộc nhiều chuyên ngành/bộ môn, kể cả nhiều bộ môn trong cùng một khoa.
- `courses` có thêm `faculty_name` và `department_name`. Khi deploy lên PostgreSQL hiện có, ứng dụng tự bổ sung cột và giữ nguyên dữ liệu cũ; giá trị `unit_name` cũ được bảo toàn và dùng để khởi tạo tên khoa nếu có.
- Học phần cũ thiếu bộ môn có cảnh báo và biểu mẫu cập nhật ngay tại thẻ học phần.
- Chỉ tiêu **Số đơn vị/khoa/bộ môn** trong trang nghiệm thu tính theo tổ hợp **Khoa + Bộ môn**, vì vậy nhiều bộ môn trong cùng một khoa được ghi nhận riêng.
- Thanh menu làm nổi bật chức năng đang mở bằng **chữ đậm, màu đỏ**; các chức năng khác giữ định dạng bình thường.

## Hiệu chỉnh v2.6 — nhãn đậm, xóa dữ liệu an toàn và xử lý video YouTube bị xóa
- Toàn bộ nhãn trường nhập/chọn (`form-label`) được hiển thị **chữ đậm** để giảng viên dễ nhận biết.
- Form tạo học phần đổi thứ tự thành **Tên học phần → Bộ môn quản lý học phần → Tên khoa**; bỏ các dòng giải thích dài về gợi ý tên khoa/bộ môn.
- Khi giảng viên bấm đồng bộ YouTube, hệ thống đồng thời **đối soát lại trạng thái toàn bộ video đã biết** để phát hiện video bị xóa, chuyển riêng tư hoặc tắt khả năng nhúng.
- Nếu video đích của QR không còn sử dụng được, **QR không bị đổi**. Giao diện đánh dấu “QR cần đổi video”; giảng viên chọn video thay thế và QR cũ tiếp tục hoạt động mà không phải in lại.
- Bổ sung nút **Xóa mã QR**. Việc xóa thực hiện theo kiểu ngừng sử dụng (soft delete), QR cũ không còn mở được nhưng lịch sử quét/xem vẫn được giữ để phục vụ nghiên cứu.
- Bổ sung **Xóa học phần khỏi danh sách**. Học phần được ẩn khỏi nghiệp vụ thường ngày nhưng dữ liệu lịch sử và QR đã phát hành được bảo toàn.
- Bổ sung xóa lớp theo kiểu ẩn khỏi danh sách; dữ liệu lịch sử vẫn giữ nguyên. Bảng `class_groups` được tự động bổ sung cột `active` khi deploy lên PostgreSQL hiện có.


## Hiệu chỉnh v2.8 — hướng dẫn đăng nhập thử nghiệm và tinh gọn footer
- Bổ sung khung **Lưu ý khi đăng nhập thử nghiệm** ngay dưới nút **Đăng nhập bằng Google**, hướng dẫn xử lý màn hình “Google chưa xác minh ứng dụng này” trong giai đoạn thử nghiệm.
- Khung hướng dẫn nêu rõ ứng dụng chỉ dùng quyền đọc dữ liệu kênh/video YouTube, không đăng, sửa hoặc xóa video.
- Footer bỏ hai dòng lặp lại **TẠO MÃ QR TỰ ĐỘNG TỪ VIDEO YOUTUBE** và **Trường Cao đẳng Sơn La**.
- Nhóm tác giả hiển thị đậm; bổ sung **Nguyễn Thị Thúy Tươi (Chủ nhiệm đề tài)**.
- Dòng **Sản phẩm nghiên cứu khoa học cấp trường phục vụ giảng dạy** được hiển thị chữ nghiêng.


## Bổ sung v2.8
- Nút **Tạo một mã QR riêng** được đưa lên đầu trang Quản lý mã QR động và mở/đóng form tạo QR riêng.
- Thêm nút **Xóa toàn bộ mã QR đã tạo** cho tài khoản hiện tại; QR ngừng hoạt động nhưng lịch sử quét/xem vẫn được giữ.
- Thêm nút quản trị **Xóa toàn bộ dữ liệu đã lưu** ở trang Tổng quan để làm sạch dữ liệu thử nghiệm; thao tác xóa toàn bộ dữ liệu trong DB và yêu cầu đăng nhập lại, nhưng không xóa cấu hình Render/Google OAuth.
- Trang chờ đăng nhập bỏ khối Nhóm tác giả ở giữa; thông tin tác giả chỉ còn ở cuối giao diện.
- Khung lưu ý đăng nhập thử nghiệm chuyển sang nền xanh nhạt.

## Hiệu chỉnh v2.8.2

- Đưa **Tỷ lệ phiên xem hoàn thành** lên cùng hàng với các thẻ thống kê Video học liệu, Học phần, Mã QR, Lượt quét và Phiên xem video.
- Bảng **Lượt quét gần đây** hiển thị toàn chiều rộng giao diện Tổng quan.
- Bỏ dòng hướng dẫn “Giảng viên chỉ cần nhập...” ở giao diện Quản lý học phần.
- Bỏ khối thông tin “Xử lý khi video YouTube bị xóa...” ở giao diện Quản lý mã QR động; chức năng kỹ thuật xử lý QR động vẫn giữ nguyên.

## Hiệu chỉnh v2.9 — Gộp sao lưu và khôi phục dữ liệu

- Gộp hai chức năng quản trị thành một menu **Sao lưu & khôi phục**.
- Giao diện mới hiển thị song song khối **Sao lưu dữ liệu** và **Khôi phục dữ liệu**.
- Khối sao lưu cho phép tạo/tải tệp ZIP và hiển thị nhanh số video, học phần, QR đang dùng và lượt quét đã lưu.
- Khôi phục dùng cụm từ xác nhận tiếng Việt **KHÔI PHỤC** thay cho `RESTORE`.
- Nút khôi phục chỉ được bật khi đã chọn tệp ZIP và nhập đúng cụm từ xác nhận.
- Có hộp xác nhận cuối cùng trước khi thay thế dữ liệu hiện tại.
- Liên kết `/admin/restore` cũ được giữ để chuyển hướng sang giao diện mới.
- Chức năng chỉ hiển thị và hoạt động với tài khoản Quản trị viên.

## v3.0 - Đánh giá nghiệm thu theo dữ liệu thật

- Bỏ nhập thủ công từng ca kiểm thử. Hệ thống tự ghi bằng chứng từ các hoạt động thật: đăng nhập Google, đồng bộ YouTube, gán video vào học phần, tạo QR, quét QR, đổi video đích, sao lưu và khôi phục.
- Phép đo phía Web App được ghi tự động; quản trị viên chỉ nhập số liệu quy trình thủ công để làm đối chứng cùng mã nhiệm vụ.
- So sánh hiệu quả chỉ tính trên các nhiệm vụ có dữ liệu ở cả hai phía (thủ công và Web App).
- Bỏ nhập từng phiếu khảo sát trong Web App. Khảo sát dùng Google Forms và Google Sheets; trang Đánh giá nghiệm thu chỉ lưu/liên kết các URL khảo sát và bảng kết quả.
- Bổ sung bảng `research_settings`; backup cũ không có bảng này vẫn được hỗ trợ khôi phục.


## Cập nhật v3.1 — nhiệm vụ đối chứng chuẩn hóa
- Trường nhiệm vụ đối chứng chuyển sang danh sách chọn thay vì tự gõ mã để tránh sai mã.
- Từ v3.4, thiết kế nghiên cứu được chốt chỉ dùng **2 nhiệm vụ đối chứng**: tạo QR riêng và tạo QR hàng loạt; các hoạt động đồng bộ/gán học liệu thuộc nhóm kiểm thử tự động.

## Cập nhật v3.4 — Playlist theo học phần và QR playlist động
- Đồng bộ cả **playlist do giảng viên tạo** và danh sách video thuộc từng playlist từ YouTube; sau mỗi lần đồng bộ, video mới/gỡ khỏi playlist được cập nhật trong Web App.
- Bổ sung quan hệ **Học phần ↔ Playlist ↔ Video** bằng bảng `course_playlists`; cùng một playlist có thể được gán cho nhiều học phần và mỗi học phần có QR playlist riêng để thống kê đúng ngữ cảnh.
- Trong **Quản lý học phần**, giảng viên có thể gán/bỏ gán playlist, xem số video trong playlist và trạng thái QR playlist.
- Trong **Mã QR động**, bổ sung **Tạo một mã QR playlist** và **Tạo QR cho tất cả playlist của học phần**. Tên QR/tệp PNG giữ đúng tên playlist tiếng Việt có dấu.
- QR playlist dẫn tới trang xem riêng của Web App, không dẫn thẳng sang YouTube. Trang xem hiển thị danh sách video và phát bằng `youtube-nocookie`; video không còn khả dụng được tự bỏ qua.
- Khi playlist thêm/gỡ video, sau đồng bộ YouTube **QR playlist cũ tự phản ánh nội dung mới, không phải in lại QR**. Nếu playlist bị xóa/không còn khả dụng, QR được giữ và hiển thị thông báo phù hợp.
- Lịch sử quét QR playlist và quá trình xem từng video trong playlist tiếp tục được ghi nhận vào thống kê của học phần.
- Phần **Đánh giá nghiệm thu** chỉ còn **2 nhiệm vụ đối chứng chuẩn**: `TAO_QR_RIENG` và `TAO_QR_HANG_LOAT`. Đồng bộ YouTube, gán video/playlist và các chức năng khác vẫn được ghi ở **Kết quả kiểm thử tự động**, không dùng làm nhiệm vụ đối chứng thủ công.
- Backup/khôi phục bổ sung bảng `course_playlists` và các trường QR playlist; backup cũ chưa có bảng này vẫn được phép khôi phục.


## Bổ sung v3.4 - Gán playlist một lần, video tự theo học phần
- Mỗi playlist có danh sách **Học phần áp dụng** ngay trong Kho video học liệu.
- Có thể chọn đồng thời nhiều học phần cho một playlist rồi bấm **Lưu học phần cho playlist** một lần.
- Toàn bộ video hiện có trong playlist tự động được gán vào các học phần đã chọn; không cần gán lại từng video.
- Khi đồng bộ YouTube, video mới thêm vào playlist tự động được bổ sung vào các học phần đang dùng playlist.
- Khi bỏ một học phần khỏi playlist, các video chỉ được kế thừa từ playlist đó tự động được bỏ khỏi học phần; video đã gán riêng hoặc còn thuộc playlist khác vẫn được giữ.
- Vùng gán video riêng trong Kho video chỉ dùng cho video lẻ hoặc trường hợp đặc biệt.


## Cập nhật v3.9

- Bổ sung giao diện **Giảng viên** dành cho Quản trị viên: cấp mã định danh GV, xem họ tên, kênh YouTube, email, chức vụ và xóa giảng viên khỏi Web App.
- Chuyển chức năng cấp mã GV khỏi **Đánh giá nghiệm thu** sang giao diện **Giảng viên**.
- Xóa giảng viên sẽ xóa tài khoản/OAuth và toàn bộ dữ liệu nghiệp vụ, học phần, QR, lượt quét/xem, kiểm thử/thực nghiệm thuộc GV; lớp và sinh viên dùng chung được giữ lại và bỏ gán GVCN.
- Bỏ khối xóa dữ liệu riêng từng GV ở Tổng quan để tránh trùng chức năng.

## Cập nhật v3.8
- Giảng viên tự hiệu chỉnh họ tên hiển thị; tên đã sửa không bị ghi đè bởi tên Google ở lần đăng nhập sau.
- Mã lớp dùng chung được sinh tự động; quản trị viên chỉ nhập tên lớp và chọn GVCN theo họ tên + email.
- Tổng quan bổ sung số lượng giảng viên và số lượng lớp; bảng quét chỉ hiển thị sinh viên.
- Thống kê khai thác và tệp CSV tập trung vào dữ liệu sinh viên, bỏ cột vai trò và dữ liệu quét GV khỏi báo cáo giao diện.
- Quản trị viên có thể xóa dữ liệu nghiệp vụ/thử nghiệm của từng giảng viên.
- Xóa toàn bộ dữ liệu làm mới cả mã GV nhưng giữ phiên quản trị đang thao tác, không yêu cầu đăng nhập lại.

## Cập nhật v3.9.1
- Giao diện **Lớp & sinh viên** của Quản trị viên được tách khỏi giao diện **Lớp chủ nhiệm**.
- Quản trị viên chỉ tạo lớp, giao/hiệu chỉnh GVCN và xem danh sách lớp đã tạo.
- Không hiển thị danh sách sinh viên, tải Excel, thêm sinh viên hoặc thay đổi trạng thái sinh viên trên giao diện Quản trị viên.
- Cột **Sĩ số đang học** chỉ tính sinh viên có quan hệ lớp còn hiệu lực tại ngày hiện tại, tương ứng trạng thái **Đang học**.
- GVCN tiếp tục quản lý đầy đủ danh sách sinh viên và biến động lớp tại giao diện **Lớp chủ nhiệm**.


## Phiên bản 4.0
- Giao diện Quản trị viên đưa **Giảng viên** lên vị trí thứ 2 ngay sau **Kênh YouTube**.
- Đổi thuật ngữ giao diện **Học phần** thành **Môn học/ mô đun**; trang quản lý dùng các nhãn “Tên môn học/ mô đun”, “Bộ môn quản lý môn học/ mô đun”.
- Trang Đánh giá nghiệm thu bỏ cột **Mã ca**, bổ sung chỉ tiêu đăng nhập hệ thống 100%, đồng bộ video 100%, tối thiểu 3 giảng viên và 50 sinh viên tham gia.
- Nhật ký lỗi có cột **Thao tác** và **Môn học/ Mô đun**, không hiển thị tên mô-đun kỹ thuật nội bộ.
- Ô sửa họ tên GV không điền/gợi lại nội dung cũ; nút **Lưu họ tên** đặt ngay bên phải ô nhập.
- Xóa toàn bộ dữ liệu đặt lại bộ đếm mã nghiệp vụ: mã GV cấp lại từ GV0001, mã lớp từ L000001, mã môn học/ mô đun từ HP000001; vẫn giữ phiên quản trị hiện tại.


## Phiên bản 4.1.1
- Giao diện Lớp chủ nhiệm: tách hai thao tác thành hai cột **Lưu** và **Xóa**, căn giữa từng nút để bảng rõ ràng hơn.


## Cập nhật v4.2.0
- Khai báo họ tên đầy đủ, nhóm chuyên môn, GVCN, tên lớp và sĩ số dự kiến lần đầu; tạo mã GV/lớp tự động.
- Quản trị viên cũng là giảng viên; nếu là GVCN thì có trang Lớp chủ nhiệm và có mã GV.
- Sau đăng nhập, màn hình chờ tự đồng bộ YouTube; có nút vào hệ thống/thử lại.
- Thêm môn học/mô đun có thể chọn ngay lớp; danh sách môn học trình bày dạng bảng với bộ chọn nhiều lớp; số lượng không đệm 0.
- Sĩ số khai báo không thay thế số SV đang học (lấy từ danh sách SV GVCN tải Excel).
- Nâng schema thêm users.profile_completed và school_classes.declared_size; không xóa dữ liệu cũ.


## Bổ sung v4.3.0
- Quản trị viên là giảng viên và có thể chủ nhiệm; Tổng quan chuyển phạm vi dữ liệu của tôi/toàn hệ thống.
- Giữ tự đồng bộ khi đăng nhập, nút Đồng bộ lại chủ động; không tạo cron 6 giờ tính phí.
- Kết nối thêm một/một số tài khoản Google YouTube bằng OAuth riêng vào cùng hồ sơ GV, không đăng xuất.
- GV có thể chọn lớp có sẵn hoặc tạo lớp chưa có khi thêm môn học/mô đun; dữ liệu lớp dùng chung.
- GV bộ môn được nạp danh sách SV đầu tiên khi lớp chưa có SV; sau đó chỉ GVCN quản lý.
- Chuyển giao GVCN với ngày hiệu lực, không đổi mã lớp; lưu lịch sử bàn giao.
- Chỉnh sửa tên môn, bộ môn, khoa, tên lớp, họ tên SV (không đổi khóa định danh); quản trị viên chuẩn hóa danh mục khoa/bộ môn; lưu lịch sử chỉnh sửa.
- QR playlist tự cập nhật nội dung khi GV đồng bộ; QR video cảnh báo nếu bị mất liên hệ môn sau chuyển playlist; video riêng tư/xóa không phát; QR bị xóa mềm trả thông báo dừng sử dụng, không xóa lịch sử thống kê.
- Sao lưu hỗ trợ bảng kết nối bổ sung, lịch sử bàn giao GVCN, lịch sử hiệu chỉnh.
- Khi dùng tính năng kết nối YouTube khác, cấu hình Google OAuth redirect URI `/youtube/connect-callback` bên cạnh `/auth/callback`.


## Cập nhật v4.3.2 — Theo dõi nghiệm thu và sinh viên

- Bảng cuối mục 1 Đánh giá nghiệm thu: nhóm theo **Chức năng** (200 bản ghi mới nhất), cột **Người thực hiện** hiển thị tên GV (email) hoặc tên SV (mã SV - lớp).
- Lượt quét QR của SV được gắn mã SV + mã lớp ngay tại thời điểm quét, **không coi chủ sở hữu QR là người quét**. Minh chứng lượt quét hiển thị **tên video/playlist – tên môn học/mô đun**.
- Dữ liệu kiểm thử cũ không bị sửa. Nếu có một lượt quét khớp duy nhất với log cũ, hệ thống hiển thị danh tính SV; nếu thiếu thông tin hoặc không chắc chắn thì hiển thị rõ chưa xác định, không đoán.
- Thống kê khai thác: bỏ biểu đồ, giữ hai bảng lịch sử quét và phiên xem; bổ sung bộ lọc môn học/mô đun, lớp, QR, mã SV và tình trạng cần theo dõi.
- Bộ lọc **Chưa quét QR** lấy danh sách SV đang học đối chiếu với các lượt quét QR **thành công**. **Chưa hoàn thành video** dành cho SV đã quét thành công nhưng chưa xem đủ các video hiện khả dụng của QR (với playlist: xét từng video).
- Danh sách cần theo dõi phải chọn một lớp và một QR; số liệu lớp hiện hành không được dùng để tính ngược lịch sử quét các đợt trước.
- CSDL bổ sung 2 trường nullable vào nhật ký kiểm thử; nâng cấp tự động, không xóa PostgreSQL. Bản sao lưu tự chứa 2 trường mới nhờ cơ chế serialize tự động.


## Điểm mới v4.3.3
- Bỏ hoàn toàn khu vực **Thêm lớp đang dạy** và đường dẫn xử lý thêm lớp tại trang **Danh sách lớp đang dạy**. Việc chọn lớp đã có hoặc tạo lớp mới và liên kết với môn học/mô đun chỉ thực hiện tại trang **Môn học/Mô đun**.
- Trang Danh sách lớp đang dạy chỉ có bảng: mã lớp, tên lớp, các môn đang dạy, sĩ số đang học, và tải Excel danh sách ban đầu khi lớp chưa có sinh viên.
- Trang công khai sau khi SV quét QR: **nhập tên lớp từ danh sách gợi ý → chọn họ tên kèm mã SV → xem học liệu**. Tải danh sách tên SV đang học theo lớp được chọn, không yêu cầu đăng nhập Google hay gõ mã SV.
- Máy chủ xác thực lớp được gán cho môn học/mô đun và sinh viên còn thuộc lớp tại thời điểm quét; dữ liệu ghi log vẫn dùng mã SV Nhà trường và mã lớp. Bổ sung nút **Đổi sinh viên** trong trang xem; lượt mở QR mới trên cùng trình duyệt yêu cầu chọn lại để tránh nhầm lẫn.
- Quy trình chọn tên chỉ là nhận diện tự khai báo phục vụ thống kê, **không phải xác thực danh tính chắc chắn**. Người có mã QR có thể nhìn thấy tên/mã của SV được liệt kê trong lớp. Cần thông báo người học và cân nhắc quyền riêng tư khi đưa vào sử dụng chính thức.
- Không thay đổi cấu trúc PostgreSQL, có thể cập nhật từ v4.3.2 mà không xóa dữ liệu.

## Cập nhật v4.3.6 – Tập trung thống kê khai thác và nghiệm thu

- **Đánh giá nghiệm thu:** giữ nguyên bảng **Theo dõi chỉ tiêu và kết quả nghiệm thu** (mục tiêu – thực tế – kết quả). Xóa khu vực nhật ký kiểm thử bị trùng; đánh số lại **1. Hiệu quả quy trình** và **2. Khảo sát người dùng**. Có liên kết sang Thống kê khai thác để xem minh chứng.
- **Thống kê khai thác – mục 1:** nhật ký hoạt động tự động của giảng viên/quản trị viên, không liệt kê lượt quét QR hay xem video của SV. Có tổng hợp đạt/không đạt và bộ lọc thời gian, chức năng, kết quả, người thực hiện.
- **Thống kê khai thác – mục 2:** một bảng 8 cột: thời gian; tên SV (3 số cuối mã); lớp; MH/MĐ; tên học liệu số; kết quả quét; thời lượng xem; trạng thái xem. Khi mở QR playlist, hiển thị tên **video thực sự đã phát** ở mỗi dòng; nếu quét nhưng chưa phát sẽ hiển thị trạng thái Chưa xem. Một lượt quét playlist vẫn chỉ có một bản ghi gốc trong `scan_logs`; các dòng xem video tham chiếu lượt quét đó, không tạo thêm scan log.
- Hai mục sử dụng bộ lọc/phân trang **độc lập**, 10 dòng/trang, phân trang bằng số; chuyển trang giữ vị trí cuộn tại bảng tương ứng.
- Có lọc SV chưa quét/chưa hoàn thành theo danh sách SV đang học ở lớp và QR được giao, không dựa đơn thuần vào những bản ghi đã tồn tại. Các khoảng ngày lọc cũng được áp dụng khi đối chiếu nhóm chưa tham gia.
- Giữ đầy đủ mã SV trong PostgreSQL; chỉ rút gọn phần **hiển thị** còn ba số cuối. Các lượt quét, phiên xem, QR, dữ liệu nghiên cứu trước đó không bị xóa hoặc ghi đè.
- Không thêm dịch vụ trả phí, không thiết lập cron định kỳ. Chỉ tạo thêm **chỉ mục** trong cơ sở dữ liệu nếu chưa có để tăng tốc truy vấn nhật ký.
- Nhật ký kết quả hệ thống vẫn là bằng chứng hoạt động tự động; bảng theo dõi chỉ tiêu nghiệm thu giữ các tiêu chí và ngưỡng ban đầu. Số liệu kiểm thử thực tế không được tự tạo.

**Lưu ý kiểm thử:** Có kiểm tra cú pháp và mô phỏng ghép nhật ký bằng SQLAlchemy/SQLite. Chưa chạy kiểm thử tích hợp Google OAuth, YouTube API và PostgreSQL trên Render trong môi trường tạo gói; cần kiểm thử sau khi deploy.
