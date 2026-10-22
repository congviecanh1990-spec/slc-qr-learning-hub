# HƯỚNG DẪN KIỂM TRA WEB APP v4.3.22 (RENDER)

## Trước khi cập nhật

1. Sao lưu dữ liệu PostgreSQL đang sử dụng và mã nguồn v4.3.21.
2. Cập nhật **toàn bộ** mã nguồn v4.3.22, giữ nguyên `DATABASE_URL`, `SECRET_KEY`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` và cấu hình OAuth Google. Biến `AUTO_CREATE_DB=1` như tệp `render.yaml` cho phép tạo **bảng bổ sung `youtube_sync_jobs`** mà không xóa bảng/dữ liệu cũ.
3. Triển khai lại lên Render. Không phải xóa các QR hiện có hay đồng bộ lại tài khoản sinh viên.

## Thử nghiệm trường hợp chỉ có video đã lưu

1. Đăng nhập Google bằng tài khoản có kênh YouTube **không tự tải video**, nhưng có một playlist thông thường (công khai hoặc riêng tư) chứa video **công khai hoặc không công khai (unlisted), cho phép nhúng** từ kênh của người khác.
2. Sau đăng nhập phải **vào thẳng giao diện hệ thống**, không bị giữ ở màn hình “Chờ đồng bộ YouTube”. Thông báo tiến độ đồng bộ được hiển thị nhưng người dùng vẫn thao tác được.
3. Giữ một tab Web App đang mở để trình duyệt tiếp tục gửi từng yêu cầu đồng bộ. Có thể chuyển giữa các trang trong hệ thống; tiến độ đã xử lý được lưu ở PostgreSQL. Khi lỗi mạng, nhấn **Tiếp tục** hoặc bấm **Đồng bộ lại** tại trang Kênh YouTube.
4. Sau khi hoàn tất, mở **Kênh YouTube** để xem trạng thái, sau đó mở **Kho video học liệu**: video của kênh khác trong playlist phải xuất hiện dưới nhãn **Video tuyển chọn**. Không đổi tên kênh đăng tải gốc thành kênh giảng viên.
5. Gán playlist/video tuyển chọn cho môn học/mô đun, tạo QR, thử mở và xem video bằng QR. Đồng thời kiểm tra QR cũ và thống kê quét/xem vẫn hoạt động.
6. Playlist rỗng phải hiển thị **Danh sách trống**, không được thông báo **Có học liệu** hoặc cho tạo QR của playlist trống.

## Thử các ngoại lệ

- Playlist có video **private** của người khác hoặc video YouTube **không cho phép nhúng**: video không được nhập làm học liệu có thể phát.
- Tài khoản chỉ có **Xem sau (Watch Later)**: YouTube Data API không hỗ trợ liệt kê playlist đặc biệt này. Cần chuyển video vào playlist thông thường do tài khoản quản lý. Đây không phải lỗi ứng dụng.
- API trả về 403 hoặc quota: hiển thị lý do ngắn gọn và ghi nhận đồng bộ **không thành công**, không suy diễn “kênh trống”. Trường hợp các playlist khác vẫn đồng bộ được phải giữ dữ liệu đã đồng bộ.
- Một playlist nhiều trang (trên 50 video): ứng dụng thực hiện nhiều yêu cầu. Ngắt giữa chừng rồi truy cập trang khác để kiểm tra có thể tiếp tục, không tự xóa video chỉ vì chưa tải đến trang cuối.
- Nếu nhận diện kênh/playlist thành công nhưng **không có video hợp lệ**, chỉ tiêu **Đồng bộ video thành công** phải ghi nhận **không đạt**; không nhầm với chỉ tiêu **Đăng nhập Google thành công**.

## Chạy kiểm thử không cần YouTube thật

```bash
python tests/test_v4322_incremental_curated.py
python tests/test_v4321_youtube_sync_empty_and_403.py
python tests/test_youtube_playlist_ownership.py
```

Kiểm thử tổng: chạy từng tệp `tests/test_*.py`. Các tệp có tên phiên bản cũ trong **thư mục tests** là kiểm thử hồi quy mã nguồn, không phải hướng dẫn triển khai cũ.

## Giới hạn kiểm tra

Kiểm thử ngoại tuyến và biên dịch thành công không thể xác nhận YouTube Data API hoặc OAuth thực tế trên tài khoản Render. Cần quan sát phiên đồng bộ thật, quyền truy cập của playlist, số video được nhập, URL QR và dữ liệu PostgreSQL sau triển khai. Đồng bộ theo từng bước do **trình duyệt đang mở** thực hiện; đây không phải tác vụ nền luôn chạy khi người dùng tắt trình duyệt. Với các playlist rất lớn hoặc nhiều tài khoản kết nối, thời gian hoàn tất vẫn phụ thuộc API của Google.
