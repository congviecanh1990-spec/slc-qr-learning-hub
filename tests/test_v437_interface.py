"""Smoke test v4.3.7 interfaces with fixture data, no OAuth/Flask/DB needed.
Usage: python tests/test_v437_interface.py (jinja2 required).
"""
import ast
from pathlib import Path
from types import SimpleNamespace as Obj
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
source = (ROOT / 'app.py').read_text()
node = ast.parse(source)
endpoint_names = {f.name for f in ast.walk(node) if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef))}
expected_routes = {'set_playlist_course_assignments','create_playlist_qr_from_library','create_video_qr_from_library','download_course_qrs','qr_page'}
assert expected_routes.issubset(endpoint_names)

# url_for mock tests template wiring instead of full Flask runtime.
def url_for(endpoint, **params):
    assert endpoint in endpoint_names or endpoint in {'static'}, endpoint
    suffix = ('/' + '/'.join(f'{k}={v}' for k,v in params.items())) if params else ''
    return '/' + endpoint + suffix

env = Environment(loader=FileSystemLoader(str(ROOT / 'templates')))
env.globals.update(url_for=url_for, csrf_token=lambda: 'example-csrf', get_flashed_messages=lambda **kw: [])
me=Obj(id=12, role='lecturer', name='Giảng viên thử', email='gv@example.test', lecturer_code='GV0012')
course=Obj(id=5, name='Môn A', owner_id=me.id, active=True, video_links=[], playlist_links=[], school_class_links=[], department_name='CNTT',faculty_name='Khoa A')
channel=Obj(title='Kênh GV', uploads_playlist_id='uploads-id', channel_id='owner-chan')
video=Obj(id=33,title='Video hướng dẫn',youtube_video_id='yt-33',thumbnail_url='',channel=channel,
          is_available=True,embeddable=True,privacy_status='public',status_label='Có thể sử dụng',
          playlist_links=[], course_links=[])
playlist=Obj(id=11,title='Playlist A',channel=channel,is_available=True,privacy_status='public',
             video_links=[Obj(video=video)],course_links=[],youtube_playlist_id='list-id')
pcl=Obj(course_id=course.id, course=course, playlist=playlist, active=True, qr=None)
playlist.course_links.append(pcl)
vc=Obj(course_id=course.id,course=course,video=video,qr=None)
video.course_links.append(vc)
video.playlist_links.append(Obj(playlist=playlist))

def base(**kwargs):
    return dict(me=me, app_name='TẠO MÃ QR',brand_logo='img.png', school_name='Trường CĐ',
                active_section='videos',has_homeroom_classes=False,authors=['Nhóm nghiên cứu'],
                request=Obj(query_string=b'p_q=Playlist+A&status=usable'),
                playlist_search='',playlist_assignment='',search='',status='',assignment='',
                playlist_filter_id=None,completion_threshold=0.9,
                **kwargs)

html = env.get_template('videos.html').render(**base(videos=[video], playlists=[playlist],
                                                courses=[course], available_playlists=[playlist]))
soup=BeautifulSoup(html,'html.parser')
assert len(soup.select('tr#playlist-11 form[action^="/create_playlist_qr_from_library"]'))==1
assert len(soup.select('tr#video-33 form[action^="/create_video_qr_from_library"]'))==1
assert soup.select_one('tr#playlist-11 form[action^="/set_playlist_course_assignments"] input[name="return_query"]')
assert 'Chưa có mã QR' in soup.select_one('tr#video-33 td:nth-of-type(4)').get_text()
assert soup.select_one('input.video-check')['form']=='assignVideoForm'
assert len(soup.select('form form'))==0, 'Nested forms invalid'
assert len(soup.select('tr#playlist-11 form select[name="course_id"]'))==1

qr=Obj(id=6,slug='testslug',title='Video hướng dẫn',course=course,course_id=course.id,
       current_target=Obj(video=video),is_playlist=False,created_at=datetime(2026,10,20),
       playlist=None)
html=env.get_template('qr.html').render(**base(courses=[course],qrs=[qr],videos=[video],
                  qr_needs_review=set(), selected_course=course, selected_course_id=5, total_qrs=1))
soup=BeautifulSoup(html, 'html.parser')
assert soup.select_one('#qr-course-filter select[name="course_id"]')
assert soup.find(string=lambda x:x and 'Tải mã QR' in x)
assert not soup.find(string=lambda x:x and 'Tạo QR riêng lẻ' in x)
assert not soup.find(string=lambda x:x and 'Tạo mã QR tự động theo môn học' in x)
assert soup.find(string=lambda x:x and 'Đổi video đích' in x)
assert len(soup.select('form form'))==0
print('PASS: template video, playlist, redirect fields, course ZIP, QR inventory, no nested forms')
