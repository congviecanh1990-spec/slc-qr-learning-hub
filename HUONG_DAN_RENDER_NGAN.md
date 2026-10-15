# Cập nhật v2.5 lên Render — hướng dẫn ngắn

1. Giữ nguyên Web Service và PostgreSQL hiện tại trên Render.
2. Giải nén bộ v2.5 và upload toàn bộ mã nguồn lên repository GitHub đang dùng.
3. Không đưa `.env`, Client Secret hoặc token lên GitHub.
4. Commit lên nhánh `main`.
5. Render Auto-Deploy sẽ tự build lại; nếu không, chọn **Manual Deploy → Deploy latest commit**.
6. Chờ trạng thái **Live**.
7. Khi ứng dụng khởi động, hệ thống tự bổ sung hai cột `faculty_name` và `department_name` vào bảng `courses`; không xóa PostgreSQL hiện tại.
8. Đăng nhập bằng tài khoản giảng viên: chỉ thấy/khai thác kênh YouTube, video, học phần, QR và thống kê thuộc dữ liệu của chính tài khoản đó.
9. Đăng nhập bằng tài khoản có email trong `ADMIN_EMAILS`: có thêm **Đánh giá nghiệm thu**, **Nhật ký lỗi**, **Sao lưu dữ liệu**, **Khôi phục dữ liệu**.
10. Mở **Học phần** để kiểm tra form gồm: **Tên học phần**, **Tên khoa**, **Bộ môn quản lý học phần**; mã học phần vẫn tự sinh. Học phần cũ có thể cập nhật khoa/bộ môn ngay trên thẻ học phần.
11. Chức năng đang mở trên thanh menu phải hiển thị **chữ đậm và màu đỏ**.

Không cần tạo lại database hoặc OAuth client.
