import os


def _db_url():
    url = os.getenv("DATABASE_URL", "sqlite:///slc_qr.db")
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]
    return url


class Config:
    APP_NAME = "TẠO MÃ QR TỰ ĐỘNG TỪ VIDEO YOUTUBE"
    APP_TAGLINE = "Công cụ hỗ trợ giảng viên tạo, quản lý và khai thác mã QR học liệu video"
    SCHOOL_NAME = "Trường Cao đẳng Sơn La"
    AUTHORS = [
        "Nguyễn Thị Thúy Tươi",
        "Hoàng Thị Nhất",
        "Nguyễn Thu Huyền",
        "Tường Thị Phương Thảo",
        "Nguyễn Hữu Thọ",
    ]
    BRAND_LOGO = "branding/logo_truong.png"
    BRAND_PRIMARY = "#8f171d"

    # Mau QR chinh thuc: den tren nen trang, logo truong o giua.
    QR_FILL_COLOR = "#000000"
    QR_BACKGROUND_COLOR = "#FFFFFF"
    QR_LOGO_RATIO = 0.23
    QR_LOGO_WHITE_PAD_RATIO = 0.012
    QR_BOX_SIZE = 14
    QR_BORDER = 4

    SECRET_KEY = os.getenv("SECRET_KEY", "dev-change-me")
    SQLALCHEMY_DATABASE_URI = _db_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
    }

    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
    GOOGLE_SCOPES = "openid email profile https://www.googleapis.com/auth/youtube.readonly"

    BASE_URL = (os.getenv("BASE_URL") or os.getenv("RENDER_EXTERNAL_URL") or "").rstrip("/")
    ADMIN_EMAILS = {
        x.strip().lower()
        for x in os.getenv("ADMIN_EMAILS", "").split(",")
        if x.strip()
    }
    RECONCILE_KEY = os.getenv("RECONCILE_KEY", "change-me")
    COMPLETION_THRESHOLD = float(os.getenv("COMPLETION_THRESHOLD", "0.90"))
    HEARTBEAT_SECONDS = int(os.getenv("HEARTBEAT_SECONDS", "5"))
    AUTO_CREATE_DB = os.getenv("AUTO_CREATE_DB", "1") == "1"

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.getenv("COOKIE_SECURE", "1") == "1"
    REMEMBER_COOKIE_HTTPONLY = True
    PREFERRED_URL_SCHEME = "https"
