# Bổ sung triển khai v4.3.22

Phiên bản này thêm bảng `youtube_sync_jobs` để lưu tiến độ đồng bộ từng phần. Giữ `AUTO_CREATE_DB=1` khi triển khai để tự tạo bảng mới và giữ nguyên các bảng PostgreSQL hiện có. Sao lưu dữ liệu trước khi nâng cấp. Đăng nhập vào giao diện không còn phụ thuộc thời gian đồng bộ; trình duyệt phải còn mở để thực hiện các bước đồng bộ. Xem `HUONG_DAN_KIEM_TRA_V4322.md`.

---

# Hướng dẫn cập nhật v4.3.16 – lọc sinh viên theo môn/lớp

1. Sao lưu dữ liệu trên Web App trước khi cập nhật. Không xóa PostgreSQL, mã QR hay lịch sử.
2. Giải nén `TAO_MA_QR_TU_DONG_YOUTUBE_v4.3.16_RENDER.zip`, cập nhật nội dung lên GitHub đang nối với Render và chờ triển khai thành công.
3. Trên **Thống kê khai thác → Mục 2**, kiểm tra bộ chọn **Tên sinh viên**: chọn môn học chỉ hiện SV theo học môn đó; chọn lớp chỉ hiện SV lớp đó; chọn cả hai chỉ hiện SV của môn học trong lớp được chọn.
4. Bỏ chú thích dưới ô chọn sinh viên; danh sách vẫn tự cập nhật khi thay đổi môn học hoặc lớp. Chọn **Lọc kết quả** để truy vấn lại bảng thống kê.
5. Nhấn **Ctrl+F5** nếu giao diện còn hiển thị bản cũ.

Không thay đổi cấu trúc PostgreSQL hoặc đường dẫn QR. Chưa kiểm thử tích hợp trên Render.

---

# Hướng dẫn nâng cấp v4.3.15 trên Render

1. Trước khi cập nhật, sao lưu cơ sở dữ liệu bằng chức năng Sao lưu & Khôi phục. Không xóa hoặc đặt lại PostgreSQL.
2. Giải nén `TAO_MA_QR_TU_DONG_YOUTUBE_v4.3.15_RENDER.zip` rồi cập nhật mã nguồn lên nhánh GitHub đang kết nối Render; chờ bản triển khai thành công.
3. Mở Thống kê khai thác → mục 2. Chọn **Chưa hoàn thành**, để lớp, học liệu và tên SV ở **Tất cả**, bấm **Lọc kết quả**. Các phiên có thời lượng > 00:00 nhưng dưới 95% phải hiển thị.
4. Chọn **Tên sinh viên** từ danh sách và lọc lại; kiểm tra chỉ các phiên thuộc SV đó hiển thị. Xóa lọc và kiểm tra 10 dòng/trang.
5. Chọn **SV chưa hoàn thành học liệu (đối chiếu lớp)** để kiểm tra trường hợp cần đối chiếu **lớp + học liệu được giao**; chức năng này tách biệt với bộ lọc phiên xem chưa hoàn thành.
6. Thử trên dữ liệu thực tế: video dài 05:35 xem 03:50 → Chưa hoàn thành; từ 05:18,25 trở lên → Hoàn thành; 00:00 → Chưa xem.

Không thay đổi schema PostgreSQL; không ảnh hưởng đường dẫn mã QR và lịch sử quét/xem. Chưa thử kết nối tích hợp thực tế với hệ thống Render.

---

# Hướng dẫn cập nhật Web App v4.3.14 trên Render

## 1. Sao lưu và triển khai

Sao lưu dữ liệu tại **Quản trị viên → Sao lưu & khôi phục**. Giải nén `TAO_MA_QR_TU_DONG_YOUTUBE_v4.3.14_RENDER.zip`, cập nhật mã nguồn lên GitHub như những lần trước và chờ Render triển khai. **Không xóa PostgreSQL**. Sau đó nhấn **Ctrl + F5** để làm mới giao diện.

## 2. Kiểm tra điều hướng

Chỉ **mục menu hiện đang mở** (ví dụ **Thống kê khai thác**) có **chữ đỏ, in đậm**. Các mục khác và nút chức năng hiển thị nét thường như bản v4.3.13.

## 3. Kiểm tra trạng thái SV theo quy tắc 95%

| Độ dài video | Thời lượng SV xem | Trạng thái đúng |
|---|---|---|
| 05:35 | 00:00 | **Chưa xem** |
| 05:35 | 03:50 | **Chưa hoàn thành** (230/335 giây = 68,7%) |
| 05:35 | 05:18 | **Chưa hoàn thành nếu dưới 318,25 giây thực tế** |
| 05:35 | 05:19 | **Hoàn thành** |

