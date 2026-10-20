# Hướng dẫn cập nhật Web App v4.3.10 trên Render

## 1. Sao lưu trước khi triển khai

Đăng nhập **Quản trị viên** → **Sao lưu & khôi phục** → tải bản sao lưu hệ thống và cất riêng. **Không tải bản sao lưu, file `.env`, token Google hoặc mật khẩu lên GitHub.**

## 2. Cập nhật mã nguồn

Giải nén `TAO_MA_QR_TU_DONG_YOUTUBE_v4.3.10_RENDER.zip`, đưa **nội dung thư mục đã giải nén** (không phải riêng tệp ZIP) vào đúng nhánh GitHub đang triển khai trên Render. Chờ Render triển khai thành công rồi truy cập Web App.

**Không tạo lại hoặc xóa PostgreSQL.** Bản v4.3.10 **không bổ sung cột/bảng mới so với v4.3.9** và giữ nguyên đường dẫn QR đã phát hành. Khi nâng từ phiên bản cũ hơn v4.3.9, vẫn phải áp dụng các nâng cấp CSDL của các phiên bản trung gian (cơ chế `AUTO_CREATE_DB=1` thực hiện nâng cấp có sẵn trong mã nguồn).

## 3. Kiểm tra các thay đổi

1. **Kho video học liệu → Playlist:** có 5 dòng/trang, nút số trang. Gán môn rồi **Lưu**: vị trí cuộn không đổi. Khi playlist đã có QR thuộc môn đang chọn, hiện **Tải mã QR** và **Xóa mã QR**; không còn **Mở thử** tại đây. Playlist chưa có QR hiển thị **Tạo mã QR**.
2. **Kho video học liệu → Video:** có 5 dòng/trang, phân trang riêng với playlist. Chọn môn học, **Tạo mã QR** trên một dòng; phải giữ nguyên vị trí, và nút đổi thành **Tải mã QR**. Các nút **Xóa** và **Đổi video đích** chỉ thao tác trên QR của môn đã chọn. Chọn video khác và **Lưu video đích**, kiểm tra QR cũ vẫn có cùng slug/URL.
3. **Playlist bị xóa/không còn khả dụng trên YouTube:** sau **Đồng bộ lại**, hệ thống ghi rõ playlist không còn trên YouTube nếu nó từng được gán môn học; GV vẫn có thể **ngừng mã QR** liên quan. QR đã in chuyển sang thông báo ngừng sử dụng sau khi xóa QR; lượt quét/xem trong quá khứ không bị xóa. Không thử bằng cách xóa playlist đang phục vụ sinh viên thật.
4. **Quản lý mã QR động:** tải PNG và **Mở thử** đã trở lại cho **cả QR video và QR playlist**; QR video còn **Đổi video đích**; cả hai loại đều có **Xóa**. Xác nhận QR playlist vẫn không thể đổi video đích theo kiểu QR video, vì playlist được đồng bộ động.
5. **Thống kê khai thác → Mục 1:** nhãn **Người thực hiện** và danh sách chọn GV/quản trị viên; quản trị viên xem lựa chọn phù hợp toàn hệ thống, GV thường chỉ xem dữ liệu trong quyền của mình.
6. **Thống kê khai thác → Mục 2:** bỏ ô nhập **Tên video/học liệu**, hai nút **Lọc kết quả** và **Xóa lọc** nằm ngay trong hàng bộ lọc. Bảng 10 dòng/trang vẫn giữ nguyên.
7. **Google OAuth:** nếu xuất hiện `mismatching_state`, hệ thống vẫn **chặn callback không hợp lệ** để chống CSRF; khi phiên đăng nhập còn nhận diện được, Web App thử khởi tạo lại đăng nhập **tối đa một lần**. Nếu lỗi lặp, kiểm tra dùng duy nhất một tab đăng nhập, cookie, tên miền/URL HTTPS nhất quán, `BASE_URL`, và **`SECRET_KEY` cố định, giống nhau ở mọi worker và qua các lần deploy**. Tuyệt đối không bỏ kiểm tra OAuth `state`.

## 4. Lưu ý nghiệp vụ

- **Xóa mã QR** trong Web App là **ngừng sử dụng QR**, không xóa video/playlist trên YouTube và không xóa lịch sử quét/xem. QR đã in không thể mở học liệu sau khi ngừng; cân nhắc trước khi xác nhận.
- Một video/playlist có thể thuộc nhiều MH/MĐ và có nhiều mã QR theo môn. Các nút trong Kho video áp dụng **đúng môn đang chọn**.
- Với playlist đã biến mất trên YouTube, không cho tạo QR mới khi nguồn không còn khả dụng. Có thể đồng bộ lại sau khi playlist xuất hiện trở lại.
- Nếu JavaScript bị tắt, thao tác tạo QR vẫn gửi biểu mẫu thông thường và có thể chuyển vị trí; giữ cuộn không tải lại trang cần JavaScript.
- **Lỗi `mismatching_state` chưa thể khẳng định được xử lý dứt điểm trên Render nếu không kiểm tra cookie/cấu hình thực tế.** Hệ thống không thể nhận diện tên người đăng nhập trước khi Google xác minh thành công, nên một số nhật ký thất bại đầu tiên vẫn ghi *Người đăng nhập chưa xác định*.

## 5. Kiểm tra trước khi đóng gói

Đã chạy `compileall`, phân tích 22 mẫu Jinja2, kiểm tra cú pháp JavaScript bằng Node, các kiểm tra bố cục v4.3.10, kiểm thử truy vấn nghiệp vụ SQLite (bàn giao, thống kê playlist, lọc nguồn YouTube), cùng kiểm thử ZIP theo môn. **Chưa chạy tích hợp thật trên Render/PostgreSQL/Google OAuth**, vì môi trường thử không có đầy đủ dịch vụ ngoài.
