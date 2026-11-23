"""Hồi quy đo QR theo hai nhiệm vụ, phân quyền và ghi thời gian/thao tác tự động."""
import ast
import os
from pathlib import Path
from types import SimpleNamespace
import pytest
from jinja2 import Environment, FileSystemLoader
from research_comparison import validate_pair_form, pair_metrics, video_coverage

ROOT=Path(__file__).resolve().parents[1]
VIDEO=dict(lecturer_id="1",course_id="2",task_kind="QR_TUNG_VIDEO_PLAYLIST",
           video_count="15",playlist_count="0",playlist_video_count="0",
           manual_operations="65",manual_seconds="450.5")
MIXED=dict(VIDEO,video_count="3",playlist_count="5",playlist_video_count="50")
BULK=dict(VIDEO,task_kind="QR_VIDEO_HANG_LOAT",video_count="15")


def test_exactly_two_kinds_and_count_per_video():
    assert validate_pair_form(VIDEO)["qr_count"]==15
    mixed=validate_pair_form(MIXED)
    assert mixed["qr_count"]==8 and mixed["playlist_video_count"]==50
    assert mixed["video_count"]+mixed["playlist_video_count"]==53
    assert validate_pair_form(BULK)["qr_count"]==15
    assert "pair_code" not in mixed and "webapp_seconds" not in mixed
    for bad in (dict(MIXED,playlist_video_count="4"),
                dict(MIXED,video_count="0",playlist_count="0",playlist_video_count="0"),
                dict(BULK,playlist_count="5",playlist_video_count="50"),
                dict(VIDEO,task_kind="QR_PLAYLIST"),
                dict(VIDEO,manual_seconds="nan")):
        with pytest.raises(ValueError):validate_pair_form(bad)


def test_group_uses_video_coverage_and_verified_only():
    def row(kind,v,pl,plv,mt,wt,mo,wo,verified=True,active=True):
        return SimpleNamespace(task_kind=kind,video_count=v,playlist_count=pl,
          playlist_video_count=plv,qr_count=v+pl,manual_seconds=mt,
          webapp_seconds=wt,manual_operations=mo,webapp_operations=wo,
          active=active,measurement_verified=verified)
    rows=[row("QR_TUNG_VIDEO_PLAYLIST",3,5,50,530,53,100,15),
          row("QR_VIDEO_HANG_LOAT",15,0,0,150,30,60,10),
          row("QR_VIDEO_RIENG",5,0,0,50,5,10,2,False),
          row("QR_VIDEO_HANG_LOAT",8,0,0,88,44,30,30,active=False)]
    assert video_coverage(rows[0])==53
    groups,tot=pair_metrics(rows)
    a={g["key"]:g for g in groups}
    assert len(groups)==2
    assert a["QR_TUNG_VIDEO_PLAYLIST"]["video_coverage"]==53
    assert a["QR_TUNG_VIDEO_PLAYLIST"]["manual_per_video"]==10.0
    assert a["QR_TUNG_VIDEO_PLAYLIST"]["app_per_video"]==1.0
    assert a["QR_TUNG_VIDEO_PLAYLIST"]["qr_count"]==8
    assert a["QR_VIDEO_HANG_LOAT"]["manual_per_video"]==10.0
    assert tot["paired_count"]==2 and tot["video_coverage"]==68
    blank,total=pair_metrics(rows[2:])
    assert blank==[] and total["time_reduction"] is None


def test_code_jinja_and_admin_only_data_form():
    ast.parse((ROOT/"app.py").read_text(encoding="utf-8"))
    ast.parse((ROOT/"models.py").read_text(encoding="utf-8"))
    env=Environment(loader=FileSystemLoader(str(ROOT/"templates")))
    for path in (ROOT/"templates").glob("*.html"):
        env.parse(path.read_text(encoding="utf-8"))
    research=(ROOT/"templates/research.html").read_text(encoding="utf-8")
    lecturer=(ROOT/"templates/research_measurement.html").read_text(encoding="utf-8")
    app=(ROOT/"app.py").read_text(encoding="utf-8")
    assert "pair_create" in research
    assert 'name="pair_code"' not in research
    assert 'name="webapp_seconds"' not in research
    assert 'name="webapp_operations"' not in research
    assert "Ví dụ: 15 QR video lẻ" not in research
    assert "manual_seconds" not in lecturer and "manual_operations" not in lecturer
    assert 'research_measurement_start' in lecturer and 'research_measurement_finish' in lecturer
    assert 'record_research_qr_creation(course.id, user.id, "video")' in app
    assert 'record_research_qr_creation(course.id, user.id, "playlist")' in app
    assert "ensure_research_comparison_schema" in app


def test_db_preserves_old_experiment_and_unverified_measurement():
    from flask import Flask
    from models import db, User, Course, ResearchComparisonPair, ExperimentRun
    app=Flask("unit")
    app.config["SQLALCHEMY_DATABASE_URI"]="sqlite://"
    db.init_app(app)
    with app.app_context():
        db.create_all()
        teacher=User(name="GV",email="gv@local.test",role="lecturer")
        db.session.add(teacher);db.session.flush()
        course=Course(owner_id=teacher.id,name="Môn học",code="H01")
        db.session.add(course);db.session.flush()
        data=validate_pair_form(VIDEO)
        data.update(lecturer_id=teacher.id,course_id=course.id)
        db.session.add(ResearchComparisonPair(
            **data,pair_code="AUTO-ONE",observer_id=teacher.id,
            lecturer_name_snapshot="GV",course_name_snapshot="Môn học"))
        db.session.add(ExperimentRun(owner_id=teacher.id,task_key="TAO_QR_RIENG",
            mode="webapp",operations_count=1,elapsed_seconds=.1,success=True))
        db.session.commit()
        assert ResearchComparisonPair.query.count()==1
        assert ExperimentRun.query.count()==1
        g,total=pair_metrics(ResearchComparisonPair.query.all())
        assert g==[] and total["paired_count"]==0


