# CẬP NHẬT v2.9 TRÊN RENDER

1. Giải nén bộ mã nguồn v2.9.
2. Mở repository GitHub đang dùng cho Web App.
3. Chọn **Add file → Upload files**.
4. Tải toàn bộ tệp/thư mục của v2.9 lên repository hiện tại.
5. Commit với nội dung gợi ý: `Update Web App to v2.9`.
6. Chờ Render tự động deploy và trạng thái trở về **Live / Deploy succeeded**.
7. Đăng nhập tài khoản Quản trị viên và kiểm tra menu **Sao lưu & khôi phục**.

## Nội dung mới v2.9

- Gộp hai menu **Sao lưu dữ liệu** và **Khôi phục dữ liệu** thành một menu **Sao lưu & khôi phục**.
- Cùng một giao diện có hai khối: **Sao lưu dữ liệu** và **Khôi phục dữ liệu**.
- Nút sao lưu tải tệp ZIP do chính hệ thống tạo.
- Khôi phục chỉ cho phép thực hiện khi đã chọn ZIP và nhập đúng cụm từ **KHÔI PHỤC**.
- Nút **Khôi phục dữ liệu** mặc định bị khóa; chỉ bật khi đủ hai điều kiện trên.
- Khi bấm khôi phục, hệ thống hỏi xác nhận lần cuối trước khi thay dữ liệu hiện tại.
- Chỉ tài khoản Quản trị viên được truy cập chức năng này.

Không xóa PostgreSQL và không tạo Web Service mới khi cập nhật v2.9.
