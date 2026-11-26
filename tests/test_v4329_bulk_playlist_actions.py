"""v4.3.29: execute actual SQLAlchemy query and bulk route bodies without Flask.

The container lacks Flask/Authlib, so this extracts exactly the shipped code via
AST and executes it against the production ORM models on in-memory SQLite.
"""
import ast
import secrets
import sys
import time
import types
from pathlib import Path
from urllib.parse import parse_qsl, urlencode
from bs4 import BeautifulSoup
import sqlalchemy as sa
from sqlalchemy.orm import declarative_base, relationship, backref, sessionmaker
from jinja2 import Environment, FileSystemLoader

ROOT = Path(__file__).resolve().parents[1]
source = (ROOT/'app.py').read_text()
mod = ast.parse(source)

class SQLAlchemy:
    def __init__(self):
        self.Model=declarative_base()
        for name in ('Column','Integer','String','Text','Date','DateTime','Boolean','Float','ForeignKey'):
            setattr(self,name,getattr(sa,name))
        self.relationship=relationship
        self.backref=backref

sys.modules['flask_sqlalchemy']=types.SimpleNamespace(SQLAlchemy=SQLAlchemy)
sys.path.insert(0,str(ROOT))
import models
engine=sa.create_engine('sqlite:///:memory:')
models.db.Model.metadata.create_all(engine)
models.db.session=sessionmaker(bind=engine)()
class Query:
    def __get__(self,obj,owner):return models.db.session.query(owner)
for m in models.db.Model.registry.mappers:m.class_.query=Query()
s=models.db.session

u1=models.User(email='one@example.test',name='GV chủ kênh',role='lecturer')
u2=models.User(email='other@example.test',name='GV khác',role='lecturer')
s.add_all([u1,u2]);s.flush()
c1=models.Course(owner_id=u1.id,code='C1',name='Lập trình Python',active=True)
c2=models.Course(owner_id=u1.id,code='C2',name='Toán rời rạc',active=True)
c_other=models.Course(owner_id=u2.id,code='C3',name='Người khác',active=True)
s.add_all([c1,c2,c_other]);s.flush()
ch1=models.YouTubeChannel(user_id=u1.id,channel_id='CH-1',title='Kênh 1',uploads_playlist_id='UU-1')
ch2=models.YouTubeChannel(user_id=u2.id,channel_id='CH-2',title='Kênh 2',uploads_playlist_id='UU-2')
s.add_all([ch1,ch2]);s.flush()
vid=models.Video(channel_id=ch1.id,youtube_video_id='V-1',title='Video công khai',is_available=True,
                 embeddable=True,privacy_status='public',uploader_channel_id=ch1.channel_id)
novid=models.Video(channel_id=ch1.id,youtube_video_id='V-2',title='Video không nhúng',is_available=True,
                   embeddable=False,privacy_status='public',uploader_channel_id=ch1.channel_id)
s.add_all([vid,novid]);s.flush()
pls=[]
for i in range(1,9):
    p=models.Playlist(channel_id=ch1.id,youtube_playlist_id=f'PL-{i}',title=f'Python {i}',is_available=True)
    s.add(p);s.flush();pls.append(p)
    if i<=6:s.add(models.PlaylistVideo(playlist_id=p.id,video_id=vid.id,position=0))
    elif i==7:s.add(models.PlaylistVideo(playlist_id=p.id,video_id=novid.id,position=0))
old=models.Playlist(channel_id=ch1.id,youtube_playlist_id='PL-OLD',title='Python cũ',is_available=False)
uploads=models.Playlist(channel_id=ch1.id,youtube_playlist_id='UU-1',title='Python uploads',is_available=True)
foreign=models.Playlist(channel_id=ch2.id,youtube_playlist_id='PL-OUT',title='Python nước ngoài',is_available=True)
s.add_all([old,uploads,foreign]);s.flush()
s.add(models.CoursePlaylist(course_id=c2.id,playlist_id=pls[0].id,added_by=u1.id,active=True))
s.add(models.CoursePlaylist(course_id=c1.id,playlist_id=old.id,added_by=u1.id,active=True))
s.commit()

