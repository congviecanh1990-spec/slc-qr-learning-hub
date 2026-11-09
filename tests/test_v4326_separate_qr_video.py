"""Kiểm thử v4.3.26: phân biệt lượt QR thực và phiên phát video; chạy SQLite độc lập."""
import ast
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from sqlalchemy import (Boolean, Column, DateTime, Float, Integer, String,
                        and_, or_, case, func, literal, union_all, select, create_engine)
from sqlalchemy.orm import declarative_base, Session, aliased
from sqlalchemy.dialects.postgresql import dialect as pg_dialect
Base = declarative_base()

class QrCode(Base):
    __tablename__ = 'qr_codes'
    id = Column(Integer, primary_key=True)
    owner_id = Column(Integer)
    title = Column(String)
    playlist_id = Column(Integer)
    course_id = Column(Integer)

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
    estimated_watch_seconds = Column(Float)
    duration_seconds = Column(Float)

class Video(Base):
    __tablename__ = 'videos'
    id = Column(Integer, primary_key=True)
    title = Column(String)
    is_available = Column(Boolean)
    privacy_status = Column(String)
    embeddable = Column(Boolean)

class PlaylistVideo(Base):
    __tablename__ = 'playlist_videos'
    id = Column(Integer, primary_key=True)
    playlist_id = Column(Integer)
    video_id = Column(Integer)

class Student(Base):
    __tablename__ = 'students'
    id = Column(Integer, primary_key=True)
    student_code = Column(String)
    full_name = Column(String)

class Course(Base):
    __tablename__ = 'courses'
    id = Column(Integer, primary_key=True)
    name = Column(String)

class SchoolClass(Base):
    __tablename__ = 'school_classes'
    id = Column(Integer, primary_key=True)
    code = Column(String)
    name = Column(String)

class ClassGroup(Base):
    __tablename__ = 'class_groups'
    id = Column(Integer, primary_key=True)
    code = Column(String)
    course_id = Column(Integer)
    name = Column(String)

path = Path(__file__).resolve().parents[1]
source = (path/'app.py').read_text(encoding='utf8')
html = (path/'templates/analytics.html').read_text(encoding='utf8')
for phrase in ('A. Thống kê lượt quét mã QR', 'B. Thống kê hoạt động khai thác video',
               'Tổng video</div>', 'Video hoàn thành</div>', 'Số lần mở video'):
    assert phrase in html, phrase
assert 'Tổng video được thống kê' not in html
assert '<th scope="col">Số lượt quét thành công</th>' not in html
assert 'qr_rows=qr_rows' in source and 'video_metrics=video_metrics' in source
assert 'student_video_ordered_query(\n                sv_query, db.engine.dialect.name, class_index=7)' in source
names = {'student_scan_metrics', 'student_qr_breakdown_query', 'student_qr_ordered_query',
         'student_video_activity_query', 'student_video_activity_metrics',
         'student_name_sort_expr', 'student_video_ordered_query',
         'vietnamese_student_sort_key', 'valid_watch_completion_expr',
         'best_watch_started_expr', 'best_watch_completed_expr'}
