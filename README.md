# Cập nhật v4.3.20 – 22/10/2026

**Mục 2 – Thống kê khai thác học liệu của sinh viên**

- Thêm 4 ô thống kê: **Tổng lượt quét**, **Quét thành công**, **Quét không thành công**, **Tỷ lệ quét thành công** (`thành công / tổng lượt quét × 100%`). Nếu chưa có lượt quét, hiển thị 0 ở các ô đếm và `—` ở tỷ lệ.
- Các ô dùng số lượt quét từ **ScanLog gốc**, không cộng các cột theo video, không nhân lượt quét khi một QR playlist mở nhiều video; tính đủ lịch sử, không giới hạn trong 10 dòng phân trang.
- Phạm vi các ô theo 4 bộ lọc **Môn học/Mô đun, Lớp, Học liệu được giao, Tên sinh viên**, tuân thủ quyền GV/Quản trị viên. **Tình trạng** chỉ lọc các dòng ở bảng video, không làm thay đổi thống kê nhật ký QR gốc.
- Bảng thông tin chi tiết sắp theo **Lớp → Môn → Tên gọi sinh viên**, tiếp đến họ tên và học liệu; sắp trong truy vấn trước khi chia 10 dòng/trang. Ưu tiên tên lớp trong `SchoolClass`, tương thích lớp cũ `ClassGroup`.
- Giữ một dòng/SV–video, 9 cột, trạng thái xem tốt nhất, các bộ lọc và file CSV nhật ký gốc; không thay đổi bảng dữ liệu PostgreSQL hoặc URL QR.
- Bổ sung `tests/test_v4320_student_metrics_sort.py` để kiểm tra tổng gốc playlist, quyền truy cập, bộ lọc, tỷ lệ, thứ tự giữa các trang và biểu thức sắp tên trên PostgreSQL.

# Thay đổi v4.3.19 – 22/10/2026

## Sửa lỗi số lượt quét bằng 0 ở bảng Thống kê khai thác học liệu SV

- Bỏ hoàn toàn đoạn mô tả dài bắt đầu bằng **“Bảng tổng hợp mỗi sinh viên – video chỉ một dòng…”** ở phần đầu mục 2. Giữ bảng với 9 cột và một hàng cho mỗi cặp SV–video.
- Tính các lượt quét thành công/thất bại **từ tất cả bản ghi `ScanLog` đã tồn tại** trong CSDL, không chỉ lượt phát sinh sau khi cập nhật. Không sửa, xóa hoặc tự tạo bản ghi quét lịch sử.
- Đối với QR video, số lượt quét theo `video_id` đã ghi trong nhật ký.
- Đối với QR **playlist**, nhật ký lưu lượt quét QR (`video_id` có thể rỗng). Mỗi lượt quét được liên kết với các video mà đúng sinh viên đã thực sự mở trong khoảng từ lượt quét đó tới lượt quét tiếp theo của cùng QR. Không giới hạn 24 giờ như cách ghép trước đây. Nếu mở 5 video từ một lượt quét playlist, mỗi dòng video sẽ thể hiện 1 lần truy cập từ QR, thay vì cả 5 dòng đều bằng 0.
- Một sinh viên mở lại cùng video nhiều lần trong **cùng một lượt quét** vẫn chỉ tính 1 lượt cho video đó. Những lượt quét **khác nhau** được cộng đúng số lần.
- **Phân biệt hai thước đo:** tổng số lượt quét QR trên Tổng quan, nhật ký quét và tệp CSV vẫn là `COUNT(DISTINCT ScanLog.id)` (không nhân theo số video). Số lượt quét tại **từng dòng video của playlist** có thể xuất hiện ở nhiều dòng video cùng truy cập từ một lượt QR; **không cộng các dòng video để suy ra tổng lượt quét toàn hệ thống.**
- Nếu một lượt quét playlist không có video nào được phát, nó được giữ trong hàng `(chưa phát video)`; lượt quét thất bại không bị suy đoán là truy cập thành công video nào. Nếu một phiên xem không có bản ghi quét tương ứng, không tự đặt số lượt quét thành 1.
- Giữ nguyên trạng thái tốt nhất (`Hoàn thành` không bị hạ khi xem lại), thời lượng xem cao nhất của một phiên, bộ lọc, phân trang và các tệp CSV gốc.
- Không thay đổi sơ đồ PostgreSQL, không cần đặt lại mã QR hoặc xóa dữ liệu. Cần sao lưu CSDL trước khi triển khai và đối chiếu trên Render bằng CSV gốc.

## Kiểm thử

`python tests/test_v4319_historical_playlist_scans.py` – kiểm tra 5 video trong playlist đã xem sau 3 ngày kể từ lượt quét, các lần xem lại, lượt quét thành công/thất bại và không nhân bản dữ liệu gốc.

---

# Thay đổi v4.3.18 – 22/10/2026

## Một dòng cho mỗi sinh viên – video ở mục 2 (Thống kê khai thác học liệu)

- Bảng thông tin chi tiết có các cột: **STT, Tên SV (Mã), Lớp, MH/MĐ, Tên học liệu số, Số lượt quét thành công, Số lượt quét không thành công, Thời lượng xem, Trạng thái**. Bỏ cột **Thời gian** và **Kết quả**; STT chạy tiếp qua các trang 10 dòng.
- **Mỗi SV–video chỉ hiển thị một hàng**, dù SV quét lại hay có nhiều phiên xem cùng video, kể cả nhiều QR trỏ tới video đó. Số lượt quét thành công/thất bại là tổng bản ghi `ScanLog` được ghi nhận và thuộc phạm vi bộ lọc. Mọi `ScanLog` chỉ được đếm **một lần**; không tự tạo lượt quét từ một phiên xem.
- QR **playlist** có thể phát nhiều video từ một lượt quét. Để tránh nhân lượt quét, lượt mở QR được gắn với video **được phát đầu tiên** trong lượt đó; các video còn lại vẫn có hàng và trạng thái riêng nhưng không cộng thêm lượt quét. Nếu QR playlist chưa phát video nào, số lượt quét của nó hiện trên một hàng **[Tên playlist] (chưa phát video)** (nhóm không phải video), không suy đoán gán cho video khác.
- `Thời lượng xem` thể hiện **phiên xem có thời lượng thực lớn nhất** đối với SV–video trong phạm vi lọc, thay vì cộng các phiên có thể xem trùng một đoạn. `Trạng thái` luôn là **tốt nhất SV từng đạt** cho video (`Chưa xem` → `Chưa hoàn thành` → `Hoàn thành`) tính từ các phiên xem đã lưu; xem lại không làm hạ cấp.
- Các lựa chọn **Đã hoàn thành, Chưa hoàn thành, Đã quét/chưa xem, Mở QR thất bại** lọc theo hàng SV–video **sau khi tổng hợp**, không lọc phiên trước khi tính số lượt quét. Hai lựa chọn đối chiếu danh sách lớp vẫn sử dụng logic đối chiếu riêng.
- Chỉ thay đổi truy vấn và hiển thị; **không thay đổi database schema, dữ liệu gốc, QR đang sử dụng hoặc CSV nhật ký quét/xem**. Vẫn giữ chống trùng lượt tải lại trong 30 giây. Thử nghiệm offline bằng SQLite, cần xác minh trực tiếp với PostgreSQL trên Render sau triển khai.

---

# Thay đổi v4.3.17 – 22/10/2026

## Trạng thái tốt nhất của SV theo từng video (không hạ cấp khi xem lại)

- **Mỗi lần quét/mở QR vẫn lưu riêng** trong `ScanLog`; số lượt quét và số lượt quét thành công trên Tổng quan được tính từ các bản ghi quét, không dựa trên trạng thái học. Cơ chế ngăn ghi trùng khi mở lại trong vòng 30 giây được giữ như bản trước.
- **Trạng thái học liệu** được suy ra theo cặp `(mã SV, ID video)` trên TẤT CẢ phiên xem đã có. Quy tắc: nếu từng có một phiên xem đủ ít nhất 95% độ dài video hợp lệ thì **Hoàn thành**; nếu chưa đạt nhưng từng xem >0,5 giây thì **Chưa hoàn thành**; nếu không có thời lượng xem thì **Chưa xem**. Về sau xem lại vài đoạn vẫn **Hoàn thành**.
- **Không cộng dồn thời gian của các phiên khác nhau** để tránh xem lặp nhiều lần cùng một đoạn ngắn mà được chứng nhận hoàn thành. Thời lượng trên mỗi dòng vẫn là số giây của phiên thực tế, không sửa nội dung lịch sử.
- Cập nhật cùng quy tắc cho API `/api/watch/start`, `/api/watch/event`, bộ lọc hoàn thành/chưa hoàn thành/chưa xem, bảng lịch sử, đối chiếu SV và CSV phiên xem. CSV giữ cả trạng thái chứng thực **của từng phiên** để đối chứng.
- **Tổng quan**: giữ nguyên tổng phiên xem và lượt quét, thêm **lượt quét thành công**, thay tỷ lệ phiên hoàn thành thành **tỷ lệ hoàn thành SV–video** (đếm mỗi cặp SV–video một lần). Chỉ bổ sung chỉ mục tra cứu, không thêm bảng/cột, không xóa hay ghi đè dữ liệu.
- Việc công nhận hoàn thành vẫn phải có thời lượng thực được xác minh, không chỉ dựa vào `ended` hoặc cờ `completed` cũ. Cần kiểm tra lại trên môi trường Render/PostgreSQL thực tế.