# Modules imports from app.py are not necessary: execute the exact functions,
# without changing their query/transaction/business logic.
helper_names={
 'filtered_library_playlist_query','ensure_course_playlist_link',
 'reconcile_course_videos_from_playlists','ensure_course_video_link','create_qr_for_course_playlist',
 'visible_playlist_query','videos_library_return_with_bulk_course',
 'course_owned_by_user','videos_library_return',
}
route_names={'bulk_assign_filtered_library_playlists','bulk_create_playlist_qrs_from_library'}
functions={node.name:node for node in ast.walk(mod) if isinstance(node,ast.FunctionDef)}
assert helper_names|route_names <=functions.keys()

class Form(dict):
    def get(self,name,default=None,type=None):
        value=super().get(name,default)
        if type and value is not None:
            try:return type(value)
            except(ValueError,TypeError):return default
        return value
    def getlist(self,name):
        value=super().get(name,[])
        return value if isinstance(value,list) else ([value] if value is not None else [])

actor=[u1]
request=types.SimpleNamespace(form=Form())
messages=[]
def abort(code):raise PermissionError(code)
def flash(msg,category):messages.append((msg,category))
def record_functional_test(code,name,passed,owner_id=None,note='',**kwargs):
    s.add(models.FunctionalTestRun(owner_id=owner_id,case_code=code,case_name=name,passed=passed,note=note,source='automatic'))
def record_webapp_experiment(owner_id,key,elapsed,operations_count=1,success=True,note='',processing_seconds=None):
    s.add(models.ExperimentRun(owner_id=owner_id,task_key=key,mode='webapp',elapsed_seconds=elapsed,
        operations_count=operations_count,success=success,note=note,system_processing_seconds=processing_seconds))

scope={**{key:getattr(models,key) for key in ('User','YouTubeChannel','Playlist','Video','PlaylistVideo','Course','CourseVideo','CoursePlaylist','QrCode')},
 'db':models.db,'or_':sa.or_,'and_':sa.and_,'select':sa.select,'secrets':secrets,'time':time,
 'request':request,'abort':abort,'flash':flash,'record_functional_test':record_functional_test,
 'record_webapp_experiment':record_webapp_experiment,
 'record_research_qr_creation':lambda course_id, lecturer_id, kind, qr_id=None: None,
 'current_user':lambda:actor[0],
 'url_for':lambda x:'/videos','redirect':lambda x:x,'parse_qsl':parse_qsl,'urlencode':urlencode}
for name in helper_names|route_names:
    function=functions[name]
    # decorators on Flask routes cannot be evaluated in a pure ORM test.
    clone=ast.FunctionDef(name=function.name,args=function.args,body=function.body,
                          decorator_list=[],returns=function.returns,type_comment=None)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[clone],type_ignores=[])),f'<{name}>','exec'),scope)

# Exact SQL scope used by the list and bulk. More than 5 matching rows.
filtered=scope['filtered_library_playlist_query']
assert len(filtered(u1,'Python','unassigned').all())==7
assert {p.id for p in filtered(u1,'Python','assigned').all()}=={pls[0].id,old.id}
assert len(filtered(u1,'Python','').all())==9
assert all(p.id not in {foreign.id,uploads.id} for p in filtered(u1,'Python','').all())

request.form=Form(course_id=str(c1.id),p_q='Python',p_assignment='unassigned',playlist_selection_mode='all',
                  return_query='p_q=Python&p_assignment=unassigned&p_page=2')
result=scope['bulk_assign_filtered_library_playlists']()
assert 'p_assignment=unassigned' in result and '#playlists' in result
assert {x.playlist_id for x in models.CoursePlaylist.query.filter_by(course_id=c1.id,active=True).all()}==({p.id for p in pls[1:]}|{old.id})
assert models.CoursePlaylist.query.filter_by(course_id=c2.id,playlist_id=pls[0].id,active=True).count()==1
# New selection from 'Tất cả' adds only previously assigned-to-other-course playlist.
request.form=Form(course_id=str(c1.id),p_q='Python',p_assignment='',playlist_selection_mode='all')
scope['bulk_assign_filtered_library_playlists']()
assert models.CoursePlaylist.query.filter_by(course_id=c1.id,active=True).count()==9
assert models.CoursePlaylist.query.filter_by(course_id=c2.id,playlist_id=pls[0].id,active=True).count()==1
assert models.CoursePlaylist.query.filter_by(course_id=c1.id,playlist_id=foreign.id).count()==0
assert models.CoursePlaylist.query.filter_by(course_id=c1.id,playlist_id=uploads.id).count()==0
# Unauthorized course and malformed filters rejected.
request.form=Form(course_id=str(c_other.id),p_q='Python')
try:scope['bulk_assign_filtered_library_playlists']();assert False
except PermissionError as e:assert str(e)=='403'
request.form=Form(course_id=str(c1.id),p_assignment='not-a-real-filter')
try:scope['bulk_assign_filtered_library_playlists']();assert False
except PermissionError as e:assert str(e)=='400'

