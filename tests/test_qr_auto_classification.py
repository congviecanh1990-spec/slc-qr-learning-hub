"""Đo lường QR phân loại theo thao tác TẢI, không dựa vào tích chọn hoặc nút TẠO."""
import json
from datetime import timedelta

from test_video_selection_across_pages import configured_app


def prepare_pairs(app, keys, kind, *, video_count, playlist_count):
    from models import db, User, QrCode, ResearchComparisonPair, utcnow
    with app.app_context():
        teacher = db.session.get(User, keys["teacher"])
        qrs = []
        for index in range(video_count + playlist_count):
            is_playlist = index >= video_count
            qr = QrCode(owner_id=teacher.id, course_id=keys["course"],
                        title=f"Mã QR đối chứng {index}",
                        slug=f"classification-test-{kind}-{index}",
                        target_type="playlist" if is_playlist else "video")
            db.session.add(qr)
            db.session.flush()
            qrs.append(qr.id)
        pair = ResearchComparisonPair(
            pair_code="CLASS-" + kind[:4] + str(qrs[0]),
            lecturer_id=teacher.id, course_id=keys["course"],
            lecturer_name_snapshot=teacher.name or "", course_name_snapshot="Học phần",
            task_kind=kind, video_count=video_count, playlist_count=playlist_count,
            playlist_video_count=playlist_count * 3,
            qr_count=len(qrs), manual_operations=20, manual_seconds=60,
            measurement_started_at=utcnow() - timedelta(seconds=8),
            measurement_operations=3, measurement_single_videos=video_count,
            measurement_single_playlists=playlist_count,
            measurement_qr_ids=json.dumps(qrs),
            measurement_saved_qr_ids="[]",
            measurement_verified=False,
        )
        db.session.add(pair)
        db.session.commit()
        return pair.id, qrs


def test_two_selected_video_qrs_are_individual_when_downloaded_by_row(configured_app):
    from models import db, ResearchComparisonPair
    app, keys, _ = configured_app
    bulk_id, qrs = prepare_pairs(app, keys, "QR_VIDEO_HANG_LOAT",
                                  video_count=2, playlist_count=0)
    with app.app_context():
        p = db.session.get(ResearchComparisonPair, bulk_id)
        individual = ResearchComparisonPair(
            pair_code="CLASS-SINGLE", lecturer_id=keys["teacher"],
            course_id=keys["course"], lecturer_name_snapshot="GV",
            course_name_snapshot="Học phần", task_kind="QR_TUNG_VIDEO_PLAYLIST",
            video_count=2, playlist_count=0, playlist_video_count=0,
            qr_count=2, manual_operations=24, manual_seconds=70)
        db.session.add(individual)
        db.session.commit()
        single_id = individual.id
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["user_id"] = keys["teacher"]
            sess["research_measurement_id"] = bulk_id
            sess["research_measurement_nonce"] = "testnonce"

        for index, qid in enumerate(qrs):
            result = client.post("/research/auto/download-saved", data={
                "download_style": "row", "qr_ids": json.dumps([qid]),
                "save_method": "directory_picker", "operations_count": 7 + index})
            assert result.status_code == 200
            data = result.json
            assert data["kind"] == "QR_TUNG_VIDEO_PLAYLIST"
            assert data["measured"] is True
            assert data["completed"] is (index == 1)
        with app.app_context():
            bulk = db.session.get(ResearchComparisonPair, bulk_id)
            single = db.session.get(ResearchComparisonPair, single_id)
            assert bulk.measurement_started_at is None
            assert bulk.measurement_qr_ids == "[]"
            assert single.measurement_download_style == "row"
            assert json.loads(single.measurement_saved_qr_ids) == qrs
            assert single.measurement_verified is True
            assert single.webapp_seconds >= 1


def test_two_playlist_qrs_download_all_count_as_bulk(configured_app):
    from models import db, ResearchComparisonPair
    app, keys, _ = configured_app
    pair_id, qrs = prepare_pairs(app, keys, "QR_VIDEO_HANG_LOAT",
                                 video_count=0, playlist_count=2)
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["user_id"] = keys["teacher"]
            sess["research_measurement_id"] = pair_id
            sess["research_measurement_nonce"] = "testnonce"
        result = client.post("/research/auto/download-saved", data={
            "download_style": "bulk", "qr_ids": json.dumps(qrs),
            "save_method": "directory_picker", "operations_count": 9})
        assert result.status_code == 200
        assert result.json["kind"] == "QR_VIDEO_HANG_LOAT"
        assert result.json["completed"] is True
        assert result.json["verified"] is True
    with app.app_context():
        pair = db.session.get(ResearchComparisonPair, pair_id)
        assert pair.measurement_download_style == "bulk"
        assert pair.measurement_verified is True


