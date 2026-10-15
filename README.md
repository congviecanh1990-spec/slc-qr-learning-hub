# SLC QR Learning Hub

Web App phục vụ đề tài **“Xây dựng công cụ hỗ trợ giảng viên tạo mã QR từ video YouTube trong giảng dạy thực hành tại Trường Cao đẳng Sơn La”** theo bản hiệu chỉnh 10/2026.

## 1. Các chức năng đã có trong bộ mã nguồn

- Đăng nhập Google OAuth 2.0, xin quyền đọc YouTube (`youtube.readonly`).
- Nhận diện kênh YouTube, đọc playlist, đồng bộ video và trạng thái.
- Lưu `privacyStatus`, `embeddable`, `uploadStatus`, trạng thái truy cập.
- Hub/WebSub: đăng ký callback công khai, xác minh callback, lưu event, làm mới video sau event.
- Đối soát YouTube Data API định kỳ bằng `cron_reconcile.py` hoặc endpoint bảo vệ `/tasks/reconcile`.
- QR động qua URL `/q/<slug>`; đổi video đích mà QR/slug không đổi.
- Lưu lịch sử mapping QR → video (`qr_target_history`).
- Tải QR PNG và ZIP toàn bộ QR.
- Focus Viewer dùng YouTube IFrame Player API với host `youtube-nocookie.com`.
- Lớp overlay riêng khi video kết thúc.
- Nhận diện mã GV/SV + lớp, không bắt buộc họ tên, không lưu IP thô.
- `scan_logs`: mã người dùng, vai trò, lớp, học phần, QR, video, thời gian, thành công/thất bại.
- `watch_sessions` + `watch_events`: play/pause/ended/heartbeat, thời lượng xem ước tính, vị trí xa nhất, tỷ lệ hoàn thành, trạng thái hoàn thành.
- Thuật toán hạn chế cộng thời gian khi người xem tua nhảy lớn.
- Bộ lọc thống kê và xuất CSV.
- Dashboard chỉ tiêu nghiệm thu: tỷ lệ quét, thời gian xử lý, giảm thao tác/thời gian, test đạt, số học phần/đơn vị/GV/SV/video, hài lòng GV/SV.
- Ghi dữ liệu so sánh thủ công – Web App, ca kiểm thử, khảo sát 5 mức.
- Nhật ký lỗi.
- Sao lưu ZIP và khôi phục dữ liệu (admin).
- PostgreSQL; không cần cài Python trên máy giảng viên/sinh viên sau khi triển khai.

## 2. Cấu trúc chính

```text
slc_qr_learning_hub/
├─ app.py
├─ wsgi.py
├─ models.py
├─ config.py
├─ security.py
├─ cron_reconcile.py
├─ requirements.txt
├─ render.yaml
├─ .env.example
├─ services/
│  ├─ youtube.py
│  └─ websub.py
├─ templates/
└─ static/
```

## 3. Triển khai trên Render bằng Blueprint

### Bước A — Đưa mã nguồn lên GitHub

Tạo một repository mới, rồi tải **toàn bộ nội dung thư mục này** lên **thư mục gốc** của repository. File `render.yaml` phải nằm ngay ở root.

### Bước B — Tạo Google Cloud OAuth trước hoặc sau lần deploy đầu

Trong Google Cloud Console:

1. Tạo/chọn Project.
2. Bật **YouTube Data API v3**.
3. Cấu hình **OAuth consent screen**.
4. Tạo **OAuth Client ID → Web application**.
5. Sau khi biết URL Render, thêm Redirect URI chính xác:

```text
https://TEN-DICH-VU.onrender.com/auth/callback
```

Nếu OAuth app đang ở chế độ Testing, thêm tài khoản giảng viên vào **Test users**.

### Bước C — Render

1. Đăng nhập Render.
2. Chọn **New → Blueprint**.
3. Kết nối repository GitHub vừa tạo.
4. Render đọc `render.yaml` và tạo:
   - Web Service `slc-qr-learning-hub`;
   - PostgreSQL `slc-qr-db`.
5. Khi Render yêu cầu biến môi trường, nhập:
   - `GOOGLE_CLIENT_ID`
   - `GOOGLE_CLIENT_SECRET`
   - `ADMIN_EMAILS` = email Google của chủ nhiệm/quản trị; nhiều email cách nhau bằng dấu phẩy.

   `BASE_URL` không bắt buộc trên Render vì mã nguồn tự dùng `RENDER_EXTERNAL_URL`. Chỉ đặt `BASE_URL` thủ công nếu sau này chuyển sang tên miền riêng.
6. `SECRET_KEY` và `RECONCILE_KEY` được Render sinh tự động theo `render.yaml`.
7. Deploy.

Render dùng:

```text
Build Command: pip install -r requirements.txt
Start Command: gunicorn -w 1 --threads 4 --timeout 120 wsgi:app
Health Check: /health
```

## 4. Thứ tự kiểm tra ngay sau khi deploy

