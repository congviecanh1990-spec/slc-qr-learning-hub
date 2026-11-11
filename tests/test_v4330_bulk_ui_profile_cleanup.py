"""Kiểm tra cấp mã nguồn v4.3.30, không cần Google/Render production."""
import ast
from pathlib import Path
import sys
import types
from datetime import date

import sqlalchemy as sa
from sqlalchemy.orm import declarative_base, relationship, backref, sessionmaker
from sqlalchemy import event
from jinja2 import Environment, FileSystemLoader

ROOT=Path(__file__).resolve().parents[1]
assert (ROOT/'VERSION.txt').read_text().strip()=='4.3.30'
sys.path.insert(0,str(ROOT))

class SQLAlchemy:
    def __init__(self):
        self.Model=declarative_base()
        for x in ('Column','Integer','String','Text','Date','DateTime','Boolean','Float','ForeignKey'):
            setattr(self,x,getattr(sa,x))
        self.relationship=relationship
        self.backref=backref
sys.modules['flask_sqlalchemy']=types.SimpleNamespace(SQLAlchemy=SQLAlchemy)
import models as m
engine=sa.create_engine('sqlite:///:memory:')
@event.listens_for(engine,'connect')
def pragma_on(conn, _):
    conn.execute('PRAGMA foreign_keys=ON')
m.db.Model.metadata.create_all(engine)
m.db.session=sessionmaker(bind=engine)()
s=m.db.session
class Query:
    def __get__(self, obj, cls): return m.db.session.query(cls)
for mp in m.db.Model.registry.mappers: mp.class_.query=Query()

u1=m.User(email='delete@example.test',name='Xóa GV',role='lecturer',faculty_name='Khoa A',department_name='Bộ môn X')
u2=m.User(email='keep@example.test',name='GV khác',role='lecturer')
s.add_all([u1,u2]); s.flush()
c1=m.Course(owner_id=u1.id,code='C1',name='Môn xóa',active=True)
c2=m.Course(owner_id=u2.id,code='C2',name='Môn chung',active=True)
s.add_all([c1,c2]);s.flush()
cl1=m.SchoolClass(code='L1',name='Lớp riêng',homeroom_teacher_id=u1.id,active=True)
cl2=m.SchoolClass(code='L2',name='Lớp chung',active=True)
s.add_all([cl1,cl2]);s.flush()
s.add_all([
    m.CourseClass(course_id=c1.id,school_class_id=cl1.id,active=True),
    m.CourseClass(course_id=c1.id,school_class_id=cl2.id,active=True),
    m.CourseClass(course_id=c2.id,school_class_id=cl2.id,active=True)])
st1=m.Student(student_code='SV1',full_name='Riêng');st2=m.Student(student_code='SV2',full_name='Chung')
s.add_all([st1,st2]);s.flush()
s.add_all([m.ClassEnrollment(school_class_id=cl1.id,student_id=st1.id,started_on=date(2026,1,1)),
           m.ClassEnrollment(school_class_id=cl2.id,student_id=st2.id,started_on=date(2026,1,1))])
ch=m.YouTubeChannel(user_id=u1.id,channel_id='youtube1',title='Kênh cần xóa')
s.add(ch);s.flush()
p=m.Playlist(channel_id=ch.id,youtube_playlist_id='PL101',title='Playlist lớp')
v=m.Video(channel_id=ch.id,youtube_video_id='VID101',title='Bài giảng',embeddable=True,is_available=True)
s.add_all([p,v]);s.flush()
s.add(m.PlaylistVideo(playlist_id=p.id,video_id=v.id,position=0))
q=m.QrCode(owner_id=u1.id,course_id=c1.id,playlist_id=p.id,target_type='playlist',slug='testslug',title='QR',active=True)
s.add(q);s.flush()
s.add(m.CoursePlaylist(course_id=c1.id,playlist_id=p.id,qr_id=q.id))
s.add(m.CourseVideo(course_id=c1.id,video_id=v.id))
s.add(m.ScanLog(participant_code='SV1',class_code=cl1.code,role='SV',course_id=c1.id,qr_id=q.id,video_id=v.id,success=True))
w=m.WatchSession(session_key='fake_session',participant_code='SV1',class_code=cl1.code,role='SV',course_id=c1.id,qr_id=q.id,video_id=v.id)
s.add(w);s.flush()
s.add(m.WatchEvent(watch_session_id=w.id,event_type='play',position=1,duration=30))
s.add(m.ErrorLog(module='youtube',actor_user_id=u1.id,actor_email=u1.email,message='Lỗi cũ'))
s.add(m.FunctionalTestRun(owner_id=u1.id,case_code='YT_SYNC',case_name='Đồng bộ',passed=False))
s.commit()

