# Triển khai v4.3.33 — bản vá deploy Render

Xem chi tiết trong `HUONG_DAN_KIEM_TRA_V4333.md`. Không xóa database; cập nhật đầy đủ root mã nguồn lên GitHub. Nếu deploy tiếp tục Failed, xem Render → Logs và tìm `[SLC STARTUP]` và `Traceback`. Nếu cần khôi phục gấp, chọn rollback về bản Live thành công gần nhất (trong ảnh là v4.3.30). Vẫn giữ Free cold-start limitation, hotfix không loại bỏ trang loading do Render sinh ra.

# Hướng dẫn triển khai v4.3.32 trên Render

1. **Sao lưu PostgreSQL và mã nguồn đang vận hành** trước khi thay đổi danh mục khoa/bộ môn dùng chung.
2. Giải nén `TAO_MA_QR_TU_DONG_YOUTUBE_v4.3.32_RENDER.zip`, tải toàn bộ tệp/thư mục bên trong vào nhánh `main` của GitHub đã kết nối Render. Không đẩy nguyên ZIP vào kho mã nguồn.
3. Giữ `DATABASE_URL`, `SECRET_KEY`, Google OAuth, `AUTO_CREATE_DB=1`. Bản v4.3.32 không thêm bảng/cột mới và không yêu cầu tạo lại PostgreSQL.
4. Chờ dịch vụ ở trạng thái **Live**, nhấn `Ctrl + F5`; kiểm tra theo `HUONG_DAN_KIEM_TRA_V4332.md`.
5. Kiểm tra hai chức năng mới: giữ môn học tạm sau gán/tạo QR hàng loạt và trang quản trị **Khoa & Bộ môn**. Nên thử hợp nhất tên trùng trên dữ liệu mẫu trước khi áp dụng chính thức.

Cơ chế dọn đúng 3 lỗi hệ thống **chỉ một lần** từ bản v4.3.28 vẫn giữ nguyên dấu mốc đã xử lý, không có xóa lỗi định kỳ. Đánh giá đồng bộ kênh không có video nhưng không phát sinh lỗi sẽ là **Đạt**, kể cả bản ghi cũ đủ căn cứ được phân loại lại.

Trình duyệt Chrome/Edge trên HTTPS có thể hỏi nơi lưu PNG/ZIP; trình duyệt khác dùng cơ chế tải mặc định (có thể bật chế độ hỏi nơi lưu trong cài đặt trình duyệt).

Chưa thử trực tiếp với PostgreSQL và YouTube Production trên Render.

**Render Free:** Sau 15 phút không truy cập, Render tự dừng và có thể hiển thị Application loading khi SV quét QR; chỉ nâng cấp compute Web Service sang gói always-on mới bảo đảm không có cold-start do ngủ. v4.3.32 tối ưu startup và thêm lỗi dự phòng video nhưng không vượt được trang chờ của Render. Xem `HUONG_DAN_KIEM_TRA_V4332.md`.
