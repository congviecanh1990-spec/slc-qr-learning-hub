# Hướng dẫn kiểm tra Web App v4.3.32 — lỗi Render khởi động khi SV quét QR

## 1. Giới hạn quan trọng của Render Free

Gói Web Service **Free** của Render tự tạm dừng sau 15 phút không có truy cập và hiển thị trang **Render – Application loading** trong quá trình khởi động. Đây là giao diện của Render *trước khi* request được chuyển tới Web App. **Không thể loại bỏ chắc chắn giao diện này chỉ bằng sửa code trong Web App**. Với yêu cầu sinh viên quét QR bất cứ lúc nào và xem ngay, chuyển Web Service sang gói trả phí không ngủ (ví dụ Starter) là phương án đáng tin cậy.

Bản v4.3.32 không tự tạo lưu lượng ping để giữ Render thức; không làm sai lệch nhật ký quét hoặc dữ liệu nghiệm thu.

## 2. Thay đổi mã nguồn

- Khởi động nhanh hơn sau lần triển khai đầu: schema migration, rà soát lớp cũ và cập nhật dữ liệu lịch sử chỉ chạy **một lần** theo dấu mốc PostgreSQL `schema_initialized_v4332`. Các lần Render thức dậy kiểm tra dấu mốc, không lặp những thao tác nặng. Không xóa các bảng dữ liệu.
- Giữ nguyên chức năng dọn chính xác ba lỗi **một lần** của v4.3.28: dấu mốc riêng `error_logs_exactly_three_once_v4328` không bị kích hoạt lại.
- Kết nối PostgreSQL có giới hạn thời gian mở kết nối 12 giây để tránh đợi vô thời hạn khi cơ sở dữ liệu không phản hồi; lỗi thực tế phải kiểm tra trong Render Logs.
- Trang xem video/playlist trên điện thoại có thêm thông báo khi trình phát nhúng YouTube không tải được hoặc báo lỗi. Có nút **Thử tải lại** và liên kết **Mở trên YouTube**. Nếu mở ngoài Web App, **thời lượng xem và hoàn thành không được hệ thống theo dõi**, không được tự tính hoàn thành.
- Không thay đổi đường dẫn QR `/q/<slug>`, không tạo lại mã QR, không thay đổi các nhật ký và công thức thống kê.

## 3. Triển khai và kiểm tra

1. Sao lưu cơ sở dữ liệu PostgreSQL đang sử dụng.
2. Cập nhật toàn bộ mã nguồn lên GitHub, để Render triển khai; giữ `DATABASE_URL`, `SECRET_KEY`, `AUTO_CREATE_DB=1` và cấu hình OAuth như cũ.
3. Kiểm tra Render Dashboard → Web Service → **Events** có trạng thái Live; kiểm tra **Logs** không có traceback, lỗi kết nối DB hoặc `WORKER TIMEOUT`.
4. Khi Render Live, mở `/health`: phản hồi dự kiến `status:ok, database:ok`.
5. Trên điện thoại, quét QR playlist và QR video, chọn đúng lớp/sinh viên và thử phát video. Xác nhận số lượt quét và phiên xem được ghi chính xác.
6. Thử chặn YouTube trên thiết bị kiểm thử: sau khoảng 14 giây nếu không khởi tạo được trình phát, xuất hiện thông báo và hai lựa chọn dự phòng; không tạo phiên xem hoàn thành giả.
7. Để kiểm tra cold start gói Free, đợi dịch vụ tự ngủ theo chính sách Render rồi quét QR. **Trang chờ Render vẫn có thể xuất hiện**; mục tiêu của tối ưu là rút ngắn phần khởi tạo của ứng dụng, không cam kết bỏ trang chờ Render.

## 4. Nếu sinh viên vẫn bị kẹt ở Render – Application loading

- Nếu không vào được trang chủ và `/health` sau một thời gian khởi động hợp lý, xem ngay **Render Logs/Events**: có thể deploy lỗi, database không phản hồi hoặc dịch vụ không đủ tài nguyên. Mã nguồn trang xem chưa được chạy nên không thể tự hiển thị thông báo sửa lỗi.
- Nếu trang chủ chạy được nhưng `/q/<slug>` lỗi, kiểm tra QR/playlist/môn/lớp và đường dẫn chính xác, không tự thay QR cũ.
- Để **ngăn màn hình thức dậy** khi SV truy cập, chuyển compute plan của Web Service (không phải Workspace) khỏi Free, bảo đảm Always On. Giữ nguyên URL và PostgreSQL.

**Kiểm thử mã nguồn ngoại tuyến không thay thế được kiểm tra với Render Production, PostgreSQL, YouTube và thiết bị sinh viên thực tế.**
