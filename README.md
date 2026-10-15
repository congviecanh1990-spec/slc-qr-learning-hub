# TẠO MÃ QR TỰ ĐỘNG TỪ VIDEO YOUTUBE — v2.5

Ứng dụng web phục vụ đề tài tại **Trường Cao đẳng Sơn La**.

## Nhóm tác giả
Nguyễn Thị Thúy Tươi; Hoàng Thị Nhất; Nguyễn Thu Huyền; Tường Thị Phương Thảo; Nguyễn Hữu Thọ.

## Các chức năng chính
- Giao diện tiếng Việt, có logo Trường Cao đẳng Sơn La.
- Bỏ tên hiển thị “SLC QR Learning Hub”.
- “YouTube & Hub/WebSub” được đổi thành giao diện dễ hiểu: **Kết nối và đồng bộ kênh YouTube**.
- Có **Kho video học liệu**; giảng viên tích chọn nhiều video và gán hàng loạt vào học phần.
- Quan hệ Video ↔ Học phần là nhiều–nhiều thông qua bảng `course_videos`.
- Tạo mã QR động hàng loạt theo học phần: chỉ tạo cho video chưa có mã, chống tạo trùng.
- Tên mã QR tự lấy theo tên video YouTube.
- QR chốt theo mẫu chính thức: **mã đen trên nền trắng, mức sửa lỗi H, logo Trường Cao đẳng Sơn La ở giữa và có viền trắng tròn bảo vệ logo**.
- Tải PNG từng mã; tải ZIP theo học phần; tải ZIP toàn bộ.
- Focus Viewer, trang nhận diện GV/SV và trang lỗi học liệu đều có logo trường.
- Giữ nguyên theo dõi lượt quét, phiên xem, thống kê, nghiệm thu, sao lưu/khôi phục.

## Luồng sử dụng chính
1. Đăng nhập bằng Google.
2. Vào **Kênh YouTube** → **Đồng bộ dữ liệu từ YouTube**.
3. Vào **Kho video học liệu** → chọn nhiều video → chọn học phần → **Gán video đã chọn vào học phần**.
4. Vào **Học phần** hoặc **Mã QR động** → bấm **Tạo mã QR cho tất cả video chưa có mã**.
5. Tải PNG/ZIP. QR đã tạo là QR động nên có thể đổi video đích mà không phải phát hành lại mã.

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
