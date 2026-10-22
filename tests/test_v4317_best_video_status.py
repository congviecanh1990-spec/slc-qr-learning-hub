"""v4.3.17 – Trạng thái tốt nhất SV–video và số lượt quét độc lập.
Kiểm thử SQL trên SQLite độc lập Flask/Render; query dùng cùng helper với app.py.
"""
from __future__ import annotations
import ast
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from sqlalchemy import (Boolean, Column, Float, Integer, String, DateTime, create_engine,
                        select, func, and_, or_, case)
from sqlalchemy.orm import declarative_base, Session, aliased

root = Path(__file__).resolve().parents[1]
source = (root / 'app.py').read_text(encoding='utf8')

Base = declarative_base()
class WatchSession(Base):
    __tablename__ = 'watch_sessions'
    id = Column(Integer, primary_key=True)
    participant_code = Column(String, nullable=False)
    role = Column(String, nullable=False)
    video_id = Column(Integer)
    qr_id = Column(Integer)
    estimated_watch_seconds = Column(Float, nullable=False, default=0)
    duration_seconds = Column(Float, nullable=False, default=0)
    completed = Column(Boolean, nullable=False, default=False)

class ScanLog(Base):
    __tablename__ = 'scan_logs'
    id = Column(Integer, primary_key=True)
    participant_code = Column(String, nullable=False)
    role = Column(String, nullable=False)
    qr_id = Column(Integer)
    video_id = Column(Integer)
    success = Column(Boolean)
    scanned_at = Column(DateTime)

engine = create_engine('sqlite:///:memory:')
Base.metadata.create_all(engine)
names = {'valid_watch_completion_expr', 'best_watch_completed_expr',
         'best_watch_started_expr', 'best_video_statuses'}
tree = ast.parse(source)
body = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
assert {n.name for n in body} == names
ns = {'WatchSession': WatchSession, 'aliased': aliased, 'select': select, 'func': func,
      'and_': and_, 'or_': or_, 'case': case}
exec(compile(ast.Module(body=body, type_ignores=[]), str(root / 'app.py'), 'exec'), ns)
THRESHOLD = .95

with Session(engine) as session:
    ns['db'] = SimpleNamespace(session=session)
    def log(student, video, nr):
        session.add(ScanLog(participant_code=student, role='SV', qr_id=1,
                            video_id=video, success=True,
                            scanned_at=datetime(2026,10,22,9,nr)))
    def view(student, video, seconds, duration=100, completed=False, qr=1):
        session.add(WatchSession(participant_code=student, role='SV', video_id=video,
                                 qr_id=qr, estimated_watch_seconds=seconds,
                                 duration_seconds=duration, completed=completed))
    def finish(student, video):
        return bool(session.scalar(select(ns['best_watch_completed_expr'](student,video,THRESHOLD))))
    def started(student, video):
        return bool(session.scalar(select(ns['best_watch_started_expr'](student,video))))
    def best(student, video):
        return ns['best_video_statuses']([(student,video)],THRESHOLD).get((student,video),'Chưa xem')
    def filter_ids(kind):
        done = ns['best_watch_completed_expr'](ScanLog.participant_code, ScanLog.video_id, THRESHOLD)
        started = ns['best_watch_started_expr'](ScanLog.participant_code, ScanLog.video_id)
        expr = done if kind=='completed' else (started & ~done if kind=='not_completed' else ~started)
        return list(session.scalars(select(ScanLog.id).where(expr)))
    # 1. Quét nhưng chưa xem; báo Chưa xem.
    log('SV1',10,1)
    session.flush()
    assert not started('SV1',10) and not finish('SV1',10)
    assert best('SV1',10)=='Chưa xem' and len(filter_ids('unwatched'))==1
    # 2. Quét lần hai, xem đủ >95%, thành Hoàn thành.
    log('SV1',10,2); view('SV1',10,98)
    session.flush()
    assert finish('SV1',10) and best('SV1',10)=='Hoàn thành'
    assert len(filter_ids('completed'))==2 and filter_ids('not_completed')==[]
    # 3. Quét lần ba xem một đoạn; vẫn Hoàn thành, nhưng lưu thời gian riêng.
    log('SV1',10,3); view('SV1',10,8)
    session.flush()
    assert finish('SV1',10) and len(filter_ids('completed'))==3
    assert session.scalar(select(func.count(ScanLog.id))) == 3
    assert session.scalar(select(func.count(ScanLog.id)).where(ScanLog.success.is_(True))) == 3
    assert session.scalar(select(func.count(WatchSession.id))) == 2
    # 4. Hai lần chưa đủ 95% không được cộng khống (dù tổng >95%).
    log('SV2',10,4); view('SV2',10,60)
    log('SV2',10,5); view('SV2',10,60)
    session.flush()
    assert best('SV2',10)=='Chưa hoàn thành' and len(filter_ids('not_completed'))==2
    # 5. Xem đủ lần tiếp theo -> Hoàn thành. Cả các log trước đều có trạng thái tốt nhất.
    log('SV2',10,6); view('SV2',10,97)
    session.flush()
    assert best('SV2',10)=='Hoàn thành' and filter_ids('not_completed')==[]
    # 6. Playlist: hoàn thành video 10 không đồng nghĩa video 20 hoàn thành.
    view('SV1',20,40)
    view('SV1',21,0,completed=True) # cờ cũ không có chứng cứ thời gian
    session.flush()
    assert best('SV1',20)=='Chưa hoàn thành'
    assert best('SV1',21)=='Chưa xem'
    assert not finish('SV1',20) and not finish('SV1',21)
    # 7. QR khác cùng video, cùng SV: kết quả tốt nhất không mất.
    view('SV1',10,5,qr=2)
    session.flush()
    assert best('SV1',10)=='Hoàn thành'
    # 8. SV khác cùng video không hưởng trạng thái của SV1.
    log('SV3',10,7)
    session.flush()
    assert best('SV3',10)=='Chưa xem'
    assert 'SV3' not in [student for (student, vid), result in
                         ns['best_video_statuses']([('SV1',10),('SV3',10)],THRESHOLD).items()
                         if result=='Hoàn thành']
    # 9. Kiểm tra tỷ lệ theo cặp SV-video, không theo số phiên.
    all_pairs = session.query(WatchSession.participant_code,WatchSession.video_id).distinct().subquery()
    finished_pairs = (session.query(all_pairs.c.participant_code)
                      .filter(ns['best_watch_completed_expr'](
                          all_pairs.c.participant_code,all_pairs.c.video_id,THRESHOLD)).count())
    assert finished_pairs==2,finished_pairs  # SV1-video10, SV2-video10
    print('PASS v4.3.17: quét độc lập, đạt 95%, trạng thái tăng một chiều, playlist, bộ lọc, cờ cũ, QR khác, tỷ lệ SV–video')

assert '"session_completed": ws.completed' in source
assert '"completed": bool(best_completed)' in source
assert 'student_viewer=(role == "SV")' in source
assert 'best_video_statuses(' in source
assert 'CREATE INDEX IF NOT EXISTS ix_watch_sessions_best_video' in source
print('PASS: API, số liệu, chỉ mục, giao diện SV cập nhật thành tích tốt nhất')
