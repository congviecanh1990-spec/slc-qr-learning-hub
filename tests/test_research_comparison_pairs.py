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
    library=(ROOT/"templates/videos.html").read_text(encoding="utf-8")
    app=(ROOT/"app.py").read_text(encoding="utf-8")
    assert "pair_create" in research
    assert 'name="pair_code"' not in research
    assert 'name="webapp_seconds"' not in research
    assert 'name="webapp_operations"' not in research
    assert "Ví dụ: 15 QR video lẻ" not in research
    assert "manual_seconds" not in library and "manual_operations" not in library
    assert 'id="thuc-nghiem-qr"' in library
    assert 'id="researchQrSaveDirectory"' in library
    assert 'id="videoBulkQrForm"' in library
    assert 'research_auto_start' in app and 'research_auto_complete' in app
    assert 'record_research_qr_creation(course.id, user.id, "video", qr.id)' in app
    assert 'record_research_qr_creation(course.id, user.id, "playlist", qr.id)' in app
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
    """Admin khai báo thủ công, GV tạo và lưu QR ở Kho, không còn trang đo riêng."""
    import json
    db_url=os.environ.get("TEST_POSTGRES_DATABASE_URL") or ("sqlite:///"+str(tmp_path/"research.sqlite"))
    monkeypatch.setenv("DATABASE_URL",db_url)
    monkeypatch.setenv("AUTO_CREATE_DB","0")
    monkeypatch.setenv("SECRET_KEY","test-only")
    monkeypatch.setenv("GOOGLE_CLIENT_ID","")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET","")
    import app as web
    from models import db, User, Course, QrCode, ResearchComparisonPair
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
        # DB Neon test cũ có bảng nhưng thiếu cột mới; không DROP dữ liệu.
        from sqlalchemy import text as sql_text
        with db.engine.begin() as conn:
            for field in ("measurement_qr_ids","measurement_saved_at","measurement_save_method"):
                conn.execute(sql_text(f"ALTER TABLE research_comparison_pairs DROP COLUMN {field}"))
    with app.test_client() as client:
        with client.session_transaction() as ss:ss["user_id"]=aid
        assert client.get("/research").status_code==200
        with app.app_context():
            cols={x["name"] for x in web.inspect(db.engine).get_columns("research_comparison_pairs")}
            assert {"measurement_qr_ids","measurement_saved_at","measurement_save_method"}<=cols
            assert User.query.count()==2 and Course.query.count()==1
        form=dict(MIXED,form_type="pair_create",lecturer_id=str(tid),course_id=str(cid))
        assert client.post("/research",data=form).status_code==302
        with app.app_context():
            pair=ResearchComparisonPair.query.filter_by(lecturer_id=tid).one()
            pid=pair.id
            assert pair.pair_code.startswith("TN") and pair.qr_count==8
            assert pair.webapp_seconds is None
        with client.session_transaction() as ss:ss["user_id"]=tid
        assert client.get("/research").status_code==302
        assert client.post("/research",data=form).status_code==302
        assert client.get("/research/measurement").status_code==302  # không có trang riêng
        before=client.get("/research/auto/files")
        assert before.status_code in (403,409)
        started=client.post("/research/auto/start",data={
            "course_id":cid,"task_kind":"QR_TUNG_VIDEO_PLAYLIST"})
        assert started.status_code==200 and started.json["active"]
        assert started.json["created"]==0 and started.json["expected"]==8
        assert client.get("/research/auto/files").status_code==409
        # Tạo 8 bản ghi QR mới, mô phỏng đúng hai đường dẫn đơn lẻ trong Kho.
        with app.app_context():
            ids=[]
            for n in range(8):
                qr=QrCode(owner_id=tid,course_id=cid,slug=f"testqr{n}",
                    title=f"Video YouTube hoặc playlist {n}",target_type="video" if n<3 else "playlist")
                db.session.add(qr);db.session.flush()
                ids.append(qr.id)
            db.session.commit()
        for kind,route,subset in [
            ("video","/videos/21/qr",ids[:3]),
            ("playlist","/playlists/8/qr",ids[3:])
        ]:
            with app.test_request_context(route,method="POST"):
                from flask import session
                session["user_id"]=tid
                session["research_measurement_id"]=pid
                for qr_id in subset:web.record_research_qr_creation(cid,tid,kind,qr_id)
                db.session.commit()
        assert client.post("/research/measurement/progress",
            data={"operations_count":"21"}).status_code==200
        files=client.get("/research/auto/files")
        assert files.status_code==200 and len(files.json["files"])==8
        finish=client.post("/research/auto/complete",data={
            "save_method":"directory_picker",
            "saved_qr_ids":json.dumps(ids),"operations_count":"23"})
        assert finish.status_code==200 and finish.json["ok"]
        with app.app_context():
            pair=db.session.get(ResearchComparisonPair,pid)
            assert pair.is_paired and pair.measurement_verified
            assert pair.measurement_save_method=="directory_picker"
            assert pair.webapp_seconds>0 and pair.webapp_operations==23
            assert pair.measurement_single_videos==3 and pair.measurement_single_playlists==5
            assert video_coverage(pair)==53 and pair.qr_count==8
        # GV không được sửa dữ liệu của quản trị viên.
        assert client.post(f"/research/comparison/{pid}/void",
            data={"void_reason":"sai dữ liệu"}).status_code in (302,403)
        assert client.post(f"/research/comparison/{pid}/reset",
            data={"reason":"sai dữ liệu"}).status_code in (302,403)
        with app.app_context():
            pair=db.session.get(ResearchComparisonPair,pid)
            assert pair.is_paired
        # Nhóm thứ 2: chỉ các QR được tạo bởi route video hàng loạt mới được ghi.
        with client.session_transaction() as ss:ss["user_id"]=aid
        bulk_form=dict(BULK,form_type="pair_create",lecturer_id=str(tid),course_id=str(cid))
        assert client.post("/research",data=bulk_form).status_code==302
        with app.app_context():
            second=ResearchComparisonPair.query.filter_by(
                lecturer_id=tid,task_kind="QR_VIDEO_HANG_LOAT").one()
            sid=second.id
        with client.session_transaction() as ss:ss["user_id"]=tid
        started=client.post("/research/auto/start",data={
            "course_id":cid,"task_kind":"QR_VIDEO_HANG_LOAT"})
        assert started.status_code==200 and started.json["id"]==sid
        with app.app_context():
            bulk_ids=[]
            for n in range(15):
                qr=QrCode(owner_id=tid,course_id=cid,slug=f"bulkqr{n}",
                    title=f"Video hàng loạt {n}",target_type="video")
                db.session.add(qr);db.session.flush()
                bulk_ids.append(qr.id)
            db.session.commit()
        with app.test_request_context("/videos/qr/bulk-selected",method="POST"):
            from flask import session
            session["user_id"]=tid
            session["research_measurement_id"]=sid
            for qr_id in bulk_ids:web.record_research_qr_creation(cid,tid,"video",qr_id)
            db.session.commit()
        # ZIP chưa giải nén hoặc chưa xác nhận thì không kết thúc được.
        invalid=client.post("/research/auto/complete",data={
            "save_method":"manual_confirmed","saved_qr_ids":json.dumps(bulk_ids),
            "operations_count":"9"})
        assert invalid.status_code==400
        finish=client.post("/research/auto/complete",data={
            "save_method":"manual_confirmed","saved_qr_ids":json.dumps(bulk_ids),
            "operations_count":"9","user_confirmed":"yes"})
        assert finish.status_code==200
        with app.app_context():
            second=db.session.get(ResearchComparisonPair,sid)
            assert second.measurement_saved_at is not None
            assert second.measurement_save_method=="manual_confirmed"
            assert second.measurement_verified is False
            groups,totals=pair_metrics(ResearchComparisonPair.query.all())
            assert len(groups)==1 and totals["video_coverage"]==53
        with client.session_transaction() as ss:ss["user_id"]=aid
        response=client.get("/research")
        assert response.status_code==200
        assert "Đủ cặp đo".encode() in response.data
