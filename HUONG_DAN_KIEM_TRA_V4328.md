# Hướng dẫn triển khai và kiểm tra Web App v4.3.28

## 1. Phạm vi thay đổi

Bản này kế thừa **toàn bộ chức năng v4.3.27**, chỉ thêm **một thao tác dọn Nhật ký lỗi hệ thống một lần duy nhất** tại lần khởi động ứng dụng đầu tiên khi triển khai v4.3.28 và `AUTO_CREATE_DB=1`.

- Chỉ khi bảng PostgreSQL `error_logs` có **đúng 3 bản ghi**, ứng dụng xóa đúng ba bản ghi đó.
- Nếu có **0, 1, 2 hoặc từ 4 bản ghi trở lên**, ứng dụng **không xóa** để tránh xóa nhầm lỗi không xác định.
- Kết quả, số bản ghi và ID liên quan được lưu một lần tại bảng `app_one_time_maintenance` (không chứa email/nội dung lỗi). Dấu mốc vẫn còn khi Render khởi động lại, deploy lại hoặc khôi phục dữ liệu qua giao diện Web App.
- Không có cơ chế dọn dẹp định kỳ, không xóa lỗi mới. Các lỗi phát sinh sau lần đầu vẫn được ghi nhận như bình thường.
- Không xóa dữ liệu quét QR, xem video, đánh giá nghiệm thu, kết quả kiểm thử, môn học hoặc QR.

**Lưu ý:** Việc xóa nhật ký chỉ làm sạch 3 bản ghi cũ; nó không sửa nguyên nhân phát sinh lỗi và không xóa các sự kiện nghiệm thu thất bại đã ghi ở bảng khác.

## 2. Trước khi triển khai

1. **Sao lưu dữ liệu** qua mục Sao lưu & khôi phục hoặc PostgreSQL trước khi triển khai; các bản ghi lỗi bị xóa không có nội dung sao lưu riêng trong Web App.
2. Xác nhận ở trang **Nhật ký lỗi hệ thống** đang có đúng 3 bản ghi, không chỉ là 3 bản ghi mới nhất trong một danh sách dài. Nếu số bản ghi thực tế khác 3, mã sẽ tự **bỏ qua vĩnh viễn**.
3. Giữ nguyên `DATABASE_URL`, `AUTO_CREATE_DB=1`, các biến môi trường và dịch vụ Render cũ.

## 3. Sau triển khai

1. Chờ Render báo triển khai thành công, mở **Nhật ký lỗi hệ thống**. Nếu ban đầu bảng có đúng 3 bản ghi, nay phải hiện **Chưa có lỗi** (trừ khi đã phát sinh lỗi mới ngay sau khi triển khai).
2. Thử khởi động lại dịch vụ: lỗi mới, nếu có, vẫn được giữ nguyên; dọn dẹp không chạy lần thứ hai.
3. Nếu nhật ký cũ không được xóa, kiểm tra số bản ghi ban đầu; bản này chủ động bỏ qua trường hợp khác 3 thay vì xóa nhầm.
4. Kiểm tra mã QR và các thống kê hoạt động vẫn giữ nguyên.

## 4. Kiểm thử ngoại tuyến

Chạy `python tests/test_v4328_cleanup_once.py`, sau đó toàn bộ `tests/test_*.py` và kiểm tra cú pháp Python/JavaScript/Jinja. Kiểm thử mã nguồn không thay thế việc kiểm tra thực tế trên PostgreSQL Production.
