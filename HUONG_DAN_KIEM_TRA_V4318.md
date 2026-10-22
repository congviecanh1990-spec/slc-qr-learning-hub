# Hướng dẫn kiểm tra bản v4.3.18 trên Render

## Thay đổi tại mục 2 – Bảng thông tin chi tiết

- Một hàng duy nhất cho mỗi sinh viên và mỗi video. Chỉ khi QR playlist **chưa phát video nào**, bảng có thể xuất hiện thêm hàng mang nhãn **(chưa phát video)** để giữ số lượt quét chưa xác định đích video.
- Các cột lần lượt: **STT | Tên SV (Mã) | Lớp | MH/MĐ | Tên học liệu số | Số lượt quét thành công | Số lượt quét không thành công | Thời lượng xem | Trạng thái**.
- Cột lượt quét tách đếm **thành công** và **không thành công**. Một lượt quét playlist được tính một lần, không nhân theo số video được phát từ playlist; khi xem nhiều video, lượt quét được gắn vào video đầu tiên mà sinh viên đã phát trong lượt đó.
- Thời lượng xem là **thời lượng xem được ghi nhận cao nhất trong một phiên**. Trạng thái được xác định theo **lần xem tốt nhất**, đã Hoàn thành thì không hạ xuống vì xem lại một đoạn ngắn.

## Các tình huống kiểm tra

| Thao tác (cùng SV, video 100 giây) | Số lượt quét thành công | Số lượt quét không thành công | Trạng thái |
|---|---:|---:|---|
| Lần 1: quét thành công, chưa xem | 1 | 0 | Chưa xem |
| Lần 2: quét lại, xem đủ 98 giây được hệ thống ghi nhận | 2 | 0 | Hoàn thành |
| Lần 3: quét lại, chỉ ôn lại 10 giây | 3 | 0 | Hoàn thành |
| Tình huống có thêm 1 lần QR không mở được | 3 | 1 | Hoàn thành |

**Chú ý:** các lần mở liên tiếp trong **30 giây** có thể được hệ thống gộp để chống tải lại trang làm tăng số liệu. Để kiểm tra ba lần quét độc lập, thực hiện cách nhau trên 30 giây.

**Kiểm tra bổ sung:** một sinh viên khác xem cùng video phải có hàng riêng; một sinh viên xem hai video trong playlist phải có hai hàng video; một lượt quét playlist được đếm đúng một lần khi đối chiếu tổng cộng hai cột đếm; bộ lọc `Đã hoàn thành`, `Chưa hoàn thành`, `Mở QR thất bại` và phân trang cần hoạt động bình thường. Hai nút **Xuất lượt quét / Xuất quá trình xem** tiếp tục cung cấp nhật ký chi tiết gốc để đối chứng.

## Triển khai an toàn

1. Sao lưu PostgreSQL hiện tại (hoặc ít nhất tải hai tệp CSV nhật ký trước khi deploy).
2. Đẩy nội dung ZIP bản v4.3.18 vào kho mã đang được Render triển khai, giữ nguyên các biến môi trường và kết nối PostgreSQL.
3. Không dùng chức năng xóa dữ liệu, không tạo lại mã QR. Ứng dụng không yêu cầu thay đổi cấu trúc CSDL.
4. Tải lại giao diện sau deploy và kiểm tra với dữ liệu lịch sử của một sinh viên đã từng quét/xem nhiều lần.

### Phạm vi kiểm thử đã thực hiện

Kiểm thử tổng hợp SQL bằng SQLite với lượt quét thành công/thất bại, nhiều video trong playlist, lọc dữ liệu, trạng thái tốt nhất và phân trang; kiểm tra cú pháp Python và mẫu Jinja. **Chưa kiểm tra trên PostgreSQL Production hoặc YouTube trực tiếp tại Render**.