---

# Thay đổi v4.3.15 – 21/10/2026

## Sửa mục 2 – Thống kê khai thác học liệu của sinh viên

- **Khắc phục bộ lọc “Chưa hoàn thành”**: trước đây mục này chuyển sang danh sách đối chiếu sĩ số, nên khi chưa chọn **Lớp** và **Học liệu được giao** thì không có dòng dữ liệu. Từ v4.3.15, nó lọc trực tiếp các **phiên xem** đã ghi nhận thời lượng > 00:00 nhưng **dưới 95%** độ dài video; không yêu cầu chọn lớp/học liệu. Các phiên chưa có độ dài video hợp lệ nhưng đã ghi nhận thời lượng xem được xem là **Chưa hoàn thành**, không tự xác nhận hoàn thành.
- Tách lựa chọn **“SV chưa hoàn thành học liệu (đối chiếu lớp)”** để giữ chức năng so sánh danh sách lớp với số video phải xem trong QR. Đối chiếu lớp và “SV chưa quét QR” yêu cầu chọn lớp và học liệu cụ thể.
- Thay bộ lọc **Thời gian** tại **mục 2** bằng danh sách **Tên sinh viên**; chỉ liệt kê sinh viên thuộc phạm vi người dùng được phép tra cứu. Hiển thị tên và **ba số cuối mã SV**; mã đầy đủ vẫn được đối chiếu ở phía máy chủ. Bộ lọc Thời gian ở **mục 1 (hoạt động hệ thống)** vẫn giữ nguyên.
- Giữ nguyên **10 dòng/trang**, thanh phân trang có số và neo về mục 2, dữ liệu lịch sử và ngưỡng hoàn thành 95%.
- Không thay đổi cấu trúc PostgreSQL, không xóa dữ liệu hoặc mã QR đã in.

**Lưu ý kỹ thuật:** các phiên cũ có thời lượng bằng 0 không được tính là “Chưa hoàn thành”; chúng thuộc “Chưa xem”. Chức năng đối chiếu lớp xem xét cả những video chưa có phiên xem, nên số SV trong kết quả đối chiếu khác số dòng phiên xem chưa hoàn thành là điều bình thường.

---

# Thay đổi v4.3.14 – 20/10/2026

- **Thanh điều hướng:** mục đang mở màu **đỏ, in đậm**; các mục còn lại nét thường. Nút chức năng không in đậm hàng loạt.
- **Quy tắc xem video bắt buộc (95%):** ước tính thời gian xem **00:00** là **Chưa xem**; từ 1 giây đến dưới 95% độ dài là **Chưa hoàn thành**; từ 95% trở lên mới là **Hoàn thành**. Ví dụ video 05:35 (335 giây), xem 03:50 (230 giây, 68,7%) là Chưa hoàn thành.
- **Thống kê đồng bộ:** Dashboard, lọc “Đã hoàn thành”, đối chiếu “SV chưa hoàn thành”, CSV và bảng lịch sử cùng kiểm tra bằng thời lượng ghi nhận / độ dài video, không dựa vào cờ completed cũ. Các bản ghi cũ vẫn được giữ nguyên trong CSDL nhưng kết quả hiển thị được tính lại.
- **Ngưỡng được cố định:** `COMPLETION_THRESHOLD=0.95` trong cấu hình ứng dụng nhằm tránh Render còn sử dụng giá trị biến môi trường cũ 0.90; `render.yaml` cũng được cập nhật lên 0.95.
- Không thêm cột/bảng, không đổi mã QR đã phát hành. Cần thử thực tế trên Render với video thử nghiệm sau triển khai.

---

# Thay đổi v4.3.13 – ngày 20/10/2026

- **Giao diện:** Bỏ in đậm hàng loạt chữ trên tất cả nút và menu điều hướng. Chữ dùng nét bình thường, giữ màu đen và nền nút sáng như bản trước; menu đang mở vẫn màu đỏ. Nút **Tải tất cả mã QR**, **Xóa tất cả mã QR**, **Tải mã QR**, **Xóa mã QR** không đổi nhãn hoặc chức năng.
- **Sửa lỗi thống kê 00:00 nhưng Hoàn thành:** Luồng cũ đặt `WatchSession.completed=True` vô điều kiện khi YouTube báo `ended`, ngay cả khi `estimated_watch_seconds=0`; v4.3.13 yêu cầu ghi nhận thời lượng xem thực tế tối thiểu bằng ngưỡng cấu hình `COMPLETION_THRESHOLD` (mặc định 90%) của độ dài video thì mới hoàn thành. Tua đến cuối, sự kiện ended đơn lẻ, video đứng hình hoặc chưa có dữ liệu thời lượng không đủ điều kiện.
- **Độ dài video:** Nếu trình phát chưa trả `getDuration()` (0 giây), máy chủ dùng `Video.duration_iso` đã đồng bộ từ YouTube để tính mẫu số. Không dùng độ dài video để thay thế cho thời gian SV thực xem.
- **Trình phát video và playlist:** Các sự kiện play/heartbeat/pause/ended được gửi theo thứ tự, chốt vị trí tại thời điểm gửi; chuyển video trong playlist kết thúc phiên cũ trước khi tạo phiên mới. Thông báo hoàn thành trên giao diện dựa vào kết quả máy chủ xác nhận, không tự đánh dấu khi YouTube kết thúc.
- **Dữ liệu lịch sử:** Giữ nguyên log trong PostgreSQL, không viết lại thời lượng xem cũ thiếu chứng cứ. Các bản ghi cũ có `completed=True` nhưng không đủ thời gian xác minh sẽ hiển thị **Chưa đủ dữ liệu xác nhận**, không còn được đếm vào tỷ lệ hoàn thành ở Dashboard, bộ lọc Hoàn thành, hoặc xuất CSV kết quả đã hoàn thành. Nếu cần điều chỉnh hồ sơ lịch sử, cần kiểm tra nhật ký sự kiện riêng, không suy đoán.
- **Triển khai:** Không thêm cột/bảng, không xóa dữ liệu, giữ nguyên mọi mã QR đã phát hành. Sau cập nhật Render nhấn **Ctrl+F5**. Cần chạy thử video dài khoảng 4–5 phút với HSSV thật theo quy trình dưới đây; chưa thử trực tiếp Google OAuth/YouTube/PostgreSQL trên Render.

---

# Thay đổi v4.3.12 – ngày 20/10/2026

- **Mã QR động – thao tác hàng loạt:** Nút tải ZIP trong **Kho mã QR** có nhãn **Tải tất cả mã QR**. Khi lọc môn học/mô đun, tệp ZIP chỉ gồm QR của môn đang chọn; khi xem tất cả, ZIP sắp theo thư mục từng môn. Nút xóa hàng loạt là **Xóa tất cả mã QR** và vẫn cần xác nhận; lưu ý **xóa toàn bộ trong phạm vi quản lý**, không phụ thuộc bộ lọc hiện tại. Nút của từng QR vẫn là **Tải mã QR** và **Xóa mã QR**.
- **Toàn Web App:** chữ trong các nút chức năng là màu đen, in đậm ở trạng thái bình thường, rê chuột, nhấn và vô hiệu hóa. Các nút nền tối chuyển sang nền nhạt cùng tông để giữ độ tương phản với chữ đen. Các tên menu (Kênh YouTube, Giảng viên, Môn học/Mô đun, Danh sách lớp đang dạy, v.v.) hiển thị in đậm. Menu đang chọn vẫn nổi bật màu đỏ.
- **Không thay đổi nghiệp vụ, URL mã QR, vai trò hoặc PostgreSQL** so với v4.3.11. Không cần xóa dữ liệu. Giao diện cần tải lại trình duyệt sau triển khai để nhận CSS mới.
- Kiểm thử: cú pháp Python, biên dịch 22 mẫu Jinja, kiểm tra nội dung các nút tải/xóa và menu, cú pháp CSS, các ca kiểm thử hồi quy offline. Chưa kiểm thử trên Render/PostgreSQL thực tế.

---

# Thay đổi v4.3.11 – ngày 20/10/2026

- Bổ sung **Đổi playlist đích** cho mã QR playlist ở **Kho video học liệu** và **Mã QR động**. Giảng viên chọn playlist mới đã đồng bộ trong kênh kết nối và còn video hợp lệ. Giữ nguyên mã QR/slug/đường dẫn và bản ghi quét/xem cũ, không tạo QR mới.
- Không cho thay playlist bằng playlist không thuộc quyền truy cập, playlist trống, hoặc playlist đã có QR khác còn hoạt động trong cùng môn. Quyền quản lý sau bàn giao môn tiếp tục tuân theo giảng viên phụ trách hiện tại.
- Khi thay đổi, chỉ cập nhật liên kết môn đang thao tác; lưu dấu vết playlist cũ/mới, người thực hiện và thời điểm trong **EditHistory** hiện có. Thống kê lượt quét chưa phát video phản ánh playlist tại thời điểm quét.
- **Kênh YouTube:** bỏ khu vực liệt kê “Playlist đã đồng bộ”.
- **Nhãn nút:** toàn bộ nút tải mã QR là **Tải mã QR**, nút xóa mã QR là **Xóa mã QR**. Các nút xuất ZIP vẫn áp dụng đúng bộ lọc và có chú thích để tránh nhầm với tải PNG riêng lẻ.
- Giữ nguyên phân trang 5 dòng Kho video và 10 dòng Thống kê; các chức năng khác kế thừa v4.3.10. Không thay schema PostgreSQL, không xóa dữ liệu hiện có.
- Kiểm tra offline: cú pháp Python, Jinja, JavaScript, nghiệp vụ SQLite thay playlist và phân quyền, lịch sử, kiểm thử hồi quy; chưa kiểm tra trực tiếp trên Render.

