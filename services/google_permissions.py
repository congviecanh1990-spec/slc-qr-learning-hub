"""Phân loại quyền Google YouTube và các lượt từ chối cấp quyền.

Không suy đoán quyền từ cấu hình yêu cầu; chỉ dùng phạm vi Google THỰC TẾ trả về.
Không coi hành động người dùng từ chối OAuth là kiểm thử chức năng thất bại.
"""
from __future__ import annotations

YOUTUBE_READ_SCOPE = "https://www.googleapis.com/auth/youtube.readonly"
USER_DENIAL_CODES = frozenset({"access_denied", "user_cancelled", "user_denied"})


def scopes_set(value):
    if isinstance(value, (list, tuple, set)):
        return {str(v).strip() for v in value if str(v).strip()}
    return set(str(value or "").split())


def has_youtube_read_permission(granted_scopes):
    return YOUTUBE_READ_SCOPE in scopes_set(granted_scopes)


def explicitly_denied_by_user(error=None, query_error=None):
    """Chỉ bắt những mã từ chối rõ ràng; lỗi mạng/CSRF/Google không được che giấu."""
    code = (getattr(error, "error", None) or "").strip().lower() if error else ""
    query = (query_error or "").strip().lower()
    return code in USER_DENIAL_CODES or query in USER_DENIAL_CODES


def historical_oauth_denial_clause(model):
    """Bộ lọc loại riêng lượt từ chối đã ghi nhầm: giữ nguyên bản ghi gốc.

    Chỉ khớp dòng AUTH_LOGIN không đạt có ghi chú CHÍNH XÁC kiểu phân loại
    'người dùng hủy / chưa đồng ý cấp quyền' của phiên bản trước.
    Không loại lỗi token, OAuth state, mất mạng, cấu hình, hay lỗi khác.
    """
    from sqlalchemy import and_
    return and_(
        model.case_code == "AUTH_LOGIN",
        model.passed.is_(False),
        model.note.ilike("%Người đăng nhập đã hủy hoặc chưa đồng ý cấp quyền cho ứng dụng%"),
    )
