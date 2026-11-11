# HƯỚNG DẪN KIỂM TRA V4.3.30 (11/11/2026)

Bản này kế thừa v4.3.29. Thử trên bản sao dữ liệu trước khi triển khai chính thức. **Sao lưu PostgreSQL trước khi thử chức năng xóa giảng viên.**

## 1. Kho video học liệu

1. Lọc playlist theo tên/trạng thái, chọn môn học trong khu thao tác hàng loạt.
2. Nút **Gán MH cho tất cả playlist** gán thêm môn cho toàn bộ kết quả lọc (mọi trang), giữ liên kết môn cũ; không xuất hiện hộp thoại xác nhận hoặc thông báo thành công.
3. Nút **Tạo QR cho tất cả playlist của môn** xử lý playlist đã gán trong môn, bỏ qua playlist không đủ điều kiện, không tạo mã trùng; không hiển thị hộp thoại hoặc thông báo thành công.
4. Nút **Tải QR đã tạo** chỉ bật nếu môn được chọn đã có QR hoạt động. Tải ZIP của tất cả QR (playlist **và** video) thuộc môn đó, không phải chỉ các QR hiện ở trang đang xem. Giữ các nút tác vụ riêng trên từng dòng playlist.

## 2. Quản lý mã QR động

- **Tổng mã QR đã tạo:** bao gồm QR đang sử dụng và QR đã ngừng sử dụng nhưng còn lưu trong cơ sở dữ liệu; QR được xóa vĩnh viễn cùng tài khoản GV sẽ không còn được tính.
- **QR đang sử dụng:** chỉ QR có `active=True`. Hai số QR playlist/video đang dùng cộng lại bằng QR đang sử dụng.
- Bộ lọc môn vẫn áp dụng đúng phạm vi QR.
- Khi tải trên Chrome/Edge máy tính với HTTPS, hộp thoại hệ thống cho chọn vị trí/tên tệp để lưu PNG hoặc ZIP. Không thể ép lưu vào một đường dẫn hệ điều hành không được người dùng cho phép.
- Với trình duyệt không hỗ trợ `showSaveFilePicker` (ví dụ nhiều phiên bản Firefox/mobile), tải xuống bằng cơ chế thông thường; trong cài đặt trình duyệt có thể bật **Hỏi vị trí lưu từng tệp trước khi tải**. Tệp tải không đi qua máy chủ để tự chọn đường dẫn cục bộ.

## 3. Môn học/mô đun, hồ sơ lần đầu

1. Tài khoản mới xác thực Google xong sẽ được yêu cầu khai báo **Khoa sinh hoạt chuyên môn** và **Bộ môn sinh hoạt chuyên môn**, ngoài họ tên, nhóm chuyên môn và thông tin chủ nhiệm (nếu có).
2. Mục Môn học/mô đun dùng nhãn **Khoa QL bộ môn**; bộ môn và khoa hiển thị danh sách gợi ý được lấy từ hồ sơ người dùng và các môn đã tạo; có thể nhập tên mới ngay trong trường.
3. Nếu bộ môn/khoa đã khai báo trong hồ sơ, trường thêm môn được điền sẵn; có thể sửa khi môn khác đơn vị quản lý.
4. Người dùng cũ đã hoàn tất hồ sơ không bị bắt nhập lại; có thể khai báo khoa/bộ môn tại form tạo/sửa môn học.

## 4. Kết quả đồng bộ YouTube

- 0 video phù hợp và 0 phần lỗi = **ĐẠT**. Minh chứng vẫn nêu: `Video đã xác minh: 0; phần lỗi: 0. Không có video phù hợp để đồng bộ.`
- Có 1 hay nhiều phần lỗi = **KHÔNG ĐẠT**, kể cả đã đọc được một số video.
- Những lần đồng bộ tự động trong dữ liệu cũ từng bị chấm Không đạt *chỉ vì* có `0 video; 0 lỗi` được phân loại lại thành Đạt khi nâng cấp (`AUTO_CREATE_DB=1`). Ghi chú gốc không thay đổi; nhật ký có lỗi thực sự không bị sửa.

## 5. Xóa giảng viên (nguy cơ mất dữ liệu vĩnh viễn)

**Chỉ quản trị viên được thực hiện.** Trước khi xóa phải nhập đúng email giảng viên và xác nhận lần cuối.

- Xóa môn giảng viên đang sở hữu, QR thuộc các môn đó hoặc thuộc tài khoản, lịch sử quét/xem và lượt hoạt động liên quan, lỗi đăng nhập/đồng bộ nhận diện được bằng ID/email, dữ liệu đồng bộ/kênh và minh chứng nghiệm thu của tài khoản.
- Lớp còn môn đang được giảng viên khác giảng dạy hoặc còn GVCN khác thì **giữ nguyên** lớp và sinh viên. Lớp không còn người sử dụng được xóa; hồ sơ sinh viên chỉ xóa khi không còn thuộc lớp nào khác và không còn có liên kết môn hợp lệ. Nếu GV xóa đang là GVCN của lớp được giữ, lớp sẽ chuyển sang chưa có GVCN.
- Không xóa được GV có kênh/video/QR còn được giảng viên khác sử dụng; hệ thống thông báo nguyên nhân và yêu cầu bàn giao/gỡ nguồn dùng chung trước. Tài khoản quản trị không thể xóa theo đường dẫn này.
- Việc xóa chạy trong một transaction: có lỗi cơ sở dữ liệu sẽ rollback, không xóa một phần. **Xóa là thao tác phá hủy, không thể khôi phục nếu thiếu bản sao lưu.**
- Các lần đăng nhập lỗi hoàn toàn trước khi Google xác định được danh tính (không có user ID hoặc email) không được tự đoán để xóa; nhật ký vô danh vẫn được giữ.

## 6. Kiểm tra triển khai Render

1. Sao lưu PostgreSQL + mã nguồn đang chạy.
2. Thay toàn bộ mã nguồn và templates/static bằng gói v4.3.30; giữ `DATABASE_URL`, `SECRET_KEY`, cấu hình Google OAuth. Giữ `AUTO_CREATE_DB=1` để bổ sung hai cột `users.faculty_name` và `users.department_name`, không xóa bảng hiện có.
3. Triển khai, kiểm tra `Live`, làm mới giao diện `Ctrl+F5`. Thử tác vụ hàng loạt và QR, tài khoản mới, đồng bộ kênh trống, tài khoản GV thử nghiệm và dữ liệu lớp dùng chung.
4. Cơ chế xóa đúng 3 lỗi cũ *một lần duy nhất* từ v4.3.28 vẫn giữ dấu mốc `app_one_time_maintenance`; **không tạo tác vụ xóa lỗi tự động mới**.

**Phạm vi kiểm thử:** các bài kiểm thử tách tiến trình chạy ngoại tuyến với SQLite/Jinja, kiểm tra cú pháp Python/JS và ZIP. Chưa thử tài khoản Google, lựa chọn vị trí tải trên từng trình duyệt thực, hoặc PostgreSQL Production của Render. Trước khi xóa GV thật nên chạy thử bằng dữ liệu sao lưu trên môi trường thử nghiệm.
