# Hướng dẫn nâng cấp Web App v4.3.9 trên Render

## 1. Sao lưu trước khi cập nhật

Đăng nhập Quản trị viên → **Sao lưu & khôi phục** → tải tệp sao lưu hệ thống; bảo quản riêng và **không đưa tệp chứa dữ liệu/token lên GitHub**.

## 2. Cập nhật mã nguồn

Giải nén `TAO_MA_QR_TU_DONG_YOUTUBE_v4.3.9_RENDER.zip`. Cập nhật toàn bộ tệp nguồn bên trong vào nhánh GitHub đang được Render triển khai (không tải nguyên ZIP thay cho mã nguồn). Đợi Render báo deploy thành công, sau đó mở Web App để kiểm tra.

Không tạo PostgreSQL mới, không sử dụng chức năng xóa dữ liệu. Bản này bổ sung **ba cột nullable trong bảng `error_logs`**. Nếu biến `AUTO_CREATE_DB=1` (mặc định trong bản đóng gói), máy chủ tự cập nhật cột khi khởi động. Nếu dùng `AUTO_CREATE_DB=0`, phải bổ sung các cột `actor_user_id INTEGER`, `actor_student_code VARCHAR(64)`, `actor_class_code VARCHAR(64)` vào bảng `error_logs` trước khi dùng phiên bản mới.

## 3. Kiểm tra sau triển khai

1. **Môn học/Mô đun:** mở và xác nhận cảnh báo chống môn trùng được làm to, chữ quan trọng in đậm.
2. **Kho video học liệu:** cuộn đến playlist ở giữa trang; chọn hoặc bỏ môn → **Lưu**; đảm bảo vẫn đứng nguyên chỗ, cùng dòng hiển thị xác nhận. Kiểm tra danh sách môn áp dụng đã lưu khi mở lại trang.
3. Với playlist **đã tạo QR**, chọn môn phù hợp để thấy **Tải mã QR / Mở thử**. Với môn khác chưa tạo QR, nút **Tạo mã QR** phải xuất hiện. Đảm bảo mã PNG tải được, URL mở thử phát được.
4. **Mã QR động:** xác nhận hàng playlist không còn nút tải/mở thử riêng; các mã video vẫn còn nút như cũ.
5. **Tải ZIP:** khi đang xem tất cả, mở ZIP để kiểm tra mỗi môn có thư mục riêng; sau đó lọc đúng môn → ZIP chỉ chứa mã thuộc môn đó; kiểm tra mục chưa gán môn nếu có.
6. **Nhật ký lỗi:** kiểm tra cột Người thực hiện thất bại; sau lỗi thật của GV, họ tên và email xuất hiện (nếu đã xác định được); lỗi tự động ghi tác vụ hệ thống; các bản ghi cũ có thể để Không xác định. Không cố ý gây lỗi trên hệ thống đang phục vụ SV.
7. **QR trên điện thoại:** SV chọn tên lớp; danh sách chỉ có **Họ tên (3 số cuối mã HSSV)**. Tiếp tục xem video, xác nhận lượt quét và phiên xem vẫn thống kê đúng sinh viên.

## 4. Lưu ý vận hành

- **Không thay đổi mã QR, slug hoặc URL đã phát hành**, không xóa lịch sử quét/xem.
- Chỉ thay đổi cách hiển thị và thao tác, ngoại trừ ba cột bổ sung cho nhật ký lỗi.
- Bản ghi nhật ký lỗi cũ không chứa định danh thì không thể tự suy luận chính xác người thực hiện. Các sự cố trước bước nhận diện SV cũng không thể gán chắc chắn cho một SV.
- Nếu trình duyệt tắt JavaScript, lưu môn playlist sẽ sử dụng cách gửi trang thông thường; cập nhật tại chỗ chỉ khả dụng khi JavaScript đang hoạt động.
- Cần **kiểm thử trên Render/PostgreSQL thật** trước khi thông báo triển khai rộng rãi.

## 5. Kết quả kiểm tra tĩnh

`python -m compileall -q .` · Jinja2 22 trang · `node --check` phần JavaScript mới · `python tests/test_v439_interface.py` · `python tests/test_v439_zip.py` · các bộ kiểm tra giao diện/nghiệp vụ trước.

