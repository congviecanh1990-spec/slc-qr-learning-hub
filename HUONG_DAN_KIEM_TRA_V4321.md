# Hướng dẫn kiểm tra sau khi triển khai v4.3.21

1. **Thống kê khai thác → Mục 2**: bốn ô tổng lượt quét, thành công, không thành công, tỷ lệ vẫn hiện như cũ; đoạn chú thích “Các chỉ số lấy từ…” đã bị bỏ. Bộ lọc và bảng 9 cột không đổi.
2. **Đăng nhập bằng Google có kênh YouTube nhưng chưa có video**: màn hình chờ hiện “Kênh đã kết nối, chưa có video học liệu”; không xuất hiện thông báo lỗi 403 hoặc vòng lặp chờ vô hạn. Chọn “Vào hệ thống” rồi có thể sử dụng các phần khác. Khi đăng video lên YouTube, quay về Kênh YouTube và bấm “Đồng bộ lại”.
3. **Tài khoản Google chưa tạo kênh YouTube**: màn hình hiển thị “Chưa tìm thấy kênh YouTube”, hướng dẫn kiểm tra tài khoản/tạo kênh.
4. **API lỗi 403 Forbidden**: hiển thị thông báo tiếng Việt về quyền truy cập. KHÔNG kết luận “kênh chưa có video”, không in “403 Client Error ... https://www.googleapis...” trên giao diện. Kiểm tra tài khoản đăng nhập và quyền truy cập YouTube; nếu chưa được khắc phục, quản trị viên cần kiểm tra API/Google OAuth qua nhật ký Render.
5. **Đăng nhập có nhiều kênh**: nếu một kênh đồng bộ được và một kênh lỗi, thông báo “Đồng bộ được một phần”; dữ liệu đã có vẫn xem được.
6. **Có video bình thường**: tự động chuyển vào hệ thống sau khi đồng bộ thành công. Nhật ký quét, thời lượng xem, QR và tỷ lệ không bị ảnh hưởng.
7. **An toàn dữ liệu**: Sao lưu PostgreSQL trước khi nâng cấp, không xóa dữ liệu và không tạo QR mới. Không yêu cầu migration cơ sở dữ liệu.

**Ghi chú về ảnh lỗi**: `403 Forbidden` khi gọi `channels.list?mine=true` nghĩa là yêu cầu tới YouTube bị từ chối; chỉ khi YouTube trả về thành công danh sách kênh và dữ liệu video rỗng mới kết luận chưa có video học liệu. Bản cập nhật sửa cách phân loại và hướng dẫn, không tự cấp quyền YouTube hay tự bật API khi bị cấm truy cập.