**Lưu ý:** 95% của 05:35 là **318,25 giây**, tức 05 phút 18,25 giây. Phép tính dùng thời lượng giây thực tế được máy chủ ghi, không chỉ giá trị phút:giây đã làm tròn trong bảng.

Bản ghi cũ có `completed=True` do cơ chế cũ sẽ không còn mang nhãn **Chưa đủ dữ liệu xác nhận**; Web App tính lại trạng thái theo thời lượng xem đã lưu: 00:00 = Chưa xem, chưa đạt 95% = Chưa hoàn thành. Lịch sử gốc không bị xóa hoặc sửa.

## 4. Kiểm tra đồng bộ báo cáo

Vào **Thống kê khai thác**, kiểm tra bộ lọc **Đã hoàn thành**, **SV chưa hoàn thành**, thống kê trên Dashboard và xuất **CSV quá trình xem**. Mọi nơi phải chỉ công nhận hoàn thành khi thực xem ít nhất **95%**. Khi quét mà không phát video, thời lượng là 00:00 và trạng thái là Chưa xem.

## 5. Cấu hình Render

Ngưỡng 95% đã được **cố định trong `config.py`**, không còn lấy từ biến môi trường `COMPLETION_THRESHOLD` cũ (vì nhiều hệ thống trước đây đã đặt 0.90). `render.yaml` ghi 0.95 cho nhất quán. Bạn không cần đặt lại PostgreSQL hoặc đổi Secret Key/OAuth.

**Đã kiểm tra offline** mã nguồn Python, giao diện Jinja/CSS, mô phỏng các trường hợp ranh giới 95% và truy vấn SQLite. Chưa kiểm thử trực tiếp trên Render/Google OAuth/YouTube API.

---

# Hướng dẫn cập nhật Web App v4.3.13 trên Render

## 1. Sao lưu

Đăng nhập Quản trị viên → **Sao lưu & khôi phục**, tải một bản sao lưu trước khi cập nhật. Không đăng tệp `.env`, dữ liệu sao lưu và khóa Google lên GitHub.

## 2. Cập nhật

Giải nén `TAO_MA_QR_TU_DONG_YOUTUBE_v4.3.13_RENDER.zip`, tải các tệp nguồn lên repository GitHub đang dùng với Render, đợi triển khai thành công. **Không xóa hoặc tạo lại PostgreSQL**. Bản này không thay đổi bảng/cột hay URL mã QR. Sau triển khai nhấn **Ctrl+F5** để nhận CSS/JavaScript mới.

## 3. Kiểm tra giao diện

Mở **Kênh YouTube**, **Kho video học liệu**, **Mã QR động**, **Thống kê khai thác**. Nút và menu phải có nét chữ bình thường, không bị in đậm hàng loạt; mục menu được chọn vẫn có màu đỏ. Nhãn các nút tải/xóa QR và chức năng giữ nguyên phiên bản trước.

## 4. Kiểm tra sửa lỗi thời lượng và hoàn thành (quan trọng)

Dùng HSSV và mã QR học liệu thử nghiệm, video dài khoảng **4–5 phút**:

1. **Chỉ xem vài giây rồi tua đến cuối**: không được báo Hoàn thành, thời lượng xem không được tự tăng thành toàn bộ thời lượng video.
2. **Xem liên tục từ đầu đến cuối**: Thống kê khai thác phải thể hiện thời lượng đã xem hợp lý (khoảng 4–5 phút tùy độ dài và mạng), trạng thái **Hoàn thành** khi ghi nhận thực tế ít nhất 90% độ dài video.
3. **Quét nhưng không phát**, hoặc tạm dừng ngay: không được báo Hoàn thành.
4. **Mở QR playlist, xem các video riêng**: mỗi video có thời lượng và trạng thái độc lập; không được lấy thời lượng video trước cho video sau.
5. **Kiểm tra bản ghi cũ `00:00 – Hoàn thành`**: nay phải hiển thị **Chưa đủ dữ liệu xác nhận**. Dữ liệu gốc vẫn giữ nguyên trong CSDL phục vụ đối chiếu.
6. **Lọc “Đã hoàn thành” và xem Dashboard**: các bản ghi không đủ thời lượng xem xác nhận không được tính vào số hoàn thành.

Nếu một video được xem hết nhưng vẫn hiện **Chưa hoàn thành**, cần kiểm tra tab Network trong trình duyệt (các yêu cầu `/api/watch/start` và `/api/watch/event`), lỗi mạng hoặc chính sách chặn YouTube IFrame API. Không được tự coi kết thúc video là bằng chứng đã xem đủ thời gian.

## 5. Những gì thay đổi trong mã