---

# Thay đổi v4.3.10 – ngày 20/10/2026

- **Kho video học liệu:** danh sách playlist và danh sách video có phân trang độc lập **5 dòng/trang** (truy vấn lấy đúng 5 dòng tại máy chủ); bộ lọc và số trang hiện tại được giữ khi thao tác.
- **Video đã có QR theo môn được chọn:** thay nút Tạo QR bằng **Tải mã QR**, đồng thời thêm **Xóa** và **Đổi video đích**. Sau khi tạo/xóa/đổi, cập nhật tại dòng hiện tại bằng yêu cầu nền để giữ vị trí, không tải lại toàn bộ trang.
- **Playlist đã có QR:** có **Tải mã QR**, **Xóa mã QR**, bỏ **Mở thử** khỏi Kho video học liệu. Playlist không còn trên YouTube vẫn được báo rõ trong thư viện khi có liên kết môn học; QR lịch sử không bị xóa tự động; không tạo QR mới cho nguồn đã mất.
- **Quản lý mã QR động:** phục hồi **Tải mã QR (PNG)** và **Mở thử** ở bảng Kho mã QR cho cả video/playlist; vẫn cho Xóa và Đổi video đích (chỉ QR video).
- **Thống kê khai thác:** mục 1 dùng danh sách chọn **Người thực hiện** thay cho ô tìm người/học liệu; mục 2 bỏ ô Tên video/học liệu, đưa hai nút lọc lên ngang hàng bộ lọc. Quyền xem thống kê và 10 dòng/trang không đổi.
- **Google OAuth:** khi Google trả lỗi `mismatching_state`/CSRF, không bỏ kiểm tra state; thử đăng nhập an toàn lại tối đa một lần nếu phiên còn hợp lệ, nếu tiếp tục lỗi thì hướng dẫn kiểm tra cookie, tab đăng nhập, BASE_URL và SECRET_KEY. Không thể cam kết hết lỗi khi chưa kiểm tra môi trường Render.
- **Dữ liệu:** không thêm bảng/cột mới so với v4.3.9; không xóa dữ liệu PostgreSQL, không tự thay mã/slug QR đã in.
- **Kiểm thử:** Jinja, Python, JavaScript, hiển thị giao diện v4.3.10 và một số tình huống SQLite mô phỏng đạt; chưa kiểm thử trực tiếp Google/Render.

---

# Thay đổi v4.3.9 – Kho học liệu, ZIP theo môn và nhật ký lỗi (20/10/2026)

- **Môn học/Mô đun:** phóng to cảnh báo chỉ tạo một môn một lần; làm đậm thông tin về dạy nhiều lớp và tránh môn trùng tên.
- **Kho video học liệu:** thao tác Lưu môn áp dụng cho playlist chạy bằng yêu cầu nền, chỉ cập nhật dòng vừa lưu, giữ nguyên vị trí cuộn; có thông báo ngay trong dòng. Khi JavaScript không hoạt động, vẫn cho gửi biểu mẫu theo cơ chế cũ.
- **Playlist đã có mã QR:** trong cột Mã QR, khi chọn môn đã có mã QR, hiện **Tải mã QR** và **Mở thử**; nếu môn chưa có QR, hiện **Tạo mã QR**. Không hiện hai nút tải/mở thử của playlist ở bảng Kho mã QR động để tránh trùng thao tác.
- **ZIP trong Mã QR động:** khi xem tất cả, ZIP chứa thư mục riêng theo **mã môn + tên môn**, và một thư mục riêng cho mã QR không gán môn. Khi đang lọc môn thì ZIP chỉ chứa QR thuộc môn đang lọc. Giữ kiểm tra phân quyền phía máy chủ, chặn yêu cầu tải môn ngoài quyền.
- **Nhật ký lỗi:** thêm người thực hiện thất bại, lưu định danh GV hoặc mã SV/lớp khi có thể xác định; hiển thị GV theo họ tên + email, SV theo họ tên + ba số cuối mã SV + tên lớp. Sự kiện tự đồng bộ không bị gán nhầm cho GV. Lỗi cũ thiếu danh tính ghi “Không xác định”, không suy đoán. Bổ sung ghi nhật ký lỗi bất thường (HTTP 500) theo danh tính phiên hợp lệ, nếu có.
- **Nhận diện sinh viên:** danh sách chọn hiển thị họ tên kèm **3 số cuối mã HSSV**; API danh sách chỉ trả mã rút gọn (không trả toàn bộ mã); biểu mẫu vẫn gửi ID sinh viên, máy chủ tiếp tục kiểm tra thông tin và lưu mã đầy đủ trong PostgreSQL.
- **Nâng cấp CSDL không phá hủy dữ liệu:** bổ sung các cột tùy chọn `error_logs.actor_user_id`, `actor_student_code`, `actor_class_code` vào bảng hiện có khi `AUTO_CREATE_DB=1`; không xóa bảng/hồ sơ trước đây. Với `AUTO_CREATE_DB=0` cần nâng cấp cấu trúc riêng trước khi khởi chạy phiên bản mới.

**Kiểm tra tại môi trường đóng gói:** chạy qua cú pháp Python, 22 mẫu Jinja2, JavaScript Node syntax, kiểm tra bố cục playlist có/chưa QR theo môn, ZIP toàn bộ/lọc/không gán/bảo vệ phân quyền, và các bộ kiểm tra độc lập kế thừa. Chưa kiểm thử tích hợp với Render, PostgreSQL thực tế hoặc Google OAuth.

---

# Thay đổi v4.3.8 – Bàn giao môn học/mô đun (20/10/2026)

- Thêm chức năng **Bàn giao môn học/mô đun** cho tài khoản Quản trị viên tại trang **Môn học/mô đun**; lịch sử bàn giao được lưu ở bảng `course_transfers` và nằm trong bản sao lưu.
- **Giữ nguyên mã QR đã phát hành**: khóa môn, QR slug/URL, nguồn video/playlist, lớp, lịch sử quét/xem và tác giả QR gốc không bị sửa/xóa. Giáo viên mới được quyền quản lý, tải, cập nhật QR và xem thống kê theo môn được tiếp nhận; giáo viên cũ mất quyền quản lý mã QR thuộc môn đó.
- Trường hợp GV tiếp nhận đã có môn trùng tên, hệ thống từ chối bàn giao, không âm thầm gộp môn. Quản trị viên xác nhận trước khi thay đổi.
- Không chuyển kênh YouTube, OAuth/token của giáo viên cũ; cần giữ tài khoản nguồn khi còn video/playlist/QR liên quan môn đã bàn giao. Bảo vệ thao tác xóa giảng viên để không xóa nhầm QR đang được sử dụng.
- Các QR cũ vẫn phục vụ người học; không tự tạo QR mới từ nguồn video/playlist chưa được giảng viên tiếp nhận kết nối YouTube.
- **Cập nhật CSDL không phá hủy dữ liệu:** nếu `AUTO_CREATE_DB=1` hệ thống tự thêm bảng `course_transfers`, không sửa/xóa dữ liệu QR cũ. Đã thêm bảng mới vào sao lưu/khôi phục.
- Bộ kiểm thử tĩnh, Jinja và SQLite chạy đạt; chưa chạy tích hợp trên Render/PostgreSQL/Google OAuth.

---

# Thay đổi v4.3.7 – ngày 20/10/2026

Phiên bản tiếp nối v4.3.6, giữ nguyên cơ sở dữ liệu PostgreSQL và lịch sử quét/xem.

1. **Kho video học liệu → Playlist**: sau khi tích chọn môn và **Lưu**, trang quay lại đúng dòng playlist. Có thêm nút **Tạo mã QR** ngay từng dòng, gắn với môn học/mô đun đã lưu. Nếu playlist gán nhiều môn, GV chọn môn cần tạo QR. Đã tồn tại QR thì không tạo trùng.
2. **Kho video học liệu → Video**: thêm cột **Mã QR** với nút **Tạo mã QR** và bộ chọn môn học/mô đun. Nếu video chưa gán, thao tác này đồng thời gán riêng video vào môn được chọn. Cột **Playlist** hiển thị **Đã có mã QR** hoặc **Chưa có mã QR** cho video có playlist (dựa vào QR video còn hoạt động); video không thuộc playlist giữ nguyên dòng **Không thuộc playlist**. Khi tạo/lưu xong trở lại đúng dòng.
3. **Mã QR động**: bỏ hai khối tạo mã “Tạo mã QR tự động theo môn học/mô đun” và “Tạo QR riêng lẻ”; chỉ giữ kho mã, lựa chọn lọc theo môn, tải mã ZIP theo đúng môn, tải từng PNG và ZIP toàn bộ. Vẫn cho xem thử/đổi video đích/ngừng sử dụng.
4. **Quản lý môn học/mô đun**: không tạo thêm môn trùng tên của cùng GV. Nếu nhập lại cùng môn, khoa, bộ môn, hệ thống dùng môn hiện có và cộng thêm lớp đang chọn, không nhân đôi môn. Nếu khoa/bộ môn không trùng, báo kiểm tra lại trước khi nhập lớp. Giao diện cho phép thêm hoặc bỏ lớp áp dụng tại môn hiện có.
5. **Chuyển môn sang GV khác**: Đã bổ sung trong v4.3.8, chỉ quản trị viên bàn giao, giữ nguyên QR/slug/đường dẫn và lịch sử; quyền quản lý QR theo người phụ trách hiện tại, YouTube vẫn theo tài khoản gốc.

