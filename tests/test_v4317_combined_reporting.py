"""Kiểm thử JOIN nhật ký và bộ lọc trạng thái tốt nhất trên SQLite."""
from pathlib import Path
from datetime import datetime, timedelta
from sqlalchemy import (Column,Integer,String,DateTime,Float,Boolean,create_engine,
                        select,or_,and_,func,literal,union_all)
from sqlalchemy.orm import declarative_base,Session,aliased
import ast

Base=declarative_base()
class ScanLog(Base):
    __tablename__='scan_logs'
    id=Column(Integer,primary_key=True)
    qr_id=Column(Integer)
    video_id=Column(Integer)
    participant_code=Column(String)
    class_code=Column(String)
    role=Column(String)
    scanned_at=Column(DateTime)
    success=Column(Boolean)
class WatchSession(Base):
    __tablename__='watch_sessions'
    id=Column(Integer,primary_key=True)
    qr_id=Column(Integer)
    video_id=Column(Integer)
    participant_code=Column(String)
    class_code=Column(String)
    role=Column(String)
    started_at=Column(DateTime)
    duration_seconds=Column(Float)
    estimated_watch_seconds=Column(Float)
class QrCode(Base):
    __tablename__='qr_codes'
    id=Column(Integer,primary_key=True)

p=Path(__file__).resolve().parents[1]
root=ast.parse((p/'app.py').read_text(encoding='utf8'))
funcs=[n for n in root.body if isinstance(n,ast.FunctionDef) and n.name in
       {'valid_watch_completion_expr','best_watch_completed_expr','best_watch_started_expr'}]
ns={'and_':and_,'select':select,'aliased':aliased,'WatchSession':WatchSession}
exec(compile(ast.Module(body=funcs,type_ignores=[]),str(p/'app.py'),'exec'),ns)
engine=create_engine('sqlite:///:memory:')
Base.metadata.create_all(engine)
at=datetime(2026,10,22,10)
with Session(engine) as ses:
    ses.add_all([
        QrCode(id=1),QrCode(id=2),
        ScanLog(id=1, qr_id=1,video_id=10,participant_code='SV1',class_code='L1',role='SV',success=True,scanned_at=at),
        ScanLog(id=2, qr_id=1,video_id=10,participant_code='SV1',class_code='L1',role='SV',success=True,scanned_at=at+timedelta(minutes=3)),
        ScanLog(id=3, qr_id=1,video_id=10,participant_code='SV1',class_code='L1',role='SV',success=True,scanned_at=at+timedelta(minutes=6)),
        WatchSession(id=11, qr_id=1,video_id=10,participant_code='SV1',class_code='L1',role='SV',started_at=at+timedelta(minutes=3,seconds=5),duration_seconds=100,estimated_watch_seconds=99),
        WatchSession(id=12, qr_id=1,video_id=10,participant_code='SV1',class_code='L1',role='SV',started_at=at+timedelta(minutes=6,seconds=5),duration_seconds=100,estimated_watch_seconds=13),
        ScanLog(id=4, qr_id=2,video_id=None,participant_code='SV2',class_code='L1',role='SV',success=True,scanned_at=at+timedelta(minutes=9)),
        WatchSession(id=13, qr_id=2,video_id=20,participant_code='SV2',class_code='L1',role='SV',started_at=at+timedelta(minutes=9,seconds=6),duration_seconds=100,estimated_watch_seconds=98),
        WatchSession(id=14, qr_id=2,video_id=21,participant_code='SV2',class_code='L1',role='SV',started_at=at+timedelta(minutes=9,seconds=8),duration_seconds=100,estimated_watch_seconds=24),
        ScanLog(id=5, qr_id=1,video_id=10,participant_code='SV3',class_code='L1',role='SV',success=True,scanned_at=at+timedelta(minutes=10)),
    ])
    ses.flush()
    scan_ref=aliased(ScanLog)
    closest_scan_id=(select(scan_ref.id).where(
        scan_ref.role=='SV',scan_ref.qr_id==WatchSession.qr_id,
        scan_ref.participant_code==WatchSession.participant_code,
        or_(scan_ref.class_code==WatchSession.class_code,
            and_(scan_ref.class_code.is_(None),WatchSession.class_code.is_(None))),
        scan_ref.scanned_at<=WatchSession.started_at,
        scan_ref.scanned_at>=WatchSession.started_at-timedelta(days=1))
        .order_by(scan_ref.scanned_at.desc(),scan_ref.id.desc()).limit(1)
        .correlate(WatchSession).scalar_subquery())
    scans=(select(ScanLog.id.label('scan_id'), WatchSession.id.label('watch_id'))
           .select_from(ScanLog).outerjoin(WatchSession,and_(WatchSession.role=='SV',closest_scan_id==ScanLog.id))
           .join(QrCode,ScanLog.qr_id==QrCode.id).where(ScanLog.role=='SV'))
    orphans=(select(literal(None).label('scan_id'),WatchSession.id.label('watch_id'))
             .select_from(WatchSession).outerjoin(ScanLog,ScanLog.id==closest_scan_id)
             .join(QrCode,WatchSession.qr_id==QrCode.id)
             .where(WatchSession.role=='SV',ScanLog.id.is_(None)))
    events=union_all(scans,orphans).subquery('sv_events')
    q=(ses.query(events.c.scan_id,events.c.watch_id)
       .select_from(events).outerjoin(ScanLog,ScanLog.id==events.c.scan_id)
       .outerjoin(WatchSession,WatchSession.id==events.c.watch_id))
    student_expr=func.coalesce(ScanLog.participant_code,WatchSession.participant_code)
    video_expr=func.coalesce(WatchSession.video_id,ScanLog.video_id)
    done=ns['best_watch_completed_expr'](student_expr,video_expr,.95)
    started=ns['best_watch_started_expr'](student_expr,video_expr)
    rows=q.all()
    assert len(rows)==6,rows  # SV1 3 scans + playlist 2 videos + SV3 1 scan
    completed=q.filter(done).all()
    assert {(r.scan_id,r.watch_id) for r in completed}=={(1,None),(2,11),(3,12),(4,13)},completed
    incomplete=q.filter(started,~done).all()
    assert {(r.scan_id,r.watch_id) for r in incomplete}=={(4,14)},incomplete
    unwatched=q.filter(ScanLog.success.is_(True),~started).all()
    assert {(r.scan_id,r.watch_id) for r in unwatched}=={(5,None)},unwatched
    assert ses.query(ScanLog).filter(ScanLog.success.is_(True)).count()==5
    print('PASS combined reporting: 5 lượt quét thành công; 6 dòng chi tiết; 4 hoàn thành, 1 chưa hoàn thành, 1 chưa xem')
