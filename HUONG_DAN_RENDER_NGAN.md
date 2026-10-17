# Cập nhật Web App v3.4 trên Render

1. Giải nén bộ mã nguồn v3.4.
2. Upload toàn bộ file/thư mục bên trong vào repository GitHub hiện tại `slc-qr-learning-hub` và Commit.
3. Render đang bật Auto-Deploy sẽ tự build/deploy. Chờ `Live` / `Deploy succeeded`.
4. Mở Web App và nhấn `Ctrl + F5`.
5. Kiểm tra thanh menu theo thứ tự: **Kênh YouTube → Học phần → Kho video học liệu → Mã QR động...**
6. Vào **Kênh YouTube** → **Đồng bộ dữ liệu từ YouTube** để cập nhật video và playlist.
7. Vào **Kho video học liệu**:
   - thử lọc video theo **Playlist**;
   - kiểm tra cột **Playlist** của từng video;
   - tại phần **Danh sách playlist**, lọc playlist theo tên hoặc trạng thái đã/chưa gán học phần;
   - chọn một hoặc nhiều playlist → chọn **Học phần đích** → **Gán playlist đã chọn vào học phần**.
8. Vào **Học phần** kiểm tra playlist vừa gán đã xuất hiện đúng học phần.
9. Các chức năng QR playlist của v3.4 giữ nguyên.

## Dữ liệu
- Không cần xóa PostgreSQL hiện tại.
- v3.4 không thêm bảng/cột mới; chỉ mở rộng giao diện và luồng lọc/gán playlist.
- Dữ liệu video, playlist, học phần, lớp, QR và lịch sử quét/xem hiện có được giữ nguyên.


Sau khi cập nhật v3.4, mở **Kho video học liệu → Danh sách playlist** để chọn các học phần áp dụng cho từng playlist. Video trong playlist sẽ tự động được gán/bỏ gán theo cấu hình này.
