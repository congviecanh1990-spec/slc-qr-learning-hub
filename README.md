# TẠO MÃ QR TỰ ĐỘNG TỪ VIDEO YOUTUBE — v3.4

Ứng dụng web phục vụ đề tài tại **Trường Cao đẳng Sơn La**.

## Nhóm tác giả
Nguyễn Thị Thúy Tươi (Chủ nhiệm đề tài); Hoàng Thị Nhất; Nguyễn Thu Huyền; Tường Thị Phương Thảo; Nguyễn Hữu Thọ.

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