- Máy chủ: cập nhật `/api/watch/start`, `/api/watch/event`, số liệu Dashboard, truy vấn thống kê và xuất CSV để dùng thời lượng xem xác minh; dùng độ dài YouTube đồng bộ nếu trình phát trả 0.
- Trình duyệt: cập nhật `static/viewer.js`, `static/playlist_viewer.js` để gửi sự kiện theo thứ tự và chỉ hiện xác nhận hoàn thành khi máy chủ trả về thành công.
- CSS: điều chỉnh `static/app.css`, trả font-weight menu/nút về 400, giữ màu sắc tương phản của nút và nhãn chức năng.

**Kiểm thử hiện có:** kiểm tra cú pháp Python/JavaScript, 22 mẫu Jinja, truy vấn SQL trên SQLite và các ca test xem đủ, tua, đứng hình, thời lượng 0, playlist, lịch sử cũ. Chưa kiểm thử trực tiếp trên Render và PostgreSQL sản xuất.

---

# Thông tin các phiên bản trước (v4.3.12)

# Ghi chú phiên bản v4.3.12

## 1. Sao lưu trước khi cập nhật

Đăng nhập **Quản trị viên → Sao lưu & khôi phục**, tải bản sao lưu riêng trước khi triển khai. Không đăng tệp `.env`, bản sao lưu PostgreSQL, token Google hoặc khóa bí mật lên GitHub.

## 2. Triển khai

Giải nén `TAO_MA_QR_TU_DONG_YOUTUBE_v4.3.12_RENDER.zip`, đưa **các tệp trong thư mục đã giải nén** vào nhánh GitHub đang triển khai; Render sẽ nhận commit và triển khai theo cấu hình hiện tại. **Không xóa hoặc tạo lại PostgreSQL.** Bản này không thêm cột/bảng mới so với v4.3.10: dùng bảng `edit_history` sẵn có để lưu lịch sử đổi playlist.

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

## 4. Cập nhật giao diện và nhãn nút v4.3.12

- Trong **Mã QR động → Kho mã QR**, nút tải ZIP hàng loạt có nhãn **Tải tất cả mã QR**; nếu đang lọc theo môn, tệp chỉ chứa QR của môn được chọn, còn nếu đang xem tất cả thì các ảnh được chia thư mục theo từng môn.
- Nút xóa hàng loạt có nhãn **Xóa tất cả mã QR**; thao tác này xóa mọi QR thuộc phạm vi quản lý **bất kể bộ lọc**, vẫn cần xác nhận. Các nút riêng của từng mã giữ nhãn **Tải mã QR**, **Xóa mã QR**.
- Chữ nút chức năng trên các trang đều **màu đen, in đậm**. Những nút nền tối trước đó được chuyển sang tông nền nhạt để dễ đọc. Tên toàn bộ mục trên thanh menu (Kênh YouTube, Giảng viên, Môn học/Mô đun, Danh sách lớp đang dạy, v.v.) được in đậm; mục đang mở vẫn hiển thị chữ đỏ.
- Sau khi Render triển khai xong, nhấn **Ctrl+F5** để trình duyệt tải lại CSS. Bản này **không thêm cột/bảng mới và không xóa dữ liệu PostgreSQL**.

## 5. Những nội dung kế thừa v4.3.11

- **Kênh YouTube:** bỏ khối “Playlist đã đồng bộ”; giữ thông tin kênh, trạng thái kết nối và nút **Đồng bộ lại**.
- **Các nút tải QR riêng lẻ** hiển thị nhãn **Tải mã QR** (không kèm PNG/ZIP); nút tải hàng loạt dùng **Tải tất cả mã QR**.
- **Các nút xóa QR riêng lẻ** hiển thị **Xóa mã QR**; thao tác xóa hàng loạt là **Xóa tất cả mã QR** và yêu cầu xác nhận.

## 6. Kiểm tra sau triển khai

Nên thử với **môn học và playlist thử nghiệm** có QR đã tạo, tránh xóa playlist thật đang phục vụ SV. Kiểm tra trường hợp playlist bị xóa, chuyển đích thành công, mở thử bản in QR cũ, nhật ký trước đó vẫn tồn tại; thử chuyển sang playlist trống hoặc playlist đã có QR khác để xác nhận Web App từ chối. Sau đó kiểm tra giao diện Kênh YouTube và các nhãn nút ở cả hai trang.

**Kiểm tra đã chạy tại môi trường đóng gói:** cú pháp Python, 22 mẫu Jinja, cú pháp JavaScript, thử luồng đổi playlist bằng chính nghiệp vụ Flask (tách ra kiểm thử offline) và cơ sở dữ liệu SQLite mô phỏng, phân quyền, sao lưu/ZIP theo môn và kiểm tra mã nguồn trước đó. **Chưa kiểm thử tích hợp với Render/PostgreSQL/Google OAuth thực tế.**
