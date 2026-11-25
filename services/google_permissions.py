"""Phân loại quyền Google YouTube và các lượt từ chối cấp quyền.

Không suy đoán quyền từ cấu hình yêu cầu; chỉ dùng phạm vi Google THỰC TẾ trả về.
Không coi hành động người dùng từ chối OAuth là kiểm thử chức năng thất bại.
"""
from __future__ import annotations

YOUTUBE_READ_SCOPE = "https://www.googleapis.com/auth/youtube.readonly"
# Các quyền rộng hơn cũng cho phép đọc dữ liệu kênh YouTube; Google có thể
# trả lại quyền đã được cấp trước đó khi include_granted_scopes=true.
YOUTUBE_READ_CAPABLE_SCOPES = frozenset({
    YOUTUBE_READ_SCOPE,
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.force-ssl",
})
USER_DENIAL_CODES = frozenset({"access_denied", "user_cancelled", "user_denied"})


def scopes_set(value):
    if isinstance(value, (list, tuple, set)):
        return {part for item in value for part in str(item or "").split() if part}
    return set(str(value or "").split())


def has_youtube_read_permission(granted_scopes):
    return bool(YOUTUBE_READ_CAPABLE_SCOPES.intersection(scopes_set(granted_scopes)))


def explicitly_denied_by_user(error=None, query_error=None):
    """Chỉ bắt những mã từ chối rõ ràng; lỗi mạng/CSRF/Google không được che giấu."""
    code = (getattr(error, "error", None) or "").strip().lower() if error else ""
    query = (query_error or "").strip().lower()
    return code in USER_DENIAL_CODES or query in USER_DENIAL_CODES


def historical_oauth_denial_clause(model):
    """Bộ lọc loại riêng lượt từ chối đã ghi nhầm: giữ nguyên bản ghi gốc.

    Chỉ khớp các lỗi rõ ràng về từ chối cấp quyền OAuth hoặc một lỗi
    YouTube permissions đã ghi trong phiên bản cũ; tuyệt đối không tự động
    loại trường hợp nhiều loại lỗi pha trộn hay lỗi mạng/cấu hình.
    """
    from sqlalchemy import and_, or_
    auth_denial = and_(
        model.case_code == "AUTH_LOGIN",
        model.passed.is_(False),
        model.note.ilike("%Người đăng nhập đã hủy hoặc chưa đồng ý cấp quyền cho ứng dụng%"),
    )
    # Bản cũ còn ghi một ca YT_SYNC "Không đạt" khi YouTube trả mã
    # thiếu quyền. Chỉ phân loại lại nếu ghi chú nhận diện chính xác
    # MỘT lỗi quyền (hoặc lỗi quyền duy nhất tại xử lý trực tiếp).
    # Nếu có nhiều lỗi pha trộn thì giữ là thất bại, chờ đối chiếu thủ công.
    yt_permission_denial = and_(
        model.case_code == "YT_SYNC",
        model.passed.is_(False),
        or_(
            model.note.ilike("Lỗi xử lý đồng bộ: YouTube chưa cho phép truy cập dữ liệu kênh%"),
            and_(
                model.note.ilike("%phần lỗi: 1.%"),
                model.note.ilike("%YouTube chưa cho phép truy cập dữ liệu kênh%"),
            ),
        ),
    )
    return or_(auth_denial, yt_permission_denial)


def only_permission_failures(failures, codes):
    """Trả True chỉ khi MỌI lỗi đồng bộ có mã phân loại rõ ràng và là lỗi quyền."""
    if not isinstance(failures, int) or failures <= 0:
        return False
    if not isinstance(codes, (list, tuple)) or len(codes) != failures:
        return False
    return all(code in {"permission", "auth_expired"} for code in codes)
