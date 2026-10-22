"""Thử nghiệm SQLite ngoại tuyến: cập nhật từng trang, tuyển chọn, bảo toàn quyền nguồn.
Không thay thế thử nghiệm OAuth/YouTube API thật trên Render.
"""
from pathlib import Path
import sys, types, json, ast
import sqlalchemy as sa
from sqlalchemy.orm import declarative_base, relationship, backref, sessionmaker

ROOT = Path(__file__).resolve().parents[1]
class SQLAlchemy:
    def __init__(self):
        self.Model = declarative_base()
        for name in ('Column','Integer','String','Text','Date','DateTime','Boolean','Float','ForeignKey'):
            setattr(self, name, getattr(sa,name))
        self.relationship = relationship
        self.backref = backref
fsa = types.ModuleType('flask_sqlalchemy')
fsa.SQLAlchemy = SQLAlchemy
sys.modules['flask_sqlalchemy'] = fsa
sys.modules['flask'] = types.SimpleNamespace(current_app=None)
sys.modules['security'] = types.SimpleNamespace(decrypt_json=lambda value:{},encrypt_json=lambda value:'')
sys.path.insert(0,str(ROOT))
import models
from services import youtube
engine = sa.create_engine('sqlite:///:memory:')
models.db.Model.metadata.create_all(engine)
models.db.session = sessionmaker(bind=engine)()
class Query:
    def __get__(self,obj,owner):
        return models.db.session.query(owner)
for mapper in models.db.Model.registry.mappers:
    mapper.class_.query = Query()

s = models.db.session
u1=models.User(email='one@school.example', name='GV có playlist',role='lecturer')
u2=models.User(email='two@school.example', name='GV dùng chung video',role='lecturer')
s.add_all([u1,u2]);s.commit()

playlist_id={u1.id:'PL-ONE',u2.id:'PL-TWO'}
chan_id={u1.id:'CH-ONE',u2.id:'CH-TWO'}

# API mô phỏng: kênh chưa đăng video, playlist private chứa 2 video nguồn ngoài.
# Video 1 công khai cho nhúng; video 2 không nhúng được; video 3 private.
video_items={
 'VID-GOOD':('UPLOADER-EXTERNAL','public',True),
 'VID-NO-EMBED':('UPLOADER-EXTERNAL','public',False),
 'VID-PRIVATE':('UPLOADER-EXTERNAL','private',True),
}
active_user=[u1.id]

def fake_get(user,path,params,credential=None):
    if path=='channels':
        return {'items':[{'id':chan_id[user.id], 'snippet':{'title':'Kênh có video đã lưu'},
              'contentDetails':{'relatedPlaylists':{'uploads':f'UU-{user.id}'}}}]}
    if path=='playlists':
        return {'items':[{'id':playlist_id[user.id], 'snippet':{'title':'Danh sách học liệu tuyển chọn'},
                          'status':{'privacyStatus':'private'}}]}
    if path=='playlistItems':
        if params['playlistId'].startswith('UU-'):
            return {'items':[]}
        if params.get('pageToken')=='NEXT':
            return {'items':[{'contentDetails':{'videoId':'VID-PRIVATE'}, 'snippet':{'position':2}}]}
        return {'items':[{'contentDetails':{'videoId':'VID-GOOD'}, 'snippet':{'position':0}},
                         {'contentDetails':{'videoId':'VID-NO-EMBED'}, 'snippet':{'position':1}}],
                'nextPageToken':'NEXT'}
    if path=='videos':
        return {'items':[{'id':vid,'snippet':{'channelId':video_items[vid][0], 'title':vid},
                 'status':{'privacyStatus':video_items[vid][1], 'embeddable':video_items[vid][2]},
                 'contentDetails':{'duration':'PT60S'}} for vid in params['id'].split(',')]}
    raise AssertionError((path,params))
youtube._get=fake_get

for user in [u1,u2]:
    job=youtube.start_incremental_sync(user)
    initial=youtube.incremental_sync_state(user)
    assert initial['status']=='running' and initial['remaining']==1
    # Bước đầu chỉ nhận diện kênh/playlist, chưa gọi videos.list.
    state=youtube.step_incremental_sync(user)
    assert state['status']=='running' and state['remaining']==2
    # Sau trang đầu chưa được xóa link cũ, và vẫn còn trang kế tiếp.
    state=youtube.step_incremental_sync(user)
    assert state['status']=='running' and state['remaining']==2
    good=models.Video.query.filter_by(youtube_video_id='VID-GOOD').first()
    assert good and good.uploader_channel_id=='UPLOADER-EXTERNAL'
    assert models.PlaylistVideo.query.join(models.Playlist).filter(models.Playlist.youtube_playlist_id==playlist_id[user.id]).count()==1
    # Tiếp tục tại request mới.
    while state['status']=='running':
        state=youtube.step_incremental_sync(user)
    assert state['status']=='done' and state['videos_found']==1 and state['failures']==0,state
    owner_row=models.Video.query.filter_by(youtube_video_id='VID-GOOD').first()
    assert owner_row.channel_id==models.YouTubeChannel.query.filter_by(channel_id='CH-ONE').first().id
    assert models.PlaylistVideo.query.filter_by(video_id=owner_row.id).count()==(1 if user.id==u1.id else 2)

# Kiểm tra truy vấn kho video thực trong app.py không suy đoán quyền sở hữu từ video.channel.
mod=ast.parse((ROOT/'app.py').read_text())
func=next(n for n in mod.body if isinstance(n,ast.FunctionDef) and n.name=='visible_video_query')
env={'db':models.db,'Video':models.Video,'PlaylistVideo':models.PlaylistVideo,
     'Playlist':models.Playlist,'YouTubeChannel':models.YouTubeChannel,'or_':sa.or_,'User':models.User}
exec(compile(ast.Module(body=[func],type_ignores=[]),'<visible_video_query>','exec'),env)
for user in (u1,u2):
    vids=env['visible_video_query'](user).all()
    assert [v.youtube_video_id for v in vids]==['VID-GOOD'],[v.youtube_video_id for v in vids]

# Playlist thật sự trống không được gắn nhãn có học liệu.
tpl=(ROOT/'templates/videos.html').read_text()
assert "'Danh sách trống'" in tpl
assert 'usable.count == 0' in tpl
assert 'Video tuyển chọn' in tpl
# Đảm bảo trình duyệt không bị ép đồng bộ chờ sau đăng nhập.
a=(ROOT/'app.py').read_text()
assert 'session["yt_auto_sync_request"] = True' in a
assert 'return redirect(url_for("index"))' in a
assert 'start_incremental_sync' in a and 'step_incremental_sync' in a
js=(ROOT/'static/youtube_sync.js').read_text()
assert '/youtube/sync/step' in js and '/youtube/sync/start' in js
print('PASS v4.3.22: đăng nhập nhanh; đồng bộ tiếp tục từng trang; playlist tuyển chọn; video private/noembed bị loại; đúng quyền GV; dữ liệu và quyền gốc giữ nguyên.')
