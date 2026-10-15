# Cập nhật v2.0 lên Render — hướng dẫn ngắn

1. Giữ nguyên Web Service và PostgreSQL đang chạy trên Render.
2. Thay mã nguồn repository GitHub bằng bộ v2.0 này; không đưa `.env` hoặc secret lên GitHub.
3. Kiểm tra có file `static/branding/logo_truong.png`.
4. Commit lên nhánh `main`.
5. Render đang Auto-Deploy sẽ tự build lại; nếu không, chọn **Manual Deploy → Deploy latest commit**.
6. Chờ trạng thái **Live**.
7. Mở `/health` để kiểm tra database.
8. Đăng nhập → Kênh YouTube → Đồng bộ → Kho video học liệu → gán video vào học phần → tạo QR hàng loạt.
9. Tải một PNG để kiểm tra QR có logo trường và dùng điện thoại quét thử.

Bản v2.0 bổ sung bảng `course_videos`; khi `AUTO_CREATE_DB=1`, bảng này được tạo tự động trong PostgreSQL hiện tại, không cần xóa database cũ.
