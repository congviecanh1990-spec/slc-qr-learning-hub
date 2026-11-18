"""Kiểm thử ngoại tuyến: bàn giao một lớp không ảnh hưởng lớp còn lại và QR."""
from pathlib import Path
import sys
import types

import sqlalchemy as sa
from sqlalchemy.orm import declarative_base, relationship, backref, sessionmaker

ROOT = Path(__file__).resolve().parents[1]
try:
    from flask_sqlalchemy import SQLAlchemy
except ModuleNotFoundError:
    class SQLAlchemy:
        def __init__(self):
            self.Model = declarative_base()
            for key in ("Column", "Integer", "String", "Text", "Date", "DateTime",
                        "Boolean", "Float", "ForeignKey"):
                setattr(self, key, getattr(sa, key))
            self.relationship = relationship
            self.backref = backref
    stub = types.ModuleType("flask_sqlalchemy")
    stub.SQLAlchemy = SQLAlchemy
    sys.modules["flask_sqlalchemy"] = stub

sys.path.insert(0, str(ROOT))
import models

engine = sa.create_engine("sqlite:///:memory:")
models.db.Model.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

with Session() as db:
    models.db.session = db
    old = models.User(email="old@example.test", name="Giảng viên 1", role="lecturer")
    new = models.User(email="new@example.test", name="Giảng viên 2", role="lecturer")
    admin = models.User(email="admin@example.test", name="Quản trị", role="admin")
    db.add_all([old, new, admin])
    db.flush()
    course = models.Course(owner_id=old.id, code="HP0001", name="Môn A", active=True)
    db.add(course)
    db.flush()
    cls1 = models.SchoolClass(code="L001", name="Lớp 1", active=True)
    cls2 = models.SchoolClass(code="L002", name="Lớp 2", active=True)
    db.add_all([cls1, cls2])
    db.flush()
    first = models.CourseClass(course_id=course.id, school_class_id=cls1.id, active=True)
    second = models.CourseClass(course_id=course.id, school_class_id=cls2.id, active=True)
    qr = models.QrCode(owner_id=old.id, course_id=course.id,
                       slug="qr-existing", title="Video hiện có", active=True)
    db.add_all([first, second, qr])
    db.flush()
    # Chuyển riêng lớp 2 (giữ nguyên chủ môn, lớp 1, URL QR).
    second.assigned_lecturer_id = new.id
    db.add(models.CourseClassTransfer(
        course_class_id=second.id, previous_lecturer_id=old.id,
        new_lecturer_id=new.id, changed_by=admin.id,
        effective_on=models.utcnow().date()))
    db.commit()

    assert course.owner_id == old.id
    assert first.assigned_lecturer_id is None
    assert second.assigned_lecturer_id == new.id
    assert qr.slug == "qr-existing" and qr.owner_id == old.id and qr.course_id == course.id
    assert db.query(models.CourseClassTransfer).count() == 1
    # Bàn giao lại lớp 2 cho giảng viên chủ môn.
    second.assigned_lecturer_id = None
    db.add(models.CourseClassTransfer(
        course_class_id=second.id, previous_lecturer_id=new.id,
        new_lecturer_id=old.id, changed_by=admin.id,
        effective_on=models.utcnow().date()))
    db.commit()
    assert db.query(models.CourseClassTransfer).count() == 2
    assert first.assigned_lecturer_id is None and second.assigned_lecturer_id is None

source = (ROOT / "app.py").read_text(encoding="utf-8")
html = (ROOT / "templates" / "courses.html").read_text(encoding="utf-8")
assert 'def transfer_course_classes(course_id):' in source
assert 'CourseClass.assigned_lecturer_id == user.id' in source
assert 'CourseClassTransfer.query.filter(' in source
assert 'url_for(\'transfer_course_classes\',course_id=c.id)' in html
assert 'Bộ môn quản lý MH/MĐ' in html
assert 'Video của MH/MĐ' in html
assert 'Playlist của MH/MĐ' in html
assert 'value="{{ me.department_name or' not in html
assert 'value="{{ me.faculty_name or' not in html
print("PASS: bàn giao từng lớp, giữ QR, lịch sử và điều kiện giao diện")
