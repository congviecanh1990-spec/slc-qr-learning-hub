**Lưu ý khi sử dụng từ v4.3.18:** Hướng dẫn này mô tả cách hiển thị của bản v4.3.17. Mục 2 nay đã gộp mỗi SV–video thành một dòng; vui lòng đọc `HUONG_DAN_KIEM_TRA_V4318.md` để kiểm tra bảng mới. Các nguyên tắc ghi nhận trạng thái tốt nhất v4.3.17 vẫn giữ nguyên.

---

# Bản v4.3.17 – Xác nhận trạng thái tốt nhất của sinh viên theo video

## Nguyên tắc

- **Lượt quét QR** được lưu bằng từng bản ghi `scan_logs`; quét thành công không tự đồng nghĩa với hoàn thành video. Vẫn giữ cơ chế chống trùng lượt mở trong 30 giây như v4.3.16 (mở lại/trang tải lại ngay có thể được gộp).
- **Trạng thái video hiện tại** được xác định từ mọi phiên xem của **đúng sinh viên và đúng video**: `Chưa xem` → `Chưa hoàn thành` → `Hoàn thành`. Sau khi có một phiên được xác thực xem ít nhất 95% video, trạng thái của cặp sinh viên–video luôn là `Hoàn thành`, kể cả lần sau chỉ xem lại một đoạn.
- **Không cộng dồn các phiên xem ngắn khác nhau** để đạt 95% (vì có thể xem trùng một đoạn nhiều lần). Mỗi phiên vẫn có chứng cứ thời lượng xem riêng.
- Một QR playlist gồm nhiều video: hoàn thành video A **không** làm video B thành hoàn thành. Mở cùng video từ QR khác vẫn nhận thành tích đã được chứng thực của SV với video ấy.
- Mục 2 của Thống kê vẫn hiển thị từng dòng lịch sử; cột `Thời lượng xem` là thời lượng của phiên, cột `Trạng thái` là kết quả tốt nhất tính đến hiện tại. Vì vậy có thể xuất hiện `00:00 – Hoàn thành` ở một lượt quét trước khi xem hoặc một lượt quét lại, nếu sinh viên đã hoàn thành video ở một phiên khác. Đây không phải dữ liệu thời lượng bị sửa.

## Cách đưa lên Render

1. Sao lưu PostgreSQL nếu có thể, hoặc tải CSV nhật ký hiện tại trước khi thay phiên bản.
2. Đẩy **toàn bộ mã nguồn v4.3.17** từ ZIP lên cùng kho mã đang triển khai (giữ nguyên biến môi trường và cơ sở dữ liệu PostgreSQL đang kết nối).
3. Để Render build/deploy bằng lệnh trong `render.yaml`. Không xóa, tạo lại hoặc reset PostgreSQL; không dùng chức năng `Xóa toàn bộ dữ liệu đã lưu`.
4. Khi ứng dụng khởi chạy, lệnh nâng cấp schema hiện có bổ sung **chỉ mục** tìm kiếm `(role, participant_code, video_id)`, không tạo bảng mới hay xóa dữ liệu.
5. Mở lại trình duyệt, nếu trang xem cũ bị cache thì tải lại để lấy file JS mới.

## Ba tình huống kiểm tra bằng một video dài 100 giây

| Thực hiện | Lượt quét thành công của SV | Trạng thái hiện tại của video |
|---|---:|---|
| Quét lần 1, không xem | 1 | Chưa xem |
| Quét lần 2, xem đủ tối thiểu 95 giây có ghi nhận liên tục | 2 | Hoàn thành |
| Quét lần 3, chỉ xem lại 10 giây cần ôn | 3 | **Hoàn thành**, không hạ cấp |

*Để tách rõ 3 lần quét, thực hiện cách nhau trên 30 giây do cơ chế chống ghi trùng đã có của bản gốc.*

Kiểm tra bổ sung: một sinh viên khác chưa xem vẫn `Chưa xem`; video thứ hai trong playlist chưa xem đủ vẫn `Chưa hoàn thành`; bộ lọc `Chưa hoàn thành` không liệt kê cặp SV–video đã hoàn thành; CSV phiên xem giữ chứng cứ trạng thái riêng của từng phiên cùng trạng thái tốt nhất.

## Những điểm chưa thể xác thực offline

Các bài kiểm tra SQL dùng SQLite và mô phỏng dữ liệu, cùng bài kiểm tra tĩnh Python/Jinja/JS, đã chạy đạt. Chưa kết nối PostgreSQL Production trên Render hay YouTube phát trực tiếp bằng trình duyệt trong quá trình tạo bản cập nhật này. Cần thực nghiệm trên chính Render sau khi deploy.
