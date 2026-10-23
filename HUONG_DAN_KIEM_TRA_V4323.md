# HƯỚNG DẪN KIỂM TRA WEB APP v4.3.23 (RENDER)

## Thay đổi chính

- Mục **Nhật ký lỗi hệ thống** (quản trị viên) bổ sung cột **Nguyên nhân có thể**.
- Cột **Người thực hiện thất bại** hiển thị tên và email nếu đã xác định được tài khoản; với tác vụ tự động hiển thị rõ **Hệ thống tự động xử lý** và email chủ sở hữu dữ liệu nếu biết.
- Lỗi đăng nhập chỉ ghi email **sau khi đã đọc được hồ sơ từ Google bằng token hợp lệ**. Lỗi xảy ra trước bước này hiển thị **Chưa xác định được email đăng nhập**; tuyệt đối không suy diễn từ tên hoặc dữ liệu phiên không xác thực.
- Khi đồng bộ từng bước gặp lỗi, Web App ghi lại email tài khoản liên quan, thao tác, thời điểm, nguyên nhân tiếng Việt dễ hiểu; màn hình **Kênh YouTube** hiển thị các nguyên nhân gần nhất.
- Các lỗi đã phân loại gồm: phiên Google không khớp, người dùng từ chối, quyền hết hiệu lực, hạn mức YouTube, kết nối quá thời gian, cấu hình dịch vụ, playlist không còn truy cập được, và lỗi xử lý khác.
- Không lưu token OAuth, URL API nguyên bản hoặc nội dung phản hồi HTTP nhạy cảm vào bản ghi lỗi mới.
- Bảo toàn chức năng đăng nhập nhanh, đồng bộ playlist tuyển chọn, QR, lượt quét, trạng thái xem tốt nhất, thống kê và quyền truy cập từ v4.3.22.

## Nâng cấp Render

1. Sao lưu PostgreSQL trước khi triển khai và giải nén toàn bộ ZIP.
2. Cập nhật dự án lên Render như các lần trước.
3. **Giữ nguyên DATABASE_URL, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, SECRET_KEY, các biến môi trường và dữ liệu hiện có.**
4. Để `AUTO_CREATE_DB=1`: ứng dụng tự bổ sung hai cột `actor_email`, `reason` vào bảng `error_logs` nếu chưa tồn tại. Không xóa bảng hoặc dữ liệu cũ.
5. Truy cập `/health` sau triển khai; đăng nhập bằng tài khoản quản trị viên và kiểm tra mục **Nhật ký lỗi hệ thống**.

## Các ca kiểm tra trên Render

| Tình huống | Kết quả mong đợi |
|---|---|
| Google đăng nhập thành công | Vào hệ thống nhanh, không phát sinh lỗi mới |
| Google hủy cấp quyền trước khi trả hồ sơ | Lưu lỗi đăng nhập, nguyên nhân dễ hiểu, email là **Chưa xác định** |
| Google đã trả hồ sơ nhưng bước xử lý sau đó lỗi | Lưu email đã nhận từ Google nếu xác minh được |
| YouTube chặn quyền kênh/playlist | Tại Nhật ký lỗi có email tài khoản dùng để đồng bộ, thao tác và nguyên nhân quyền truy cập |
| Hết quota hoặc timeout | Nguyên nhân được phân biệt đúng; không hiển thị đường dẫn API dài |
| Tài khoản phụ bị ngắt kết nối trong lúc đồng bộ | Lưu trạng thái lỗi và email GV chính nếu không còn email tài khoản phụ |
| Đồng bộ hoàn tất và có nhiều phần lỗi | Màn hình Kênh YouTube nêu các nguyên nhân gần nhất; bằng chứng YT_SYNC không tính nhầm thành công |
| Mở lại trạng thái sau khi đồng bộ xong | Không ghi thêm lần lỗi giống nhau chỉ vì xem lại màn hình |
| QR và báo cáo học liệu | Hoạt động như trước, không đổi trạng thái hoàn thành đã đạt |

**Giới hạn dữ liệu cũ:** Bản ghi lịch sử trước khi cập nhật nếu chưa có người dùng/email thì không thể truy nguyên email một cách đáng tin cậy. Hệ thống không tự điền người thực hiện cho những bản ghi không đủ bằng chứng.

**Giới hạn kiểm thử:** Các bài kiểm tra kèm mã nguồn chạy ngoại tuyến/mô phỏng; cần kiểm tra thực tế OAuth và API YouTube khi đưa lên Render.
