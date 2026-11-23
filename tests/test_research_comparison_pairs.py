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
