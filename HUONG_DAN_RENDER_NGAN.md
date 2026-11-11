# Hướng dẫn triển khai v4.3.30 trên Render

1. **Sao lưu PostgreSQL và mã nguồn đang vận hành**, vì bản này thay đổi quy trình xóa giảng viên và dữ liệu liên quan.
2. Giải nén `TAO_MA_QR_TU_DONG_YOUTUBE_v4.3.30_RENDER.zip`, tải toàn bộ tệp/thư mục bên trong vào nhánh `main` của GitHub đã kết nối Render. Không đẩy nguyên ZIP vào kho mã nguồn.
3. Giữ `DATABASE_URL`, `SECRET_KEY`, Google OAuth, `AUTO_CREATE_DB=1`. Hệ thống bổ sung hai cột hồ sơ khoa/bộ môn, không yêu cầu tạo mới PostgreSQL.
4. Chờ dịch vụ ở trạng thái **Live**, nhấn `Ctrl + F5`; kiểm tra theo `HUONG_DAN_KIEM_TRA_V4330.md`.
5. **Không xóa giảng viên thật trước khi thử trên dữ liệu sao lưu**. Nếu học liệu/kênh vẫn được người khác sử dụng, hệ thống sẽ chặn để tránh mất QR/lịch sử của họ.

Cơ chế dọn đúng 3 lỗi hệ thống **chỉ một lần** từ bản v4.3.28 vẫn giữ nguyên dấu mốc đã xử lý, không có xóa lỗi định kỳ. Đánh giá đồng bộ kênh không có video nhưng không phát sinh lỗi sẽ là **Đạt**, kể cả bản ghi cũ đủ căn cứ được phân loại lại.

Trình duyệt Chrome/Edge trên HTTPS có thể hỏi nơi lưu PNG/ZIP; trình duyệt khác dùng cơ chế tải mặc định (có thể bật chế độ hỏi nơi lưu trong cài đặt trình duyệt).

Chưa thử trực tiếp với PostgreSQL và YouTube Production trên Render.