def test_flask_role_workflow_and_legacy_schema(tmp_path,monkeypatch):
    """Kiểm cả SQLite và Postgres tạm ở CI; KHÔNG truy cập Neon thật."""
    db_url=os.environ.get("TEST_POSTGRES_DATABASE_URL") or ("sqlite:///"+str(tmp_path/"research.sqlite"))
    monkeypatch.setenv("DATABASE_URL",db_url)
    monkeypatch.setenv("AUTO_CREATE_DB","0")
    monkeypatch.setenv("SECRET_KEY","test-only")
    monkeypatch.setenv("GOOGLE_CLIENT_ID","")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET","")
    import app as web
    from models import db, User, Course, ResearchComparisonPair
    app=web.create_app()
    app.config.update(TESTING=True,WTF_CSRF_ENABLED=False,SESSION_COOKIE_SECURE=False)
    with app.app_context():
        db.create_all()
        admin=User(name="Chủ nhiệm",email="admin@local.test",role="admin",profile_completed=True)
        teacher=User(name="GV thực nghiệm",email="teacher@local.test",role="lecturer",profile_completed=True)
        db.session.add_all([admin,teacher]);db.session.flush()
        course=Course(name="Tin học",code="HP1",owner_id=teacher.id)
        db.session.add(course);db.session.commit()
        aid,tid,cid=admin.id,teacher.id,course.id
        db.session.remove()
        # Giả lập db test tạo ở phiên bản cũ, có table nhưng thiếu cột đo.
        from sqlalchemy import text as sql_text
        with db.engine.begin() as conn:
            conn.execute(sql_text(
                "ALTER TABLE research_comparison_pairs DROP COLUMN measurement_verified"))
            conn.execute(sql_text(
                "ALTER TABLE research_comparison_pairs DROP COLUMN measurement_operations"))
        assert "measurement_verified" not in {
            col["name"] for col in web.inspect(db.engine).get_columns("research_comparison_pairs")}
    with app.test_client() as client:
        with client.session_transaction() as ss:ss["user_id"]=aid
        response=client.get("/research")
        assert response.status_code==200
        with app.app_context():
            cols={c["name"] for c in web.inspect(db.engine).get_columns("research_comparison_pairs")}
            assert {"measurement_verified","measurement_operations"}<=cols
            assert User.query.count()==2 and Course.query.count()==1
        form=dict(MIXED,form_type="pair_create",lecturer_id=str(tid),course_id=str(cid))
        res=client.post("/research",data=form)
        assert res.status_code==302
        with app.app_context():
            pair=ResearchComparisonPair.query.filter_by(lecturer_id=tid).one()
            pid=pair.id
            assert pair.pair_code.startswith("TN") and pair.qr_count==8
            assert pair.webapp_seconds is None
        # Giảng viên không được nhập biểu mẫu nghiên cứu (chỉ có quyền đo).
        with client.session_transaction() as ss:ss["user_id"]=tid
        res=client.get("/research")
        assert res.status_code==302
        res=client.post("/research",data=form)
        assert res.status_code==302
        assert client.get("/research/measurement").status_code==200
        res=client.post(f"/research/measurement/{pid}/start")
        assert res.status_code==302
        with app.app_context():
            pair=db.session.get(ResearchComparisonPair,pid)
            assert pair.measurement_started_at is not None
        # Không được kết thúc khi chưa tạo đủ QR / chưa có thao tác.
        res=client.post(f"/research/measurement/{pid}/finish",data={"operations_count":"8"})
        assert res.status_code==302
        with app.app_context():
            pair=db.session.get(ResearchComparisonPair,pid)
            assert not pair.is_paired and pair.webapp_seconds is None
        # Mô phỏng sự kiện QR thực sự tạo mới từ đúng các route đang instrument.
        with app.test_request_context("/videos/21/qr",method="POST"):
            from flask import session
            session["user_id"]=tid
            session["research_measurement_id"]=pid
            for _ in range(3):web.record_research_qr_creation(cid,tid,"video")
            db.session.commit()
        with app.test_request_context("/playlists/8/qr",method="POST"):
            from flask import session
            session["user_id"]=tid
            session["research_measurement_id"]=pid
            for _ in range(5):web.record_research_qr_creation(cid,tid,"playlist")
            db.session.commit()
        progress=client.post("/research/measurement/progress",data={"operations_count":"21"})
        assert progress.status_code==200
        res=client.post(f"/research/measurement/{pid}/finish",data={"operations_count":"23"})
        assert res.status_code==302
        with app.app_context():
            pair=db.session.get(ResearchComparisonPair,pid)
            assert pair.is_paired and pair.measurement_verified
            assert pair.webapp_seconds > 0 and pair.webapp_operations==23
            assert pair.measurement_single_videos==3 and pair.measurement_single_playlists==5
            assert video_coverage(pair)==53 and pair.qr_count==8
        # Không cho giảng viên sửa kết quả WebApp hoặc loại bản ghi.
        # Trang nghiên cứu cũ từ chối qua chuyển hướng, API mới từ chối qua 403.
        assert client.post(f"/research/comparison/{pid}/void",
            data={"void_reason":"test invalid"}).status_code in (302,403)
        assert client.post(f"/research/comparison/{pid}/reset",data={"reason":"test invalid"}).status_code==403
        with client.session_transaction() as ss:ss["user_id"]=aid
        res=client.get("/research")
        assert res.status_code==200
        assert "Đủ cặp đo".encode() in res.data
