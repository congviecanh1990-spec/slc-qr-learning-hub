# Hướng dẫn triển khai Web App v4.3.29 lên Render

1. **Sao lưu dữ liệu PostgreSQL** và giữ một bản mã nguồn hiện đang chạy trước khi cập nhật.
2. Giải nén `TAO_MA_QR_TU_DONG_YOUTUBE_v4.3.29_RENDER.zip`. Tải **các tệp và thư mục bên trong** lên nhánh `main` của kho GitHub đã liên kết Render; **không tải cả tệp ZIP** như mã nguồn. Xóa các tệp hướng dẫn phiên bản cũ không còn dùng trong kho (nếu có), nhưng không xóa mã nguồn, bảng dữ liệu hoặc môi trường.
3. Giữ nguyên `DATABASE_URL`, `SECRET_KEY`, Google OAuth và các biến môi trường. **Không xóa PostgreSQL, không tạo lại QR**, không đặt lại hệ thống. Giữ `AUTO_CREATE_DB=1` nếu đang dùng.
4. Render triển khai commit mới. Sau khi trạng thái dịch vụ là **Live**, tải lại giao diện bằng `Ctrl + F5`.
5. Vào **Kho video học liệu → Danh sách playlist**, thử hai nút mới dưới bộ lọc như `HUONG_DAN_KIEM_TRA_V4329.md`; kiểm tra bộ lọc nhiều trang, QR cũ, playlist trống và quyền giảng viên.

**Giữ nguyên quy tắc dọn lỗi của v4.3.28:** nếu tác vụ xóa đúng 3 lỗi cũ đã chạy/bỏ qua và để lại dấu mốc trong `app_one_time_maintenance`, v4.3.29 **không chạy lại**. Nếu đây là lần đầu triển khai dòng mã có tính năng v4.3.28, điều kiện xóa một lần ban đầu vẫn áp dụng. Không có xóa lỗi định kỳ hay xóa lỗi sau này.

Bản mới không bổ sung bảng/cột PostgreSQL. Các kết quả kiểm thử mã nguồn là ngoại tuyến; cần xác minh luồng thực tế trên Render sau khi triển khai.
