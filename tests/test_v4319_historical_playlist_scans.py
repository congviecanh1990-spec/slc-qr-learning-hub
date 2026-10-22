"""Hồi quy v4.3.19: dữ liệu playlist đã quét/xem từ những ngày trước.
Chạy độc lập PostgreSQL: python tests/test_v4319_historical_playlist_scans.py
"""
from __future__ import annotations

import ast
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from sqlalchemy import (Boolean, Column, DateTime, Float, Integer, String, create_engine,
                        select, func, and_, or_, case, literal, union_all)
from sqlalchemy.orm import declarative_base, Session, aliased
from sqlalchemy.dialects.postgresql import dialect as pg_dialect

Base = declarative_base()

class ScanLog(Base):
    __tablename__ = "scan_logs"
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
    __tablename__ = "watch_sessions"
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

class QrCode(Base):
    __tablename__ = "qr_codes"
    id = Column(Integer, primary_key=True)

class Video(Base):
    __tablename__ = "videos"
    id = Column(Integer, primary_key=True)

class Course(Base):
    __tablename__ = "courses"
    id = Column(Integer, primary_key=True)

root = Path(__file__).resolve().parents[1]
source = (root / 'app.py').read_text(encoding='utf8')
html = (root / 'templates/analytics.html').read_text(encoding='utf8')
assert 'Bảng tổng hợp <strong>mỗi sinh viên' not in html
assert '<th scope="col">Số lượt quét thành công</th>' in html
assert '<th scope="col">Số lượt quét không thành công</th>' in html
assert '<th scope="col">STT</th>' in html

names = {'student_video_summary_query', 'best_watch_completed_expr', 'best_watch_started_expr'}
funcs = [n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name in names]
assert {n.name for n in funcs} == names
engine = create_engine('sqlite:///:memory:')
Base.metadata.create_all(engine)
with Session(engine) as session:
    namespace = {'ScanLog': ScanLog, 'WatchSession': WatchSession, 'QrCode': QrCode,
                 'Course': Course, 'Video': Video, 'db': SimpleNamespace(session=session),
                 'aliased': aliased, 'select': select, 'and_': and_, 'or_': or_,
                 'func': func, 'literal': literal, 'union_all': union_all, 'case': case}
    exec(compile(ast.Module(body=funcs, type_ignores=[]), str(root/'app.py'), 'exec'), namespace)
    start = datetime(2026, 9, 20, 8, 0, 0)
    session.add_all([QrCode(id=q) for q in (1,2,3)] + [Course(id=1)] +
                    [Video(id=v) for v in (101, 102, 103, 104, 105, 200)])
    def scan(id, who, qr, day, vid=None, good=True, cls='LOP1'):
        session.add(ScanLog(id=id, participant_code=who, role='SV', class_code=cls,
                            qr_id=qr, course_id=1, video_id=vid,
                            scanned_at=start+timedelta(days=day), success=good))
    def watch(id, who, qr, vid, day, sec, cls='LOP1'):
        session.add(WatchSession(id=id, participant_code=who, role='SV', class_code=cls,
                                 qr_id=qr, course_id=1, video_id=vid,
                                 started_at=start+timedelta(days=day),
                                 duration_seconds=100, estimated_watch_seconds=sec))
    # Một lượt quét QR playlist trước đây; xem 5 video sau 3 ngày (trước đây bị đếm 0).
    scan(1, 'SV012', 1, 0)
    for index, video_id in enumerate(range(101, 106), 1):
        watch(index, 'SV012', 1, video_id, 3+index*.001, 98)
    # Một lần xem lại cùng video không làm tăng số quét.
    watch(6, 'SV012', 1, 102, 4, 10)
    # Lần quét sau, xem lại hai video.
    scan(2, 'SV012', 1, 5)
    watch(7, 'SV012', 1, 101, 5.001, 12)
    watch(8, 'SV012', 1, 102, 5.002, 11)
    # Thất bại không truy cập được playlist: chỉ hiện riêng playlist.
    scan(3, 'SV012', 1, 6, good=False)
    # SV khác cùng QR; không ảnh hưởng SV012.
    scan(4, 'SV999', 1, 1)
    watch(9, 'SV999', 1, 103, 1.001, 95)
    # QR video độc lập: ba lượt quét, 1 thất bại.
    scan(5, 'SV012', 2, 7, vid=200)
    scan(6, 'SV012', 2, 8, vid=200)
    scan(7, 'SV012', 2, 9, vid=200, good=False)
    watch(10, 'SV012', 2, 200, 8.001, 98)
    # Có phiên xem không có nhật ký quét: không suy diễn số quét giả.
    watch(11, 'SVZERO', 3, 105, 10, 98)
    # Một lượt quét chưa phát video: có hàng playlist chưa phát.
    scan(8, 'SV012', 3, 11)
    session.flush()

    q = namespace['student_video_summary_query'](SimpleNamespace(role='admin'))
    results = {(r[0], r[1]): r for r in q.all()}
    for v in range(101,106):
        expected = 2 if v in (101,102) else 1
        assert results[('SV012',v)][3] == expected, (v, results[('SV012',v)])
        assert results[('SV012',v)][4] == 0
        assert results[('SV012',v)][5] == 98
    assert (results[('SV012',-1)][3], results[('SV012',-1)][4]) == (0,1)
    assert (results[('SV012',200)][3], results[('SV012',200)][4]) == (2,1)
    assert results[('SV999',103)][3] == 1
    assert results[('SVZERO',105)][3] == 0
    assert results[('SV012',-3)][3] == 1
    assert len(results) == 10, sorted(results)
    # Mỗi ScanLog.id trong DB là MỘT lượt toàn hệ thống, không đổi dù 5 video cùng QR.
    assert session.query(ScanLog).filter(ScanLog.success.is_(True)).count() == 6
    assert session.query(ScanLog).filter(ScanLog.success.is_(False)).count() == 2
    # Scope không lẫn giữa QR, lớp, SV.
    playlist = namespace['student_video_summary_query'](SimpleNamespace(role='admin'),qr_id=1)
    assert len(playlist.all()) == 7
    direct = namespace['student_video_summary_query'](SimpleNamespace(role='admin'),qr_id=2)
    assert [(r[0],r[1],r[3],r[4]) for r in direct] == [('SV012',200,2,1)]
    assert namespace['student_video_summary_query'](SimpleNamespace(role='admin'),invalid_scope=True).count() == 0
    assert namespace['student_video_summary_query'](SimpleNamespace(role='admin'),class_code='KHAC').count() == 0
    # Quyền GV chỉ thấy QR được quản lý; không nhân JOIN bản ghi của GV khác.
    namespace['managed_qr_scope'] = lambda uid: QrCode.id == 1
    scoped = namespace['student_video_summary_query'](SimpleNamespace(role='lecturer',id=77))
    assert {(r[0],r[1]) for r in scoped.all()} == {(r[0],r[1]) for r in playlist.all()}
    # SQL tạo được cho PostgreSQL (production); dữ liệu live vẫn cần kiểm chứng riêng.
    sql = str(q.statement.compile(dialect=pg_dialect()))
    assert 'lead(' in sql.lower() and 'scan_video_links' in sql
    print('PASS v4.3.19: 5 video lịch sử gắn đúng lượt quét QR playlist; '
          'xem lại không nhân lượt; đã hoàn thành vẫn hoàn thành; '
          'SV/QR khác tách biệt; thất bại/nhật ký gốc chính xác; SQL PostgreSQL hợp lệ.')
