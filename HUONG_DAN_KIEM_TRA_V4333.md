# HƯỚNG DẪN KIỂM TRA WEB APP v4.3.33 — BẢN VÁ TRIỂN KHAI RENDER

## 1. Lý do phát hành

Ảnh Render 18/11/2026 thể hiện hai lần deploy `v4.3.32`, `v4.3.32_1` báo `Failed`, còn `v4.3.30` trước đó thành công. **Ảnh chỉ cho biết trạng thái, không chứa dòng lỗi cụ thể**. Do đó không thể khẳng định nguyên nhân là do mã nguồn mà không đọc Logs.

Bản v4.3.33 loại bỏ thay đổi rủi ro về khởi tạo cơ sở dữ liệu đưa vào v4.3.32, quay lại luồng đã dùng ở v4.3.31 và trước đó: `db.create_all` → `ensure_schema_upgrades` → `migrate_legacy_classes` → `cleanup_initial_three_error_logs_once`.

- Không còn phụ thuộc tệp mới `services/startup.py` hoặc đánh dấu `schema_initialized_v4332`.
- Bỏ tuỳ chọn kết nối PostgreSQL mới thêm tại v4.3.32, trở về cấu hình engine trước đó.
- Bổ sung các dòng `[SLC STARTUP]` để khi deploy lỗi có thể xác định bước thất bại tại **Render → Logs** mà không lộ token.
- Giữ chức năng xử lý lỗi trình phát YouTube trên điện thoại của v4.3.32.
- Không xóa dữ liệu và **không kích hoạt lại** việc xóa 3 lỗi cũ: vẫn kiểm tra dấu mốc riêng bền vững của v4.3.28.

## 2. Cập nhật mã nguồn đầy đủ

Sao lưu PostgreSQL trước. Giải nén ZIP và cập nhật *tất cả* các thư mục/tệp vào root GitHub của dự án (không upload nguyên ZIP, không tạo thư mục lồng nhau). Trên Render giữ nguyên DATABASE_URL, SECRET_KEY, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, AUTO_CREATE_DB=1 và các biến đã dùng. Kiểm tra **Build Command**, **Start Command** và **Health Check** vẫn là giá trị hiện có (render.yaml mặc định `gunicorn -w 1 --threads 4 --timeout 120 wsgi:app`, `/health`).

## 3. Kiểm tra Deploy và Logs

1. Chọn Render Web Service → `Deploys`, mở bản deploy mới; ghi nhận `Live` hay `Failed`.
2. Nếu báo Failed, mở `Logs` của deploy hoặc runtime và tìm `Traceback`, `Error`, `ModuleNotFoundError`, `Worker failed to boot`, `psycopg` và các dòng `[SLC STARTUP]`.
3. Nếu không có dòng `[SLC STARTUP]`, lỗi có thể xảy ra trước giai đoạn gọi `create_app()` (build, import, thư viện hoặc cấu hình); gửi **30–60 dòng cuối của Logs**. Che token, khóa bí mật, URL DB nếu có.
4. Nếu có `[SLC STARTUP] FAILED step=...`, gửi tên bước và phần traceback liền sau.
5. Nếu Live, kiểm tra `/health`, một QR video, một QR playlist, trang quản trị và thống kê. Không cần tạo QR mới.

## 4. Khôi phục truy cập ngay khi cần

Nếu sinh viên không vào được Web App, ưu tiên Render `Deploys` → bản gần nhất **thành công** (trong ảnh là v4.3.30) → `Rollback`, nếu tùy chọn còn khả dụng. Đây là thao tác triển khai lại mã nguồn cũ, **không phải xóa PostgreSQL**. Theo tài liệu Render, thao tác rollback có thể tắt Auto-Deploy, nên cần kiểm tra lại khi cập nhật bản sửa.

## 5. Giới hạn về gói Free

Sự cố `Failed` khác với màn hình `Render – Application loading` khi Render Free thức dậy. v4.3.33 **không thể** ngăn trang chờ trước khi ứng dụng được khởi động. Nếu muốn dịch vụ luôn sẵn sàng, cần Web Service không ngủ. Không dùng lượt truy cập giả để làm sai số liệu nghiệm thu.

## 6. Phạm vi kiểm thử

Đã kiểm tra mã nguồn và bộ kiểm thử ngoại tuyến; môi trường tạo tệp không truy cập được PostgreSQL/Render, và không cài sẵn đầy đủ Flask/Authlib/psycopg để chạy Gunicorn tích hợp. **Không cam kết bản vá giải quyết mọi lỗi Render nếu chưa đối chiếu log thực tế.**
