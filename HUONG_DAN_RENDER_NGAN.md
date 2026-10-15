# Cập nhật v2.3 lên Render — hướng dẫn ngắn

1. Giữ nguyên Web Service và PostgreSQL hiện tại trên Render.
2. Giải nén bộ v2.3 và upload toàn bộ mã nguồn lên repository GitHub đang dùng.
3. Không đưa `.env`, Client Secret hoặc token lên GitHub.
4. Commit lên nhánh `main`.
5. Render Auto-Deploy sẽ tự build lại; nếu không, chọn **Manual Deploy → Deploy latest commit**.
6. Chờ trạng thái **Live**.
7. Mở trang **Học phần** để kiểm tra: form chỉ còn **Tên học phần** và **Tên khoa/bộ môn**; mã học phần được tạo tự động.
8. Khi thêm lớp, form chỉ còn **Tên lớp**; mã lớp được tạo tự động.
9. Tên khoa/bộ môn đã dùng trước đây sẽ xuất hiện dưới dạng gợi ý để chọn lại nhanh.

Bản v2.3 không thay đổi cấu trúc database so với v2.2, vì vậy không cần xóa hoặc tạo lại PostgreSQL.