c1id=c1.id; c2id=c2.id; cl1id=cl1.id; cl2id=cl2.id; st1id=st1.id; st2id=st2.id; qid=q.id; chid=ch.id

astmod=ast.parse((ROOT/'app.py').read_text())
node=next(n for n in ast.walk(astmod) if isinstance(n,ast.FunctionDef) and n.name=='delete_lecturer_business_data')
clone=ast.FunctionDef(name=node.name,args=node.args,body=node.body,decorator_list=[],returns=node.returns,type_comment=None)
ns={**{name:getattr(m,name) for name in vars(m) if isinstance(getattr(m,name),type)},'db':m.db,'or_':sa.or_, 'func':sa.func}
exec(compile(ast.fix_missing_locations(ast.Module(body=[clone],type_ignores=[])),'app.py','exec'),ns)
result=ns['delete_lecturer_business_data'](u1)
assert result=={'courses':1,'qrs':1,'classes':1},result
assert m.Course.query.filter_by(id=c1id).count()==0
assert m.QrCode.query.filter_by(id=qid).count()==0
assert m.WatchSession.query.count()==0
assert m.WatchEvent.query.count()==0
assert m.ScanLog.query.count()==0
assert m.SchoolClass.query.filter_by(id=cl1id).count()==0
assert m.Student.query.filter_by(id=st1id).count()==0
assert m.SchoolClass.query.filter_by(id=cl2id).count()==1
assert m.Student.query.filter_by(id=st2id).count()==1
assert m.Course.query.filter_by(id=c2id).count()==1
assert m.YouTubeChannel.query.filter_by(id=chid).count()==0
# Tiếp tục xóa tài khoản + nhật ký xác thực, mô phỏng transaction của route quản trị.
uid=u1.id
m.FunctionalTestRun.query.filter_by(owner_id=uid).delete(synchronize_session=False)
m.ErrorLog.query.filter(sa.or_(m.ErrorLog.actor_user_id == uid,
                               sa.func.lower(m.ErrorLog.actor_email) == u1.email.casefold())).delete(synchronize_session=False)
m.User.query.filter_by(id=uid).delete(synchronize_session=False)
s.commit()
assert m.User.query.filter_by(id=uid).count()==0
assert m.User.query.filter_by(id=u2.id).count()==1
assert m.ErrorLog.query.count()==0 and m.FunctionalTestRun.query.count()==0

source=(ROOT/'app.py').read_text()
assert 'passed = result["failures"] == 0' in source
assert 'if result[\'videos_found\'] == 0' in source
assert 'User.query.filter_by(id=lecturer.id).delete' in source
assert 'faculty_name = db.Column' in (ROOT/'models.py').read_text()
assert 'department_name = db.Column' in (ROOT/'models.py').read_text()
video_ui=(ROOT/'templates/videos.html').read_text()
qr_ui=(ROOT/'templates/qr.html').read_text()
profile_ui=(ROOT/'templates/profile_setup.html').read_text()
course_ui=(ROOT/'templates/courses.html').read_text()
assert 'Gán MH cho tất cả playlist' in video_ui
assert 'Tải QR đã tạo' in video_ui
assert 'playlistBulkDownloadQr' in video_ui
assert 'Tổng mã QR đã tạo' in qr_ui and 'QR playlist' in qr_ui and 'QR video' in qr_ui
assert 'qr-save-picker' in video_ui and 'qr-save-picker' in qr_ui
assert 'showSaveFilePicker' in (ROOT/'static/qr_save_picker.js').read_text()
assert 'Khoa QL bộ môn' in course_ui
assert 'Bộ môn sinh hoạt chuyên môn' in profile_ui
assert 'Khoa sinh hoạt chuyên môn' in profile_ui
j=Environment(loader=FileSystemLoader(str(ROOT/'templates')))
for path in (ROOT/'templates').glob('*.html'):
    j.parse(path.read_text())
