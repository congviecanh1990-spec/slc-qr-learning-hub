"""Regression checks for comparable QR research measurements (no production DB)."""
import ast
from pathlib import Path
from types import SimpleNamespace

import pytest
from jinja2 import Environment, FileSystemLoader

from research_comparison import validate_pair_form, validate_webapp_observation, pair_metrics


ROOT = Path(__file__).resolve().parents[1]
BASE = dict(pair_code="TN01-VIDEO", lecturer_id="1", course_id="2",
            task_kind="QR_VIDEO_RIENG", video_count="15", playlist_count="0",
            playlist_video_count="0", qr_count="15",
            manual_operations="65", manual_seconds="450.5",
            webapp_operations="20", webapp_seconds="90.5")


def test_video_and_playlist_not_conflated():
    video = validate_pair_form(BASE)
    assert video["qr_count"] == 15 and video["video_count"] == 15
    assert video["manual_seconds"] == 450.5
    example = dict(BASE, pair_code="TN02-PLAYLIST", task_kind="QR_PLAYLIST",
                   video_count="0", playlist_count="5",
                   playlist_video_count="50", qr_count="5")
    playlist = validate_pair_form(example)
    assert playlist["qr_count"] == 5 and playlist["playlist_video_count"] == 50
    for bad in (
        dict(example, qr_count="50"),
        dict(example, video_count="3"),
        dict(example, playlist_video_count="3"),
        dict(BASE, playlist_count="5"),
        dict(BASE, manual_seconds="nan"),
        dict(BASE, pair_code="!!!"),
        dict(BASE, webapp_operations="", webapp_seconds="5"),
    ):
        with pytest.raises(ValueError):
            validate_pair_form(bad)


def test_can_save_manual_first_and_complete_later():
    manual = validate_pair_form(dict(BASE, webapp_operations="", webapp_seconds=""))
    assert manual["webapp_operations"] is None and manual["webapp_seconds"] is None
    assert validate_webapp_observation(dict(webapp_operations="10", webapp_seconds="25.5")) == (10, 25.5)
    with pytest.raises(ValueError):
        validate_webapp_observation(dict(webapp_operations="0", webapp_seconds="25.5"))


def test_grouped_comparison_uses_paired_workload():
    def row(kind, n, mt, wt, mo, wo, paired=True, active=True):
        return SimpleNamespace(task_kind=kind, qr_count=n, manual_seconds=mt,
                               webapp_seconds=wt if paired else None,
                               manual_operations=mo, webapp_operations=wo if paired else None,
                               active=active)
    rows = [
        row("QR_VIDEO_RIENG", 15, 450, 90, 60, 15),
        row("QR_VIDEO_RIENG", 3, 90, 30, 12, 3),
        row("QR_PLAYLIST", 5, 200, 50, 30, 5),
        row("QR_PLAYLIST", 50, 3000, 100, 100, 2, paired=False),
        row("QR_PLAYLIST", 5, 500, 500, 50, 50, active=False),
    ]
    group, totals = pair_metrics(rows)
    by_key = {x["key"]:x for x in group}
    assert len(group)==2
    assert by_key["QR_VIDEO_RIENG"]["qr_count"] == 18
    assert by_key["QR_VIDEO_RIENG"]["manual_per_qr"] == 30.0
    assert by_key["QR_VIDEO_RIENG"]["app_per_qr"] == round(120/18, 2)
    assert by_key["QR_PLAYLIST"]["qr_count"] == 5
    assert by_key["QR_PLAYLIST"]["manual_per_qr"] == 40.0
    assert by_key["QR_PLAYLIST"]["time_reduction"] == 75.0
    assert totals["paired_count"] == 3 and totals["qr_count"] == 23
    empty, waiting = pair_metrics([rows[3], rows[4]])
    assert empty == [] and waiting["time_reduction"] is None


def test_code_and_jinja_compile_and_kpi_uses_paired_only():
    app_source=(ROOT/"app.py").read_text(encoding="utf-8")
    ast.parse(app_source)
    models_source=(ROOT/"models.py").read_text(encoding="utf-8")
    ast.parse(models_source)
    jinja=Environment(loader=FileSystemLoader(str(ROOT/"templates")))
    for path in (ROOT/"templates").glob("*.html"):
        jinja.parse(path.read_text(encoding="utf-8"))
    research_ui=(ROOT/"templates/research.html").read_text(encoding="utf-8")
    assert 'name="form_type" value="pair_create"' in research_ui
    assert "research_pair_webapp_result" in research_ui
    assert "for g in paired_groups" in research_ui
    assert 'ResearchComparisonPair.query.filter_by(active=True)' in app_source
    assert 'reduction_time = paired_totals["time_reduction"]' in app_source


