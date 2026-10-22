"""Hồi quy v4.3.20: thẻ QR mục 2 và thứ tự lớp / môn / tên SV.
Chạy: python tests/test_v4320_student_metrics_sort.py (SQLite độc lập).
"""
from __future__ import annotations

import ast
from pathlib import Path
from datetime import datetime, timedelta
from types import SimpleNamespace
from sqlalchemy import (Boolean, Column, DateTime, Float, Integer, String,
                        create_engine, select, func, and_, or_, case, literal, union_all)
from sqlalchemy.orm import declarative_base, Session, aliased
from sqlalchemy.dialects.postgresql import dialect as pg_dialect

Base = declarative_base()

class ScanLog(Base):
    __tablename__ = 'scan_logs'
    id = Column(Integer, primary_key=True)
    participant_code = Column(String)
    role = Column(String)
    class_code = Column(String)
    course_id = Column(Integer)
    qr_id = Column(Integer)
    video_id = Column(Integer)
    scanned_at = Column(DateTime)
    success = Column(Boolean)

class WatchSession(Base):
    __tablename__ = 'watch_sessions'
    id = Column(Integer, primary_key=True)
    participant_code = Column(String)
    role = Column(String)
    class_code = Column(String)
    course_id = Column(Integer)
    qr_id = Column(Integer)
    video_id = Column(Integer)
    started_at = Column(DateTime)
    duration_seconds = Column(Float)
    estimated_watch_seconds = Column(Float)

class QrCode(Base):
    __tablename__ = 'qr_codes'
    id = Column(Integer, primary_key=True)
    owner_id = Column(Integer)

class Course(Base):
    __tablename__ = 'courses'
    id = Column(Integer, primary_key=True)
    name = Column(String)

class SchoolClass(Base):
    __tablename__ = 'school_classes'
    id = Column(Integer, primary_key=True)
    code = Column(String, unique=True)
    name = Column(String)

class ClassGroup(Base):
    __tablename__ = 'class_groups'
    id = Column(Integer, primary_key=True)
    code = Column(String)
    course_id = Column(Integer)
    name = Column(String)

class Student(Base):
    __tablename__ = 'students'
    id = Column(Integer, primary_key=True)
    student_code = Column(String, unique=True)
    full_name = Column(String)

class Video(Base):
    __tablename__ = 'videos'
    id = Column(Integer, primary_key=True)

root = Path(__file__).resolve().parents[1]
source = (root / 'app.py').read_text(encoding='utf-8')
html = (root / 'templates/analytics.html').read_text(encoding='utf-8')
assert 'Tổng lượt quét</div>' in html
assert 'Quét thành công</div>' in html
assert 'Quét không thành công</div>' in html
assert 'Tỷ lệ quét thành công</div>' in html
assert 'student_metrics=student_metrics' in source
assert 'student_video_ordered_query(sv_query, db.engine.dialect.name)' in source
assert 'Bảng tổng hợp <strong>mỗi sinh viên' not in html

names = {'student_scan_metrics', 'student_video_summary_query', 'student_name_sort_expr',
         'student_video_ordered_query', 'vietnamese_student_sort_key'}