# Seed a QR created in an older release: batch must never replace its slug.
preexisting=models.QrCode(owner_id=u1.id,course_id=c1.id,playlist_id=pls[1].id,
        target_type='playlist',title=pls[1].title,slug='existing-qr-preserved',active=True)
s.add(preexisting);s.flush()
old_link=models.CoursePlaylist.query.filter_by(course_id=c1.id,playlist_id=pls[1].id).first()
old_link.qr_id=preexisting.id
s.commit()

# NEW: no course selected, no checkbox, unmatched search and wrong course_id.
# All active links owned by lecturer still receive their own QR.
request.form=Form(course_id=str(c_other.id),playlist_selection_mode='none',
    selected_playlist_ids=[],p_q='does-not-exist',return_query='p_q=wrong&p_page=2')
result=scope['bulk_create_playlist_qrs_from_library']()
assert result.startswith('/videos?') and '#playlists' in result
qrs=models.QrCode.query.filter_by(target_type='playlist',active=True).all()
assert {q.playlist_id for q in qrs if q.course_id==c1.id}=={p.id for p in pls[:6]}
assert {q.playlist_id for q in qrs if q.course_id==c2.id}=={pls[0].id}
assert all(q.course_id in {c1.id,c2.id} for q in qrs),qrs
assert {q.slug for q in qrs if q.playlist_id==pls[1].id and q.course_id==c1.id}=={'existing-qr-preserved'}
before_qr_ids={q.id for q in qrs}
scope['bulk_create_playlist_qrs_from_library']()
assert {q.id for q in models.QrCode.query.filter_by(target_type='playlist',active=True).all()}==before_qr_ids
assert models.FunctionalTestRun.query.filter_by(case_code='QR_PLAYLIST_FILTERED_BULK').count()==2
assert models.ExperimentRun.query.filter_by(task_key='TAO_QR_HANG_LOAT').count()==2
assert not any(q.course_id==c_other.id for q in qrs)

# Ô tích vẫn điều khiển Gán môn. Nhưng nút Tạo QR mới xử lý tất cả
# playlist đã gán, kể cả playlist đã bỏ tích hoặc ở trang khác.
selection_course=models.Course(owner_id=u1.id, code='C-SELECT', name='Chỉ playlist được tích', active=True)
s.add(selection_course);s.commit()
excluded_assign={pls[1].id,pls[5].id}
request.form=Form(course_id=str(selection_course.id),p_q='Python',p_assignment='',
                  playlist_selection_mode='all',
                  excluded_playlist_ids=[str(i) for i in excluded_assign])
scope['bulk_assign_filtered_library_playlists']()
selected_assigned={r.playlist_id for r in models.CoursePlaylist.query.filter_by(
    course_id=selection_course.id,active=True).all()}
assert selected_assigned == {p.id for p in pls}-excluded_assign
assert models.CoursePlaylist.query.filter_by(course_id=selection_course.id,playlist_id=foreign.id).count()==0
assert models.CoursePlaylist.query.filter_by(course_id=selection_course.id,playlist_id=uploads.id).count()==0

request.form=Form(playlist_selection_mode='none',selected_playlist_ids=[],
                  excluded_playlist_ids=[str(pls[0].id)],p_q='no-rows')
scope['bulk_create_playlist_qrs_from_library']()
selected_qrs={q.playlist_id for q in models.QrCode.query.filter_by(
    course_id=selection_course.id,target_type='playlist',active=True).all()}
assert selected_qrs=={pls[i].id for i in (0,2,3,4)},selected_qrs
assert s.query(models.CourseVideo).count()>=1

# Invalid selection remains rejected for assigning; QR ignores selection only.
request.form=Form(course_id=str(selection_course.id),p_q='Python',playlist_selection_mode='all',
                  excluded_playlist_ids=['not-a-number'])
try:scope['bulk_assign_filtered_library_playlists']();assert False
except PermissionError as e:assert str(e)=='400'

