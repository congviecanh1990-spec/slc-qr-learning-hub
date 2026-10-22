"""SQL thực (SQLite) cho bảng tổng hợp v4.3.18, không cần Flask hay Render."""
from pathlib import Path
from datetime import datetime, timedelta
from types import SimpleNamespace
import ast
from sqlalchemy import (create_engine, Column, Integer, String, DateTime, Float, Boolean,
                        select, and_, or_, case, func, literal, union_all)
from sqlalchemy.orm import declarative_base, Session, aliased

Base=declarative_base()
class ScanLog(Base):
    __tablename__='scan_logs'
    id=Column(Integer,primary_key=True)
    participant_code=Column(String)
    role=Column(String)
    class_code=Column(String)
    course_id=Column(Integer)
    qr_id=Column(Integer)
    video_id=Column(Integer)
    scanned_at=Column(DateTime)
    success=Column(Boolean)
class WatchSession(Base):
    __tablename__='watch_sessions'
    id=Column(Integer,primary_key=True)
    participant_code=Column(String)
    role=Column(String)
    class_code=Column(String)
    course_id=Column(Integer)
    qr_id=Column(Integer)
    video_id=Column(Integer)
    started_at=Column(DateTime)
    duration_seconds=Column(Float)
    estimated_watch_seconds=Column(Float)
class QrCode(Base):
    __tablename__='qr_codes'
    id=Column(Integer,primary_key=True)
class Video(Base):
    __tablename__='videos'
    id=Column(Integer,primary_key=True)
class Course(Base):
    __tablename__='courses'
    id=Column(Integer,primary_key=True)

