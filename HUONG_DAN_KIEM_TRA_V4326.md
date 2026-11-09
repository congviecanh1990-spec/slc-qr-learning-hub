# HƯỚNG DẪN KIỂM TRA WEB APP v4.3.26 (Render)

## Phạm vi cập nhật

Tại **Thống kê khai thác → 2. Thống kê khai thác học liệu của sinh viên**, bổ sung hai phần độc lập, dùng chung bộ lọc môn học, lớp, học liệu QR và sinh viên:

**A. Thống kê lượt quét mã QR**

- Bốn ô **Tổng lượt quét**, **Quét thành công**, **Quét không thành công**, **Tỷ lệ quét thành công** đọc từ nhật ký `scan_logs` gốc, không cộng số video trong playlist.
- Bảng **Chi tiết lượt quét QR theo học liệu/playlist**: một dòng theo sinh viên × lớp × môn × mã QR, có số lượt quét thực tế thành công/không thành công. Các số phải cộng khớp bốn ô khi tính trên tất cả trang (ở bộ lọc mặc định hoặc khi không chọn riêng lọc trạng thái thất bại).

**B. Thống kê hoạt động khai thác video**

- Bốn ô **Tổng video**, **Video đã xem**, **Video hoàn thành**, **Tỷ lệ hoàn thành**. Các ô tính trên toàn bộ phạm vi lọc, không chỉ 10 dòng trang hiện tại, trước khi lọc theo trạng thái xem.
- **Tổng video** là số cặp *sinh viên–video* đã ghi nhận qua nhật ký xem hoặc video phát được thuộc QR mà sinh viên đã quét thành công. Nếu lọc nhiều sinh viên, một video được hai sinh viên tiếp cận được tính hai cặp, đúng với việc đánh giá từng người học. Không tính video riêng tư/không thể nhúng chỉ vì chúng có trong playlist hiện tại.
- Bảng video: một hàng cho mỗi sinh viên–video; **Số lần mở video** tính các phiên `watch_sessions` với thời gian phát thực tế **trên 0,5 giây**, không suy ra từ việc quét QR. Tính số lần mở và thời lượng tốt nhất trên mọi QR mà sinh viên từng dùng để phát cùng video.
- Trạng thái **Chưa xem / Chưa hoàn thành / Hoàn thành** dựa vào tiến độ tốt nhất trên mọi phiên. Xem lại một đoạn ngắn sau khi hoàn thành không làm giảm trạng thái.
- **Tỷ lệ hoàn thành** = Video hoàn thành / Tổng video × 100; nếu Tổng video bằng 0, hiển thị dấu `—` để không ngộ nhận là 0% thất bại.
- Cả hai bảng sắp xếp theo **lớp → môn/mô đun → tên gọi sinh viên**, trước khi phân trang; mỗi bảng có số trang riêng (10 dòng/trang).
- Nếu lọc **Mở QR thất bại**, chỉ bảng QR trả về những mã có lượt thất bại; không suy diễn lượt thất bại thành một video đã mở.
- Hai lựa chọn **SV chưa quét QR** và **SV chưa hoàn thành học liệu (đối chiếu lớp)** vẫn phục vụ đối chiếu sĩ số và tách khỏi số lần phát video thực.

## Tình huống kiểm thử chính

1. Đăng nhập giảng viên, vào mục 2, chọn một sinh viên và QR playlist có 8 video phát được.
2. Sinh viên quét playlist thành công **4 lần**. Ở phần A, **Tổng lượt quét = 4, thành công = 4, không thành công = 0, tỷ lệ = 100%**; bảng A chỉ có **1 dòng cho sinh viên–QR**, cột số lượt quét = 4.
3. Sinh viên mở phát 7/8 video; chỉ xem đủ >=95% của 1 video. Phần B phải hiển thị **Tổng video = 8, Video đã xem = 7, Video hoàn thành = 1, tỷ lệ hoàn thành = 12,5%**. Video chưa phát có **Số lần mở video = 0**, trạng thái **Chưa xem**.
4. Sinh viên xem lại 3 giây video đã hoàn thành: số lần mở video ấy tăng thêm 1, trạng thái vẫn **Hoàn thành**; **Tổng lượt quét chỉ tăng nếu thực sự có lượt quét QR mới được hệ thống ghi nhận**.
5. Nếu sinh viên hoàn thành video qua QR khác, các mục ghi trạng thái tốt nhất của cùng sinh viên–video; số lượt quét của QR đang lọc vẫn độc lập.
6. Đổi bộ lọc lớp, môn, sinh viên, QR; chuyển trang cả hai bảng; đảm bảo mỗi trang có số thứ tự phù hợp và không lộ dữ liệu QR/khóa học của giảng viên khác.
7. Kiểm tra **Không có dữ liệu**: các số đếm bằng 0; hai tỷ lệ hiển thị `—`.
8. Kiểm tra CSV lịch sử quét và xem vẫn giữ nguyên bản ghi sự kiện, không bị gộp/xóa.

## Kết quả kiểm tra ngoại tuyến

- Kiểm thử SQLAlchemy SQLite v4.3.26 cho tình huống 4 quét / 8 video / 7 xem / 1 hoàn thành, dùng lại QR khác và phân quyền giảng viên.
- Các kiểm thử hồi quy của hệ thống vẫn được giữ trong thư mục `tests/` (một số test lịch sử được chỉnh câu khẳng định giao diện do hai cột quét ở bảng video đã được thay thế).
- Cú pháp Python, 23 mẫu Jinja, cú pháp JavaScript và cấu trúc ZIP được kiểm tra.

**Chưa đối chiếu dữ liệu PostgreSQL thật trên Render**. Trước khi cập nhật, hãy sao lưu PostgreSQL; triển khai mã mới vào đúng kho GitHub/Render hiện có và giữ nguyên các biến môi trường. Không cần thay đổi cấu trúc cơ sở dữ liệu, xóa video, QR hoặc nhật ký quét/xem.

**Lưu ý về dữ liệu lịch sử:** Với các phiên cũ chỉ có sự kiện quét QR mà thiếu bản ghi phát video, hệ thống chỉ ghi nhận quét QR; không tạo số lần mở video giả. Với playlist từng đổi nội dung, catalog video chưa xem dựa trên danh sách video khả dụng hiện có; lịch sử video đã phát vẫn đọc từ `watch_sessions`.
