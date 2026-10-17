# Cập nhật v3.9.2

Bản này bổ sung chức năng cho GVCN xóa sinh viên bị nhập nhầm/nhập thừa khỏi lớp. Khi xóa, các lượt quét và dữ liệu xem liên quan của sinh viên trong lớp cũng bị loại khỏi thống kê. Không cần xóa PostgreSQL.

# Cập nhật Web App v3.7 trên Render

Bản v3.7 kế thừa trực tiếp v3.6 và **không cần tạo lại PostgreSQL**.

1. Giải nén gói v3.7.
2. Mở repository GitHub đang dùng cho Web App.
3. Tải toàn bộ tệp/thư mục ở thư mục gốc của v3.7 lên nhánh `main`, ghi đè các tệp cùng tên.
4. Commit thay đổi và chờ Render tự triển khai đến trạng thái `Live`.
5. Mở lại Web App và nhấn `Ctrl + F5`.

Sau khi cập nhật, kiểm tra lần lượt:
- Đăng nhập bằng tài khoản giảng viên; thông báo vai trò phải hiển thị bằng tiếng Việt.
- Quản trị viên thấy menu **Lớp & sinh viên**; có thể tạo lớp và giao GVCN.
- GVCN thấy menu **Lớp chủ nhiệm**; có thể tải Excel, thêm một SV và thay đổi trạng thái kèm ngày hiệu lực.
- Học phần chỉ hiển thị các số liệu tóm tắt và vùng chọn **Lớp áp dụng**.
- Trang **Mã QR động** ưu tiên tạo QR theo học phần; hai chức năng tạo QR đơn lẻ nằm ở khu vực **Tạo QR riêng lẻ**.
- Sinh viên quét QR chỉ nhập **Mã sinh viên do Nhà trường cấp**, không phải chọn lớp.

Bản v3.7 bổ sung các bảng dùng chung cho lớp/sinh viên và tự giữ nguyên dữ liệu cũ. Tệp Excel mẫu có thể tải ngay trong giao diện Lớp & sinh viên/Lớp chủ nhiệm.


Phiên bản v3.9: bổ sung giao diện Giảng viên, chuyển cấp mã GV khỏi trang nghiệm thu và bổ sung xóa toàn bộ tài khoản/dữ liệu của một giảng viên.

Phiên bản v3.9.1: tách giao diện Lớp & sinh viên của Quản trị viên thành danh mục lớp gọn; chi tiết sinh viên chỉ hiển thị cho GVCN. Sĩ số trên danh sách lớp là số sinh viên đang học tại thời điểm hiện tại.
