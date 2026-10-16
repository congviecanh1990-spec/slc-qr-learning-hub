# Cập nhật v3.1

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


## Kiểm tra riêng sau khi deploy v3.1
1. Vào **Đánh giá nghiệm thu** → **Hiệu quả quy trình**.
2. Trường **Nhiệm vụ đối chứng** phải là danh sách chọn, không còn ô tự gõ mã.
3. Danh sách phải có 4 nhiệm vụ chuẩn: Đồng bộ YouTube, Gán video vào học phần, Tạo QR hàng loạt, Tạo một QR riêng.
4. Bảng **Danh mục nhiệm vụ đối chứng cần thực hiện** phải hiển thị trạng thái dữ liệu của từng nhiệm vụ.
5. Dữ liệu cũ có mã không chuẩn vẫn được giữ trong PostgreSQL nhưng không được dùng cho bảng so sánh chuẩn v3.1.
