# Cập nhật Web App v3.2 trên Render

1. Giải nén bộ mã nguồn v3.2.
2. Upload toàn bộ file/thư mục bên trong vào repository GitHub hiện tại `slc-qr-learning-hub` và Commit.
3. Render đang bật Auto-Deploy sẽ tự build/deploy. Chờ `Live` / `Deploy succeeded`.
4. Mở Web App và nhấn `Ctrl + F5`.
5. Vào **Kênh YouTube** → **Đồng bộ dữ liệu từ YouTube**. Kiểm tra danh sách playlist đã xuất hiện.
6. Vào **Học phần** → chọn một hoặc nhiều playlist → **Gán playlist**.
7. Vào **Mã QR động**:
   - thử **Tạo một mã QR playlist**;
   - thử **Tạo QR playlist còn thiếu** theo học phần;
   - mở thử QR và kiểm tra trang xem hiển thị danh sách video trong playlist.
8. Thêm/gỡ một video trong playlist trên YouTube → đồng bộ lại → mở chính QR playlist cũ để kiểm tra nội dung thay đổi mà không tạo QR mới.
9. Vào **Đánh giá nghiệm thu** → **Hiệu quả quy trình**. Danh sách nhiệm vụ đối chứng phải chỉ có:
   - `TAO_QR_RIENG` — Tạo và lưu mã QR riêng;
   - `TAO_QR_HANG_LOAT` — Tạo và lưu mã QR hàng loạt.

## Dữ liệu
- Không cần xóa PostgreSQL hiện tại.
- Hệ thống tự tạo bảng `course_playlists` và tự bổ sung các cột mới cho `playlists`/`qr_codes` khi khởi động.
- Dữ liệu video, học phần, lớp, QR và lịch sử quét/xem hiện có được giữ nguyên.