root=Path(__file__).resolve().parents[1]
source=(root/'app.py').read_text(encoding='utf8')
names={'student_video_summary_query','best_watch_completed_expr','best_watch_started_expr'}
funcs=[n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name in names]
assert {n.name for n in funcs}==names
engine=create_engine('sqlite:///:memory:')
Base.metadata.create_all(engine)
with Session(engine) as session:
    ns={'ScanLog':ScanLog,'WatchSession':WatchSession,'QrCode':QrCode,
        'Course':Course,'Video':Video,'db':SimpleNamespace(session=session),
        'aliased':aliased,'select':select,'and_':and_,'or_':or_,
        'func':func,'literal':literal,'union_all':union_all,
        'case':case,'timedelta':timedelta}
    exec(compile(ast.Module(body=funcs,type_ignores=[]),str(root/'app.py'),'exec'),ns)
    at=datetime(2026,10,22,8)
    session.add_all([QrCode(id=n) for n in (1,2,3,4)]+[Video(id=n) for n in (10,20,21)]+[Course(id=1)])
    def scan(id,who,qr,video,minutes,success=True,course=1,cls='L1',role='SV'):
        session.add(ScanLog(id=id,participant_code=who,role=role,class_code=cls,
                            course_id=course,qr_id=qr,video_id=video,
                            scanned_at=at+timedelta(minutes=minutes),success=success))
    def watch(id,who,qr,video,minutes,watched,duration=100,course=1,cls='L1',role='SV'):
        session.add(WatchSession(id=id,participant_code=who,role=role,class_code=cls,
                                 course_id=course,qr_id=qr,video_id=video,
                                 started_at=at+timedelta(minutes=minutes),
                                 estimated_watch_seconds=watched,duration_seconds=duration))
    # Một SV-video có 3 lượt mở thành công, 1 thất bại, 2 phiên, xem lại 10s.
    scan(1,'SV-A',1,10,0)
    scan(2,'SV-A',1,10,5)
    watch(1,'SV-A',1,10,6,98)
    scan(3,'SV-A',1,10,10)
    watch(2,'SV-A',1,10,11,10)
    scan(4,'SV-A',1,10,15,False)
    # Khác SV, cùng video (không được gộp với SV-A).
    scan(5,'SV-B',1,10,0)
    # Playlist: 1 lần mở, 2 video, chỉ video đầu tiên nhận 1 lượt quét.
    scan(6,'SV-A',2,None,25)
    watch(3,'SV-A',2,20,26,96)
    watch(4,'SV-A',2,21,27,30)
    # Playlist chưa phát: giữ 1 dòng chưa phát, không gán bừa cho video.
    scan(7,'SV-A',3,None,30)
    # Thất bại với playlist không phát video.
    scan(8,'SV-A',4,None,32,False)
    # Mở lại video20 từ mã khác, kết quả tốt nhất vẫn hoàn thành.
    scan(9,'SV-A',1,20,40)
    watch(5,'SV-A',1,20,41,12)
    # Phiên xem không có ScanLog (giữ video được xem, 0 lượt quét).
    watch(6,'SV-C',1,10,45,20)
    # Không tính lịch sử giảng viên vào báo cáo sinh viên.
    scan(10,'GV',1,10,46,role='GV')
    session.flush()
    user=SimpleNamespace(role='admin')
    query=ns['student_video_summary_query'](user)
    entries={(r[0],r[1]): r for r in query.all()}
    assert len(entries)==7,[(k,r[3],r[4]) for k,r in entries.items()]
    assert (entries[('SV-A',10)][3],entries[('SV-A',10)][4],entries[('SV-A',10)][5])==(3,1,98),entries[('SV-A',10)]
    assert (entries[('SV-A',20)][3],entries[('SV-A',20)][4],entries[('SV-A',20)][5])==(2,0,96),entries[('SV-A',20)]
    assert (entries[('SV-A',21)][3],entries[('SV-A',21)][4],entries[('SV-A',21)][5])==(0,0,30),entries[('SV-A',21)]
    assert (entries[('SV-A',-3)][3],entries[('SV-A',-3)][4])==(1,0)
    assert (entries[('SV-A',-4)][3],entries[('SV-A',-4)][4])==(0,1)
    assert (entries[('SV-B',10)][3],entries[('SV-B',10)][4])==(1,0)
    assert (entries[('SV-C',10)][3],entries[('SV-C',10)][4],entries[('SV-C',10)][5])==(0,0,20)
    assert sum(r[3] for r in entries.values())==7
    assert sum(r[4] for r in entries.values())==2
    # Video completed khi có 1 phiên >=95%, không tụt khi xem lại.
    for pair,expect in [(('SV-A',10),True),(('SV-A',20),True),(('SV-A',21),False),(('SV-B',10),False)]:
        code,vid=pair
        assert bool(session.scalar(select(ns['best_watch_completed_expr'](code,vid,.95)))) is expect
    # Lọc môn/lớp/QR/SV tiến hành trước nhóm để không lẫn lịch sử khác phạm vi.
    assert len(ns['student_video_summary_query'](user,qr_id=2).all())==2
    assert len(ns['student_video_summary_query'](user,student_code='SV-B').all())==1
    assert ns['student_video_summary_query'](user,invalid_scope=True).count()==0
    assert ns['student_video_summary_query'](user,class_code='OTHER').count()==0
    assert ns['student_video_summary_query'](user,course_id=222).count()==0
    # Đếm, phân trang và bộ lọc trạng thái sử dụng nhóm chứ không xem từng phiên.
    q=ns['student_video_summary_query'](user)
    cols=q.column_descriptions
    code,vid,latest,success_count,fail_count=[cols[i]['expr'] for i in range(5)]
    completed=ns['best_watch_completed_expr'](code,vid,.95)
    started=ns['best_watch_started_expr'](code,vid)
    assert {(r[0],r[1]) for r in q.filter(completed).all()}=={('SV-A',10),('SV-A',20)}
    assert {(r[0],r[1]) for r in q.filter(vid>0,started,~completed).all()}=={('SV-A',21),('SV-C',10)}
    assert {(r[0],r[1]) for r in q.filter(fail_count>0).all()}=={('SV-A',10),('SV-A',-4)}
    assert len(q.order_by(latest.desc()).offset(0).limit(3).all())==3
    assert len(q.order_by(latest.desc()).offset(3).limit(3).all())==3
    print('PASS v4.3.18: 7 dòng SV–video/playlist; 7 lượt thành công, 2 lượt thất bại; playlist không nhân lượt; lọc/trạng thái/phân trang đạt')
