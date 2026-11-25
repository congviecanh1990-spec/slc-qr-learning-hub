"""Bảo đảm thiếu quyền YouTube là trạng thái cấp quyền, không phải lỗi ứng dụng."""
from types import SimpleNamespace

import pytest

from test_video_selection_across_pages import configured_app


def test_permission_helpers_classify_only_explicit_user_denial():
    from services.google_permissions import (
        has_youtube_read_permission, explicitly_denied_by_user,
        YOUTUBE_READ_SCOPE, historical_oauth_denial_clause,
    )
    assert has_youtube_read_permission("openid email profile " + YOUTUBE_READ_SCOPE)
    assert has_youtube_read_permission(["profile", YOUTUBE_READ_SCOPE])
    assert has_youtube_read_permission("https://www.googleapis.com/auth/youtube")
    assert has_youtube_read_permission(["email https://www.googleapis.com/auth/youtube.force-ssl"])
    assert not has_youtube_read_permission("openid email profile")
    assert not has_youtube_read_permission(None)
    assert explicitly_denied_by_user(query_error="access_denied")
    assert explicitly_denied_by_user(SimpleNamespace(error="access_denied"))
    for value in ("mismatching_state", "invalid_client", "invalid_grant", "timeout"):
        assert not explicitly_denied_by_user(SimpleNamespace(error=value))
        assert not explicitly_denied_by_user(query_error=value)


def test_twice_refusing_youtube_consent_is_not_system_failure(configured_app):
    from models import db, FunctionalTestRun, ErrorLog
    app, _, web = configured_app
    with app.test_client() as client:
        for _ in range(2):
            response = client.get("/auth/callback?error=access_denied")
            assert response.status_code == 302
            assert response.headers["Location"].endswith("/auth/youtube-permission")
        instructions = client.get("/auth/youtube-permission")
        assert instructions.status_code == 200
        assert "Đăng nhập lại và cấp quyền YouTube" in instructions.get_data(as_text=True)
    with app.app_context():
        assert FunctionalTestRun.query.filter_by(case_code="AUTH_LOGIN").count() == 0
        assert ErrorLog.query.filter_by(module="oauth").count() == 0


def test_login_requires_youtube_scope_before_creating_session(configured_app, monkeypatch):
    from models import db, User, OAuthAccount, FunctionalTestRun
    from services.google_permissions import YOUTUBE_READ_SCOPE
    app, keys, web = configured_app
    class FakeGoogle:
        scopes = "openid email profile"
        def authorize_access_token(self):
            return {"access_token": "fake-test-token", "scope": self.scopes}
    google = FakeGoogle()
    monkeypatch.setattr(web.oauth, "google", google, raising=False)

    class FakeResponse:
        def raise_for_status(self): return None
        def json(self):
            return {"email": "video-selection-teacher@test.local", "sub": "google-sub-verified"}
    def get(url, **kwargs):
        assert url.endswith("/v1/userinfo")
        return FakeResponse()
    monkeypatch.setattr(web.requests, "get", get)
    with app.app_context():
        teacher = db.session.get(User, keys["teacher"])
        teacher.google_sub = "google-sub-verified"
        db.session.commit()
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["user_id"] = keys["teacher"]
            sess.pop("youtube_permission_verified_sub", None)
        # Một session cũ có user_id nhưng không chứng nhận YouTube KHÔNG mở được Web App.
        forbidden = client.get("/videos")
        assert forbidden.status_code == 302
        assert forbidden.headers["Location"].endswith("/auth/youtube-permission")
        denied = client.get("/auth/callback")
        assert denied.status_code == 302
        assert denied.headers["Location"].endswith("/auth/youtube-permission")
        with client.session_transaction() as sess:
            assert sess.get("user_id") is None
        with app.app_context():
            assert OAuthAccount.query.filter_by(user_id=keys["teacher"]).count() == 0
            assert FunctionalTestRun.query.filter_by(case_code="AUTH_LOGIN").count() == 0
        google.scopes = "openid email profile " + YOUTUBE_READ_SCOPE
        allowed = client.get("/auth/callback")
        assert allowed.status_code == 302
        with client.session_transaction() as sess:
            assert sess["user_id"] == keys["teacher"]
            assert sess["youtube_permission_verified_sub"] == "google-sub-verified"
        with app.app_context():
            oauth_account = OAuthAccount.query.filter_by(user_id=keys["teacher"]).one()
            assert YOUTUBE_READ_SCOPE in oauth_account.scopes
            assert FunctionalTestRun.query.filter_by(case_code="AUTH_LOGIN", passed=True).count() == 1
        assert client.get("/videos").status_code == 200


