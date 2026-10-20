"""Offline SQLite test for exact v4.3.11 route logic; no Flask/OAuth required."""
import ast, sys, types
from pathlib import Path
from datetime import datetime
import sqlalchemy as sa
from sqlalchemy.orm import declarative_base, relationship, backref, sessionmaker
ROOT=Path(__file__).resolve().parents[1]
try:
    import flask_sqlalchemy
except ModuleNotFoundError:
    class SQLAlchemy:
        def __init__(self):
            self.Model=declarative_base()
            for k in ('Column','Integer','String','Text','Date','DateTime','Boolean','Float','ForeignKey'):
                setattr(self,k,getattr(sa,k))
            self.relationship=relationship;self.backref=backref
    m=types.ModuleType('flask_sqlalchemy');m.SQLAlchemy=SQLAlchemy;sys.modules['flask_sqlalchemy']=m
sys.path.insert(0,str(ROOT))
import models as M
engine=sa.create_engine('sqlite:///:memory:')
M.db.Model.metadata.create_all(engine)
Session=sessionmaker(bind=engine)
s=Session();M.db.session=s
for mapper in M.db.Model.registry.mappers:
    mapper.class_.query=s.query(mapper.class_)
u=M.User(email='gv@example.test',name='GV',role='lecturer');outsider=M.User(email='other@example.test',name='Other',role='lecturer');s.add_all([u,outsider]);s.flush()
ch=M.YouTubeChannel(user_id=u.id,channel_id='channel-a',title='Kênh A');och=M.YouTubeChannel(user_id=outsider.id,channel_id='channel-other',title='Kênh khác');s.add_all([ch,och]);s.flush()
old=M.Playlist(channel_id=ch.id,youtube_playlist_id='old-list',title='Playlist đã xóa',is_available=False)
new=M.Playlist(channel_id=ch.id,youtube_playlist_id='new-list',title='Playlist mới',is_available=True)
foreign=M.Playlist(channel_id=och.id,youtube_playlist_id='foreign-list',title='Ngoài quyền',is_available=True)
empty=M.Playlist(channel_id=ch.id,youtube_playlist_id='empty-list',title='Trống',is_available=True)
s.add_all([old,new,foreign,empty]);s.flush()
v=M.Video(channel_id=ch.id,youtube_video_id='v01',uploader_channel_id='channel-a',title='Video 1',is_available=True)
s.add(v);s.flush();s.add(M.PlaylistVideo(playlist_id=new.id,video_id=v.id))
course=M.Course(owner_id=u.id,code='HP001',name='Môn A',active=True);s.add(course);s.flush()
qr=M.QrCode(owner_id=u.id,course_id=course.id,slug='KEEP-THIS-QR',title=old.title,target_type='playlist',playlist_id=old.id,active=True)
s.add(qr);s.flush()
old_link=M.CoursePlaylist(course_id=course.id,playlist_id=old.id,qr_id=qr.id,active=True,added_by=u.id);s.add(old_link)
sc=M.ScanLog(participant_code='student001',role='SV',qr_id=qr.id,course_id=course.id,class_code='L01',success=True)
w=M.WatchSession(session_key='sess-1',participant_code='student001',role='SV',qr_id=qr.id,course_id=course.id,video_id=v.id,estimated_watch_seconds=60)
s.add_all([sc,w]);s.commit()

mod=ast.parse((ROOT/'app.py').read_text())
create_app=next(node for node in mod.body if isinstance(node,ast.FunctionDef) and node.name=='register_routes')
route=next(node for node in ast.walk(create_app) if isinstance(node,ast.FunctionDef) and node.name=='qr_retarget_playlist')
route.decorator_list=[]
class UserRequest:
    def __init__(self):self.value=new.id
    @property
    def form(self):return self
    def get(self,k,type=None):return self.value if k=='playlist_id' else None
request=UserRequest()
messages=[]
class Stop(Exception):pass

def abort(code):raise Stop(code)

def current_user():return u

def owned(course,user):return course.owner_id==user.id

def can_manage(qr,user):return (qr.course.owner_id==user.id) if qr.course else (qr.owner_id==user.id)

