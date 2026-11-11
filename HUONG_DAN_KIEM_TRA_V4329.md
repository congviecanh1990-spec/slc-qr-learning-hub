# Hướng dẫn kiểm tra Web App v4.3.29 – Thao tác playlist hàng loạt

## 1. Nội dung cập nhật

Bản này kế thừa v4.3.28. **Giữ nguyên giao diện và các nút riêng của từng playlist**, đồng thời bổ sung khu vực thao tác hàng loạt ngay dưới bộ lọc tại **Kho video học liệu → 1. Danh sách playlist**:

- **Chọn môn học/mô đun:** Chỉ liệt kê môn đang hoạt động do giảng viên phụ trách.
- **Gán tất cả playlist đã lọc:** Gán **thêm** môn đã chọn cho **tất cả playlist khớp bộ lọc đã áp dụng, trên mọi trang phân trang**. Bỏ qua playlist không còn khả dụng. **Không xóa các môn khác đang gán cho playlist**. Sau thao tác, các video thuộc playlist tự được liên kết với môn.
- **Tạo QR cho tất cả playlist của môn:** Tạo QR cho tất cả playlist đang gán môn đã chọn, **không phụ thuộc vào bộ lọc hiện tại**. Chỉ tạo mới khi playlist còn khả dụng và có ít nhất một video có thể phát; giữ nguyên QR hoạt động đã phát hành. Playlist trống, video riêng tư/không cho nhúng và playlist không khả dụng được bỏ qua.

Hai nút **hoạt động độc lập**. Người dùng có thể tạo QR riêng lẻ như trước. Hộp thoại xác nhận nêu rõ phạm vi trước khi thực hiện, tránh thao tác nhầm. Bộ lọc được xử lý ở phía máy chủ theo quyền của tài khoản hiện tại; không cho phép gán hoặc tạo QR vào môn/kênh của người khác.

## 2. Kiểm tra trên Render

**Trước triển khai:** Sao lưu PostgreSQL, lưu mã nguồn đang chạy, giữ nguyên `DATABASE_URL`, Google OAuth, `SECRET_KEY` và `AUTO_CREATE_DB=1`.

**Tình huống A – Gán theo bộ lọc qua nhiều trang**
1. Đăng nhập giảng viên có từ 6 playlist trở lên, vào **Kho video học liệu**.
2. Chọn bộ lọc **Chưa gán môn học/mô đun**, bấm **Lọc playlist**, ghi lại tổng số kết quả (>5).
3. Chọn một môn học, bấm **Gán tất cả playlist đã lọc**, xác nhận.
4. Kiểm tra mục **Đã gán**: mọi playlist thuộc kết quả cũ ở tất cả các trang phải được gán; bộ lọc **Chưa gán** không còn liệt kê chúng. Các playlist không khớp điều kiện lọc phải giữ nguyên.
5. Kiểm tra playlist từng có môn khác: môn cũ phải còn nguyên.

**Tình huống B – Tạo QR tất cả playlist của môn**
1. Ở mục **Danh sách playlist**, chọn môn đã được gán các playlist.
2. Bấm **Tạo QR cho tất cả playlist của môn**, xác nhận. Kể cả khi đang lọc **Chưa gán**, QR vẫn được tạo cho các playlist **đã gán môn được chọn**.
3. Ở bộ lọc **Đã gán**, kiểm tra mỗi playlist có video hợp lệ đều hiển thị **Tải QR**, **Đổi đích**, **Xóa QR** trên cùng một dòng khi chọn môn tương ứng.
4. Bấm lại nút tạo hàng loạt, kiểm tra số QR và đường dẫn/slug **không đổi**.
5. Kiểm tra playlist trống, video không cho nhúng, playlist bị gỡ: không tạo QR mới.
6. Thử **Tạo mã QR** của một playlist riêng lẻ để bảo đảm chức năng cũ không thay đổi.

**Tình huống C – Nhật ký và an toàn dữ liệu**
- Kiểm tra số liệu `ASSIGN_PLAYLIST_FILTERED_BULK`, `QR_PLAYLIST_FILTERED_BULK` trong bản ghi nhiệm vụ kiểm thử, và `TAO_QR_HANG_LOAT` trong phép đo nhiệm vụ tạo QR hàng loạt.
- Không xóa các mã QR trước đây, lịch sử quét, xem video, dữ liệu nghiệm thu.
- **Cơ chế v4.3.28:** Chỉ kiểm tra/xóa đúng 3 bản ghi lỗi `error_logs` một lần duy nhất khi lần đầu được triển khai với `AUTO_CREATE_DB=1` và chưa có dấu mốc. Dấu mốc `app_one_time_maintenance` tiếp tục được giữ; **v4.3.29 không khởi động lại việc xóa lỗi**.

## 3. Kiểm thử ngoại tuyến

Chạy tất cả tệp `tests/test_*.py`. Riêng `tests/test_v4329_bulk_playlist_actions.py` kiểm tra trực tiếp biểu thức SQLAlchemy và phần thân các thao tác mới với SQLite mô phỏng: lọc nhiều trang, tài khoản khác, giữ nguyên môn trước đó, QR có sẵn, playlist trống/không thể phát, ghi nhận nhiệm vụ và các nút riêng lẻ.

Kiểm thử ngoại tuyến không thay thế kiểm tra với OAuth/YouTube và PostgreSQL đang hoạt động trên Render.
