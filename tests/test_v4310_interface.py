"""Smoke regression: run `python tests/test_v4310_interface.py` without Flask or OAuth."""
import ast
from pathlib import Path
from types import SimpleNamespace as O
from datetime import datetime
from urllib.parse import urlencode
from bs4 import BeautifulSoup
from jinja2 import Environment, FileSystemLoader
P=Path(__file__).resolve().parents[1]
a=(P/'app.py').read_text()
endpoints={n.name for n in ast.walk(ast.parse(a)) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}

def url_for(name,**params):
    assert name in endpoints or name=='static',name
    return '/'+name+('?' + urlencode(params) if params else '')

env=Environment(loader=FileSystemLoader(str(P/'templates')))
env.globals.update(url_for=url_for,csrf_token=lambda:'csrf-test',get_flashed_messages=lambda **kw:[])
me=O(id=8,role='lecturer',name='GV kiểm tra',email='teacher@example.test',lecturer_code='GV0008')
cs=[O(id=i,name=f'Môn học {i}',owner_id=8,active=True) for i in (1,2)]
ch=O(title='Kênh YouTube GV',uploads_playlist_id='uploads',user_id=8)
v=O(id=33,title='Video thực hành',youtube_video_id='yt-33',thumbnail_url='',channel=ch, is_available=True,embeddable=True, privacy_status='public',status_label='Công khai',playlist_links=[],course_links=[])
p=O(id=11,title='Playlist 1',channel=ch,is_available=True,privacy_status='public',video_links=[],course_links=[],youtube_playlist_id='playlist1')
qv=O(id=20,slug='v20',active=True,course_id=1,course=cs[0],is_playlist=False,title=v.title,created_at=datetime.now(),current_target=O(video=v),playlist=None)
qp=O(id=21,slug='p21',active=True,course_id=1,course=cs[0],is_playlist=True,title=p.title,created_at=datetime.now(),current_target=None,playlist=p)
v.course_links=[O(course_id=1,course=cs[0],video=v,qr=qv)]
p.course_links=[O(course_id=1,course=cs[0],active=True,qr=qp), O(course_id=2,course=cs[1],active=True,qr=None)]
p.video_links=[O(video=v)]
v.playlist_links=[O(playlist=p)]

def ctx(**kw):
    d=dict(me=me,app_name='TẠO MÃ QR',brand_logo='x.png',school_name='Trường Cao đẳng',active_section='videos',authors=[],has_homeroom_classes=False,completion_threshold=.9,request=O(query_string=b'p_page=2&v_page=2'),courses=cs,available_playlists=[p],playlists=[p],videos=[v],retarget_videos=[v],library_args={'p_page':'2','v_page':'2'},playlist_total=8,playlist_page=2,playlist_pages=2,video_total=12,video_page=2,video_pages=3,playlist_search='',playlist_assignment='',search='',status='',assignment='',playlist_filter_id=None)
    d.update(kw)
    return d

html=env.get_template('videos.html').render(**ctx())
soup=BeautifulSoup(html,'html.parser')
assert soup.select_one('tr#playlist-11 .playlist-qr-create')
assert soup.select_one('tr#playlist-11 .playlist-qr-download')
assert soup.select_one('tr#playlist-11 .playlist-qr-delete-form')
assert not soup.select('tr#playlist-11 .playlist-qr-preview')
assert soup.select_one('tr#playlist-11 select option[data-qr-delete]')
assert soup.select_one('tr#video-33 select option[data-qr-png]')
assert soup.select_one('tr#video-33 .video-qr-download')
assert soup.select_one('tr#video-33 .video-qr-delete')
assert soup.select_one('tr#video-33 .video-qr-retarget')
assert soup.select_one('tr#video-33 .video-qr-retarget select option[value="33"]')
assert not soup.select('form form'), 'Nested forms!'
assert '5 dòng/trang' in html
assert any('v_page=3' in x.get('href','') and 'p_page=2' in x.get('href','') for x in soup.select('a.page-link')), 'Pagination missing other group state'
assert 'data-library-qr-form' in html and 'window.scrollTo(originalX,originalY)' in html
print('PASS: playlists/videos paged independently; QR state/create/download/delete/retarget; scroll preserved; no nested forms')

html=env.get_template('qr.html').render(**ctx(qrs=[qv,qp],videos=[v],selected_course=cs[0],selected_course_id=1,total_qrs=2,qr_needs_review=set()))
soup=BeautifulSoup(html,'html.parser')
for qr_id in (20,21):
    row=next(x for x in soup.select('table.qr-inventory-table tbody tr') if f'/qr_png?qr_id={qr_id}' in str(x))
    assert row.find(string=lambda x:x and 'Mở thử' in x)
    assert row.find(string=lambda x:x and 'Xóa' in x)
assert soup.select_one('table.qr-inventory-table button[data-bs-target="#qr-edit-20"]')
assert len(soup.select('table.qr-inventory-table button[data-bs-target="#qr-edit-21"]'))==0
print('PASS: QR inventory supports playlist/video PNG, preview, delete; video retarget')

# Playlist no longer supplied by YouTube keeps visible source status for cleanup, rather than delete records.
p.is_available=False
html=env.get_template('videos.html').render(**ctx())
assert 'Playlist không còn trên YouTube' in html
print('PASS: unavailable playlist labelled for QR deactivation')

assert 'mismatching_state' in a and 'oauth_retry_attempt' in a
assert 'system_actors' in a and 'sys_actor_id' in a
assert 'video_total = q.count()' in a and 'playlist_total = pq.count()' in a
print('PASS: OAuth mismatch guarded, stats dropdown wired, SQL pagination backend')
