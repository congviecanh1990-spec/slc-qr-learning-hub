"""Kiểm thử độc lập: playlist không được tự nhận video của kênh thứ ba.

Chạy: python tests/test_youtube_playlist_ownership.py
Không cần tài khoản Google, PostgreSQL hay Flask/Authlib.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys
import types
from datetime import datetime, timezone

CHANNELS, VIDEOS, PLAYLISTS, LINKS = [], [], [], []


class Query:
    def __init__(self, collection, filters=None):
        self.collection = collection
        self.filters = filters or {}

    def filter_by(self, **filters):
        return Query(self.collection, {**self.filters, **filters})

    def all(self):
        return [x for x in self.collection if all(getattr(x, k) == v for k, v in self.filters.items())]

    def first(self):
        return next(iter(self.all()), None)


class QueryProperty:
    def __get__(self, instance, owner):
        return Query(owner._records)


class YouTubeChannel:
    _records = CHANNELS
    query = QueryProperty()

    def __init__(self, id, user_id, channel_id):
        self.id, self.user_id, self.channel_id = id, user_id, channel_id
        self.connected_account_id = None
        CHANNELS.append(self)


class Video:
    _records = VIDEOS
    query = QueryProperty()

    def __init__(self, channel_id, youtube_video_id):
        self.id = len(VIDEOS) + 1
        self.channel_id, self.youtube_video_id = channel_id, youtube_video_id
        self.uploader_channel_id = None
        self.is_available = True
        VIDEOS.append(self)

    @property
    def channel(self):
        return next(c for c in CHANNELS if c.id == self.channel_id)

    @channel.setter
    def channel(self, value):
        self.channel_id = value.id


class Playlist:
    _records = PLAYLISTS
    query = QueryProperty()

    def __init__(self, channel_id, youtube_playlist_id, **kwargs):
        self.id = len(PLAYLISTS) + 1
        self.channel_id, self.youtube_playlist_id = channel_id, youtube_playlist_id
        for k, v in kwargs.items():
            setattr(self, k, v)
        PLAYLISTS.append(self)


class PlaylistVideo:
    _records = LINKS
    query = QueryProperty()

    def __init__(self, playlist_id, video_id, position=None):
        self.playlist_id, self.video_id, self.position = playlist_id, video_id, position
        LINKS.append(self)


class Session:
    def add(self, instance):
        pass  # Các đối tượng test được đưa vào bộ nhớ ngay lúc khởi tạo.

    def delete(self, instance):
        for rows in (LINKS, VIDEOS, PLAYLISTS, CHANNELS):
            if instance in rows:
                rows.remove(instance)
                return
        raise AssertionError('Đối tượng không tồn tại')

    def flush(self):
        pass

    def commit(self):
        pass

    def get(self, kind, id):
        return next((x for x in kind._records if x.id == id), None)


model = types.ModuleType('models')
for name, obj in dict(
    db=types.SimpleNamespace(session=Session()),
    OAuthAccount=type('OAuthAccount', (), {}),
    ConnectedGoogleAccount=type('ConnectedGoogleAccount', (), {}),
    YouTubeChannel=YouTubeChannel, Playlist=Playlist, Video=Video,
    PlaylistVideo=PlaylistVideo, Course=type('Course', (), {}),
    CourseVideo=type('CourseVideo', (), {}), CoursePlaylist=type('CoursePlaylist', (), {}),
    ErrorLog=type('ErrorLog', (), {}), YouTubeSyncJob=type('YouTubeSyncJob', (), {}), utcnow=lambda: datetime.now(timezone.utc),
).items():
    setattr(model, name, obj)
sys.modules['models'] = model
sys.modules['flask'] = types.SimpleNamespace(current_app=None)
sys.modules['security'] = types.SimpleNamespace(decrypt_json=lambda token: {}, encrypt_json=lambda token: '')

service_file = pathlib.Path(__file__).resolve().parents[1] / 'services' / 'youtube.py'
spec = importlib.util.spec_from_file_location('youtube_under_test', service_file)
service = importlib.util.module_from_spec(spec)
spec.loader.exec_module(service)


class User:
    id = 1


user = User()
channel_a = YouTubeChannel(id=1, user_id=1, channel_id='YT-A')
channel_b = YouTubeChannel(id=2, user_id=1, channel_id='YT-B')
other_teacher = YouTubeChannel(id=3, user_id=2, channel_id='YT-OTHER-TEACHER')
playlist = Playlist(channel_a.id, 'PL-A', title='Danh sách A')

# Bản ghi sai từ phiên bản cũ: video kênh khác bị gán cho kênh A.
legacy_foreign = Video(channel_a.id, 'VID-OLD-FOREIGN')
old_link = PlaylistVideo(playlist.id, legacy_foreign.id)

# Video thuộc kênh B đã được giảng viên kết nối là nguồn hợp lệ.
video_b = Video(channel_b.id, 'VID-B')
video_b.uploader_channel_id = 'YT-B'

# Video thuộc GV khác không được phép thao tác/chuyển quyền sở hữu.
other_video = Video(other_teacher.id, 'VID-OTHER-TEACHER')

owned = {
    'VID-OWN': 'YT-A',
    'VID-OLD-FOREIGN': 'YT-NOT-CONNECTED',
    'VID-NEW-FOREIGN': 'YT-NOT-CONNECTED',
    'VID-B': 'YT-B',
    'VID-OTHER-TEACHER': 'YT-OTHER-TEACHER',
}


def fake_get(user, path, params, credential=None):
    if path == 'playlistItems':
        return {'items': [
            {'contentDetails': {'videoId': vid}, 'snippet': {'position': i}}
            for i, vid in enumerate(['VID-OWN', 'VID-OLD-FOREIGN', 'VID-NEW-FOREIGN', 'VID-B'])
        ]}
    if path == 'videos':
        return {'items': [
            {'id': vid, 'snippet': {'channelId': owned[vid], 'title': vid},
             'status': {'privacyStatus': 'public', 'embeddable': True}, 'contentDetails': {}}
            for vid in params['id'].split(',') if vid in owned
        ]}
    raise AssertionError(path)


service._get = fake_get
service.sync_playlist_items(user, channel_a, 'PL-A')
assert Video.query.filter_by(youtube_video_id='VID-OWN').first().uploader_channel_id == 'YT-A'
assert Video.query.filter_by(youtube_video_id='VID-NEW-FOREIGN').first() is not None, 'Phải đồng bộ video công khai tuyển chọn!' 
assert legacy_foreign in VIDEOS, 'Không được xóa lịch sử dữ liệu cũ!'
assert legacy_foreign.uploader_channel_id == 'YT-NOT-CONNECTED', 'Phải xác định đúng nguồn video cũ'
assert old_link in LINKS, 'Video tuyển chọn hợp lệ phải được giữ ở playlist do GV quản lý'
assert len(LINKS) == 4, 'Playlist cần giữ cả 2 video tuyển chọn hợp lệ'
assert {v.youtube_video_id for v in VIDEOS if v.id in {link.video_id for link in LINKS}} == {'VID-OWN', 'VID-B', 'VID-OLD-FOREIGN', 'VID-NEW-FOREIGN'}

service.sync_video_ids(user, channel_a, ['VID-OTHER-TEACHER'])
assert other_video.channel_id == other_teacher.id, 'Không được chuyển video của GV khác'
assert other_video.is_available, 'Không được đổi trạng thái video của GV khác'

# Gỡ video khỏi playlist không được xóa bản ghi video đã lưu.
def empty_playlist(user, path, params, credential=None):
    return {'items': []}

service._get = empty_playlist
service.sync_playlist_items(user, channel_a, 'PL-A')
assert LINKS == [], 'Phải gỡ hết liên kết khi playlist không còn video'
assert Video.query.filter_by(youtube_video_id='VID-OWN').first() is not None
print('OK: nguồn tải lên nguyên gốc, video tuyển chọn công khai, quyền sở hữu không bị chuyển, lịch sử giữ nguyên.')