Không tự xóa mã QR đã in hoặc lịch sử thống kê, không yêu cầu xóa dữ liệu Render/PostgreSQL. Nên sao lưu DB trước khi triển khai chính thức.

Kiểm thử tĩnh: `python -m compileall -q .`, `python tests/test_v437_interface.py`, `python tests/test_youtube_playlist_ownership.py`, `python tests/test_combined_reporting_sql.py`. Để kiểm thử tích hợp các đường POST cần cài dependencies trong `requirements.txt`, kết nối DB thử nghiệm và xác thực Google test.

---

# BỔ SUNG v4.3.5 — Giao diện thống kê, QR và nghiệm thu

- **Thống kê khai thác:** hiển thị “Tên sinh viên (Mã)” với ba chữ số cuối mã SV, tên học liệu số; bỏ cột mã QR. Bộ lọc chọn học liệu bằng tên, không cho lọc tự do theo mã sinh viên. Bảng phiên xem lấy tên video thực tế, kể cả khi phát từ playlist. Mã SV đầy đủ vẫn lưu trong CSDL và vẫn dùng để đối chiếu.
- **Mã QR động:** số lượng playlist/QR hiển thị dạng số nguyên tự nhiên; chuẩn hóa nhãn nút; kho mã QR dạng bảng gồm học liệu, loại, môn học, trạng thái, ngày tạo và thao tác. Các hành động đổi video đích, mở thử và xóa QR vẫn giữ nguyên nghiệp vụ.
- **Giảng viên:** bỏ ghi chú dài về xóa GV; đổi nút chuẩn hóa dữ liệu dùng chung thành “Lưu”.
- **Đánh giá nghiệm thu:** giản lược lời dẫn; tăng chữ ở bốn ô tổng hợp; bảng kết quả tự ghi 10 dòng/trang, phân trang số, lọc thời gian/chức năng/kết quả và tìm tên người thực hiện/học liệu. Tổng hợp số liệu trên toàn bộ bản ghi khớp bộ lọc. Mã SV trên giao diện chỉ còn ba chữ số cuối; dữ liệu gốc không thay đổi.
- Bản này **không thêm cột hay bảng PostgreSQL**.

---

# BỔ SUNG v4.3.4 — Sửa nguồn video lẫn từ kênh YouTube khác

- Khi đồng bộ YouTube, xác định kênh **thực sự đăng tải** theo trường `snippet.channelId` của YouTube Data API, không coi video xuất hiện trong playlist là video của chủ playlist.
- Kho video học liệu, bộ chọn tạo QR và các chỉ số số video chỉ tính video đã xác minh thuộc các kênh giảng viên thực sự kết nối. Video của kênh thứ hai đã kết nối hợp lệ vẫn được sử dụng.
- Video bị nhập nhầm trước đây sẽ không còn xuất hiện sau khi triển khai và đồng bộ lại. Các liên kết playlist-video không hợp lệ được tự loại khỏi playlist; bản ghi video, mã QR, lịch sử quét/xem **không bị xóa**.
- Mã QR video cũ liên quan đến video sai nguồn được đánh dấu cần rà soát nếu gắn với môn học; không tự ngừng hoạt động hoặc thay đích.
- Thêm cột PostgreSQL `videos.uploader_channel_id` (tự cập nhật schema khi Web App khởi động). **Không xóa database**. Các video cũ chỉ có thông tin kiểm chứng sau khi bấm **Đồng bộ lại**.
- Kiểm thử độc lập tại `tests/test_youtube_playlist_ownership.py` (chạy không cần OAuth/DB).

---

# Bổ sung v4.3.1 — hiệu chỉnh giao diện và bổ sung lớp đang dạy

- Trang **Lớp chủ nhiệm** bỏ các câu giải thích dài đã được yêu cầu loại bỏ; giữ các thao tác Excel, thêm SV, sửa tên, trạng thái và xóa nhập nhầm.
- Trang **Kênh YouTube** thay mô tả kết nối thêm kênh thành: **“Liên kết với tài khoản Google khác để tích hợp thêm video học liệu”**.
- Thanh menu có trạng thái chọn **độc lập** cho Lớp chủ nhiệm, Danh sách lớp đang dạy và Quản lý lớp; Kho video học liệu vẫn dùng trạng thái riêng.
- Trang **Danh sách lớp đang dạy** có thêm biểu mẫu chọn môn học/mô đun đang phụ trách, chọn lớp đã lưu hoặc nhập lớp mới. Khi lớp chưa có danh sách sinh viên, GV bộ môn được tải tệp Excel hoặc thêm SV ban đầu trực tiếp trong trang này. Khi lớp đã có SV, chỉ GVCN được tiếp tục cập nhật.
- Không đổi cấu trúc cơ sở dữ liệu PostgreSQL; nâng cấp trực tiếp từ v4.3.0, không yêu cầu xóa dữ liệu hoặc tạo lại mã GV/lớp.

---

# TẠO MÃ QR TỰ ĐỘNG TỪ VIDEO YOUTUBE — v4.1

## Điểm mới v4.1
- Với tài khoản giảng viên kiêm GVCN, menu **Lớp chủ nhiệm** được đưa lên vị trí thứ 2, ngay sau **Kênh YouTube**.
- Trong **Lớp chủ nhiệm**, bỏ dòng hướng dẫn và tiêu đề cột “Xóa nhập nhầm”; chức năng xóa sinh viên nhập sai vẫn được giữ dưới cột **Thao tác**.
- Trong **Đánh giá nghiệm thu**, các mục tiêu 100% hiển thị trực tiếp **100%**, không có dấu “=” phía trước.
- Đổi chỉ tiêu **Số đơn vị/khoa/bộ môn** thành **Số bộ môn** và đếm theo tên bộ môn duy nhất của các môn học/mô đun thực nghiệm.
- Chỉ tiêu **Số giảng viên tham gia** hiển thị mục tiêu **>= 3 (GV CN khác CNTT: >= 1)**; số thực tế theo dạng `5 (2)`, trong đó số trong ngoặc là giảng viên thuộc nhóm chuyên môn khác CNTT.
- Giao diện **Giảng viên** bổ sung trường **Nhóm chuyên môn** (Công nghệ thông tin / Khác CNTT) để quản trị viên xác định chính xác số liệu trong ngoặc của chỉ tiêu nghiệm thu.


## Bổ sung v3.9.2
- GVCN có thể xóa một sinh viên bị nhập nhầm/nhập thừa khỏi chính lớp mình chủ nhiệm.
- Khi xóa, hệ thống đồng thời xóa lượt quét, phiên xem và sự kiện xem phát sinh của sinh viên đó trong lớp, nên các thống kê được tính lại theo dữ liệu còn lại.
- Nếu sinh viên không còn thuộc lớp nào khác, hồ sơ sinh viên và dữ liệu nhận diện cũ còn sót lại cũng được xóa.
- Nút Xóa được tách rõ khỏi chức năng Thay đổi trạng thái; bảo lưu/nghỉ học/chuyển lớp phải dùng thay đổi trạng thái để bảo toàn lịch sử.

# TẠO MÃ QR TỰ ĐỘNG TỪ VIDEO YOUTUBE — v3.7

Ứng dụng web phục vụ đề tài tại **Trường Cao đẳng Sơn La**.

## Điểm mới v3.7
- **Lớp và sinh viên được quản lý dùng chung toàn hệ thống**, không tạo lại danh sách theo từng học phần.
- Quản trị viên tạo lớp và giao **giảng viên chủ nhiệm (GVCN)**; GVCN quản lý danh sách sinh viên của lớp mình.
- Mã sinh viên dùng **đúng mã do Nhà trường cấp**, không sinh thêm mã nội bộ cho sinh viên.
- GVCN có thể tải danh sách ban đầu hoặc bổ sung nhiều sinh viên bằng Excel; có thể thêm một sinh viên riêng lẻ.
- Khi sinh viên bảo lưu, nghỉ học, chuyển trường/chuyển lớp..., GVCN chỉ thay đổi trạng thái và **ngày có hiệu lực**; dữ liệu lịch sử trước đó không bị sửa.
- Lịch sử lớp lưu theo khoảng thời gian, nhờ đó lượt quét cũ vẫn giữ đúng lớp tại thời điểm phát sinh, còn sĩ số hiện tại thay đổi theo biến động mới.
- Giảng viên bộ môn chỉ chọn lớp dùng chung cho học phần; không tải lại danh sách sinh viên.
- Sinh viên quét QR **nhập tên lớp và chọn họ tên kèm mã SV** từ danh sách SV đang học của lớp đó. Hệ thống kiểm tra quan hệ lớp–môn học/mô đun của QR trước khi ghi lượt quét; mỗi lượt mở QR của SV cần xác nhận lại danh tính để tránh nhầm trên thiết bị dùng chung.
- Giao diện **Quản lý học phần** được thu gọn: chỉ giữ số video/QR, playlist/QR, số lớp và khu vực chọn lớp áp dụng.
- Giao diện **Mã QR động** đưa hai chức năng tạo QR một video/một playlist xuống khu vực **Tạo QR riêng lẻ**; quy trình chính ưu tiên tạo theo học phần.
- Thông báo đăng nhập và lỗi quyền truy cập được chuẩn hóa bằng tiếng Việt; tài khoản giảng viên truy cập nhầm trang quản trị được đưa về giao diện phù hợp thay vì hiện trang lỗi 403 thô.
- Sao lưu/khôi phục bổ sung dữ liệu lớp dùng chung, sinh viên, lịch sử biến động và liên kết lớp-học phần.

