"""Offline templates tests without Flask."""
import ast
from pathlib import Path
from types import SimpleNamespace as O
from datetime import datetime
from urllib.parse import urlencode
from jinja2 import Environment, FileSystemLoader
from bs4 import BeautifulSoup
P=Path(__file__).resolve().parents[1]
functions={n.name for n in ast.walk(ast.parse((P/'app.py').read_text())) if isinstance(n,ast.FunctionDef)}
def url_for(name,**kw):
    assert name in functions or name=='static',name
    return '/'+name+('?' + urlencode(kw) if kw else '')
env=Environment(loader=FileSystemLoader(str(P/'templates')))
env.globals.update(url_for=url_for,csrf_token=lambda:'csrf',get_flashed_messages=lambda **kw:[])
me=O(id=1,role='lecturer',name='GV',email='gv@example.test')
course=O(id=5,name='Môn A',owner_id=1,active=True)
channel=O(title='Kênh',user_id=1,uploads_playlist_id='uploads',channel_id='YTID',hub_subscription=None,last_synced_at=None,videos=[],playlists=[])
p=O(id=10,title='Playlist cũ',is_available=False,channel=channel,privacy_status='public',video_links=[],youtube_playlist_id='old')
p2=O(id=11,title='Playlist mới',is_available=True,channel=channel,privacy_status='public',video_links=[],youtube_playlist_id='new')
qr=O(id=30,title=p.title,slug='slug',course_id=5,course=course,playlist_id=p.id,is_playlist=True,playlist=p,active=True,created_at=datetime.now())
p.course_links=[O(qr=qr,active=True,course_id=5,course=course)];p2.course_links=[]
ctx=dict(me=me,app_name='TẠO MÃ QR',brand_logo='img.png',school_name='Trường CĐ',active_section='videos',authors=[],has_homeroom_classes=False,completion_threshold=.9,
         request=O(query_string=b''),playlists=[p],videos=[],courses=[course],available_playlists=[p2],replacement_playlists=[p2],
         retarget_videos=[],playlist_search='',playlist_assignment='',search='',status='',assignment='',playlist_filter_id=None,
         library_args={},qrs=[qr],qr_needs_review=set(),selected_course=course,selected_course_id=5,total_qrs=1,
         channels=[channel],extra_accounts=[],hub_events=[])
for path in (P/'templates').glob('*.html'):
    env.parse(path.read_text())
html=env.get_template('videos.html').render(**ctx)
s=BeautifulSoup(html,'html.parser')
assert not s.select('form form')
assert s.select_one('tr#playlist-10 option[data-qr-retarget-playlist]')
assert s.select_one('tr#playlist-10 form.playlist-qr-retarget select option[value="11"]')
assert s.select_one('tr#playlist-10 .playlist-qr-retarget-toggle')
assert "window.scrollTo(originalX,originalY)" in html
html=env.get_template('qr.html').render(**ctx)
s=BeautifulSoup(html,'html.parser')
assert s.select_one('#qr-edit-30 form[action^="/qr_retarget_playlist"] select option[value="11"]')
assert s.select_one('table.qr-inventory-table button[data-bs-target="#qr-edit-30"]')
assert not s.select('form form')
for btn in s.select('a.btn,button.btn'):
    label=btn.get_text(' ',strip=True)
    if 'Tải' in label and 'mã QR' in label:assert label in ('Tải mã QR','Tải tất cả mã QR'),label
    if 'Xóa' in label and 'mã QR' in label:assert label in ('Xóa mã QR','Xóa tất cả mã QR'),label
html=env.get_template('youtube.html').render(**ctx)
assert 'Playlist đã đồng bộ' not in html
assert 'Kết nối nhiều kênh' in html
print('PASS: v4.3.11 both playlist retarget interfaces, buttons, no nested forms, YouTube layout, 22 parsed templates')
