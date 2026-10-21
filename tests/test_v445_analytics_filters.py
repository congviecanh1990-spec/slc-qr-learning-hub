"""v4.3.15: Kiểm tra bộ lọc SV, trạng thái xem và playlist bằng SQLAlchemy/SQLite.
Không cần Flask, PostgreSQL hoặc OAuth. Chạy: python tests/test_v445_analytics_filters.py.
"""
from __future__ import annotations
import ast
from datetime import datetime, timedelta
from pathlib import Path
from sqlalchemy import (Column, Integer, String, Float, Boolean, DateTime,
                        and_, or_, select, union_all, literal, func, create_engine)
from sqlalchemy.orm import declarative_base, aliased, Session

root = Path(__file__).resolve().parents[1]
source = (root / 'app.py').read_text(encoding='utf-8')
html = (root / 'templates/analytics.html').read_text(encoding='utf-8')
assert 'name="student_id"' in html
assert 'name="sv_period"' not in html
assert 'student_code_tail(st.student_code)' in html
assert "('not_completed','Chưa hoàn thành')" in html
assert "('roster_not_completed','SV chưa hoàn thành học liệu (đối chiếu lớp)')" in html
assert 'incomplete_watch_expr(current_app.config["COMPLETION_THRESHOLD"])' in source
assert 'status in {"not_scanned", "roster_not_completed"}' in source
assert 'selected_student_code' in source
assert 'func.coalesce(ScanLog.participant_code, WatchSession.participant_code) == selected_student_code' in source

Base = declarative_base()
class ScanLog(Base):
    __tablename__ = 'scan_logs'
    id = Column(Integer, primary_key=True)
    participant_code = Column(String)
    class_code = Column(String)
    role = Column(String)
    qr_id = Column(Integer)
    scanned_at = Column(DateTime)
    success = Column(Boolean)
class WatchSession(Base):
    __tablename__ = 'watch_sessions'
    id = Column(Integer, primary_key=True)
    qr_id = Column(Integer)
    participant_code = Column(String)
    class_code = Column(String)
    role = Column(String)
    started_at = Column(DateTime)
    estimated_watch_seconds = Column(Float)
    duration_seconds = Column(Float)
class QrCode(Base):
    __tablename__ = 'qr_codes'
    id = Column(Integer, primary_key=True)
    owner_id = Column(Integer)

# Dùng đúng biểu thức SQL từ mã nguồn v4.3.15.
tree = ast.parse(source)
names = {'incomplete_watch_expr', 'valid_watch_completion_expr', 'watch_status_label',
         'safe_watch_number', 'valid_watch_completion'}
functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
assert len(functions) == len(names)
ns = {'and_': and_, 'or_': or_, 'func': func, 'WatchSession': WatchSession,
      'math': __import__('math')}
exec(compile(ast.Module(body=functions,type_ignores=[]),str(root/'app.py'),'exec'),ns)

