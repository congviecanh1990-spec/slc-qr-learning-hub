"""Tóm tắt nguyên nhân lỗi cho báo cáo mà không lộ token, URL OAuth hoặc dữ liệu nhạy cảm."""

import re


def login_failure_reason(exc):
    """Không bao giờ suy diễn email từ lỗi OAuth/state chưa xác minh."""
    msg = str(exc or "").lower()
    if any(x in msg for x in ("mismatching_state", "csrf warning", "invalid_state")):
        return "Phiên xác thực Google không còn khớp; có thể do mở nhiều tab hoặc cookie bị thay đổi."
    if any(x in msg for x in ("access_denied", "user_cancelled", "user_denied", "consent_required")):
        return "Người đăng nhập đã hủy hoặc chưa đồng ý cấp quyền cho ứng dụng."
    if any(x in msg for x in ("invalid_client", "redirect_uri_mismatch", "unauthorized_client")):
        return "Cấu hình ứng dụng Google OAuth chưa phù hợp; cần quản trị viên kiểm tra."
    if any(x in msg for x in ("invalid_grant", "expired", "token")):
        return "Mã hoặc phiên xác thực Google không còn hợp lệ; hãy đăng nhập lại."
    if any(x in msg for x in ("scope", "permission", "insufficient", "403 client error", "401 client error")):
        return "Google chưa cho phép ứng dụng truy cập tài khoản hoặc quyền đã hết hiệu lực."
    if "tài khoản google này đã" in msg or "tài khoản youtube này đã" in msg:
        return "Tài khoản Google/YouTube này đã liên kết với một hồ sơ giảng viên khác."
    if any(x in msg for x in ("timed out", "timeout", "read timeout")):
        return "Google phản hồi quá thời gian cho phép; hãy thử lại sau."
    if any(x in msg for x in ("connection", "network", "name resolution", "dns")):
        return "Không kết nối được tới Google; hãy kiểm tra đường truyền và thử lại."
    if "email" in msg:
        return "Google chưa cung cấp email hợp lệ để xác định tài khoản."
    return "Đăng nhập gặp lỗi xử lý hoặc kết nối chưa xác định; hãy kiểm tra nhật ký và thử lại."


def safe_error_diagnostic(exc):
    """Dùng thông tin loại lỗi/mã phân loại thay cho chuỗi ngoại lệ có token hoặc URL."""
    category = type(exc).__name__
    code = getattr(exc, "code", None)
    safe_code = re.sub(r"[^a-zA-Z0-9_-]", "", str(code or ""))[:45]
    return (f"Loại lỗi: {category[:80]}" + (f"; mã: {safe_code}" if safe_code else ""))