## Nhóm tác giả
Nguyễn Thị Thúy Tươi (Chủ nhiệm đề tài); Hoàng Thị Nhất; Nguyễn Thu Huyền; Tường Thị Phương Thảo; Nguyễn Hữu Thọ.

## Điểm mới v3.6
- **Kho video học liệu:** bỏ mã kỹ thuật YouTube (dạng `PL...`) hiển thị dưới tên playlist; giảng viên chỉ thấy tên playlist cần dùng.
- **Mã QR động:** mỗi học phần hiển thị rõ số video, số QR video đã có/chưa có; dòng playlist hiển thị số lượng kèm tên playlist và số QR playlist đã có/chưa có.
- Nút **Mở thử** chuyển sang chế độ xem thử dành cho giảng viên: không yêu cầu nhập mã GV/SV và không ghi lượt quét/thời lượng xem vào thống kê.
- Bổ sung **Mã GV thực nghiệm** cho tài khoản giảng viên. Quản trị viên cấp mã tại trang **Đánh giá nghiệm thu**; sau khi cấp, mã hiển thị trên giao diện khi giảng viên đăng nhập.
- Khi giảng viên đã đăng nhập và thực sự quét QR, hệ thống tự dùng Mã GV đã cấp, không yêu cầu nhập lại.
- Sinh viên **không cần đăng nhập Web App**. Khi quét QR do giảng viên cung cấp, sinh viên chỉ nhập **Mã sinh viên do Nhà trường cấp**; hệ thống tự xác định lớp theo dữ liệu GVCN và thời điểm quét.
- Trang nhận diện công khai không yêu cầu chọn vai trò hoặc chọn lớp; luồng công khai mặc định là sinh viên.
- PostgreSQL được nâng cấp nhẹ bằng cột `users.lecturer_code`; dữ liệu hiện có được giữ nguyên.

## Các chức năng chính
- Giao diện tiếng Việt, có logo Trường Cao đẳng Sơn La.
- Bỏ tên hiển thị “SLC QR Learning Hub”.
- “YouTube & Hub/WebSub” được đổi thành giao diện dễ hiểu: **Kết nối và đồng bộ kênh YouTube**.
- Có **Kho video học liệu**; giảng viên có thể lọc video theo playlist, xem playlist của từng video, chọn nhiều video hoặc nhiều playlist và gán trực tiếp vào học phần.
- Quan hệ Video ↔ Học phần là nhiều–nhiều thông qua bảng `course_videos`.
- Tạo mã QR động hàng loạt theo học phần: chỉ tạo cho video chưa có mã, chống tạo trùng.
- Tên mã QR tự lấy theo tên video YouTube.
- QR chốt theo mẫu chính thức: **mã đen trên nền trắng, mức sửa lỗi H, logo Trường Cao đẳng Sơn La ở giữa và có viền trắng tròn bảo vệ logo**.
- Tải PNG từng mã; tải ZIP theo học phần; tải ZIP toàn bộ.
- Focus Viewer, trang nhận diện GV/SV và trang lỗi học liệu đều có logo trường.
- Giữ nguyên theo dõi lượt quét, phiên xem, thống kê, nghiệm thu, sao lưu/khôi phục.

## Luồng sử dụng chính
1. Đăng nhập bằng Google.
2. Vào **Học phần** để tạo/kiểm tra học phần cần sử dụng.
3. Vào **Kênh YouTube** → **Đồng bộ dữ liệu từ YouTube** khi cần cập nhật học liệu.
4. Vào **Kho video học liệu** → lọc theo playlist nếu cần → chọn video hoặc playlist → chọn học phần → gán vào học phần.
5. Vào **Học phần** hoặc **Mã QR động** → tạo QR cho video/playlist chưa có mã.
6. Tải PNG/ZIP. QR đã tạo là QR động nên có thể cập nhật đích mà không phải phát hành lại mã.




## Điểm mới v3.5.1
- Hiệu chỉnh nội dung **Hướng dẫn gán học liệu vào học phần** trong Kho video học liệu theo nội dung đã chốt:
  - Nếu kênh YouTube đã tổ chức video theo playlist, ưu tiên gán playlist cho học phần; các video trong playlist tự động được gán vào học phần tương ứng.
  - Nếu không muốn gán toàn bộ video trong playlist cho học phần, chọn từng video cần sử dụng và gán video đó vào học phần tương ứng.
- Không thay đổi logic, cơ sở dữ liệu hoặc schema PostgreSQL của v3.5.

## Điểm mới v3.5
- Trong **Kho video học liệu**, phần **Danh sách playlist** được đưa lên trước **Danh sách video** để giảng viên ưu tiên phân loại học liệu theo playlist.
- Bổ sung khung hướng dẫn ngắn: nếu kênh YouTube đã tổ chức video theo playlist thì gán playlist cho học phần; nếu không muốn dùng cả playlist hoặc video chưa thuộc playlist phù hợp thì chọn video riêng và gán cho học phần.
- Cột **Học phần áp dụng** của từng playlist chuyển từ danh sách checkbox hiển thị thường trực sang **danh sách thả xuống chọn nhiều học phần**. Giao diện không còn kéo dài khi có nhiều học phần.
- Bộ chọn hiển thị số học phần đã chọn; giảng viên có thể mở lại danh sách, bỏ học phần cũ, chọn học phần mới và bấm **Lưu** để hiệu chỉnh.
- Không thay đổi cơ chế dữ liệu v3.4: video trong playlist tự kế thừa các học phần của playlist; video gán riêng vẫn được giữ theo quy tắc an toàn.
- Không thay đổi schema PostgreSQL.

## Điểm mới v3.4
- **Học phần** được đưa lên vị trí thứ 2 trên menu, ngay sau **Kênh YouTube**.
- **Kho video học liệu** bổ sung bộ lọc **Playlist** cho danh sách video.
- Mỗi video hiển thị các playlist đang chứa video đó.
- Bổ sung khu vực **Danh sách playlist** ngay trong Kho video học liệu.
- Có thể tìm kiếm playlist, lọc playlist đã/chưa gán học phần, chọn nhiều playlist và gán trực tiếp vào học phần.
- Không thay đổi schema PostgreSQL.

## Nâng cấp từ v1.0 trên Render
Bản v2.1 kế thừa cấu trúc dữ liệu của v2.0; các bảng dữ liệu cũ được giữ nguyên. Khi Web Service khởi động, `db.create_all()` sẽ tự tạo bảng mới nếu `AUTO_CREATE_DB=1`.

Các biến môi trường cũ tiếp tục dùng:
- `DATABASE_URL`
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `ADMIN_EMAILS`
- `SECRET_KEY`
- `RECONCILE_KEY`
- `COMPLETION_THRESHOLD`
- `HEARTBEAT_SECONDS`
- `COOKIE_SECURE`
- `AUTO_CREATE_DB`

Không đưa `.env` hoặc Client Secret lên GitHub.

## Logo thương hiệu
Logo chính thức nằm tại:

`static/branding/logo_truong.png`

Logo được dùng cho header, trang đăng nhập, Focus Viewer, trang nhận diện người học và mã QR.

## Cấu trúc chính
- `app.py`: route, gán video vào học phần, tạo QR hàng loạt, QR có logo.
- `models.py`: mô hình dữ liệu; v2.0 có thêm `CourseVideo` / `course_videos`.
- `templates/`: giao diện tiếng Việt.
- `static/app.css`: nhận diện giao diện.
- `static/branding/logo_truong.png`: logo trường.
- `static/viewer.js`: theo dõi trạng thái xem bằng YouTube IFrame Player API.
- `render.yaml`: triển khai Render + PostgreSQL.

## Kiểm tra sau khi deploy
- `/health` phải trả trạng thái database `ok`.
- Đăng nhập Google thành công.
- Đồng bộ được video.
- Tạo được học phần.
- Chọn nhiều video và gán vào học phần.
- Tạo QR hàng loạt, bấm lần hai không sinh QR trùng.
- PNG tải về có logo trường và quét được.
- Mở QR → nhận diện GV/SV → Focus Viewer.
- Đổi video đích nhưng slug/QR không đổi.
- Lịch sử quét và quá trình xem xuất CSV được.

## Lưu ý dữ liệu nghiên cứu
Thời lượng xem là giá trị ước tính từ trạng thái trình phát. Không dùng log xem để khẳng định mức độ chú ý, mức độ hiểu bài hoặc kết quả học tập.


