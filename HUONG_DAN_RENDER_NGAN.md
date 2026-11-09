# Hướng dẫn triển khai Web App v4.3.28 lên Render

1. **Sao lưu trước khi nâng cấp:** dùng **Sao lưu & khôi phục** trong Web App hoặc công cụ sao lưu PostgreSQL. Bản sao lưu có nhật ký lỗi hiện tại nên lưu cẩn thận và không đưa lên GitHub.
2. Giải nén `TAO_MA_QR_TU_DONG_YOUTUBE_v4.3.28_RENDER.zip`. Cập nhật **toàn bộ mã nguồn bên trong** lên nhánh `main` của kho GitHub hiện dùng cho Render. Không tải nguyên ZIP như một tệp mã nguồn.
3. Giữ nguyên `DATABASE_URL`, Google OAuth, `SECRET_KEY`, dữ liệu và mã QR hiện có; đặt `AUTO_CREATE_DB=1`. Render triển khai bản commit mới.
4. **Lần khởi động đầu:** ứng dụng kiểm tra `error_logs` và chỉ xóa nếu có đúng 3 lỗi. Lưu một dấu mốc vĩnh viễn tại `app_one_time_maintenance` để lần khởi động sau không xóa lỗi nữa. Nếu số lỗi khác 3, tác vụ được đánh dấu đã bỏ qua và không thử lại.
5. Sau deploy, đăng nhập **Quản trị viên → Nhật ký lỗi**, kiểm tra ba lỗi cũ biến mất (nếu trước đó có đúng 3 bản ghi). Các lỗi mới vẫn được ghi bình thường. Kiểm tra lại chức năng QR, thống kê và lịch sử xem.

**Quan trọng:** Không xóa PostgreSQL, không đặt lại cơ sở dữ liệu và không khôi phục bản sao lưu cũ ngay sau khi dọn lỗi; khôi phục backup có thể đưa ba lỗi cũ trở lại, nhưng cơ chế dọn lỗi vẫn không chạy lần thứ hai. Nếu số lượng bản ghi không đúng 3, bản này sẽ không tự ý xóa bất kỳ lỗi nào.

Đọc `HUONG_DAN_KIEM_TRA_V4328.md` để xem các điều kiện và tình huống kiểm tra chi tiết. Chưa thử nghiệm trên PostgreSQL Production của Render.