def test_new_table_sqlite_preserves_legacy_experiments():
    from flask import Flask
    from models import db, User, Course, ResearchComparisonPair, ExperimentRun
    flask_app=Flask("research-pair-test")
    flask_app.config.update(SQLALCHEMY_DATABASE_URI="sqlite://",TESTING=True)
    db.init_app(flask_app)
    with flask_app.app_context():
        db.create_all()
        lecturer=User(email="research-lecturer@example.test",name="Giảng viên",role="lecturer")
        db.session.add(lecturer);db.session.flush()
        course=Course(owner_id=lecturer.id,name="Học phần",code="HP1")
        db.session.add(course);db.session.flush()
        values=validate_pair_form(BASE)
        values.update(lecturer_id=lecturer.id,course_id=course.id)
        p=ResearchComparisonPair(**values,
             lecturer_name_snapshot="Giảng viên",course_name_snapshot="Học phần")
        db.session.add(p)
        db.session.add(ExperimentRun(owner_id=lecturer.id,task_key="TAO_QR_RIENG",
            mode="webapp",operations_count=1,elapsed_seconds=.05,success=True))
        db.session.commit()
        assert ResearchComparisonPair.query.count()==1
        assert ExperimentRun.query.count()==1
        groups,totals=pair_metrics(ResearchComparisonPair.query.all())
        assert groups[0]["qr_count"]==15 and totals["paired_count"]==1


def test_research_admin_workflow_end_to_end(tmp_path, monkeypatch):
    """GET/POST thật qua Flask: nhập thủ công, hoàn thiện Web App, loại lượt sai."""
    # CI có thể chạy cùng phép kiểm thử với PostgreSQL tạm thời (không dùng Neon).
    import os
    db_url=os.environ.get("TEST_POSTGRES_DATABASE_URL") or ("sqlite:///"+str(tmp_path/"research-workflow.sqlite3"))
    monkeypatch.setenv("DATABASE_URL",db_url)
    monkeypatch.setenv("AUTO_CREATE_DB","0")
    monkeypatch.setenv("SECRET_KEY","ci-only-secret")
    monkeypatch.setenv("GOOGLE_CLIENT_ID","")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET","")
    import app as webapp
    from models import db, User, Course, ResearchComparisonPair
    application=webapp.create_app()
    application.config.update(
        TESTING=True, WTF_CSRF_ENABLED=False, SESSION_COOKIE_SECURE=False
    )
    with application.app_context():
        db.create_all()
        admin=User(email="admin-r@example.test",name="Admin",role="admin",profile_completed=True)
        teacher=User(email="teacher-r@example.test",name="GV thực nghiệm",role="lecturer",profile_completed=True)
        db.session.add_all([admin,teacher]);db.session.flush()
        course=Course(owner_id=teacher.id,name="Lập trình Python",code="HP001")
        db.session.add(course);db.session.commit()
        admin_id,teacher_id,course_id=admin.id,teacher.id,course.id
        # Render có thể đang dùng Neon nhánh test được tạo trước bản cập nhật:
        # mô phỏng cơ sở dữ liệu thiếu đúng bảng mới, phải tự bổ sung không mất dữ liệu.
        ResearchComparisonPair.__table__.drop(bind=db.engine)
        assert not db.inspect(db.engine).has_table("research_comparison_pairs")
    with application.test_client() as client:
        with client.session_transaction() as session:
            session["user_id"]=admin_id
        response=client.get("/research")
        assert response.status_code==200
        with application.app_context():
            assert db.inspect(db.engine).has_table("research_comparison_pairs")
            assert User.query.count()==2 and Course.query.count()==1
        assert b"pair_create" in response.data
        form=dict(BASE,form_type="pair_create",lecturer_id=str(teacher_id),
                  course_id=str(course_id),webapp_operations="",webapp_seconds="")
        result=client.post("/research",data=form,follow_redirects=False)
        assert result.status_code==302
        with application.app_context():
            pair=ResearchComparisonPair.query.filter_by(pair_code="TN01-VIDEO").one()
            pair_id=pair.id
            assert pair.webapp_seconds is None
        response=client.get("/research")
        assert response.status_code==200
        assert "Chờ bổ sung Web App".encode() in response.data
        result=client.post(f"/research/comparison/{pair_id}/webapp",
            data=dict(webapp_operations="12",webapp_seconds="50.5"),
            follow_redirects=False)
        assert result.status_code==302
        with application.app_context():
            pair=db.session.get(ResearchComparisonPair,pair_id)
            assert pair.is_paired and pair.webapp_seconds==50.5
        response=client.get("/research")
        assert response.status_code==200
        assert "Đủ cặp đo".encode() in response.data
        result=client.post(f"/research/comparison/{pair_id}/void",
            data={"void_reason":"Thao tác không hợp lệ"},follow_redirects=False)
        assert result.status_code==302
        with application.app_context():
            pair=db.session.get(ResearchComparisonPair,pair_id)
            assert pair.active is False and pair.void_reason
        response=client.get("/research")
        assert response.status_code==200
        assert "Chưa đủ cặp đo".encode() in response.data or "Chưa có cặp đo".encode() in response.data