def test_missing_scope_uses_google_tokeninfo_not_config_default(configured_app, monkeypatch):
    from models import db, User, OAuthAccount, FunctionalTestRun
    from services.google_permissions import YOUTUBE_READ_SCOPE
    app, keys, web = configured_app
    class FakeGoogle:
        def authorize_access_token(self):
            return {"access_token": "fake-token-without-scope"}
    monkeypatch.setattr(web.oauth, "google", FakeGoogle(), raising=False)
    requested = []
    class FakeResponse:
        def __init__(self, payload): self.payload = payload
        def raise_for_status(self): return None
        def json(self): return self.payload
    def fake_get(url, **kwargs):
        requested.append(url)
        if url.endswith("/v1/userinfo"):
            return FakeResponse({"email":"video-selection-teacher@test.local","sub":"google-uid"})
        if url.endswith("/tokeninfo"):
            assert kwargs["params"]["access_token"] == "fake-token-without-scope"
            return FakeResponse({"scope":"openid email profile"})
        pytest.fail("Unexpected external request")
    monkeypatch.setattr(web.requests, "get", fake_get)
    with app.test_client() as client:
        denied = client.get("/auth/callback")
        assert denied.status_code == 302
        assert denied.headers["Location"].endswith("/auth/youtube-permission")
    assert len(requested) == 2
    with app.app_context():
        assert OAuthAccount.query.count() == 0
        assert FunctionalTestRun.query.count() == 0


def test_historical_user_refusals_remain_auditable_but_do_not_reduce_kpi(configured_app):
    from models import db, FunctionalTestRun
    from services.google_permissions import historical_oauth_denial_clause
    from bs4 import BeautifulSoup
    app, keys, _web = configured_app
    with app.app_context():
        rows = [
            FunctionalTestRun(case_code="AUTH_LOGIN", case_name="Đăng nhập Google",
                passed=False, owner_id=keys["teacher"], source="automatic",
                note="Nguyên nhân: Người đăng nhập đã hủy hoặc chưa đồng ý cấp quyền cho ứng dụng."),
            FunctionalTestRun(case_code="AUTH_LOGIN", case_name="Đăng nhập Google",
                passed=False, owner_id=keys["teacher"], source="automatic",
                note="Nguyên nhân: Người đăng nhập đã hủy hoặc chưa đồng ý cấp quyền cho ứng dụng."),
            FunctionalTestRun(case_code="AUTH_LOGIN", case_name="Đăng nhập Google",
                passed=True, owner_id=keys["teacher"], source="automatic", note="Đủ quyền."),
            FunctionalTestRun(case_code="YT_SYNC", case_name="Đồng bộ YouTube",
                passed=False, owner_id=keys["teacher"], source="automatic", note="Lỗi mạng thực."),
        ]
        db.session.add_all(rows);db.session.commit()
        assert FunctionalTestRun.query.count() == 4  # Lịch sử KHÔNG bị sửa/xóa.
        assert FunctionalTestRun.query.filter(~historical_oauth_denial_clause(FunctionalTestRun)).count() == 2
    with app.test_client() as client:
        with client.session_transaction() as sess: sess["user_id"] = keys["teacher"]
        page = client.get("/analytics?sys_period=all")
        assert page.status_code == 200
        soup = BeautifulSoup(page.data, "html.parser")
        metrics = [x.get_text(" ", strip=True) for x in
                   soup.select("#hoat-dong-he-thong .display-6")[:4]]
        assert metrics == ["2", "1", "1", "50.0%"]


