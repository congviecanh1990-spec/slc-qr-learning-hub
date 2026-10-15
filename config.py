import os


def _db_url():
    url = os.getenv("DATABASE_URL", "sqlite:///slc_qr.db")
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]
    return url


class Config:
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
