# HƯỚNG DẪN KIỂM TRA WEB APP v4.3.24 TRÊN RENDER

## 1. Nội dung thay đổi

Tại **Kho video học liệu → 1. Danh sách playlist**, thao tác bấm **Lưu** để chọn/bỏ môn học/mô đun phải cập nhật trực tiếp các cột **Môn học/mô đun áp dụng** và **Mã QR** trên cùng dòng, không phải lọc lại. Sau khi bấm **Tạo mã QR** cũng cập nhật trực tiếp các nút tải và quản lý mã QR. Cơ chế mới lấy nội dung dòng đã cập nhật trực tiếp từ máy chủ thay vì tải lại cả trang danh sách (dễ bị ảnh hưởng bởi bộ lọc và phân trang).

Không thay đổi cơ sở dữ liệu, mã QR có sẵn, dữ liệu sinh viên hoặc lịch sử quét/xem.

## 2. Triển khai

1. Sao lưu dữ liệu PostgreSQL trước khi cập nhật.
2. Giải nén ZIP; triển khai đầy đủ mã nguồn và thư mục `templates`, trong đó có **tệp mới** `templates/_playlist_library_row.html`. Không chỉ thay tệp `app.py`.
3. Giữ nguyên `DATABASE_URL`, `SECRET_KEY`, thông tin Google OAuth và các biến môi trường Render hiện tại. Không xóa bảng hoặc tạo lại QR.
4. Chờ Render hoàn tất triển khai; tải lại trang web một lần để trình duyệt nhận JavaScript mới. Thử lại trên Chrome ở chế độ ẩn danh nếu còn giao diện cũ do bộ nhớ đệm.

## 3. Các trường hợp kiểm tra thủ công

| Thao tác | Kết quả mong đợi |
|---|---|
| Lọc **Chưa gán môn học/mô đun**, chọn một playlist còn video phát được, tích chọn môn, bấm **Lưu** | Trên cùng dòng xuất hiện **Đã chọn 1 môn học/mô đun** và **Tạo mã QR**; không cần bấm **Lọc playlist**. |
| Đang ở trang 2–3 của danh sách, vẫn lọc **Chưa gán**, bấm lưu | Dòng đang thao tác vẫn cập nhật ngay dù sau khi lưu nó không còn thuộc bộ lọc. |
| Gán hai môn | Chọn môn trong cột QR, mỗi môn hiển thị QR độc lập. |
| Bấm **Tạo mã QR** | Cùng dòng cập nhật nút **Tải mã QR** và **Xóa mã QR** khi tạo thành công. |
| Bỏ toàn bộ môn, bấm **Lưu** | Phần chọn môn trở về **Chưa gán**; vùng QR nhắc gán môn trước, không tạo QR mới. QR cũ không bị xóa vì thao tác bỏ gán. |
| Playlist không có video dùng được | Không thể bấm **Tạo mã QR** dù đã gán môn. |
| Mạng lỗi khi bấm **Lưu** | Hiện cảnh báo chưa xác nhận được việc lưu; không tự gửi lại POST gây trùng thao tác. |
| Trình duyệt tắt JavaScript | Lệnh lưu dạng POST/redirect tiếp tục hoạt động (có thể phải đổi bộ lọc để xem dòng). |

**Lưu ý với bộ lọc:** Khi đang lọc **Chưa gán** và vừa gán môn, dòng đã gán vẫn tạm hiện để bạn thao tác tạo QR ngay. Khi bấm lọc lại hoặc tải lại trang, bộ lọc đang chọn được áp dụng bình thường và dòng đó chuyển sang nhóm **Đã gán**.

## 4. Kiểm thử mã nguồn đã thực hiện

- Kiểm tra cú pháp Python và JavaScript.
- Bộ kiểm thử hồi quy trong `tests/`.
- Kiểm thử riêng `tests/test_v4324_playlist_immediate_update.py`: trạng thái chưa gán → đã gán, có/không có QR, bỏ gán, playlist trống, dữ liệu HTML thoát ký tự và giao thức trả về một dòng cập nhật.

**Giới hạn:** Chưa thử thao tác trực tiếp với PostgreSQL và tài khoản trên Render. Sau triển khai cần đối chiếu ít nhất một playlist thực tế trước khi dùng nghiệm thu.
