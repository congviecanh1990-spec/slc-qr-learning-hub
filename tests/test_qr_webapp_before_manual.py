"""Web App tạo lượt đo trước; quản trị viên bổ sung đối chứng sau, không mất số đo."""
import json

from test_video_selection_across_pages import configured_app


def test_webapp_first_then_admin_manual_pairing(configured_app):
    from models import db, User, QrCode, ResearchComparisonPair
    from research_comparison import pair_metrics
    app, ids, web = configured_app
    with app.app_context():
        admin=User(email="auto-research-admin@test.local",role="admin",
                   name="Quản trị nghiệm thu",profile_completed=True)
        db.session.add(admin);db.session.commit()
        admin_id=admin.id

    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["user_id"] = ids["teacher"]
        start=client.post("/research/auto/start",data={
            "course_id":ids["course"],"task_kind":"QR_TUNG_VIDEO_PLAYLIST"})
        assert start.status_code == 200, start.get_data(as_text=True)
        assert start.json["active"] is True
        pair_id=start.json["id"]
        with app.app_context():
            p=db.session.get(ResearchComparisonPair,pair_id)
            assert p.auto_discovered is True
            assert p.manual_operations == 0 and p.manual_seconds == 0
            assert p.qr_count == 0

        new_qr=client.post(f'/videos/{ids["video_ids"][0]}/qr',
            data={"course_id":ids["course"]})
        assert new_qr.status_code == 302
        with app.app_context():
            pair=db.session.get(ResearchComparisonPair,pair_id)
            assert pair.qr_count == 1 and pair.video_count == 1
            assert pair.playlist_count == 0
            qr_id=json.loads(pair.measurement_qr_ids)[0]
            before_count=ResearchComparisonPair.query.count()

        done=client.post("/research/auto/download-saved", data={
            "download_style":"row","qr_ids":json.dumps([qr_id]),
            "save_method":"directory_picker","operations_count":"7"})
        assert done.status_code == 200, done.get_data(as_text=True)
        assert done.json["completed"] is True
        assert done.json["verified"] is True
        assert done.json["kind"] == "QR_TUNG_VIDEO_PLAYLIST"
        with app.app_context():
            pair=db.session.get(ResearchComparisonPair,pair_id)
            assert pair.webapp_seconds > 0 and pair.webapp_operations == 7
            assert pair.is_paired is False
            seconds=pair.webapp_seconds
            metrics=pair_metrics([pair])
            assert metrics[0][0]["web_count"] == 1
            assert metrics[0][0]["n"] == 0
            assert metrics[0][0]["time_reduction"] is None
            assert metrics[1]["pending_manual"] == 1

        with client.session_transaction() as sess:
            sess["user_id"] = admin_id
        report=client.get("/research")
        assert report.status_code == 200
        html=report.get_data(as_text=True)
        assert "Chờ nhập thủ công" in html
        assert "Lượt Web App đã xác minh:" in html
        assert "7" in html

        manual=client.post("/research",data={
            "form_type":"pair_create","existing_pair_id":str(pair_id),
            "lecturer_id":str(ids["teacher"]),"course_id":str(ids["course"]),
            "task_kind":"QR_TUNG_VIDEO_PLAYLIST",
            "video_count":"1","playlist_count":"0","playlist_video_count":"0",
            "manual_operations":"21","manual_seconds":"85.5",
            "note":"Đo thủ công sau Web App"},follow_redirects=True)
        assert manual.status_code == 200
        assert "Đã bổ sung số đo thủ công" in manual.get_data(as_text=True)
        with app.app_context():
            assert ResearchComparisonPair.query.count() == before_count
            pair=db.session.get(ResearchComparisonPair,pair_id)
            assert pair.manual_operations == 21
            assert pair.manual_seconds == 85.5
            assert pair.webapp_seconds == seconds
            assert pair.webapp_operations == 7
            assert pair.is_paired is True
            gs,totals=pair_metrics([pair])
            assert gs[0]["n"]==1
            assert totals["paired_count"]==1
            assert totals["pending_manual"]==0

        duplicate=client.post("/research",data={
            "form_type":"pair_create","existing_pair_id":str(pair_id),
            "lecturer_id":str(ids["teacher"]),"course_id":str(ids["course"]),
            "task_kind":"QR_TUNG_VIDEO_PLAYLIST",
            "video_count":"1","playlist_count":"0","playlist_video_count":"0",
            "manual_operations":"99","manual_seconds":"1"},follow_redirects=True)
        assert "không phù hợp" in duplicate.get_data(as_text=True)
        with app.app_context():
            assert db.session.get(ResearchComparisonPair,pair_id).manual_operations == 21


