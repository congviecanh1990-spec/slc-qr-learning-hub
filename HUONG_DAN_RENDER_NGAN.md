# Web App v4.3.8 – Cập nhật chức năng bàn giao môn học/mô đun

## Trước khi cập nhật

1. **Sao lưu PostgreSQL hiện tại** qua mục **Sao lưu & khôi phục** (Quản trị viên) và lưu bản ZIP ở nơi an toàn. Tuyệt đối không đưa ZIP sao lưu (có dữ liệu riêng tư/token mã hóa) lên GitHub.
2. Giải nén tệp mã nguồn v4.3.8, cập nhật **các tệp nằm bên trong** lên nhánh GitHub Render đang chạy. Không đưa nguyên tệp ZIP mã nguồn lên nhánh để thay cho các tệp mã nguồn.
3. Để Render chạy bản triển khai mới. **Không chọn xóa dữ liệu** hoặc tạo PostgreSQL mới. Với biến môi trường mặc định `AUTO_CREATE_DB=1`, hệ thống sẽ tự tạo **bảng mới `course_transfers`** để ghi lịch sử bàn giao; không xóa bảng/dữ liệu cũ.

## Kiểm thử sau khi Render deploy thành công

1. Đăng nhập tài khoản **Quản trị viên** → **Môn học/mô đun** → **Bàn giao môn học/mô đun cho giảng viên khác**.
2. Chọn môn đang thuộc GV A, chọn GV B, tích xác nhận rồi bấm **Bàn giao môn học/mô đun**. Không chọn giảng viên đã có môn cùng tên; phải xử lý trùng môn trước.
3. Xác nhận GV A không còn nhìn thấy môn bàn giao trong danh sách môn và không có quyền sửa/xóa/tải QR của môn đó; QR riêng không gắn môn của GV A vẫn thuộc GV A.
4. Đăng nhập GV B: môn được bàn giao hiển thị, lớp học giữ nguyên, QR cũ xuất hiện trong **Mã QR động**; có thể tải PNG và ZIP QR theo môn, mở thử và (nếu cần) đổi video đích sang video thuộc kênh GV B đã kết nối.
5. **Quan trọng:** Lấy một mã QR đã in/đã phát hành từ trước, quét bằng tài khoản SV thử: URL `/q/...` không đổi và học liệu vẫn phát nếu video/playlist YouTube nguồn còn khả dụng. Kiểm tra lịch sử quét/xem trước và sau bàn giao trong **Thống kê khai thác**.
6. Quản trị viên kiểm tra mục **Lịch sử bàn giao gần đây**. Kiểm tra chức năng sao lưu có tệp `course_transfers.json`.
7. Nếu video/playlist cũ do kênh GV A sở hữu, **không xóa tài khoản/kênh YouTube GV A** khi còn được tham chiếu. Hệ thống ngăn xóa giảng viên có nguồn học liệu hoặc mã QR đã bàn giao. Bàn giao **không chuyển quyền sở hữu kênh YouTube**.

## Quy tắc được áp dụng

- **Bàn giao có hiệu lực ngay**, chỉ Quản trị viên thực hiện và có xác nhận trước khi lưu; lưu lịch sử người bàn giao, GV cũ, GV mới và ngày thực hiện.
- **Mã môn, mã QR, slug/URL QR, hình ảnh QR, lớp áp dụng, liên kết học liệu, lịch sử quét/xem và tác giả QR ban đầu đều không thay đổi.** Quyền quản lý QR thuộc môn đi theo GV đang phụ trách.
- Không tự tạo thêm QR từ video/playlist chưa thuộc kênh YouTube GV B kết nối. Những QR cũ đã tạo từ nguồn GV A vẫn tiếp tục hoạt động và có thể được GV B quản lý.
- Tài khoản/kênh YouTube gốc vẫn cần duy trì; nếu video bị xóa, chuyển riêng tư hoặc khóa nhúng ở YouTube, **Web App không thể đảm bảo video tiếp tục phát**, dù hình QR vẫn giữ nguyên.
- Với dự án cài đặt `AUTO_CREATE_DB=0`, cần thực hiện tạo bảng `course_transfers` theo `models.py` bằng quy trình triển khai CSDL của đơn vị trước khi sử dụng chức năng này.

## Mức độ kiểm thử

Đã chạy kiểm tra cú pháp Python, 22 mẫu Jinja2, kiểm thử SQLite trên mô hình dữ liệu thực về quy tắc quyền QR khi bàn giao và bàn giao tiếp lần hai, cùng các bài kiểm tra giao diện hiện có. **Chưa kiểm thử Google OAuth/PostgreSQL/Render trực tiếp trong môi trường thực tế**.
