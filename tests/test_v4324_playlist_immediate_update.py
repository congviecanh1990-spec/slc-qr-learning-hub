"""Offline acceptance tests: the updated playlist row is independent of list pagination/filter."""
from pathlib import Path
import ast
from datetime import datetime
from types import SimpleNamespace as NS
from jinja2 import Environment, FileSystemLoader, select_autoescape
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]
tpl=(ROOT/'templates/videos.html').read_text()
fragment=(ROOT/'templates/_playlist_library_row.html').read_text()
app=(ROOT/'app.py').read_text()

def fake_url_for(name, **kwargs):
    if name=='set_playlist_course_assignments': return f'/playlists/{kwargs["playlist_id"]}/set-courses'
    if name=='create_playlist_qr_from_library': return f'/playlists/{kwargs["playlist_id"]}/qr'
    if name=='qr_png': return f'/qr/{kwargs["qr_id"]}.png'
    if name=='delete_qr': return f'/qr/{kwargs["qr_id"]}/delete'
    if name=='qr_retarget_playlist': return f'/qr/{kwargs["qr_id"]}/retarget'
    return '/'+name

env=Environment(loader=FileSystemLoader(str(ROOT/'templates')),autoescape=select_autoescape(('html',)))
env.globals.update(url_for=fake_url_for,csrf_token=lambda:'csrf-unit-test',get_flashed_messages=lambda **_ : [])
lecturer=NS(id=7,name='Cô Tươi',email='gv@example.test',role='lecturer')
course=NS(id=5,owner_id=7,active=True,name='Lập trình Python')
channel=NS(title='YouTube giảng viên')
video=NS(id=11,title='Kiểu dữ liệu list',is_available=True,embeddable=True,privacy_status='public')
p=NS(id=39,title='LT python – Kiểu dữ liệu list', channel=channel, video_links=[NS(video=video)],
     course_links=[],is_available=True,privacy_status='unlisted')

def render_row():
    return BeautifulSoup(env.get_template('_playlist_library_row.html').render(p=p,courses=[course],
        replacement_playlists=[p],me=lecturer,request=NS(query_string=b'p_assignment=unassigned&p_page=3'),
        library_return_query='p_assignment=unassigned&p_page=3'),'html.parser')

# First rendering under 'Chưa gán' filter: QR absent.
before=render_row()
assert before.select_one('tr#playlist-39')
assert not before.select_one('.playlist-qr-actions')
assert 'Lưu trước' in before.select_one('td:last-child').get_text()
# After saving: the fragment MUST be rendered independently, even though on list
# page 3 'unassigned' it would not exist anymore.
p.course_links=[NS(course_id=5, course=course, active=True, qr=None)]
after=render_row()
assert after.select_one('.playlist-qr-course-select option')['value']=='5'
assert after.select_one('.playlist-qr-create') and not after.select_one('.playlist-qr-create').has_attr('disabled')
assert after.select_one('tr#playlist-39')['data-playlist-usable']=='1'
assert after.select_one('.course-picker-label').get_text(strip=True)=='Đã chọn 1 môn học/ mô đun'
assert after.select_one('.course-picker-summary')
# Idempotent same QR renders 'Tải' actions from existing QR id.
p.course_links=[NS(course_id=5, course=course, active=True, qr=NS(id=91,active=True))]
after_qr=render_row()
assert after_qr.select_one('.playlist-qr-course-select option')['data-qr-png']=='/qr/91.png'
# Removing assignment must remove QR controls immediately.
p.course_links[0].active=False
unassigned=render_row()
assert not unassigned.select_one('.playlist-qr-actions')
# No eligible playable video -> cannot offer active Create QR action.
p.course_links[0].active=True
p.video_links=[]
empty=render_row()
assert empty.select_one('tr#playlist-39')['data-playlist-usable']=='0'
assert empty.select_one('.playlist-qr-create').has_attr('disabled')
# Malicious playlist title/course name should be escaped in JSON HTML before insertion.
p.title='<script>alert("test")</script>'
course.name='<svg/onload=alert(1)>'
assert '<script>' not in env.get_template('_playlist_library_row.html').render(p=p,courses=[course],
    replacement_playlists=[p],me=lecturer,library_return_query='')
# JS must use a server-returned fragment, not a filtered /videos list.
assert 'result.row_html' in tpl and 'fragment.content.querySelector' in tpl
assert 'newRow.id !== row.id' in tpl
assert "response.headers.get('content-type')" in tpl
assert "row.replaceWith(newRow)" in tpl
assert "row.dataset.playlistUsable!=='1'" in tpl
assert 'hãy lọc lại để xem trạng thái mới' not in tpl
# Server must return JSON fragment after commit (not a redirect requiring pagination).
mod=ast.parse(app)
route=next(n for n in ast.walk(mod) if isinstance(n,ast.FunctionDef) and n.name=='set_playlist_course_assignments')
src=ast.get_source_segment(app,route)
assert 'db.session.commit()' in src
assert '"X-Requested-With"' in src and 'playlist_library_row_json(playlist_id, user)' in src
assert 'playlist_library_row_json(playlist_id, user)' in src
helper=next(n for n in ast.walk(mod) if isinstance(n,ast.FunctionDef) and n.name=='playlist_library_row_json')
assert 'db.session.expire_all()' in ast.get_source_segment(app,helper) and '"row_html"' in ast.get_source_segment(app,helper)
assert 'return redirect(videos_library_return(' in src  # non-JS fallback
create=next(n for n in ast.walk(mod) if isinstance(n,ast.FunctionDef) and n.name=='create_playlist_qr_from_library')
assert 'return playlist_library_row_json(playlist.id, user)' in ast.get_source_segment(app,create)
print('PASS v4.3.24: render independent of filter/page, immediate QR selection, remove/empty, escaped text, AJAX server contract.')
