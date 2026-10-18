# HƯỚNG DẪN CẬP NHẬT WEB APP v4.3.3 TRÊN RENDER

Bản này kế thừa v4.3.2, **không xóa hoặc tạo lại PostgreSQL, không cần thay biến môi trường Google OAuth**.

1. Giữ bản ZIP v4.3.2 làm bản dự phòng và chủ động sao lưu dữ liệu qua chức năng **Sao lưu & khôi phục** trước khi cập nhật.
2. Giải nén ZIP v4.3.3; vào repository GitHub hiện có `congviecanh1990-spec/slc-qr-learning-hub`, nhánh `main`.
3. Dùng **Add file → Upload files**, tải các file/thư mục ở *gốc thư mục đã giải nén* lên; ghi đè các tệp tương ứng; kiểm tra đã có các thay đổi trong `app.py`, `templates/classes.html`, `templates/identify.html`, `templates/viewer.html`, `templates/playlist_viewer.html`, rồi **Commit changes**.
4. Vào Render để theo dõi triển khai tự động; chỉ thử nghiệm khi trạng thái **Live** và log không báo lỗi.
5. Mở tài khoản GV bộ môn: vào **Danh sách lớp đang dạy**; chỉ còn bảng các lớp, không có form “Thêm lớp đang dạy”. Thử tải Excel ban đầu ở lớp chưa có danh sách (nếu có quyền).
6. Vào **Môn học/Mô đun** và kiểm tra thao tác tạo/chọn lớp vẫn hoạt động.
7. Với mã QR đã gán môn và lớp có SV đang học: dùng trình duyệt ẩn danh quét QR, nhập tên lớp, chọn đúng họ tên (mã SV), xem học liệu. Kiểm tra nhật ký quét có mã SV và lớp đã chọn.
8. Thử quét cùng QR trên cùng trình duyệt một lần nữa và thử **Đổi sinh viên** để bảo đảm không tự dùng danh tính của SV trước.
9. Thử lớp không được gán với môn, SV bảo lưu/nghỉ học, QR không hoạt động: hệ thống không cho chọn người không hợp lệ và không ghi lượt xem thành công giả.

## Ghi chú về dữ liệu cá nhân
Việc hiển thị tên kèm mã SV theo danh sách lớp làm tăng khả năng lộ dữ liệu cho người có mã QR. Đây là cách nhận diện tự khai báo, không xác nhận người đang chọn thực sự là SV đó. Cần có thông báo cho sinh viên, đánh giá quyền riêng tư và cân nhắc biện pháp xác thực phù hợp trước khi áp dụng chính thức.

## Kiểm tra trước phát hành
Mã nguồn đã được kiểm tra cú pháp Python và cú pháp template Jinja; chưa được kiểm thử tích hợp Google OAuth, PostgreSQL, YouTube API trên Render trong môi trường đóng gói. Kết quả cuối cùng cần xác nhận sau triển khai.