def test_webapp_bulk_first_then_manual_autofind_and_exact_count(configured_app):
    from models import db, User, ResearchComparisonPair
    app, ids, web=configured_app
    with app.app_context():
        admin=User(email="auto-research-admin2@test.local",
                   role="admin",name="Quản trị",profile_completed=True)
        db.session.add(admin);db.session.commit()
        admin_id=admin.id
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["user_id"] = ids["teacher"]
        start=client.post("/research/auto/start",data={
            "course_id":ids["course"],"task_kind":"QR_VIDEO_HANG_LOAT",
            "selected_count":"2"})
        assert start.json["active"] is True
        for video_id in ids["video_ids"][:2]:
            assert client.post(f"/videos/{video_id}/qr",
                data={"course_id":ids["course"]}).status_code == 302
        with app.app_context():
            pair=db.session.get(ResearchComparisonPair,start.json["id"])
            assert (pair.video_count,pair.playlist_count,pair.qr_count)==(2,0,2)
            qr_ids=json.loads(pair.measurement_qr_ids)
        finish=client.post("/research/auto/download-saved",data={
            "download_style":"bulk","qr_ids":json.dumps(qr_ids),
            "save_method":"directory_picker","operations_count":"14"})
        assert finish.json["completed"] is True
        assert finish.json["kind"]=="QR_VIDEO_HANG_LOAT"
        with client.session_transaction() as sess:
            sess["user_id"] = admin_id
        result=client.post("/research",data={
            "form_type":"pair_create",
            "lecturer_id":str(ids["teacher"]),"course_id":str(ids["course"]),
            "task_kind":"QR_VIDEO_HANG_LOAT","video_count":"2",
            "playlist_count":"0","playlist_video_count":"0",
            "manual_operations":"40","manual_seconds":"250"},follow_redirects=True)
        assert "Đã bổ sung số đo thủ công" in result.get_data(as_text=True)
        with app.app_context():
            pair=db.session.get(ResearchComparisonPair,start.json["id"])
            assert pair.manual_seconds == 250
            assert pair.webapp_operations == 14
            assert ResearchComparisonPair.query.count() == 1


def test_admin_lecturer_qr_create_immediately_appears_in_acceptance(configured_app):
    """Lỗi báo thực tế: admin kiêm giảng viên tạo QR mà bảng nghiệm thu trống."""
    from models import db, User, ResearchComparisonPair
    app, ids, _web = configured_app
    with app.app_context():
        teacher = db.session.get(User, ids["teacher"])
        teacher.role = "admin"
        db.session.commit()
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["user_id"] = ids["teacher"]

        library = client.get("/videos")
        assert library.status_code == 200
        assert "window.researchMeasurement =" in library.get_data(as_text=True)
        assert "research_measurement.js" in library.get_data(as_text=True)

        started = client.post("/research/auto/start", data={
            "course_id": ids["course"], "task_kind": "QR_TUNG_VIDEO_PLAYLIST"})
        assert started.status_code == 200
        assert started.json["active"] is True
        measurement_id = started.json["id"]

        created = client.post(f'/videos/{ids["video_ids"][0]}/qr',
                              data={"course_id": str(ids["course"])})
        assert created.status_code == 302

        with app.app_context():
            pair = db.session.get(ResearchComparisonPair, measurement_id)
            assert pair.qr_count == 1
            assert pair.video_count == 1
            assert pair.measurement_start_source == "ui_preflight"
            assert pair.webapp_seconds is None

        report = client.get("/research")
        assert report.status_code == 200
        html = report.get_data(as_text=True)
        assert "1 lượt Web App đang thực hiện" in html
        assert "Đã ghi nhận tạo QR; chờ tải và lưu tệp" in html
        assert "Đang chạy – chưa chốt" in html
        assert "Tin học ứng dụng" in html

        with app.app_context():
            pair = db.session.get(ResearchComparisonPair, measurement_id)
            qr_ids = json.loads(pair.measurement_qr_ids)
        saved = client.post("/research/auto/download-saved", data={
            "download_style": "row", "qr_ids": json.dumps(qr_ids),
            "save_method": "directory_picker", "operations_count": "6"})
        assert saved.status_code == 200
        assert saved.json["completed"] is True
        assert saved.json["verified"] is True

        report = client.get("/research")
        assert report.status_code == 200
        assert "Lượt Web App đã xác minh:" in report.get_data(as_text=True)
        with app.app_context():
            pair = db.session.get(ResearchComparisonPair, measurement_id)
            assert pair.webapp_operations == 6
            assert pair.manual_operations == 0


def test_backend_qr_creation_survives_missing_javascript_start(configured_app):
    """POST tạo QR không có preflight vẫn phải lưu một dòng để người dùng thấy."""
    from models import db, User, ResearchComparisonPair
    app, ids, _web = configured_app
    with app.app_context():
        lecturer = db.session.get(User, ids["teacher"])
        lecturer.role = "admin"
        db.session.commit()
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["user_id"] = ids["teacher"]
            assert "research_measurement_id" not in sess
        created = client.post(f'/videos/{ids["video_ids"][0]}/qr',
                              data={"course_id": str(ids["course"])})
        assert created.status_code == 302

        with app.app_context():
            rows = ResearchComparisonPair.query.all()
            assert len(rows) == 1
            pair = rows[0]
            assert pair.qr_count == 1
            assert pair.measurement_start_source == "server_fallback"
            qr_id = json.loads(pair.measurement_qr_ids)[0]

        report = client.get("/research")
        assert report.status_code == 200
        assert "Đã ghi nhận tạo QR; chờ tải và lưu tệp" in report.get_data(as_text=True)
        assert "Mốc bắt đầu dự phòng; cần đo lại từ đầu để tính KPI" in report.get_data(as_text=True)

        saved = client.post("/research/auto/download-saved", data={
            "download_style": "row", "qr_ids": json.dumps([qr_id]),
            "save_method": "directory_picker", "operations_count": "2"})
        assert saved.status_code == 200
        assert saved.json["completed"] is True
        assert saved.json["verified"] is False
        with app.app_context():
            pair = ResearchComparisonPair.query.one()
            assert pair.webapp_seconds is not None
            assert pair.measurement_verified is False
