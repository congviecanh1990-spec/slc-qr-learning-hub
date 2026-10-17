# Cập nhật Web App v3.6 trên Render

1. Giải nén bộ mã nguồn v3.6.
2. Upload toàn bộ file/thư mục bên trong vào repository GitHub hiện tại `slc-qr-learning-hub` và Commit.
3. Render đang bật Auto-Deploy sẽ tự build/deploy. Chờ `Live` / `Deploy succeeded`.
4. Mở Web App và nhấn `Ctrl + F5`.
5. Kiểm tra **Kho video học liệu**: tên playlist không còn hiển thị mã kỹ thuật `PL...`.
6. Kiểm tra **Mã QR động**: phần mô tả học phần hiển thị số video/QR và số playlist/tên playlist/QR.
7. Với tài khoản quản trị, vào **Đánh giá nghiệm thu** → **Mã định danh giảng viên** → cấp mã GV cho từng giảng viên.
8. Đăng nhập bằng tài khoản giảng viên để kiểm tra Mã GV đã hiển thị trên giao diện.
9. Tại **Mã QR động**, bấm **Mở thử**: phải vào thẳng trang học liệu, có thông báo chế độ xem thử và không hiện form Mã GV/SV.
10. Dùng trình duyệt chưa đăng nhập Web App hoặc điện thoại của sinh viên quét QR: trang công khai phải hiện **Mã sinh viên + Lớp**, không yêu cầu đăng nhập.

## Dữ liệu
- Không cần xóa PostgreSQL hiện tại.
- v3.6 tự bổ sung cột `users.lecturer_code` để lưu Mã GV do quản trị viên cấp.
- Dữ liệu video, playlist, học phần, lớp, QR và lịch sử quét/xem hiện có được giữ nguyên.