print('PASS v4.3.30: xóa môn/QR/log/lớp riêng; giữ nguyên SV/lớp dùng chung; UI/profile/đồng bộ/QR save; 23 mẫu Jinja')

# Không tự chỉnh kết quả thất bại thực sự; chỉ phân loại lại 0 video/0 lỗi.
s.add_all([
    m.FunctionalTestRun(owner_id=u2.id,case_code='YT_SYNC',case_name='Đồng bộ',passed=False,
                        source='automatic',note='Video đã xác minh: 0; phần lỗi: 0. Không có video phù hợp để đồng bộ.'),
    m.FunctionalTestRun(owner_id=u2.id,case_code='YT_SYNC',case_name='Đồng bộ',passed=False,
                        source='automatic',note='Video đã xác minh: 0; phần lỗi: 1. Nguyên nhân: 403'),
]);s.commit()
import re
upgrade_sql = re.search(r'UPDATE functional_test_runs SET passed = TRUE\s+WHERE case_code.*?note LIKE.*?\n\s*"""', source, re.S)
assert upgrade_sql is not None
sql = upgrade_sql.group(0).split('"""')[0]
with engine.begin() as conn:
    conn.execute(sa.text(sql))
records=m.FunctionalTestRun.query.order_by(m.FunctionalTestRun.id).all()
assert [r.passed for r in records] == [True,False]
print('PASS v4.3.30: chỉ điều chỉnh đồng bộ 0 video / 0 lỗi; lỗi thực sự vẫn Không đạt')

# Trường hợp kênh nguồn GV A đang phục vụ video được môn của GV B sử dụng:
# route xóa phải dừng lại, tuyệt đối không xóa mã QR/học liệu của GV B.
u3=m.User(email='source@example.test',name='GV nguồn',role='lecturer')
admin=m.User(email='admin@example.test',name='Quản trị',role='admin')
s.add_all([u3,admin]);s.flush()
source_channel=m.YouTubeChannel(user_id=u3.id,channel_id='youtube3',title='Nguồn dùng chung')
s.add(source_channel);s.flush()
shared_video=m.Video(channel_id=source_channel.id,youtube_video_id='SHARED-101',title='Video dùng chung')
s.add(shared_video);s.flush()
s.add(m.CourseVideo(course_id=c2id,video_id=shared_video.id))
s.commit()
node=next(n for n in ast.walk(astmod) if isinstance(n,ast.FunctionDef) and n.name=='delete_lecturer_account')
clone=ast.FunctionDef(name=node.name,args=node.args,body=node.body,decorator_list=[],returns=node.returns,type_comment=None)
messages=[]
from sqlalchemy.orm import aliased
mock_ns=dict(ns)
mock_ns.update({'aliased':aliased,'request':types.SimpleNamespace(form={'confirm_email':u3.email}),
                'current_user':lambda:admin,'flash':lambda msg,kind:messages.append((msg,kind)),
                'abort':lambda code:(_ for _ in ()).throw(PermissionError(code)),
                'url_for':lambda name:'/admin/lecturers','redirect':lambda url:url,
                'delete_lecturer_business_data':ns['delete_lecturer_business_data']})
exec(compile(ast.fix_missing_locations(ast.Module(body=[clone],type_ignores=[])),'app.py','exec'),mock_ns)
assert mock_ns['delete_lecturer_account'](u3.id) == '/admin/lecturers'
assert m.User.query.filter_by(id=u3.id).count()==1
assert m.CourseVideo.query.filter_by(video_id=shared_video.id).count()==1
assert messages and messages[-1][1]=='warning'
print('PASS v4.3.30: không xóa giảng viên nếu nguồn học liệu vẫn dùng trong môn của GV khác')