1. Mở `https://TEN-DICH-VU.onrender.com/health` → phải thấy `status: ok`.
2. Nhấn **Đăng nhập bằng Google/YouTube**.
3. Vào **YouTube → Đồng bộ kênh/video**.
4. Kiểm tra **Kho video**.
5. Vào **YouTube → Đăng ký/gia hạn Hub**.
6. Tạo **Học phần + lớp**.
7. Vào **QR động → tạo QR**.
8. Tải PNG hoặc mở thử QR.
9. Dùng điện thoại/quyền trình duyệt khác mở URL QR → nhập mã SV → xem Focus Viewer.
10. Phát, dừng, tua, xem hết video → kiểm tra **Thống kê**.
11. Đổi video đích của QR → mở lại chính QR cũ để xác nhận QR động.
12. Vào **Nghiệm thu** để nhập phép đo thủ công/Web App, ca kiểm thử và khảo sát.

## 5. Đối soát API định kỳ

### Cách chuẩn: Render Cron Job

Mã chạy cron đã có:

```text
python cron_reconcile.py
```

Cron này:

- đối soát trạng thái video bằng YouTube Data API;
- đánh dấu video không còn truy cập;
- gia hạn các subscription Hub/WebSub sắp hết hạn.

Không khai báo cron trực tiếp trong `render.yaml` mặc định để việc deploy Web + PostgreSQL không tự phát sinh một dịch vụ Cron có thể yêu cầu gói tính phí. Khi cần nghiệm thu chính thức, tạo Render Cron Job trỏ tới cùng repo và đặt lịch phù hợp, ví dụ hằng ngày.

### Cách thay thế

Gọi:

```text
POST /tasks/reconcile
Header: X-Task-Key: <RECONCILE_KEY>
```

Endpoint này được bảo vệ bằng khóa riêng.

## 6. Quy tắc dữ liệu xem

Hệ thống chỉ coi dữ liệu xem là **ước tính hành vi truy cập**.

- Heartbeat chỉ gửi khi player ở trạng thái phát.
- Nếu vị trí phát nhảy xa hơn thời gian thực đã trôi qua, hệ thống coi đó là seek/tua và không cộng toàn bộ đoạn nhảy.
- Phiên được đánh dấu hoàn thành khi có event `ended` hoặc thời lượng xem ước tính đạt ngưỡng cấu hình (`COMPLETION_THRESHOLD`, mặc định 90%).
- Không dùng watch log để khẳng định mức độ chú ý, mức độ hiểu bài hay kết quả học tập.

## 7. Bảo vệ dữ liệu

- Không lưu địa chỉ IP thô trong `scan_logs`.
- Mã GV/SV là mã định danh nghiên cứu, không bắt buộc tên thật.
- OAuth token được mã hóa trước khi ghi vào PostgreSQL bằng khóa dẫn xuất từ `SECRET_KEY`.
- Tệp backup có thể chứa token ở **dạng mã hóa**; vẫn phải coi backup là dữ liệu nhạy cảm và không chia sẻ công khai.
- Trang thống kê yêu cầu đăng nhập.
- Admin được xác định qua `ADMIN_EMAILS`.

## 8. Sao lưu/khôi phục

Admin có menu:

- **Sao lưu** → tải ZIP chứa manifest và dữ liệu các bảng.
- **Khôi phục** → chọn đúng ZIP do hệ thống sinh và gõ `RESTORE`.

Khôi phục sẽ thay toàn bộ dữ liệu hiện tại. Nên tạo một bản backup mới ngay trước khi thử nghiệm restore.

## 9. Các ca kiểm thử nên ghi ở trang “Nghiệm thu”

Tối thiểu nên có:

1. OAuth đăng nhập thành công.
2. Nhận diện đúng kênh.
3. Đồng bộ playlist/video.
4. Nhận biết private/unavailable/không cho nhúng.
5. Không tạo trùng bản ghi video khi đồng bộ lại.
6. Tạo QR động.
7. Tải PNG.
8. Tải ZIP nhiều QR.
9. Đổi video đích nhưng slug/QR giữ nguyên.
10. Focus Viewer phát đúng video.
11. Overlay riêng sau khi ended.
12. Hub/WebSub callback xác minh thành công.
13. Hub event được ghi và xử lý.
14. API reconciliation cập nhật video bị xóa/private/không nhúng.
15. Scan log ghi đủ mã, vai trò, lớp, học phần, QR, video, thời gian.
16. Bộ lọc + CSV.
17. Watch log có play/pause/ended/heartbeat.
18. Tua nhảy lớn không cộng sai toàn bộ thời lượng.
19. Sao lưu ZIP.
20. Khôi phục backup.

## 10. Lưu ý trước nghiệm thu

Bộ mã nguồn này đã bao phủ kiến trúc và chức năng cốt lõi của bản thuyết minh. Tuy nhiên, các **chỉ tiêu định lượng** (≥98%, ≤5 giây, ≥30%, ≥95%, ≥3 học phần, ≥2 đơn vị, ≥5 GV, ≥60 SV, ≥100 video/tình huống, ≥80% hài lòng) chỉ được xác nhận sau khi có dữ liệu thực nghiệm thật.