def valid_playlist(user):
    return (s.query(M.Playlist).join(M.YouTubeChannel).filter(
        M.YouTubeChannel.user_id==user.id,M.Playlist.is_available.is_(True)))

def flash(msg,level):messages.append(msg)

def record_functional_test(*a,**kw):pass

def redirect(x):return x

def url_for(x,**kw):return '/'+x

def qr_action_destination(qr):return '/qr'

G=dict(User=M.User, QrCode=M.QrCode,Course=M.Course,Playlist=M.Playlist,CoursePlaylist=M.CoursePlaylist,
       EditHistory=M.EditHistory,CourseVideo=M.CourseVideo,PlaylistVideo=M.PlaylistVideo,Video=M.Video,
       db=M.db,request=request,current_user=current_user,
       visible_playlist_query=valid_playlist,qr_managed_by_user=can_manage,course_owned_by_user=owned,
       qr_action_destination=qr_action_destination,
       record_functional_test=record_functional_test,flash=flash,abort=abort,redirect=redirect,url_for=url_for)
helpers=[n for n in mod.body if isinstance(n,ast.FunctionDef) and n.name in {'reconcile_course_videos_from_playlists','ensure_course_video_link'}]
assert len(helpers)==2
exec(compile(ast.Module(body=helpers+[route],type_ignores=[]),'<actual QR functions>','exec'),G)

# Cannot replace QR using empty playlist, another account's playlist or same target.
request.value=foreign.id
assert G['qr_retarget_playlist'](qr.id)=='/qr' and qr.playlist_id==old.id
request.value=empty.id
assert G['qr_retarget_playlist'](qr.id)=='/qr' and qr.playlist_id==old.id
request.value=new.id
assert G['qr_retarget_playlist'](qr.id)=='/qr'
s.refresh(qr);s.refresh(old_link)
assert qr.slug=='KEEP-THIS-QR' and qr.owner_id==u.id and qr.playlist_id==new.id
assert old_link.qr_id is None and old_link.active is False
new_link=s.query(M.CoursePlaylist).filter_by(course_id=course.id,playlist_id=new.id).one()
assert new_link.qr_id==qr.id and new_link.active is True
assert s.query(M.ScanLog).one().qr_id==qr.id and s.query(M.WatchSession).one().qr_id==qr.id
change=s.query(M.EditHistory).filter_by(entity_kind='qr_playlist',entity_id=qr.id,field='playlist_target').one()
assert old.title in change.old_value and new.title in change.new_value and change.changed_by==u.id
assert s.query(M.QrCode).count()==1
added=s.query(M.CourseVideo).filter_by(course_id=course.id,video_id=v.id).one()
assert added.source_playlist_id==new.id and added.manual_added is False
# Same-target repeat is idempotent.
request.value=new.id
G['qr_retarget_playlist'](qr.id)
assert s.query(M.EditHistory).count()==1
# Another active QR for that same course+playlist is rejected.
third=M.Playlist(channel_id=ch.id,youtube_playlist_id='third',title='Playlist 3',is_available=True)
s.add(third);s.flush();s.add(M.PlaylistVideo(playlist_id=third.id,video_id=v.id));s.flush()
qr2=M.QrCode(owner_id=u.id,course_id=course.id,slug='ANOTHER-QR',title='Playlist 3',target_type='playlist',playlist_id=third.id,active=True)
s.add(qr2);s.flush();s.add(M.CoursePlaylist(course_id=course.id,playlist_id=third.id,qr_id=qr2.id,active=True,added_by=u.id));s.commit()
request.value=third.id
G['qr_retarget_playlist'](qr.id)
assert qr.playlist_id==new.id
# Previous lecturer no access after course handover, even if original QR owner.
course.owner_id=outsider.id;s.commit()
try:G['qr_retarget_playlist'](qr.id)
except Stop as e:assert e.args[0]==403
else:raise AssertionError('Previous lecturer able to retarget handed-off QR')
print('PASS: v4.3.11 playlist QR retarget, exact slug, ACL, scan/watch history, ownership, empty/duplicate rejection, audit')