def test_zip_without_verified_save_not_accepted_and_outside_qr_rejected(configured_app):
    from models import db, ResearchComparisonPair
    app, keys, _ = configured_app
    pid, qrs = prepare_pairs(app, keys, "QR_VIDEO_HANG_LOAT",
                             video_count=2, playlist_count=0)
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["user_id"] = keys["teacher"]
            sess["research_measurement_id"] = pid
        pending = client.post("/research/auto/download-saved", data={
            "download_style": "bulk", "qr_ids": json.dumps(qrs),
            "save_method": "not_verified", "operations_count": 3})
        assert pending.status_code == 200
        assert pending.json["measured"] is False
        invalid = client.post("/research/auto/download-saved", data={
            "download_style": "bulk", "qr_ids": json.dumps([qrs[0], qrs[1] + 3000]),
            "save_method": "directory_picker", "operations_count": 4})
        assert invalid.status_code == 200 and not invalid.json["measured"]
    with app.app_context():
        pair = db.session.get(ResearchComparisonPair, pid)
        assert pair.webapp_seconds is None
        assert pair.measurement_verified is False


def test_research_library_mode_controls_gone_but_download_buttons_remain(configured_app):
    from bs4 import BeautifulSoup
    app, keys, _ = configured_app
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["user_id"] = keys["teacher"]
        response = client.get("/videos")
        assert response.status_code == 200
        soup = BeautifulSoup(response.data,"html.parser")
        assert soup.select_one("#thuc-nghiem-qr") is None
        assert not soup.select('[name="qrWorkMode"]')
        assert soup.select_one("#playlistBulkDownloadQr") is not None
        assert soup.select_one('#assignVideoForm button[formaction*="download-selected"]') is not None


def test_playlist_bulk_download_returns_only_selected_qrs_not_entire_course(configured_app):
    """Tải tất cả từ Kho playlist KHÔNG được lẫn QR của playlist bỏ chọn."""
    import io
    import zipfile
    from models import db, User, Playlist, YouTubeChannel, CoursePlaylist, QrCode
    app, keys, _web = configured_app
    with app.app_context():
        teacher = db.session.get(User, keys["teacher"])
        channel = YouTubeChannel.query.filter_by(user_id=teacher.id).first()
        playlist_ids = [keys["playlist"]]
        for index in range(2):
            playlist = Playlist(channel_id=channel.id,
                youtube_playlist_id=f"TEST-BULK-PLAYLIST-{index}",
                title=f"Playlist hàng loạt {index}")
            db.session.add(playlist)
            db.session.flush()
            playlist_ids.append(playlist.id)
        qr_ids = []
        for index, playlist_id in enumerate(playlist_ids):
            qr = QrCode(owner_id=teacher.id, course_id=keys["course"],
                playlist_id=playlist_id, target_type="playlist",
                slug=f"test-selected-playlist-{index}",title=f"QR playlist {index}")
            db.session.add(qr)
            db.session.flush()
            qr_ids.append(qr.id)
            db.session.add(CoursePlaylist(course_id=keys["course"],
                playlist_id=playlist_id, qr_id=qr.id, active=True))
        db.session.commit()
    data={
        "course_id":str(keys["course"]),
        "playlist_selection_mode":"none",
        "selected_playlist_ids":[str(x) for x in playlist_ids[:2]],
    }
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["user_id"] = keys["teacher"]
        json_response = client.post("/playlists/qr/download-selected",
            data=data,headers={"Accept":"application/json"})
        assert json_response.status_code == 200
        assert {row["id"] for row in json_response.json["files"]} == set(qr_ids[:2])
        assert len(json_response.json["files"]) == 2
        zip_response = client.post("/playlists/qr/download-selected",data=data)
        assert zip_response.status_code == 200
        assert zip_response.mimetype == "application/zip"
        with zipfile.ZipFile(io.BytesIO(zip_response.data)) as archive:
            files = archive.namelist()
            assert len(files) == 2
            assert all(name.endswith(".png") for name in files)
            assert all(archive.read(name).startswith(bytes([137,80,78,71,13,10,26,10]))
                for name in files)
        excluded = client.post("/playlists/qr/download-selected",
            data={"course_id":keys["course"],"playlist_selection_mode":"all",
                  "excluded_playlist_ids":[str(playlist_ids[1])]},
            headers={"Accept":"application/json"})
        assert excluded.status_code == 200
        assert {row["id"] for row in excluded.json["files"]} == {qr_ids[0],qr_ids[2]}


