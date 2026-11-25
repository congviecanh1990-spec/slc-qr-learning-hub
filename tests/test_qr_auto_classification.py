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
