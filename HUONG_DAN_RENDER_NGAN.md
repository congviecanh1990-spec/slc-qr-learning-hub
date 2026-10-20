# Hướng dẫn cập nhật Web App v4.3.11 trên Render

## 1. Sao lưu trước khi cập nhật

Đăng nhập **Quản trị viên → Sao lưu & khôi phục**, tải bản sao lưu riêng trước khi triển khai. Không đăng tệp `.env`, bản sao lưu PostgreSQL, token Google hoặc khóa bí mật lên GitHub.

## 2. Triển khai

Giải nén `TAO_MA_QR_TU_DONG_YOUTUBE_v4.3.11_RENDER.zip`, đưa **các tệp trong thư mục đã giải nén** vào nhánh GitHub đang triển khai; Render sẽ nhận commit và triển khai theo cấu hình hiện tại. **Không xóa hoặc tạo lại PostgreSQL.** Bản này không thêm cột/bảng mới so với v4.3.10: dùng bảng `edit_history` sẵn có để lưu lịch sử đổi playlist.

## 3. Khắc phục QR playlist đã bị xóa

1. Tạo playlist mới trên YouTube (có thể đặt lại đúng tên cũ). Cần có video học liệu thuộc một trong các kênh giảng viên đang kết nối với Web App và được đồng bộ thành công. **Playlist tạo lại sẽ có ID mới**, không tự thay thế được playlist đã xóa.
2. Vào **Kênh YouTube → Đồng bộ lại**.
3. Mở **Kho video học liệu → Danh sách playlist**, tìm playlist cũ có QR, chọn đúng môn học/mô đun, bấm **Đổi playlist đích**, chọn playlist mới và **Lưu playlist đích**. Giữ nguyên vị trí cuộn khi JavaScript hoạt động.
4. Hoặc vào **Mã QR động**, tìm QR playlist cũ, bấm **Đổi playlist đích**, chọn playlist mới và **Lưu playlist đích**.
5. Kiểm tra bằng **Mở thử** trên trang Mã QR động và quét lại bản in QR cũ.

### Các ràng buộc an toàn

- QR/slug/đường dẫn **giữ nguyên**, không phát hành thêm QR, không xóa bản ghi lượt quét/xem cũ, không chuyển tài khoản YouTube.
- Chỉ chấp nhận **playlist có video đã đồng bộ, còn khả dụng và thuộc kênh người đang quản lý môn đã kết nối**. Không cho thay thế bằng playlist từ tài khoản khác/chưa được kết nối.
- Nếu playlist thay thế đã có mã QR hoạt động khác **trong cùng môn**, Web App từ chối để tránh QR trùng đích.
- Chỉ cập nhật liên kết playlist của **môn được chọn**, không thay đổi các môn khác dùng playlist cũ.
- Lịch sử đổi playlist ghi vào `edit_history`: playlist cũ, playlist mới, người thực hiện và thời gian. Các lượt xem video cũ vẫn giữ tham chiếu video ban đầu; lượt quét cũ chưa phát video vẫn hiển thị tên playlist tại thời điểm quét trong Thống kê khai thác.
- QR mới chỉ phát nội dung playlist mới **từ thời điểm thay đổi**, không thay đổi dữ liệu đã ghi trước đó.

## 4. Cập nhật giao diện

- **Kênh YouTube:** bỏ khối “Playlist đã đồng bộ”; giữ thông tin kênh, trạng thái kết nối và nút **Đồng bộ lại**.
- **Tất cả các nút tải QR** hiển thị nhãn **Tải mã QR** (không kèm PNG/ZIP), phạm vi tải phụ thuộc nút và bộ lọc; rê chuột xem gợi ý phạm vi.
- **Tất cả các nút xóa QR** hiển thị **Xóa mã QR**. Thao tác xóa toàn bộ có thêm ghi chú **Toàn bộ mã QR** và xác nhận trước khi thực hiện.

## 5. Kiểm tra sau triển khai

Nên thử với **môn học và playlist thử nghiệm** có QR đã tạo, tránh xóa playlist thật đang phục vụ SV. Kiểm tra trường hợp playlist bị xóa, chuyển đích thành công, mở thử bản in QR cũ, nhật ký trước đó vẫn tồn tại; thử chuyển sang playlist trống hoặc playlist đã có QR khác để xác nhận Web App từ chối. Sau đó kiểm tra giao diện Kênh YouTube và các nhãn nút ở cả hai trang.

**Kiểm tra đã chạy tại môi trường đóng gói:** cú pháp Python, 22 mẫu Jinja, cú pháp JavaScript, thử luồng đổi playlist bằng chính nghiệp vụ Flask (tách ra kiểm thử offline) và cơ sở dữ liệu SQLite mô phỏng, phân quyền, sao lưu/ZIP theo môn và kiểm tra mã nguồn trước đó. **Chưa kiểm thử tích hợp với Render/PostgreSQL/Google OAuth thực tế.**
