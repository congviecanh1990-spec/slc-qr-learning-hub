# Cập nhật v3.0 trên Render

1. Giải nén bộ mã nguồn v3.0.
2. Upload toàn bộ nội dung vào repository GitHub hiện tại `slc-qr-learning-hub` và Commit.
3. Render đang bật Auto-Deploy sẽ tự build/deploy lại. Chờ trạng thái `Live` / `Deploy succeeded`.
4. Mở Web App, nhấn Ctrl+F5.
5. Đăng nhập tài khoản Quản trị viên -> `Đánh giá nghiệm thu`.
6. Kiểm tra 3 khối mới: `Kết quả kiểm thử tự động`, `Hiệu quả quy trình`, `Khảo sát người dùng`.
7. Sử dụng thử các chức năng thật (đăng nhập, đồng bộ YouTube, gán video, tạo QR...) rồi quay lại Đánh giá nghiệm thu để xem log tự động.
8. Nhập dữ liệu đối chứng thủ công với mã nhiệm vụ trùng mã Web App, ví dụ `TAO_QR_HANG_LOAT`.
9. Dán liên kết Google Form khảo sát GV, Google Form khảo sát SV và Google Sheets kết quả vào phần `Cấu hình liên kết khảo sát`.

Không cần xóa PostgreSQL. `db.create_all()` sẽ tạo bảng mới `research_settings`; schema `functional_test_runs` được nâng cấp tự động trên PostgreSQL.