def test_sync_permission_failure_is_not_failed_functional_test(configured_app, monkeypatch):
    """Quyền chưa cấp không làm sai lệch KPI; lỗi cấu hình thật vẫn là Không đạt."""
    from models import db, YouTubeSyncJob, FunctionalTestRun
    app, keys, web = configured_app
    with app.app_context():
        db.session.add(YouTubeSyncJob(user_id=keys["teacher"], status="running",
                                      payload_json='{"accounts":[],"tasks":[]}'))
        db.session.commit()

    sync_state = {"status": "done", "failures": 1, "failure_codes": ["permission"],
                  "failure_reasons": ["YouTube chưa cho phép truy cập dữ liệu kênh."],
                  "videos_found": 0}
    monkeypatch.setattr(web, "step_incremental_sync", lambda user: dict(sync_state))
    with app.test_client() as client:
        with client.session_transaction() as sess: sess["user_id"] = keys["teacher"]
        denied = client.post("/youtube/sync/step")
        assert denied.status_code == 200
        assert denied.json["authorization_required"] is True
        with app.app_context():
            assert FunctionalTestRun.query.filter_by(case_code="YT_SYNC", passed=False).count() == 0
        # Trường hợp không phải do cấp quyền vẫn ghi nhận Không đạt.
        sync_state = dict(sync_state, failure_codes=["configuration"])
        technical = client.post("/youtube/sync/step")
        assert technical.status_code == 200
        assert not technical.json.get("authorization_required")
        with app.app_context():
            assert FunctionalTestRun.query.filter_by(case_code="YT_SYNC", passed=False).count() == 1


def test_permission_only_classification_is_conservative():
    from services.google_permissions import only_permission_failures
    assert only_permission_failures(1, ["permission"])
    assert only_permission_failures(2, ["permission", "auth_expired"])
    assert not only_permission_failures(0, [])
    assert not only_permission_failures(1, [])
    assert not only_permission_failures(2, ["permission"])
    assert not only_permission_failures(2, ["permission", "configuration"])
    assert not only_permission_failures(1, ["temporary"])
    assert not only_permission_failures(1, ["error"])


def test_historical_sync_permission_excluded_only_with_clear_evidence(configured_app):
    from models import db, FunctionalTestRun
    from services.google_permissions import historical_oauth_denial_clause
    app, keys, _web = configured_app
    with app.app_context():
        rows = [
            FunctionalTestRun(case_code="YT_SYNC", case_name="Đồng bộ video YouTube",
                passed=False, owner_id=keys["teacher"], source="automatic",
                note="Video đã xác minh: 0; phần lỗi: 1. Nguyên nhân: GV: YouTube chưa cho phép truy cập dữ liệu kênh của tài khoản này (lỗi quyền truy cập)."),
            FunctionalTestRun(case_code="YT_SYNC", case_name="Đồng bộ video YouTube",
                passed=False, owner_id=keys["teacher"], source="automatic",
                note="Video đã xác minh: 0; phần lỗi: 2. Nguyên nhân: YouTube chưa cho phép truy cập dữ liệu kênh; lỗi cấu hình API."),
            FunctionalTestRun(case_code="YT_SYNC", case_name="Đồng bộ video YouTube",
                passed=False, owner_id=keys["teacher"], source="automatic",
                note="Video đã xác minh: 0; phần lỗi: 1. Nguyên nhân: Dịch vụ YouTube Data API chưa sẵn sàng."),
        ]
        db.session.add_all(rows);db.session.commit()
        assert FunctionalTestRun.query.count() == 3
        excluded = FunctionalTestRun.query.filter(historical_oauth_denial_clause(FunctionalTestRun)).all()
        assert len(excluded) == 1
        assert "phần lỗi: 1" in excluded[0].note
        assert FunctionalTestRun.query.count() == 3  # Lịch sử gốc vẫn còn.