def test_zip_mixed_old_qrs_manual_confirmation_finishes_only_new_qrs(configured_app):
    """ZIP tải nhiều môn có QR cũ: không mắc kẹt ở trạng thái tạm tính."""
    from models import db, User, Course, QrCode, ResearchComparisonPair
    from research_comparison import pair_metrics
    app, keys, _ = configured_app
    pid, created = prepare_pairs(
        app, keys, "QR_VIDEO_HANG_LOAT", video_count=2, playlist_count=0)
    with app.app_context():
        teacher = db.session.get(User, keys["teacher"])
        other_course = Course(name="Toán rời rạc", code="EXTRA-DOWNLOAD",
                              owner_id=teacher.id)
        db.session.add(other_course)
        db.session.flush()
        old_qr = QrCode(owner_id=teacher.id, course_id=other_course.id,
                        title="QR có sẵn môn khác", slug="old-other-course-qr",
                        target_type="video")
        db.session.add(old_qr); db.session.commit()
        all_ids = [*created, old_qr.id]
    with app.test_client() as client:
        with client.session_transaction() as ss:
            ss["user_id"] = keys["teacher"]
            ss["research_measurement_id"] = pid
        pending = client.post("/research/auto/download-saved", data={
            "download_style": "bulk", "qr_ids": json.dumps(all_ids),
            "save_method": "not_verified", "operations_count": "7"})
        assert pending.status_code == 200
        assert pending.json["matched"] == 2
        assert pending.json["downloaded"] == 3
        assert pending.json["measured"] is False
        with app.app_context():
            p = db.session.get(ResearchComparisonPair, pid)
            assert p.measurement_finished_at is None
            assert p.measurement_operations == 7
            assert p.measurement_download_style == "bulk"
            assert p.measurement_verified is False

        confirmed = client.post("/research/auto/download-saved", data={
            "download_style": "bulk", "qr_ids": json.dumps(all_ids),
            "save_method": "manual_confirmed", "user_confirmed": "yes",
            "operations_count": "9"})
        assert confirmed.status_code == 200
        assert confirmed.json["measured"] is True
        assert confirmed.json["completed"] is True
        assert confirmed.json["verified"] is False
        assert confirmed.json["saved"] == 2
        assert confirmed.json["expected"] == 2
        with app.app_context():
            p = db.session.get(ResearchComparisonPair, pid)
            assert json.loads(p.measurement_saved_qr_ids) == created
            assert p.webapp_operations == 9 and p.webapp_seconds > 0
            assert p.measurement_finished_at is not None
            assert p.measurement_save_method == "manual_confirmed"
            assert not p.measurement_verified
            assert pair_metrics([p])[1]["web_count"] == 0
            teacher = db.session.get(User, keys["teacher"])
            teacher.role = "admin"
            db.session.commit()
        report = client.get("/research")
        assert report.status_code == 200
        content = report.get_data(as_text=True)
        assert "Đã chốt theo xác nhận giảng viên" in content
        assert "chưa xác minh độc lập" in content
        assert "1 lượt" in content
        assert "Tạm tính – đang đo" not in content


def test_qr_download_measurement_reopens_only_unique_owned_pending_pair(configured_app):
    """Phiên tạo QR bị mất khỏi session vẫn được nối lại nếu khớp duy nhất."""
    from models import db, ResearchComparisonPair, User, QrCode
    app, keys, _ = configured_app
    pid, created = prepare_pairs(
        app, keys, "QR_TUNG_VIDEO_PLAYLIST", video_count=1, playlist_count=0)
    with app.test_client() as client:
        with client.session_transaction() as ss: ss["user_id"] = keys["teacher"]
        restored = client.post("/research/auto/download-saved", data={
            "download_style": "row", "qr_ids": json.dumps(created),
            "save_method": "not_verified", "operations_count": "2"})
        assert restored.status_code == 200
        assert restored.json["matched"] == 1
        with client.session_transaction() as ss:
            assert ss["research_measurement_id"] == pid
        saved = client.post("/research/auto/download-saved", data={
            "download_style": "row", "qr_ids": json.dumps(created),
            "save_method": "manual_confirmed", "user_confirmed": "yes",
            "operations_count": "3"})
        assert saved.json["completed"] is True
        assert saved.json["verified"] is False
        with app.app_context():
            assert db.session.get(ResearchComparisonPair, pid).webapp_operations == 3


def test_browser_download_requires_explicit_save_confirmation():
    """Không tự khẳng định đã lưu khi Chrome chỉ bắt đầu tải tệp."""
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    script = (root / "static/research_measurement.js").read_text(encoding="utf-8")
    assert "Tôi đã lưu đủ tệp QR" in script
    assert "manual_confirmed',true" in script
    assert "await recordDownload(style,ids,'not_verified')" in script
    assert "queuePending(style,ids)" in script
    assert "sessionStorage.setItem(pendingKey" in script
    assert "measurement_verified" not in script
    report = (root / "templates/research.html").read_text(encoding="utf-8")
    assert "Đã ghi nhận tải QR; chờ giảng viên xác nhận đã lưu tệp" in report