## Mẫu QR chính thức v2.1
- Mã QR màu đen, nền trắng.
- Error correction H.
- Logo trường đặt chính giữa, kích thước khoảng 23% chiều rộng ảnh QR.
- Có vòng trắng mỏng quanh logo.
- PNG/ZIP và QR tạo hàng loạt đều gọi chung một hàm sinh QR để bảo đảm đồng nhất.

## Hiệu chỉnh v2.2
- Tên mã QR và tên tệp PNG luôn đúng bằng **tên video YouTube**, giữ nguyên tiếng Việt có dấu; không thêm mã học phần/slug.
- Tạo mã hàng loạt từ trang **Quản lý mã QR động** giữ nguyên tại trang này, không chuyển sang trang Học phần.
- Trang xem video thay thông tin kỹ thuật bằng nhắc nhở người học xem đầy đủ, không tua nhanh/bỏ qua hướng dẫn.
- Footer: **Sản phẩm nghiên cứu khoa học cấp trường phục vụ giảng dạy**.
- Trang chờ đăng nhập bỏ dòng tên trường bị lặp và giữ tiêu đề **TẠO MÃ QR TỰ ĐỘNG TỪ VIDEO YOUTUBE** trên một dòng.

## Hiệu chỉnh v2.3
- **Mã học phần được hệ thống tự động sinh**, giảng viên không còn phải nhập mã. Khi tạo mới, chỉ nhập **Tên học phần** và **Tên khoa/bộ môn**.
- Tên học phần không dùng danh sách gợi ý từ dữ liệu đã nhập trước; trường nhập được đặt `autocomplete=off` và đổi tên trường dữ liệu để hạn chế lịch sử gợi ý cũ của trình duyệt.
- **Tên khoa/bộ môn vẫn được gợi ý từ các dữ liệu đã dùng trước đây** để giảng viên có thể chọn lại nhanh mà không phải gõ lại.
- **Mã lớp được hệ thống tự động sinh**; khi thêm lớp, giảng viên chỉ nhập **Tên lớp**.
- Các mã tự động được tạo từ ID nội bộ của cơ sở dữ liệu theo dạng `HPxxxxxx` và `Lxxxxxx`, bảo đảm ổn định và tránh trùng khi nhiều giảng viên cùng sử dụng.
- Giao diện thường ngày ưu tiên hiển thị **tên học phần** và **tên lớp**, giảm thuật ngữ kỹ thuật không cần thiết đối với giảng viên không chuyên CNTT.
- Không thay đổi cấu trúc bảng dữ liệu, nên có thể cập nhật trực tiếp từ v2.2 lên Render mà không xóa PostgreSQL hiện tại.

## Hiệu chỉnh v2.4 — Chính sách quyền riêng tư
- Bổ sung trang công khai `/privacy` dạng HTML cho ứng dụng.
- Công bố rõ dữ liệu Google/YouTube được truy cập, dữ liệu hệ thống lưu, mục đích sử dụng, nguyên tắc chia sẻ, bảo vệ, lưu giữ và quyền của người dùng.
- Công bố phạm vi `youtube.readonly`: chỉ đọc dữ liệu kênh/video, không đăng/sửa/xóa video.
- Nêu rõ token OAuth được mã hóa trước khi lưu và lịch sử quét không lưu IP thô.
- Bổ sung cam kết tuân thủ Google API Services User Data Policy và Limited Use.
- Thêm liên kết **Chính sách quyền riêng tư** tại trang đăng nhập và footer toàn hệ thống để người dùng truy cập dễ dàng.
- URL dùng để điền trong Google Auth Platform sau khi deploy: `https://<ten-mien-cua-web-app>/privacy`.

## Hiệu chỉnh v2.5 — phân quyền giảng viên, khoa/bộ môn và menu đang chọn
- Tài khoản không nằm trong `ADMIN_EMAILS` luôn được xác định là **Giảng viên** khi đăng nhập. Tài khoản giảng viên chỉ đồng bộ kênh/video của chính họ; chỉ quản lý học phần, QR và thống kê thuộc dữ liệu họ phụ trách.
- Các chức năng quản trị/nghiệm thu (**Đánh giá nghiệm thu, Nhật ký lỗi, Sao lưu dữ liệu, Khôi phục dữ liệu**) chỉ hiển thị và cho phép truy cập với tài khoản **Quản trị viên**.
- Trang **Học phần** tách rõ **Tên khoa** và **Bộ môn quản lý học phần** để hỗ trợ thực nghiệm với giảng viên thuộc nhiều chuyên ngành/bộ môn, kể cả nhiều bộ môn trong cùng một khoa.
- `courses` có thêm `faculty_name` và `department_name`. Khi deploy lên PostgreSQL hiện có, ứng dụng tự bổ sung cột và giữ nguyên dữ liệu cũ; giá trị `unit_name` cũ được bảo toàn và dùng để khởi tạo tên khoa nếu có.
- Học phần cũ thiếu bộ môn có cảnh báo và biểu mẫu cập nhật ngay tại thẻ học phần.
- Chỉ tiêu **Số đơn vị/khoa/bộ môn** trong trang nghiệm thu tính theo tổ hợp **Khoa + Bộ môn**, vì vậy nhiều bộ môn trong cùng một khoa được ghi nhận riêng.
- Thanh menu làm nổi bật chức năng đang mở bằng **chữ đậm, màu đỏ**; các chức năng khác giữ định dạng bình thường.

## Hiệu chỉnh v2.6 — nhãn đậm, xóa dữ liệu an toàn và xử lý video YouTube bị xóa
- Toàn bộ nhãn trường nhập/chọn (`form-label`) được hiển thị **chữ đậm** để giảng viên dễ nhận biết.
- Form tạo học phần đổi thứ tự thành **Tên học phần → Bộ môn quản lý học phần → Tên khoa**; bỏ các dòng giải thích dài về gợi ý tên khoa/bộ môn.
- Khi giảng viên bấm đồng bộ YouTube, hệ thống đồng thời **đối soát lại trạng thái toàn bộ video đã biết** để phát hiện video bị xóa, chuyển riêng tư hoặc tắt khả năng nhúng.
- Nếu video đích của QR không còn sử dụng được, **QR không bị đổi**. Giao diện đánh dấu “QR cần đổi video”; giảng viên chọn video thay thế và QR cũ tiếp tục hoạt động mà không phải in lại.
- Bổ sung nút **Xóa mã QR**. Việc xóa thực hiện theo kiểu ngừng sử dụng (soft delete), QR cũ không còn mở được nhưng lịch sử quét/xem vẫn được giữ để phục vụ nghiên cứu.
- Bổ sung **Xóa học phần khỏi danh sách**. Học phần được ẩn khỏi nghiệp vụ thường ngày nhưng dữ liệu lịch sử và QR đã phát hành được bảo toàn.
- Bổ sung xóa lớp theo kiểu ẩn khỏi danh sách; dữ liệu lịch sử vẫn giữ nguyên. Bảng `class_groups` được tự động bổ sung cột `active` khi deploy lên PostgreSQL hiện có.


## Hiệu chỉnh v2.8 — hướng dẫn đăng nhập thử nghiệm và tinh gọn footer
- Bổ sung khung **Lưu ý khi đăng nhập thử nghiệm** ngay dưới nút **Đăng nhập bằng Google**, hướng dẫn xử lý màn hình “Google chưa xác minh ứng dụng này” trong giai đoạn thử nghiệm.
- Khung hướng dẫn nêu rõ ứng dụng chỉ dùng quyền đọc dữ liệu kênh/video YouTube, không đăng, sửa hoặc xóa video.
- Footer bỏ hai dòng lặp lại **TẠO MÃ QR TỰ ĐỘNG TỪ VIDEO YOUTUBE** và **Trường Cao đẳng Sơn La**.
- Nhóm tác giả hiển thị đậm; bổ sung **Nguyễn Thị Thúy Tươi (Chủ nhiệm đề tài)**.
- Dòng **Sản phẩm nghiên cứu khoa học cấp trường phục vụ giảng dạy** được hiển thị chữ nghiêng.


## Bổ sung v2.8
- Nút **Tạo một mã QR riêng** được đưa lên đầu trang Quản lý mã QR động và mở/đóng form tạo QR riêng.
- Thêm nút **Xóa toàn bộ mã QR đã tạo** cho tài khoản hiện tại; QR ngừng hoạt động nhưng lịch sử quét/xem vẫn được giữ.
- Thêm nút quản trị **Xóa toàn bộ dữ liệu đã lưu** ở trang Tổng quan để làm sạch dữ liệu thử nghiệm; thao tác xóa toàn bộ dữ liệu trong DB và yêu cầu đăng nhập lại, nhưng không xóa cấu hình Render/Google OAuth.
- Trang chờ đăng nhập bỏ khối Nhóm tác giả ở giữa; thông tin tác giả chỉ còn ở cuối giao diện.
- Khung lưu ý đăng nhập thử nghiệm chuyển sang nền xanh nhạt.

## Hiệu chỉnh v2.8.2

