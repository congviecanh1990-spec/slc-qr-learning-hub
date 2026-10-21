"""v4.3.16 – Kiểm tra danh sách SV động lọc theo môn, lớp và giao môn-lớp.

Chạy offline bằng SQLAlchemy/SQLite; không cần đăng nhập Google hay PostgreSQL.
"""
from __future__ import annotations
import ast
from datetime import datetime, date, timedelta
from pathlib import Path
from types import SimpleNamespace
from sqlalchemy import (create_engine, Column, Integer, String, Boolean, Date,
                        ForeignKey, or_)
from sqlalchemy.orm import Session, declarative_base, relationship

root=Path(__file__).resolve().parents[1]
app_src=(root/'app.py').read_text(encoding='utf-8')
html=(root/'templates/analytics.html').read_text(encoding='utf-8')
tree=ast.parse(app_src)
helper=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='analytics_students_for_filters')
assert 'api/analytics/students' in app_src
assert '"id": st.id' in app_src
assert 'student_code_tail(st.student_code)' in app_src
assert '"student_code":' not in app_src[app_src.index('def analytics_student_options():'):app_src.index('@app.get("/analytics")')]
assert 'id="filterCourse"' in html and 'id="filterClass"' in html and 'id="filterStudent"' in html
assert 'filterStudentHint' not in html and 'Danh sách sinh viên theo môn học và lớp đang chọn.' not in html
assert "url_for('analytics_student_options')" in html
assert "course.addEventListener('change',updateStudents)" in html
assert "cls.addEventListener('change',updateStudents)" in html

Base=declarative_base()
class Student(Base):
    __tablename__='students'
    id=Column(Integer,primary_key=True)
    full_name=Column(String)
    student_code=Column(String)
class SchoolClass(Base):
    __tablename__='school_classes'
    id=Column(Integer,primary_key=True)
    code=Column(String)
    active=Column(Boolean)
class ClassEnrollment(Base):
    __tablename__='class_enrollments'
    id=Column(Integer,primary_key=True)
    student_id=Column(Integer,ForeignKey('students.id'))
    school_class_id=Column(Integer,ForeignKey('school_classes.id'))
    started_on=Column(Date)
    ended_on=Column(Date)
class Course(Base):
    __tablename__='courses'
    id=Column(Integer,primary_key=True)
    owner_id=Column(Integer)
    active=Column(Boolean)
class CourseClass(Base):
    __tablename__='course_classes'
    id=Column(Integer,primary_key=True)
    course_id=Column(Integer,ForeignKey('courses.id'))
    school_class_id=Column(Integer,ForeignKey('school_classes.id'))
    active=Column(Boolean)

engine=create_engine('sqlite:///:memory:')
Base.metadata.create_all(engine)
ns={'Student':Student,'SchoolClass':SchoolClass,'ClassEnrollment':ClassEnrollment,
    'Course':Course,'CourseClass':CourseClass,'or_':or_,
    'utcnow':lambda:datetime(2026,10,21)}
exec(compile(ast.Module(body=[helper],type_ignores=[]),str(root/'app.py'),'exec'),ns)
filter_students=ns['analytics_students_for_filters']
with Session(engine) as sess:
    Student.query=sess.query(Student)
    sess.add_all([
        SchoolClass(id=1,code='A',active=True),
        SchoolClass(id=2,code='B',active=True),
        SchoolClass(id=3,code='C',active=True),
        SchoolClass(id=4,code='D',active=False),
        Course(id=10,owner_id=1,active=True),
        Course(id=20,owner_id=1,active=True),
        Course(id=30,owner_id=2,active=True),
        Course(id=40,owner_id=1,active=False),
        CourseClass(id=1,course_id=10,school_class_id=1,active=True),
        CourseClass(id=2,course_id=10,school_class_id=2,active=True),
        CourseClass(id=3,course_id=20,school_class_id=2,active=True),
        CourseClass(id=4,course_id=30,school_class_id=3,active=True),
        CourseClass(id=5,course_id=10,school_class_id=3,active=False),
        CourseClass(id=6,course_id=40,school_class_id=1,active=True),
        Student(id=101,full_name='SV A',student_code='SV000101'),
        Student(id=102,full_name='SV B',student_code='SV000102'),
        Student(id=103,full_name='SV C',student_code='SV000103'),
        Student(id=104,full_name='SV D',student_code='SV000104'),
        Student(id=105,full_name='SV chuyển lớp',student_code='SV000105'),
        Student(id=106,full_name='SV bảo lưu',student_code='SV000106'),
        ClassEnrollment(id=1,student_id=101,school_class_id=1,started_on=date(2026,9,1)),
        ClassEnrollment(id=2,student_id=102,school_class_id=2,started_on=date(2026,9,1)),
        ClassEnrollment(id=3,student_id=103,school_class_id=3,started_on=date(2026,9,1)),
        ClassEnrollment(id=4,student_id=104,school_class_id=4,started_on=date(2026,9,1)),
        ClassEnrollment(id=5,student_id=105,school_class_id=1,started_on=date(2026,9,1),ended_on=date(2026,10,1)),
        ClassEnrollment(id=6,student_id=105,school_class_id=3,started_on=date(2026,10,1)),
        ClassEnrollment(id=7,student_id=106,school_class_id=1,started_on=date(2026,9,1),ended_on=date(2026,10,20)),
    ])
    sess.commit()
    admin=SimpleNamespace(role='admin',id=99)
    gv1=SimpleNamespace(role='lecturer',id=1)
    gv2=SimpleNamespace(role='lecturer',id=2)
    def ids(u,course=None,cls=''):
        return {s.id for s in filter_students(u,course,cls).all()}
    assert ids(admin,10)=={101,102}, ids(admin,10)
    assert ids(admin,None,'A')=={101},ids(admin,None,'A')
    assert ids(admin,None,'B')=={102}
    assert ids(admin,10,'B')=={102}
    assert ids(admin,10,'C')==set()  # Có sinh viên ở C nhưng lớp C KHÔNG áp dụng môn 10.
    assert ids(admin,20,'A')==set()
    assert ids(admin,20,'B')=={102}
    assert ids(gv1,10)=={101,102}
    assert ids(gv1,20)=={102}
    assert ids(gv1,None,'A')=={101}
    assert ids(gv1,None,'C')==set()  # Lớp C không thuộc GV1.
    assert ids(gv1,30)==set()       # Không tiết lộ SV môn của GV2.
    assert ids(gv2,30)=={103,105}
    assert ids(gv2,10)==set()
    assert ids(admin,40)==set()     # Môn ngừng hoạt động.
    assert ids(admin,None,'D')==set() # Lớp ngừng hoạt động.
    assert ids(admin,None)=={101,102,103,105}
    print('PASS v4.3.16 – lọc SV theo môn, lớp, giao môn-lớp; trạng thái hiện hành; quyền GV/Admin; không rò mã SV')
