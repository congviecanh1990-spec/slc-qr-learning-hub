# TẠO MÃ QR TỰ ĐỘNG TỪ VIDEO YOUTUBE — v2.1

Ứng dụng web phục vụ đề tài tại **Trường Cao đẳng Sơn La**.

## Nhóm tác giả
Nguyễn Thị Thúy Tươi; Hoàng Thị Nhất; Nguyễn Thu Huyền; Tường Thị Phương Thảo; Nguyễn Hữu Thọ.

## Điểm mới của v2.1
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