funcs = [node for node in ast.parse(source).body if isinstance(node, ast.FunctionDef) and node.name in names]
assert {node.name for node in funcs} == names
engine = create_engine('sqlite:///:memory:')
Base.metadata.create_all(engine)
with Session(engine) as session:
    namespace = {
        'ScanLog': ScanLog, 'WatchSession': WatchSession, 'QrCode': QrCode,
        'Course': Course, 'Video': Video, 'SchoolClass': SchoolClass,
        'ClassGroup': ClassGroup, 'Student': Student,
        'db': SimpleNamespace(session=session), 'func': func, 'case': case,
        'aliased': aliased, 'select': select, 'and_': and_, 'or_': or_,
        'literal': literal, 'union_all': union_all,
        'managed_qr_scope': lambda uid: QrCode.owner_id == uid,
    }
    exec(compile(ast.Module(body=funcs, type_ignores=[]), str(root/'app.py'), 'exec'), namespace)
    base = datetime(2026, 10, 1, 8)
    session.add_all([
        QrCode(id=1, owner_id=1), QrCode(id=2, owner_id=2),
        Course(id=1, name='Toán'), Course(id=2, name='Lịch sử'),
        SchoolClass(id=1, code='CLASS-B', name='B Lớp'),
        SchoolClass(id=2, code='CLASS-A', name='A Lớp'),
        ClassGroup(id=1, code='LEGACY', course_id=1, name='C Lớp'),
        Student(id=1, student_code='SV01', full_name='Nguyễn Thị Bình'),
        Student(id=2, student_code='SV02', full_name='Trần Văn An'),
        Student(id=3, student_code='SV03', full_name='Lê Đức Cường'),
        Video(id=10), Video(id=11), Video(id=12), Video(id=13), Video(id=14),
    ])
    def scan(id, code, clazz, course, qr, day, success=True, vid=None, role='SV'):
        session.add(ScanLog(id=id, participant_code=code, role=role,
            class_code=clazz, course_id=course, qr_id=qr, video_id=vid,
            scanned_at=base+timedelta(days=day), success=success))
    def watch(id, code, clazz, course, qr, vid, day):
        session.add(WatchSession(id=id, participant_code=code, role='SV',
            class_code=clazz, course_id=course, qr_id=qr, video_id=vid,
            started_at=base+timedelta(days=day), duration_seconds=100,
            estimated_watch_seconds=98))
    # 1 lượt playlist truy cập hai video vẫn chỉ đếm 1 lượt QR ở các thẻ.
    scan(1, 'SV01', 'CLASS-A', 1, 1, 1)
    watch(1, 'SV01', 'CLASS-A', 1, 1, 10, 1.01)
    watch(2, 'SV01', 'CLASS-A', 1, 1, 11, 1.02)
    scan(2, 'SV01', 'CLASS-A', 1, 1, 2, False)
    scan(3, 'SV02', 'CLASS-A', 1, 1, 3, vid=10)
    scan(4, 'SV03', 'CLASS-A', 2, 1, 4, vid=12)
    scan(5, 'SV03', 'CLASS-B', 1, 1, 5, vid=13)
    scan(6, 'SV03', 'LEGACY', 1, 1, 6, vid=14)
    scan(7, 'SV03', 'CLASS-A', 1, 2, 7, vid=10)  # QR GV khác
    scan(8, 'SV03', 'CLASS-A', 2, 2, 8, False, vid=12)
    scan(9, 'GV01', 'CLASS-A', 1, 1, 9, vid=10, role='GV')  # loại trừ
    session.flush()

    admin = SimpleNamespace(role='admin')
    lecturer = SimpleNamespace(role='lecturer', id=1)
    metrics = namespace['student_scan_metrics']
    assert metrics(admin) == {'total': 8, 'successful': 6, 'unsuccessful': 2, 'rate': 75.0}
    assert metrics(lecturer) == {'total': 6, 'successful': 5, 'unsuccessful': 1,
                                 'rate': round(500 / 6, 1)}
    assert metrics(admin, class_code='CLASS-A')['total'] == 6
    assert metrics(admin, course_id=1)['total'] == 6
    assert metrics(admin, course_id=2)['total'] == 2
    assert metrics(admin, qr_id=1) == {'total': 6, 'successful': 5, 'unsuccessful': 1,
                                      'rate': round(500 / 6, 1)}
    assert metrics(admin, student_code='SV01') == {'total': 2, 'successful': 1,
                                                    'unsuccessful': 1, 'rate': 50.0}
    assert metrics(lecturer, class_code='CLASS-A', course_id=1, qr_id=1,
                   student_code='SV01')['total'] == 2
    assert metrics(admin, invalid_scope=True) == {'total': 0, 'successful': 0,
                                                  'unsuccessful': 0, 'rate': None}
    assert metrics(admin, class_code='NONEXISTENT')['rate'] is None
    # Tình trạng đã hoàn thành không ảnh hưởng tổng của ScanLog gốc:
    # cùng quét 1 QR playlist, 2 video đã hoàn thành, 1 lượt QR.
    q = namespace['student_video_summary_query'](admin)
    assert len(q.all()) >= 6
    ordered = namespace['student_video_ordered_query'](q, 'sqlite').all()
    ordered_data = [(r[6], r[7].name if r[7] else None, r[0]) for r in ordered]
    assert ordered_data[0][0] == 'CLASS-A'
    assert ordered_data[-1][0] == 'LEGACY', ordered_data
    class_a = [(course, who) for cls, course, who in ordered_data if cls == 'CLASS-A']
    assert class_a.index(('Lịch sử', 'SV03')) < class_a.index(('Toán', 'SV01'))
    assert [cls for cls, course, who in ordered_data[:4]] == ['CLASS-A'] * 4
    # Trang 1 và trang 2 vẫn tuân theo thứ tự toàn cục.
    page1 = namespace['student_video_ordered_query'](q, 'sqlite').limit(3).all()
    page2 = namespace['student_video_ordered_query'](q, 'sqlite').offset(3).limit(3).all()
    assert [r[0:2] for r in page1 + page2] == [r[0:2] for r in ordered[:6]]
    assert namespace['vietnamese_student_sort_key']('Trần Văn An') < namespace['vietnamese_student_sort_key']('Nguyễn Thị Bình')
    # PostgreSQL thực tế xếp theo tên gọi (từ cuối), không chỉ theo họ đầu.
    pg_order = namespace['student_video_ordered_query'](q, 'postgresql')
    pg_sql = str(pg_order.statement.compile(dialect=pg_dialect()))
    assert 'regexp_replace(' in pg_sql and 'ORDER BY' in pg_sql
    assert 'school_classes' in pg_sql and 'class_groups' in pg_sql

print('PASS v4.3.20: thẻ quét từ ScanLog gốc; scope GV/lớp/môn/QR/SV; '
      'tỷ lệ chính xác; QR playlist không nhân tổng; thứ tự SQL trước phân trang; '
      'legacy class và PostgreSQL ORDER BY theo tên gọi.')