# No selected playlist: old assign behavior stays unchanged.
default_none_course=models.Course(owner_id=u1.id,code='C-DEFAULT-NONE',name='Không gán mặc định',active=True)
s.add(default_none_course);s.commit()
request.form=Form(course_id=str(default_none_course.id),p_q='')
scope['bulk_assign_filtered_library_playlists']()
assert models.CoursePlaylist.query.filter_by(course_id=default_none_course.id).count()==0
scope['bulk_create_playlist_qrs_from_library']()
assert models.QrCode.query.filter_by(course_id=default_none_course.id).count()==0

# Playlist matching a filter and another assigned outside the filter:
# both must receive QR because "đã gán MH/MĐ" is global.
filtered_course=models.Course(owner_id=u1.id,code='C-QR-FILTER',name='QR không phụ thuộc lọc',active=True)
s.add(filtered_course);s.commit()
request.form=Form(course_id=str(filtered_course.id),p_q='Python 1',playlist_selection_mode='all')
scope['bulk_assign_filtered_library_playlists']()
assert {r.playlist_id for r in models.CoursePlaylist.query.filter_by(
    course_id=filtered_course.id,active=True).all()}=={pls[0].id}
s.add(models.CoursePlaylist(course_id=filtered_course.id,playlist_id=pls[1].id,added_by=u1.id,active=True));s.commit()
scope['bulk_create_playlist_qrs_from_library']()
filtered_qrs={q.playlist_id for q in models.QrCode.query.filter_by(
    course_id=filtered_course.id,target_type='playlist',active=True).all()}
assert filtered_qrs=={pls[0].id,pls[1].id}

# Playlist chỉ có video không nhúng sẽ không có QR dù đã được gán môn.
none_course=models.Course(owner_id=u1.id,code='C-NONE',name='Bỏ tất cả rồi chọn lại',active=True)
s.add(none_course);s.commit()
request.form=Form(course_id=str(none_course.id),p_q='Python',p_assignment='',
    playlist_selection_mode='none',selected_playlist_ids=[str(pls[1].id),str(pls[6].id)])
scope['bulk_assign_filtered_library_playlists']()
assert {x.playlist_id for x in models.CoursePlaylist.query.filter_by(
    course_id=none_course.id,active=True).all()}=={pls[1].id,pls[6].id}
scope['bulk_create_playlist_qrs_from_library']()
assert {q.playlist_id for q in models.QrCode.query.filter_by(
    course_id=none_course.id,target_type='playlist',active=True).all()}=={pls[1].id}

# Invalid assignment modes still fail.
request.form=Form(course_id=str(none_course.id),p_q='Python',playlist_selection_mode='invalid')
try:scope['bulk_assign_filtered_library_playlists']();assert False
except PermissionError as e:assert str(e)=='400'

# Existing single-playlist forms still exist; bulk is a separate, non-nested form.
ui=(ROOT/'templates/videos.html').read_text()
env=Environment(loader=FileSystemLoader(str(ROOT/'templates')))
env.parse(ui)
soup=BeautifulSoup(ui,'html.parser')
assert 'id="playlistBulkActions"' in ui
assert 'value="{{ playlist_search }}"' in ui
assert 'value="{{ playlist_assignment }}"' in ui
assert 'formaction="{{ url_for(\'bulk_create_playlist_qrs_from_library\') }}"' in ui
assert 'Gán MH cho playlist đã chọn' in ui
assert 'Tạo QR cho playlist đã gán MH/MĐ' in ui
assert 'playlistBulkActions' in ui and 'data-confirm-bulk' not in ui
assert 'id="selectAllPlaylists"' in ui
assert 'excluded_playlist_ids' in ui and 'sessionStorage.setItem' in ui
assert 'playlist-bulk-check' in (ROOT/'templates/_playlist_library_row.html').read_text()
assert "selected_playlist_ids" in ui and "playlist_selection_mode" in ui
assert "Chưa chọn playlist nào trên tất cả các trang." in ui
assert "selectAllPlaylists" in ui and "master.checked?'all':'none'" in ui
assert "keyword.trim() ? 'all' : 'none'" in ui
assert "filterForm?.addEventListener('submit'" in ui
assert 'set_playlist_course_assignments' in (ROOT/'templates/_playlist_library_row.html').read_text()
assert 'create_playlist_qr_from_library' in (ROOT/'templates/_playlist_library_row.html').read_text()
print('PASS v4.3.29: all pages; server filters; no cross-user writes; additive assignment; reusing QR; no QR for empty/unusable playlists; preserved single actions.')
