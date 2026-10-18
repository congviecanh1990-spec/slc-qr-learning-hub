# HƯỚNG DẪN CẬP NHẬT v4.3.0

**Không xóa dịch vụ Render, PostgreSQL hay repository hiện tại.** Nên sao lưu dữ liệu bằng menu **Sao lưu & khôi phục** trước khi cập nhật.

1. Giải nén ZIP; mở repository GitHub `congviecanh1990-spec/slc-qr-learning-hub` (nhánh `main`). Tải toàn bộ nội dung *bên trong* thư mục vừa giải nén lên GitHub, giữ đúng cấu trúc tệp.
2. Chọn **Commit changes**. Chờ Render tự triển khai đến trạng thái **Live**.
3. **Quan trọng cho tính năng kết nối thêm tài khoản YouTube**: vào Google Cloud Console > Google Auth Platform > Clients > ứng dụng OAuth đang sử dụng, bổ sung URI điều hướng được ủy quyền:
   `https://slc-qr-learning-hub.onrender.com/youtube/connect-callback`
   Giữ nguyên URI cũ `https://slc-qr-learning-hub.onrender.com/auth/callback`.
   Nếu chưa thêm URI mới, chức năng kết nối kênh phụ sẽ chưa hoạt động, các chức năng còn lại vẫn dùng được.
4. Dùng trình duyệt nhấn Ctrl+F5, đăng nhập; kiểm tra: Tổng quan, Môn học/Mô đun, Lớp chủ nhiệm, Danh sách lớp đang dạy, Kênh YouTube, Mã QR động.
5. Thử nghiệm với dữ liệu mẫu: GV bộ môn tạo lớp khi chưa có; GVCN nhận lớp đã có; tạo môn rồi sửa tên; upload Excel; thử sửa họ tên SV; chuyển một video giữa playlist và bấm **Đồng bộ lại**; thử ngừng sử dụng một QR đã có rồi quét lại.

**Không có cron job đồng bộ định kỳ trả phí.** Đồng bộ chỉ chạy lúc đăng nhập, khi GV bấm Đồng bộ lại và từ WebSub đối với sự kiện được YouTube hỗ trợ. 

**Lưu ý**: Các thử nghiệm Google OAuth, YouTube Data API và PostgreSQL thực cần kiểm tra trên Render; kiểm tra cục bộ tại nơi đóng gói chỉ gồm cú pháp Python, template và liên kết.