- Đưa **Tỷ lệ phiên xem hoàn thành** lên cùng hàng với các thẻ thống kê Video học liệu, Học phần, Mã QR, Lượt quét và Phiên xem video.
- Bảng **Lượt quét gần đây** hiển thị toàn chiều rộng giao diện Tổng quan.
- Bỏ dòng hướng dẫn “Giảng viên chỉ cần nhập...” ở giao diện Quản lý học phần.
- Bỏ khối thông tin “Xử lý khi video YouTube bị xóa...” ở giao diện Quản lý mã QR động; chức năng kỹ thuật xử lý QR động vẫn giữ nguyên.

## Hiệu chỉnh v2.9 — Gộp sao lưu và khôi phục dữ liệu

- Gộp hai chức năng quản trị thành một menu **Sao lưu & khôi phục**.
- Giao diện mới hiển thị song song khối **Sao lưu dữ liệu** và **Khôi phục dữ liệu**.
- Khối sao lưu cho phép tạo/tải tệp ZIP và hiển thị nhanh số video, học phần, QR đang dùng và lượt quét đã lưu.
- Khôi phục dùng cụm từ xác nhận tiếng Việt **KHÔI PHỤC** thay cho `RESTORE`.
- Nút khôi phục chỉ được bật khi đã chọn tệp ZIP và nhập đúng cụm từ xác nhận.
- Có hộp xác nhận cuối cùng trước khi thay thế dữ liệu hiện tại.
- Liên kết `/admin/restore` cũ được giữ để chuyển hướng sang giao diện mới.
- Chức năng chỉ hiển thị và hoạt động với tài khoản Quản trị viên.

## v3.0 - Đánh giá nghiệm thu theo dữ liệu thật

- Bỏ nhập thủ công từng ca kiểm thử. Hệ thống tự ghi bằng chứng từ các hoạt động thật: đăng nhập Google, đồng bộ YouTube, gán video vào học phần, tạo QR, quét QR, đổi video đích, sao lưu và khôi phục.
- Phép đo phía Web App được ghi tự động; quản trị viên chỉ nhập số liệu quy trình thủ công để làm đối chứng cùng mã nhiệm vụ.
- So sánh hiệu quả chỉ tính trên các nhiệm vụ có dữ liệu ở cả hai phía (thủ công và Web App).
- Bỏ nhập từng phiếu khảo sát trong Web App. Khảo sát dùng Google Forms và Google Sheets; trang Đánh giá nghiệm thu chỉ lưu/liên kết các URL khảo sát và bảng kết quả.
- Bổ sung bảng `research_settings`; backup cũ không có bảng này vẫn được hỗ trợ khôi phục.


## Cập nhật v3.1 — nhiệm vụ đối chứng chuẩn hóa
- Trường nhiệm vụ đối chứng chuyển sang danh sách chọn thay vì tự gõ mã để tránh sai mã.
- Từ v3.4, thiết kế nghiên cứu được chốt chỉ dùng **2 nhiệm vụ đối chứng**: tạo QR riêng và tạo QR hàng loạt; các hoạt động đồng bộ/gán học liệu thuộc nhóm kiểm thử tự động.

## Cập nhật v3.4 — Playlist theo học phần và QR playlist động
- Đồng bộ cả **playlist do giảng viên tạo** và danh sách video thuộc từng playlist từ YouTube; sau mỗi lần đồng bộ, video mới/gỡ khỏi playlist được cập nhật trong Web App.
- Bổ sung quan hệ **Học phần ↔ Playlist ↔ Video** bằng bảng `course_playlists`; cùng một playlist có thể được gán cho nhiều học phần và mỗi học phần có QR playlist riêng để thống kê đúng ngữ cảnh.
- Trong **Quản lý học phần**, giảng viên có thể gán/bỏ gán playlist, xem số video trong playlist và trạng thái QR playlist.
- Trong **Mã QR động**, bổ sung **Tạo một mã QR playlist** và **Tạo QR cho tất cả playlist của học phần**. Tên QR/tệp PNG giữ đúng tên playlist tiếng Việt có dấu.
- QR playlist dẫn tới trang xem riêng của Web App, không dẫn thẳng sang YouTube. Trang xem hiển thị danh sách video và phát bằng `youtube-nocookie`; video không còn khả dụng được tự bỏ qua.
- Khi playlist thêm/gỡ video, sau đồng bộ YouTube **QR playlist cũ tự phản ánh nội dung mới, không phải in lại QR**. Nếu playlist bị xóa/không còn khả dụng, QR được giữ và hiển thị thông báo phù hợp.
- Lịch sử quét QR playlist và quá trình xem từng video trong playlist tiếp tục được ghi nhận vào thống kê của học phần.
- Phần **Đánh giá nghiệm thu** chỉ còn **2 nhiệm vụ đối chứng chuẩn**: `TAO_QR_RIENG` và `TAO_QR_HANG_LOAT`. Đồng bộ YouTube, gán video/playlist và các chức năng khác vẫn được ghi ở **Kết quả kiểm thử tự động**, không dùng làm nhiệm vụ đối chứng thủ công.
- Backup/khôi phục bổ sung bảng `course_playlists` và các trường QR playlist; backup cũ chưa có bảng này vẫn được phép khôi phục.


## Bổ sung v3.4 - Gán playlist một lần, video tự theo học phần
- Mỗi playlist có danh sách **Học phần áp dụng** ngay trong Kho video học liệu.
- Có thể chọn đồng thời nhiều học phần cho một playlist rồi bấm **Lưu học phần cho playlist** một lần.
- Toàn bộ video hiện có trong playlist tự động được gán vào các học phần đã chọn; không cần gán lại từng video.
- Khi đồng bộ YouTube, video mới thêm vào playlist tự động được bổ sung vào các học phần đang dùng playlist.
- Khi bỏ một học phần khỏi playlist, các video chỉ được kế thừa từ playlist đó tự động được bỏ khỏi học phần; video đã gán riêng hoặc còn thuộc playlist khác vẫn được giữ.
- Vùng gán video riêng trong Kho video chỉ dùng cho video lẻ hoặc trường hợp đặc biệt.


## Cập nhật v3.9

- Bổ sung giao diện **Giảng viên** dành cho Quản trị viên: cấp mã định danh GV, xem họ tên, kênh YouTube, email, chức vụ và xóa giảng viên khỏi Web App.
- Chuyển chức năng cấp mã GV khỏi **Đánh giá nghiệm thu** sang giao diện **Giảng viên**.
- Xóa giảng viên sẽ xóa tài khoản/OAuth và toàn bộ dữ liệu nghiệp vụ, học phần, QR, lượt quét/xem, kiểm thử/thực nghiệm thuộc GV; lớp và sinh viên dùng chung được giữ lại và bỏ gán GVCN.
- Bỏ khối xóa dữ liệu riêng từng GV ở Tổng quan để tránh trùng chức năng.

## Cập nhật v3.8
- Giảng viên tự hiệu chỉnh họ tên hiển thị; tên đã sửa không bị ghi đè bởi tên Google ở lần đăng nhập sau.
- Mã lớp dùng chung được sinh tự động; quản trị viên chỉ nhập tên lớp và chọn GVCN theo họ tên + email.
- Tổng quan bổ sung số lượng giảng viên và số lượng lớp; bảng quét chỉ hiển thị sinh viên.
- Thống kê khai thác và tệp CSV tập trung vào dữ liệu sinh viên, bỏ cột vai trò và dữ liệu quét GV khỏi báo cáo giao diện.
- Quản trị viên có thể xóa dữ liệu nghiệp vụ/thử nghiệm của từng giảng viên.
- Xóa toàn bộ dữ liệu làm mới cả mã GV nhưng giữ phiên quản trị đang thao tác, không yêu cầu đăng nhập lại.

## Cập nhật v3.9.1
- Giao diện **Lớp & sinh viên** của Quản trị viên được tách khỏi giao diện **Lớp chủ nhiệm**.
- Quản trị viên chỉ tạo lớp, giao/hiệu chỉnh GVCN và xem danh sách lớp đã tạo.
- Không hiển thị danh sách sinh viên, tải Excel, thêm sinh viên hoặc thay đổi trạng thái sinh viên trên giao diện Quản trị viên.
- Cột **Sĩ số đang học** chỉ tính sinh viên có quan hệ lớp còn hiệu lực tại ngày hiện tại, tương ứng trạng thái **Đang học**.
- GVCN tiếp tục quản lý đầy đủ danh sách sinh viên và biến động lớp tại giao diện **Lớp chủ nhiệm**.


## Phiên bản 4.0
- Giao diện Quản trị viên đưa **Giảng viên** lên vị trí thứ 2 ngay sau **Kênh YouTube**.
- Đổi thuật ngữ giao diện **Học phần** thành **Môn học/ mô đun**; trang quản lý dùng các nhãn “Tên môn học/ mô đun”, “Bộ môn quản lý môn học/ mô đun”.
- Trang Đánh giá nghiệm thu bỏ cột **Mã ca**, bổ sung chỉ tiêu đăng nhập hệ thống 100%, đồng bộ video 100%, tối thiểu 3 giảng viên và 50 sinh viên tham gia.
- Nhật ký lỗi có cột **Thao tác** và **Môn học/ Mô đun**, không hiển thị tên mô-đun kỹ thuật nội bộ.
- Ô sửa họ tên GV không điền/gợi lại nội dung cũ; nút **Lưu họ tên** đặt ngay bên phải ô nhập.
- Xóa toàn bộ dữ liệu đặt lại bộ đếm mã nghiệp vụ: mã GV cấp lại từ GV0001, mã lớp từ L000001, mã môn học/ mô đun từ HP000001; vẫn giữ phiên quản trị hiện tại.