stamp = datetime(2026,10,20,10)
engine = create_engine('sqlite:///:memory:')
Base.metadata.create_all(engine)
with Session(engine) as db:
    db.add_all([
        QrCode(id=1,owner_id=1),
        # Một lượt quét QR playlist, nhưng hai video với trạng thái khác nhau.
        ScanLog(id=1,qr_id=1,participant_code='SV-000125',class_code='L1',role='SV',
                scanned_at=stamp,success=True),
        WatchSession(id=11,qr_id=1,participant_code='SV-000125',class_code='L1',role='SV',
                     started_at=stamp+timedelta(seconds=5),estimated_watch_seconds=230,duration_seconds=335),
        WatchSession(id=12,qr_id=1,participant_code='SV-000125',class_code='L1',role='SV',
                     started_at=stamp+timedelta(seconds=10),estimated_watch_seconds=320,duration_seconds=335),
        # Quét rồi chưa xem -> chỉ xuất hiện ở Chưa xem, không phải Chưa hoàn thành.
        ScanLog(id=2,qr_id=1,participant_code='SV-000026',class_code='L1',role='SV',
                scanned_at=stamp+timedelta(minutes=1),success=True),
        # Sinh viên đã xem nhưng thời lượng video không xác định -> chưa hoàn thành.
        WatchSession(id=13,qr_id=1,participant_code='SV-000026',class_code='L1',role='SV',
                     started_at=stamp+timedelta(minutes=1,seconds=5),estimated_watch_seconds=140,duration_seconds=0),
        # Không nhầm bản ghi của lớp khác với người đã xem.
        ScanLog(id=3,qr_id=1,participant_code='SV-000999',class_code='L1',role='SV',
                scanned_at=stamp+timedelta(minutes=2),success=True),
        WatchSession(id=14,qr_id=1,participant_code='SV-000999',class_code='L1',role='SV',
                     started_at=stamp+timedelta(minutes=2,seconds=4),estimated_watch_seconds=0,duration_seconds=335),
        # Dữ liệu lịch sử orphan cũng phải hiện.
        WatchSession(id=15,qr_id=1,participant_code='SV-000777',class_code='L1',role='SV',
                     started_at=stamp+timedelta(minutes=4),estimated_watch_seconds=30,duration_seconds=335),
    ])
    db.commit()
    ref = aliased(ScanLog)
    nearest = (select(ref.id).where(
        ref.role=='SV', ref.qr_id==WatchSession.qr_id,
        ref.participant_code==WatchSession.participant_code,
        or_(ref.class_code==WatchSession.class_code,
            and_(ref.class_code.is_(None),WatchSession.class_code.is_(None))),
        ref.scanned_at<=WatchSession.started_at,
        ref.scanned_at>=WatchSession.started_at-timedelta(days=1),
    ).order_by(ref.scanned_at.desc(),ref.id.desc()).limit(1)
     .correlate(WatchSession).scalar_subquery())
    scan_events = (select(ScanLog.id.label('scan_id'), WatchSession.id.label('watch_id'))
                   .select_from(ScanLog).outerjoin(WatchSession,
                   and_(WatchSession.role=='SV',nearest==ScanLog.id))
                   .join(QrCode,ScanLog.qr_id==QrCode.id).where(ScanLog.role=='SV'))
    orphan_events = (select(literal(None).label('scan_id'),WatchSession.id.label('watch_id'))
                     .select_from(WatchSession).outerjoin(ScanLog,ScanLog.id==nearest)
                     .join(QrCode,WatchSession.qr_id==QrCode.id)
                     .where(WatchSession.role=='SV',ScanLog.id.is_(None)))
    events = union_all(scan_events,orphan_events).subquery()
    q = (db.query(events.c.scan_id,events.c.watch_id,ScanLog.participant_code,
                  WatchSession.participant_code)
         .select_from(events).outerjoin(ScanLog,ScanLog.id==events.c.scan_id)
         .outerjoin(WatchSession,WatchSession.id==events.c.watch_id)
         .filter(ns['incomplete_watch_expr'](0.95)))
    rows = q.all()
    assert {r.watch_id for r in rows} == {11,13,15}, rows
    assert db.query(events.c.scan_id).count() == 5, 'Playlist chỉ có một lượt quét nhưng nhiều video.'
    students_filtered = q.filter(func.coalesce(ScanLog.participant_code,WatchSession.participant_code)=='SV-000125').all()
    assert [r.watch_id for r in students_filtered] == [11], students_filtered
    assert ns['watch_status_label'](db.get(WatchSession,11),0.95) == 'Chưa hoàn thành'
    assert ns['watch_status_label'](db.get(WatchSession,12),0.95) == 'Hoàn thành'
    assert ns['watch_status_label'](db.get(WatchSession,14),0.95) == 'Chưa xem'
    print('PASS v4.3.15: lọc chưa hoàn thành <95%, lọc SV, nhiều video playlist, phiên orphan, không nhầm chưa xem')
