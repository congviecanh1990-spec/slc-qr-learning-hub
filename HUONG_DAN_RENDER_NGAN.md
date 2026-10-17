# Cập nhật Web App v4.0 trên Render

Bản v4.0 kế thừa trực tiếp v3.9.2, không cần tạo lại PostgreSQL và không cần cấu hình lại Google OAuth.

1. Giải nén gói v4.0.
2. Mở repository GitHub đang dùng cho Web App.
3. Tải toàn bộ tệp/thư mục ở thư mục gốc của v4.0 lên nhánh `main`, ghi đè các tệp cùng tên.
4. Commit thay đổi và chờ Render tự triển khai đến trạng thái `Live`.
5. Mở lại Web App và nhấn `Ctrl + F5`.

Sau khi cập nhật, kiểm tra:
- Với Quản trị viên, menu **Giảng viên** nằm ngay sau **Kênh YouTube**.
- Menu/trang **Môn học/ mô đun** hiển thị các nhãn mới đúng quy ước.
- Trang **Đánh giá nghiệm thu** không còn cột Mã ca; có chỉ tiêu đăng nhập 100%, đồng bộ video 100%, tối thiểu 3 giảng viên và 50 sinh viên tham gia.
- Trang **Nhật ký lỗi** có cột **Thao tác** và **Môn học/ Mô đun**.
- Ô sửa họ tên GV không điền lại nội dung đã nhập trước; nút **Lưu họ tên** nằm ngay bên phải ô nhập.
- Khi **Xóa toàn bộ dữ liệu đã lưu**, phiên Quản trị viên hiện tại vẫn được giữ; mã GV cấp lại từ `GV0001`, mã lớp từ `L000001`, mã môn học/ mô đun từ `HP000001`.

Schema hiện có được nâng cấp tự động thêm thông tin phục vụ Nhật ký lỗi; dữ liệu cũ được giữ nguyên nếu không sử dụng chức năng xóa toàn bộ dữ liệu.