nodes = [n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name in names]
assert {n.name for n in nodes} == names
engine = create_engine('sqlite:///:memory:')
Base.metadata.create_all(engine)
with Session(engine) as session:
    ns = dict(db=SimpleNamespace(session=session), ScanLog=ScanLog,
              WatchSession=WatchSession, QrCode=QrCode, Video=Video,
              PlaylistVideo=PlaylistVideo, Student=Student, Course=Course,
              SchoolClass=SchoolClass, ClassGroup=ClassGroup,
              func=func, case=case, literal=literal, union_all=union_all,
              select=select, and_=and_, or_=or_, aliased=aliased,
              managed_qr_scope=lambda uid: QrCode.owner_id == uid)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path/'app.py'), 'exec'), ns)
    st = datetime(2026,11,9,9)
    session.add_all([QrCode(id=1,owner_id=10,title='Playlist Python',playlist_id=5,course_id=1),
                     QrCode(id=2,owner_id=20,title='QR GV khác',playlist_id=6,course_id=1),
                     Course(id=1,name='Python'),
                     Student(id=1,student_code='ST01',full_name='Nguyễn Văn Bình'),
                     SchoolClass(id=1,code='A',name='Lớp A')])
    for vid in range(101,109):
        session.add(Video(id=vid,title=f'Video {vid}',is_available=True,
                          privacy_status='unlisted',embeddable=True))
        session.add(PlaylistVideo(id=vid,playlist_id=5,video_id=vid))
    session.add(Video(id=109,title='Video private',is_available=True,
                      privacy_status='private',embeddable=False))
    session.add(PlaylistVideo(id=109,playlist_id=5,video_id=109))
    # 4 lượt QR thành công; 8 video trong playlist; tất cả quét từ một SV.
    for i in range(1,5):
        session.add(ScanLog(id=i,participant_code='ST01',role='SV',class_code='A',
                            course_id=1,qr_id=1,scanned_at=st+timedelta(minutes=i),success=True))
    # Lượt quét thất bại của SV khác (không được ghép vào bảng của ST01)
    session.add(ScanLog(id=5,participant_code='ST02',role='SV',class_code='A',
                        course_id=1,qr_id=1,scanned_at=st,success=False))
    # QR của giảng viên khác, bị loại khỏi scope quản lý của GV 10
    session.add(ScanLog(id=6,participant_code='ST01',role='SV',class_code='A',
                        course_id=1,qr_id=2,scanned_at=st,success=True))
    for i,vid in enumerate(range(102,109),1):
        session.add(WatchSession(id=i,participant_code='ST01',role='SV',
            class_code='A',course_id=1,qr_id=1,video_id=vid,
            started_at=st+timedelta(hours=1,minutes=i),
            estimated_watch_seconds=95 if vid==102 else 4,
            duration_seconds=100))
    # Xem lại 3 giây video đã hoàn thành: không hạ trạng thái, tăng số phiên 102 lên 2.
    session.add(WatchSession(id=8,participant_code='ST01',role='SV',class_code='A',
        course_id=1,qr_id=1,video_id=102,started_at=st+timedelta(hours=2),
        estimated_watch_seconds=3,duration_seconds=100))
    session.flush()
    admin=SimpleNamespace(role='admin')
    gv=SimpleNamespace(role='lecturer',id=10)
    m=ns['student_scan_metrics'](gv,student_code='ST01')
    assert (m['total'],m['successful'],m['unsuccessful'],m['rate']) == (4,4,0,100.0),m
    q=ns['student_qr_breakdown_query'](gv,student_code='ST01')
    assert sum(x[4] for x in q.all()) == 4
    qsort=ns['student_qr_ordered_query'](q,'sqlite').all()
    assert len(qsort)==1 and qsort[0][4:7] == (4,4,0),qsort
    v=ns['student_video_activity_query'](gv,.95,student_code='ST01')
    metrics=ns['student_video_activity_metrics'](v)
    assert metrics == {'total':8,'viewed':7,'completed':1,'rate':12.5},metrics
    rows=ns['student_video_ordered_query'](v,'sqlite',class_index=7).all()
    assert len(rows)==8,rows
    info={r[1]:r for r in rows}
    assert info[101][3] == 0 and info[101][5] == 0
    assert info[102][3] == 2 and info[102][6] == 1 and info[102][4] == 95
    assert sum(r[3] for r in rows) == 8  # 7 video đã mở, 1 video xem lại: KHÔNG phải 8 quét QR
    assert ns['student_video_activity_query'](gv,.95,invalid_scope=True).count()==0
    assert ns['student_video_activity_query'](gv,.95,class_code='XX').count()==0
    assert ns['student_video_activity_query'](gv,.95,qr_id=2).count()==0
    assert len(ns['student_video_activity_query'](admin,.95,student_code='ST01').all()) == 8
    assert 'playlist_videos' in str(v.statement.compile(dialect=pg_dialect()))
    assert 'ORDER BY' in str(ns['student_qr_ordered_query'](q,'postgresql').statement.compile(dialect=pg_dialect()))
    # Mở cùng video qua QR thứ hai không làm tụt trạng thái QR thứ nhất.
    session.add(QrCode(id=3,owner_id=10,title='QR video khác',course_id=1))
    session.add(WatchSession(id=9,participant_code='ST01',role='SV',class_code='A',
        course_id=1,qr_id=3,video_id=101,started_at=st+timedelta(hours=4),
        estimated_watch_seconds=98,duration_seconds=100))
    session.flush()
    filtered = ns['student_video_activity_query'](gv,.95,qr_id=1,student_code='ST01')
    global_metrics = ns['student_video_activity_metrics'](filtered)
    assert global_metrics == {'total':8,'viewed':8,'completed':2,'rate':25.0},global_metrics
    video101 = next(x for x in filtered.all() if x[1] == 101)
    assert video101[3] == 1 and video101[4] == 98 and video101[6] == 1,video101
    assert ns['student_scan_metrics'](gv,qr_id=1,student_code='ST01')['total'] == 4
print('PASS v4.3.26: QR gốc 4, 8 video, 7 đã xem, 1 hoàn thành, xem lại không tụt, phân quyền và thứ tự SQL.')
