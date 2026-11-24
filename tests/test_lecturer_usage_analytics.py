"""Kiểm thử bảng thống kê khai thác theo giảng viên."""
from datetime import date, timedelta
import io

from openpyxl import load_workbook
from test_video_selection_across_pages import configured_app


def test_lecturer_scope_deduplicates_students_and_counts_completion(configured_app):
    from models import (
        db, User, Course, SchoolClass, CourseClass, ClassEnrollment,
        Student, CourseVideo, QrCode, ScanLog, WatchSession,
    )
    from lecturer_usage import lecturer_usage_rows
    app, keys, _ = configured_app
    today = date.today()
    with app.app_context():
        owner = db.session.get(User, keys["teacher"])
        another = db.session.get(User, keys["other"])
        course = db.session.get(Course, keys["course"])
        cl = SchoolClass(code="T01", name="Lớp T01", active=True)
        db.session.add(cl)
        db.session.flush()
        db.session.add(CourseClass(course_id=course.id, school_class_id=cl.id, active=True))
        students = [
            Student(student_code="SV-1001", full_name="Sinh viên 1"),
            Student(student_code="SV-1002", full_name="Sinh viên 2"),
        ]
        db.session.add_all(students)
        db.session.flush()
        for student in students:
            db.session.add(ClassEnrollment(
                school_class_id=cl.id, student_id=student.id, started_on=today-timedelta(days=20)))
        for vid in keys["video_ids"][:2]:
            db.session.add(CourseVideo(course_id=course.id, video_id=vid))
        qr = QrCode(owner_id=owner.id, course_id=course.id,
                    slug="thong-ke-gv-01", title="Học liệu", active=True)
        db.session.add(qr)
        db.session.flush()
        for code, success in [
            ("SV-1001", False), ("SV-1001", True), ("SV-1001", True),
            ("SV-1002", False)]:
            db.session.add(ScanLog(participant_code=code, role="SV",
                                   class_code=cl.code, course_id=course.id,
                                   qr_id=qr.id, success=success))
        for i, video_id in enumerate(keys["video_ids"][:2]):
            db.session.add(WatchSession(
                session_key="test-gv-watch-"+str(i), participant_code="SV-1001",
                role="SV", class_code=cl.code, course_id=course.id,
                qr_id=qr.id, video_id=video_id,
                duration_seconds=100, estimated_watch_seconds=100))
        db.session.commit()
        own = lecturer_usage_rows(owner, 0.95, today)[0]
        assert own["courses"] == 1
        assert own["classes"] == 1
        assert own["roster"] == 2
        assert own["scanned"] == 2
        assert own["successful"] == 1
        assert own["finished"] == 1
        assert own["qr"] == 1
        # Người khác không được xem dữ liệu giảng viên này.
        other_rows = lecturer_usage_rows(another, 0.95, today)
        assert len(other_rows) == 1
        assert other_rows[0]["roster"] == 0

        # Bàn giao LỚP sang GV khác: chủ môn không tiếp tục tính lớp đã giao.
        cc = CourseClass.query.filter_by(course_id=course.id, school_class_id=cl.id).one()
        cc.assigned_lecturer_id = another.id
        db.session.commit()
        old = lecturer_usage_rows(owner, 0.95, today)[0]
        new = lecturer_usage_rows(another, 0.95, today)[0]
        assert old["classes"] == 0 and old["courses"] == 0 and old["roster"] == 0
        assert old["qr"] == 1, "QR vẫn thuộc người đã tạo mã trước bàn giao"
        assert new["classes"] == 1 and new["courses"] == 1
        assert new["roster"] == 2 and new["successful"] == 1
        assert new["finished"] == 1


def test_analytics_system_has_5_rows_and_lecturers_excel(configured_app):
    from models import db, FunctionalTestRun
    app, keys, _ = configured_app
    with app.app_context():
        for i in range(12):
            db.session.add(FunctionalTestRun(
                owner_id=keys["teacher"], source="automatic",
                case_code="DEMO-"+str(i), case_name="Thử nghiệm "+str(i),
                passed=True,
            ))
        db.session.commit()
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["user_id"] = keys["teacher"]
        response = client.get("/analytics?sys_period=all")
        assert response.status_code == 200
        assert b"5 d" in response.data or "5 dòng/trang".encode("utf-8") in response.data
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.data, "html.parser")
        section = soup.select_one("#hoat-dong-he-thong")
        assert section is not None
        assert len(section.select("table tbody tr")) == 5 + 1  # nhật ký 5 + bảng giảng viên
        assert "thong-ke-giang-vien" in response.get_data(as_text=True)
        assert "export_xlsx=lecturers" in response.get_data(as_text=True)
        exported = client.get("/analytics?export_xlsx=lecturers")
        assert exported.status_code == 200
        wb = load_workbook(io.BytesIO(exported.data), read_only=True)
        assert "Thống kê khai thác theo giảng viên" in wb.active["A1"].value
        assert wb.active.max_column == 10
        wb.close()