## Phiên bản 4.1.1
- Giao diện Lớp chủ nhiệm: tách hai thao tác thành hai cột **Lưu** và **Xóa**, căn giữa từng nút để bảng rõ ràng hơn.


## Cập nhật v4.2.0
- Khai báo họ tên đầy đủ, nhóm chuyên môn, GVCN, tên lớp và sĩ số dự kiến lần đầu; tạo mã GV/lớp tự động.
- Quản trị viên cũng là giảng viên; nếu là GVCN thì có trang Lớp chủ nhiệm và có mã GV.
- Sau đăng nhập, màn hình chờ tự đồng bộ YouTube; có nút vào hệ thống/thử lại.
- Thêm môn học/mô đun có thể chọn ngay lớp; danh sách môn học trình bày dạng bảng với bộ chọn nhiều lớp; số lượng không đệm 0.
- Sĩ số khai báo không thay thế số SV đang học (lấy từ danh sách SV GVCN tải Excel).
- Nâng schema thêm users.profile_completed và school_classes.declared_size; không xóa dữ liệu cũ.


## Bổ sung v4.3.0
- Quản trị viên là giảng viên và có thể chủ nhiệm; Tổng quan chuyển phạm vi dữ liệu của tôi/toàn hệ thống.
- Giữ tự đồng bộ khi đăng nhập, nút Đồng bộ lại chủ động; không tạo cron 6 giờ tính phí.
- Kết nối thêm một/một số tài khoản Google YouTube bằng OAuth riêng vào cùng hồ sơ GV, không đăng xuất.
- GV có thể chọn lớp có sẵn hoặc tạo lớp chưa có khi thêm môn học/mô đun; dữ liệu lớp dùng chung.
- GV bộ môn được nạp danh sách SV đầu tiên khi lớp chưa có SV; sau đó chỉ GVCN quản lý.
- Chuyển giao GVCN với ngày hiệu lực, không đổi mã lớp; lưu lịch sử bàn giao.
- Chỉnh sửa tên môn, bộ môn, khoa, tên lớp, họ tên SV (không đổi khóa định danh); quản trị viên chuẩn hóa danh mục khoa/bộ môn; lưu lịch sử chỉnh sửa.
- QR playlist tự cập nhật nội dung khi GV đồng bộ; QR video cảnh báo nếu bị mất liên hệ môn sau chuyển playlist; video riêng tư/xóa không phát; QR bị xóa mềm trả thông báo dừng sử dụng, không xóa lịch sử thống kê.
- Sao lưu hỗ trợ bảng kết nối bổ sung, lịch sử bàn giao GVCN, lịch sử hiệu chỉnh.
- Khi dùng tính năng kết nối YouTube khác, cấu hình Google OAuth redirect URI `/youtube/connect-callback` bên cạnh `/auth/callback`.


## Cập nhật v4.3.2 — Theo dõi nghiệm thu và sinh viên

- Bảng cuối mục 1 Đánh giá nghiệm thu: nhóm theo **Chức năng** (200 bản ghi mới nhất), cột **Người thực hiện** hiển thị tên GV (email) hoặc tên SV (mã SV - lớp).
- Lượt quét QR của SV được gắn mã SV + mã lớp ngay tại thời điểm quét, **không coi chủ sở hữu QR là người quét**. Minh chứng lượt quét hiển thị **tên video/playlist – tên môn học/mô đun**.
- Dữ liệu kiểm thử cũ không bị sửa. Nếu có một lượt quét khớp duy nhất với log cũ, hệ thống hiển thị danh tính SV; nếu thiếu thông tin hoặc không chắc chắn thì hiển thị rõ chưa xác định, không đoán.
- Thống kê khai thác: bỏ biểu đồ, giữ hai bảng lịch sử quét và phiên xem; bổ sung bộ lọc môn học/mô đun, lớp, QR, mã SV và tình trạng cần theo dõi.
- Bộ lọc **Chưa quét QR** lấy danh sách SV đang học đối chiếu với các lượt quét QR **thành công**. **Chưa hoàn thành video** dành cho SV đã quét thành công nhưng chưa xem đủ các video hiện khả dụng của QR (với playlist: xét từng video).
- Danh sách cần theo dõi phải chọn một lớp và một QR; số liệu lớp hiện hành không được dùng để tính ngược lịch sử quét các đợt trước.
- CSDL bổ sung 2 trường nullable vào nhật ký kiểm thử; nâng cấp tự động, không xóa PostgreSQL. Bản sao lưu tự chứa 2 trường mới nhờ cơ chế serialize tự động.


## Điểm mới v4.3.3
- Bỏ hoàn toàn khu vực **Thêm lớp đang dạy** và đường dẫn xử lý thêm lớp tại trang **Danh sách lớp đang dạy**. Việc chọn lớp đã có hoặc tạo lớp mới và liên kết với môn học/mô đun chỉ thực hiện tại trang **Môn học/Mô đun**.
- Trang Danh sách lớp đang dạy chỉ có bảng: mã lớp, tên lớp, các môn đang dạy, sĩ số đang học, và tải Excel danh sách ban đầu khi lớp chưa có sinh viên.
- Trang công khai sau khi SV quét QR: **nhập tên lớp từ danh sách gợi ý → chọn họ tên kèm mã SV → xem học liệu**. Tải danh sách tên SV đang học theo lớp được chọn, không yêu cầu đăng nhập Google hay gõ mã SV.
- Máy chủ xác thực lớp được gán cho môn học/mô đun và sinh viên còn thuộc lớp tại thời điểm quét; dữ liệu ghi log vẫn dùng mã SV Nhà trường và mã lớp. Bổ sung nút **Đổi sinh viên** trong trang xem; lượt mở QR mới trên cùng trình duyệt yêu cầu chọn lại để tránh nhầm lẫn.
- Quy trình chọn tên chỉ là nhận diện tự khai báo phục vụ thống kê, **không phải xác thực danh tính chắc chắn**. Người có mã QR có thể nhìn thấy tên/mã của SV được liệt kê trong lớp. Cần thông báo người học và cân nhắc quyền riêng tư khi đưa vào sử dụng chính thức.
- Không thay đổi cấu trúc PostgreSQL, có thể cập nhật từ v4.3.2 mà không xóa dữ liệu.

## Cập nhật v4.3.6 – Tập trung thống kê khai thác và nghiệm thu

- **Đánh giá nghiệm thu:** giữ nguyên bảng **Theo dõi chỉ tiêu và kết quả nghiệm thu** (mục tiêu – thực tế – kết quả). Xóa khu vực nhật ký kiểm thử bị trùng; đánh số lại **1. Hiệu quả quy trình** và **2. Khảo sát người dùng**. Có liên kết sang Thống kê khai thác để xem minh chứng.
- **Thống kê khai thác – mục 1:** nhật ký hoạt động tự động của giảng viên/quản trị viên, không liệt kê lượt quét QR hay xem video của SV. Có tổng hợp đạt/không đạt và bộ lọc thời gian, chức năng, kết quả, người thực hiện.
- **Thống kê khai thác – mục 2:** một bảng 8 cột: thời gian; tên SV (3 số cuối mã); lớp; MH/MĐ; tên học liệu số; kết quả quét; thời lượng xem; trạng thái xem. Khi mở QR playlist, hiển thị tên **video thực sự đã phát** ở mỗi dòng; nếu quét nhưng chưa phát sẽ hiển thị trạng thái Chưa xem. Một lượt quét playlist vẫn chỉ có một bản ghi gốc trong `scan_logs`; các dòng xem video tham chiếu lượt quét đó, không tạo thêm scan log.
- Hai mục sử dụng bộ lọc/phân trang **độc lập**, 10 dòng/trang, phân trang bằng số; chuyển trang giữ vị trí cuộn tại bảng tương ứng.
- Có lọc SV chưa quét/chưa hoàn thành theo danh sách SV đang học ở lớp và QR được giao, không dựa đơn thuần vào những bản ghi đã tồn tại. Các khoảng ngày lọc cũng được áp dụng khi đối chiếu nhóm chưa tham gia.
- Giữ đầy đủ mã SV trong PostgreSQL; chỉ rút gọn phần **hiển thị** còn ba số cuối. Các lượt quét, phiên xem, QR, dữ liệu nghiên cứu trước đó không bị xóa hoặc ghi đè.
- Không thêm dịch vụ trả phí, không thiết lập cron định kỳ. Chỉ tạo thêm **chỉ mục** trong cơ sở dữ liệu nếu chưa có để tăng tốc truy vấn nhật ký.
- Nhật ký kết quả hệ thống vẫn là bằng chứng hoạt động tự động; bảng theo dõi chỉ tiêu nghiệm thu giữ các tiêu chí và ngưỡng ban đầu. Số liệu kiểm thử thực tế không được tự tạo.

**Lưu ý kiểm thử:** Có kiểm tra cú pháp và mô phỏng ghép nhật ký bằng SQLAlchemy/SQLite. Chưa chạy kiểm thử tích hợp Google OAuth, YouTube API và PostgreSQL trên Render trong môi trường tạo gói; cần kiểm thử sau khi deploy.
