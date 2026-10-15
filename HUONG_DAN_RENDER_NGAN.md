# HƯỚNG DẪN NHANH — CHỈ 8 BƯỚC

1. Giải nén gói mã nguồn.
2. Upload **toàn bộ file/thư mục** vào root của GitHub repository.
3. Vào Google Cloud, bật **YouTube Data API v3** và tạo **OAuth Client ID – Web application**.
4. Vào Render → **New → Blueprint** → chọn repository.
5. Nhập `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `ADMIN_EMAILS`.
6. Deploy xong, lấy URL `https://...onrender.com` (ứng dụng tự nhận URL Render).
7. Trong Google OAuth Client, thêm Redirect URI: `https://...onrender.com/auth/callback`.
8. Mở Web App → đăng nhập Google → YouTube → Đồng bộ → tạo Học phần → tạo QR → mở thử QR.

Nếu `/health` trả `{"status":"ok","database":"ok"}` thì Web App và PostgreSQL đã kết nối đúng.
