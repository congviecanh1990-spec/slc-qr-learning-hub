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
            # Video thứ hai được xem qua một QR/phiên khác:
            # quy tắc mục B vẫn công nhận thành tích SV–video trên toàn hệ thống.
            db.session.add(WatchSession(
                session_key="test-gv-watch-"+str(i), participant_code="SV-1001",
                role="SV", class_code=cl.code, course_id=(course.id if i == 0 else None),
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



def test_admin_who_also_teaches_appears_in_lecturer_statistics(configured_app):
    """Quản trị viên kiêm GV phải có một dòng thống kê đầy đủ, không bị bỏ sót."""
    from models import db, User, Course, SchoolClass, CourseClass, QrCode
    from lecturer_usage import lecturer_usage_rows
    app, keys, _ = configured_app
    with app.app_context():
        admin = User(email="admin-teaches@test.local", name="Quản trị kiêm GV",
                     role="admin", profile_completed=True)
        db.session.add(admin)
        db.session.flush()
        course = Course(owner_id=admin.id, name="Tin học do quản trị dạy",
                        code="ADMIN-TIN", active=True)
        school_class = SchoolClass(code="ADMIN-CLASS", name="Lớp quản trị", active=True)
        db.session.add_all([course, school_class])
        db.session.flush()
        db.session.add(CourseClass(course_id=course.id,
                                   school_class_id=school_class.id, active=True))
        db.session.add(QrCode(owner_id=admin.id, course_id=course.id,
                              title="QR quản trị", slug="qr-admin-teaches", active=True))
        db.session.commit()
        rows = lecturer_usage_rows(admin, 0.95, date.today())
        matching = [r for r in rows if r["email"] == admin.email]
        assert len(matching) == 1
        assert matching[0]["courses"] == 1
        assert matching[0]["classes"] == 1
        assert matching[0]["qr"] == 1
        # Không loại giảng viên thông thường khi bổ sung quản trị viên.
        assert any(r["email"] == "video-selection-teacher@test.local" for r in rows)
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["user_id"] = admin.id
        page = client.get("/analytics")
        assert page.status_code == 200
        assert "Quản trị kiêm GV" in page.get_data(as_text=True)
        file = client.get("/analytics?export_xlsx=lecturers")
        assert file.status_code == 200
        wb = load_workbook(io.BytesIO(file.data), read_only=True)
        displayed = [row[1] for row in wb.active.iter_rows(min_row=5, values_only=True)]
        assert "Quản trị kiêm GV" in displayed
        wb.close()



def test_scan_from_teacher_owned_qr_without_course_is_not_lost(configured_app):
    """QR cũ thiếu liên kết môn vẫn ghi nhận khi do chính GV tạo và quét trong lớp đang dạy."""
    from models import db, User, Course, SchoolClass, CourseClass, Student, ClassEnrollment, QrCode, ScanLog
    from lecturer_usage import lecturer_usage_rows
    app, keys, _ = configured_app
    today = date.today()
    with app.app_context():
        teacher = db.session.get(User, keys["teacher"])
        course = db.session.get(Course, keys["course"])
        school_class = SchoolClass(code="LEGACY-L01", name="Lớp quét mã QR cũ")
        db.session.add(school_class)
        db.session.flush()
        db.session.add(CourseClass(course_id=course.id,
                                   school_class_id=school_class.id, active=True))
        student = Student(student_code="LEGACY-ST01", full_name="Sinh viên QR cũ")
        db.session.add(student)
        db.session.flush()
        db.session.add(ClassEnrollment(student_id=student.id,
                                       school_class_id=school_class.id,
                                       started_on=today-timedelta(days=1)))
        old_qr = QrCode(owner_id=teacher.id, course_id=None,
                        slug="qr-legacy-without-course", title="Mã QR cũ")
        db.session.add(old_qr)
        db.session.flush()
        db.session.add(ScanLog(
            role="SV", participant_code=student.student_code,
            class_code=school_class.code, course_id=None,
            qr_id=old_qr.id, success=True))
        db.session.commit()
        stats = lecturer_usage_rows(teacher, 0.95, today)[0]
        assert stats["roster"] == 1
        assert stats["scanned"] == 1
        assert stats["successful"] == 1


def test_lecturer_delete_two_step_confirmation_and_keep_classes(configured_app):
    """Không xác nhận => không xóa; chọn giữ lớp => không xóa roster, nhưng xóa QR/lỗi."""
    from datetime import timedelta
    from models import (db, User, Course, SchoolClass, CourseClass, Student,
                        ClassEnrollment, QrCode, ErrorLog, ScanLog)
    app, keys, _ = configured_app
    with app.app_context():
        admin = User(email="delete-admin@test.local", role="admin", name="Quản trị", profile_completed=True)
        db.session.add(admin);db.session.flush()
        gv = db.session.get(User, keys["teacher"])
        course = db.session.get(Course, keys["course"])
        cl = SchoolClass(code="DELETE-KEEP", name="Lớp cần giữ",
                         homeroom_teacher_id=gv.id, active=True)
        db.session.add(cl);db.session.flush()
        db.session.add(CourseClass(course_id=course.id, school_class_id=cl.id, active=True))
        student = Student(student_code="DELETE-SV1", full_name="SV cần giữ")
        db.session.add(student);db.session.flush()
        db.session.add(ClassEnrollment(student_id=student.id, school_class_id=cl.id,
                                       started_on=date.today()-timedelta(days=2)))
        qr = QrCode(owner_id=gv.id, course_id=course.id, slug="delete-keep-qr",
                    title="Học liệu sắp xóa", active=True)
        db.session.add(qr);db.session.flush()
        db.session.add(ScanLog(participant_code=student.student_code, role="SV",
                               class_code=cl.code, course_id=course.id,
                               qr_id=qr.id, success=True))
        db.session.add(ErrorLog(module="test", message="Lỗi thuộc giảng viên",
                                actor_user_id=gv.id, actor_email=gv.email))
        db.session.commit()
        aid, uid, cid, sid, qid = admin.id, gv.id, cl.id, student.id, qr.id
    with app.test_client() as client:
        with client.session_transaction() as ss: ss["user_id"] = aid
        page = client.get("/admin/lecturers")
        assert page.status_code == 200
        html = page.get_data(as_text=True)
        assert "Không – Giữ danh sách lớp" in html and "Có – Xóa lớp không dùng chung" in html
        assert 'name="confirm_email"' not in html and "prompt(" not in html
        route = f"/admin/lecturers/{uid}/delete"
        assert client.post(route, data={}).status_code == 302
        with app.app_context():
            assert db.session.get(User, uid) is not None
        assert client.post(route, data={"confirm_delete":"yes"}).status_code == 302
        with app.app_context():
            assert db.session.get(User, uid) is not None
        response = client.post(route, data={
            "confirm_delete":"yes", "delete_classes":"no"})
        assert response.status_code == 302
        with app.app_context():
            assert db.session.get(User, uid) is None
            assert db.session.get(QrCode, qid) is None
            assert db.session.get(SchoolClass, cid) is not None
            assert db.session.get(SchoolClass, cid).homeroom_teacher_id is None
            assert db.session.get(Student, sid) is not None
            assert ClassEnrollment.query.filter_by(school_class_id=cid, student_id=sid).count() == 1
            assert ErrorLog.query.filter_by(actor_email="video-selection-teacher@test.local").count() == 0


def test_lecturer_delete_classes_preserves_shared_and_removes_exclusive(configured_app):
    """Chọn xóa lớp: chỉ lớp riêng bị xóa; lớp GVCN khác dạy vẫn còn."""
    from datetime import timedelta
    from models import (db, User, Course, SchoolClass, CourseClass, Student,
                        ClassEnrollment)
    app, keys, _ = configured_app
    with app.app_context():
        admin = User(email="delete-admin2@test.local", role="admin", name="Quản trị", profile_completed=True)
        db.session.add(admin);db.session.flush()
        gv = db.session.get(User, keys["teacher"])
        other = db.session.get(User, keys["other"])
        course = db.session.get(Course, keys["course"])
        other_course = Course(owner_id=other.id, name="Môn của người khác",
                              code="SHARED-OTHER", active=True)
        db.session.add(other_course);db.session.flush()
        exclusive = SchoolClass(code="DELETE-ONLY", name="Lớp chỉ GV này dạy",
                                homeroom_teacher_id=gv.id, active=True)
        shared = SchoolClass(code="DELETE-SHARED", name="Lớp dùng chung",
                             homeroom_teacher_id=gv.id, active=True)
        db.session.add_all([exclusive, shared]);db.session.flush()
        db.session.add_all([
            CourseClass(course_id=course.id, school_class_id=exclusive.id, active=True),
            CourseClass(course_id=course.id, school_class_id=shared.id, active=True),
            CourseClass(course_id=other_course.id, school_class_id=shared.id, active=True),
        ])
        student1=Student(student_code="DELETE-SV-ONLY", full_name="SV lớp riêng")
        student2=Student(student_code="DELETE-SV-SHARED", full_name="SV lớp chung")
        db.session.add_all([student1,student2]);db.session.flush()
        for student, cls in [(student1,exclusive),(student2,shared)]:
            db.session.add(ClassEnrollment(student_id=student.id,school_class_id=cls.id,
                started_on=date.today()-timedelta(days=3)))
        db.session.commit()
        aid, uid = admin.id, gv.id
        exclusive_id, shared_id, own_student, shared_student = exclusive.id, shared.id, student1.id, student2.id
    with app.test_client() as client:
        with client.session_transaction() as ss: ss["user_id"]=aid
        response=client.post(f"/admin/lecturers/{uid}/delete",
                             data={"confirm_delete":"yes", "delete_classes":"yes"})
        assert response.status_code == 302
        with app.app_context():
            assert db.session.get(User,uid) is None
            assert db.session.get(SchoolClass,exclusive_id) is None
            assert db.session.get(Student,own_student) is None
            assert db.session.get(SchoolClass,shared_id) is not None
            assert db.session.get(Student,shared_student) is not None
            assert CourseClass.query.filter_by(course_id=other_course.id,school_class_id=shared_id).count() == 1
