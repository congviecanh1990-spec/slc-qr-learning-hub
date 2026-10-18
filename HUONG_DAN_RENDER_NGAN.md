# HƯỚNG DẪN CẬP NHẬT WEB APP v4.2.0

Phiên bản v4.2.0 nâng cấp từ v4.1.1, không tạo database PostgreSQL mới và không yêu cầu thay đổi thông số OAuth Google.

## Cập nhật
1. Giải nén tệp ZIP, tải các tệp/thư mục bên trong lên nhánh `main` của repository GitHub đang sử dụng; ghi đè tệp có sẵn và Commit.
2. Chờ dịch vụ Render triển khai và báo **Live**. Không xóa cơ sở dữ liệu cũ.
3. Mở Web App, đăng nhập bằng một tài khoản Google giảng viên. Lần đầu trên bản mới, xác nhận họ tên, chọn nhóm chuyên môn, có/không chủ nhiệm lớp. Nếu có, nhập tên lớp và sĩ số khai báo.
4. Quan sát trang “Chờ trong giây lát để hệ thống đồng bộ kênh YouTube…”. Khi thành công hệ thống tự chuyển trang. Nếu thất bại, có thể vào hệ thống và bấm đồng bộ lại trên trang Kênh YouTube.
5. Kiểm tra mã GV được cấp tự động; GVCN kiểm tra mã lớp và tải danh sách Excel. Vào trang Môn học/ mô đun, thêm môn học và chọn lớp; kiểm tra bảng môn học và các bộ đếm không thêm số 0 đầu.

## Lưu ý quan trọng
- Những tài khoản đã đăng nhập trước đây vẫn phải xác nhận họ tên và nhóm chuyên môn **một lần** khi sử dụng bản mới.
- Sĩ số khai báo của GVCN **không** thay thế số SV thực tế; phải tải Excel theo đúng mã SV của Nhà trường để sử dụng quét QR và thống kê.
- Nếu tên lớp đã tồn tại của giảng viên khác, hệ thống từ chối tạo trùng. Quản trị viên có thể kiểm tra và chuyển giao GVCN ở danh sách lớp.
- Tự đồng bộ cần quyền YouTube đọc dữ liệu, kết nối mạng và hạn mức API. Trên Render miễn phí, quá trình khởi động/đồng bộ có thể chậm. Nút “Vào hệ thống” không làm mất quyền đăng nhập.
- Chưa chạy kiểm thử tích hợp với dịch vụ Google/Render trong môi trường tạo tệp. Cần nghiệm thu các thao tác thực tế sau triển khai.
