"""Kiểm thử ngoại tuyến: kênh chưa có video khác hẳn lỗi 403 (không cần tài khoản Google)."""
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace

class DummySession:
    def rollback(self): pass

class DummyQuery:
    def filter_by(self, **kwargs): return self
    def all(self): return []

sys.modules['flask'] = SimpleNamespace(current_app=None)
sys.modules['models'] = SimpleNamespace(
    db=SimpleNamespace(session=DummySession()),
    OAuthAccount=type('OAuthAccount', (), {}),
    ConnectedGoogleAccount=type('ConnectedGoogleAccount', (), {'query': DummyQuery()}),
    YouTubeChannel=type('YouTubeChannel', (), {}),
    Playlist=type('Playlist', (), {}), Video=type('Video', (), {}),
    PlaylistVideo=type('PlaylistVideo', (), {}), Course=type('Course', (), {}),
    CourseVideo=type('CourseVideo', (), {}), CoursePlaylist=type('CoursePlaylist', (), {}),
    ErrorLog=type('ErrorLog', (), {}), utcnow=lambda: None,
)
sys.modules['security'] = SimpleNamespace(decrypt_json=lambda x: {}, encrypt_json=lambda x: '')
path = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('sync_test_target', path/'services'/'youtube.py')
service = importlib.util.module_from_spec(spec)
spec.loader.exec_module(service)

class FakeResponse:
    def __init__(self, status_code, reason):
        self.status_code = status_code
        self.ok = status_code == 200
        self.text = '{"error":"internal raw details"}'
        self.reason = reason
    def json(self):
        return {'error': {'errors': [{'reason': self.reason}]}}

# Dịch lỗi 403 sang hướng dẫn tiếng Việt, không lộ URL kỹ thuật.
for reason, code in [('forbidden','permission'),('insufficientPermissions','permission'),
                     ('quotaExceeded','quota'),('accessNotConfigured','configuration')]:
    error = service._friendly_http_error(FakeResponse(403, reason))
    assert error.code == code, (reason, error.code)
    assert 'https://' not in str(error) and '403 Client Error' not in str(error)

# Dù cùng 0 video, có phản hồi kênh hợp lệ mới được coi là kênh trống.
empty = service.build_sync_summary([SimpleNamespace(videos=[])], [])
assert empty['ok'] is True and empty['status'] == 'empty'
assert 'chưa tìm thấy video' in empty['message']
ready = service.build_sync_summary([SimpleNamespace(videos=[SimpleNamespace(is_available=True)])], [])
assert ready['ok'] and ready['status'] == 'synced'

issues=service.SyncIssues()
issues.codes.append('permission')
issues.append('GV: YouTube chưa cho phép truy cập dữ liệu kênh')
for channels, target in [([], 'permission'),([SimpleNamespace(videos=[])], 'partial')]:
    result=service.build_sync_summary(channels,issues)
    assert result['ok'] is False and result['status'] == target
    assert result['status'] != 'empty'

no_channel=service.SyncIssues(); no_channel.codes.append('no_channel')
no_channel.append('GV: Không tìm thấy kênh YouTube thuộc tài khoản này.')
result=service.build_sync_summary([],no_channel)
assert result['status']=='no_channel'

# Nếu channels.list trả về danh sách trống, phải giải thích thiếu kênh, không là thiếu video.
user=SimpleNamespace(id=1, email='example@edu.vn')
service._get=lambda *args,**kwargs:{'items':[]}
channels, issues=service.sync_all_connected_channels(user)
assert channels==[] and issues.codes==['no_channel']
assert service.build_sync_summary(channels,issues)['status']=='no_channel'

# Nếu YouTube từ chối, 0 kênh/0 video không được diễn giải là kênh trống.
service._get=lambda *args,**kwargs: (_ for _ in ()).throw(service.YouTubeSyncError('permission','Không có quyền'))
channels, issues=service.sync_all_connected_channels(user)
assert channels==[] and issues.codes==['permission']
assert service.build_sync_summary(channels,issues)['status']=='permission'

html=(path/'templates'/'sync_wait.html').read_text()
assert 'status===\'empty\'' in html and "status==='no_channel'" in html
assert "['permission','configuration','quota']" in html
assert '403 Client Error' not in html
assert 'go-youtube' in html
analytics=(path/'templates'/'analytics.html').read_text()
assert 'Các chỉ số lấy từ nhật ký quét QR gốc' not in analytics
assert 'Tổng lượt quét' in analytics and 'Tỷ lệ quét thành công' in analytics
print('OK: thông báo kênh trống, thiếu kênh, lỗi 403, quota, cấu hình API và giao diện.')
