"""UI v4.3.9 checks without OAuth/Flask: python tests/test_v439_interface.py"""
from pathlib import Path
from types import SimpleNamespace as Obj
from datetime import datetime
import ast
from bs4 import BeautifulSoup
from jinja2 import Environment, FileSystemLoader

ROOT=Path(__file__).resolve().parents[1]
src=(ROOT/'app.py').read_text()
endpoint_names={f.name for f in ast.walk(ast.parse(src)) if isinstance(f,(ast.FunctionDef,ast.AsyncFunctionDef))}
def url_for(name,**params):
    assert name in endpoint_names or name == 'static',name
    return '/' + name + ('?' + '&'.join(f'{k}={v}' for k,v in params.items()) if params else '')
env=Environment(loader=FileSystemLoader(str(ROOT/'templates')))
env.globals.update(url_for=url_for,csrf_token=lambda:'test-csrf',get_flashed_messages=lambda **kwargs:[])
me=Obj(id=12,role='lecturer',name='Giảng viên thử',email='gv@example.test',lecturer_code='GV0012')
c1=Obj(id=5,name='Lập trình Python',owner_id=12,active=True)
c2=Obj(id=6,name='Cơ sở dữ liệu',owner_id=12,active=True)
channel=Obj(title='Kênh GV',uploads_playlist_id='uploads-id',channel_id='owner-chan')
playlist=Obj(id=11,title='Playlist thí nghiệm',channel=channel,is_available=True,privacy_status='public',video_links=[],course_links=[],youtube_playlist_id='list-id')
playlist_qr=Obj(id=55,slug='s55',title=playlist.title,course=c1,course_id=c1.id,is_playlist=True,playlist=playlist,created_at=datetime(2026,10,20),current_target=None,active=True)
playlist.course_links=[Obj(course=c1,course_id=c1.id,active=True,qr=playlist_qr),Obj(course=c2,course_id=c2.id,active=True,qr=None)]
video=Obj(id=33,title='Video thực hành',youtube_video_id='yt-33',thumbnail_url='',channel=channel,is_available=True,embeddable=True,privacy_status='public',status_label='Có thể sử dụng',playlist_links=[],course_links=[])
playlist.video_links=[Obj(video=video)]
video.playlist_links=[Obj(playlist=playlist)]
def base(**kwargs):
    return dict(me=me, app_name='TẠO MÃ QR',brand_logo='img.png', school_name='Trường CĐ',active_section='videos',has_homeroom_classes=False,authors=['Nhóm'],completion_threshold=.9,request=Obj(query_string=b''),playlist_search='',playlist_assignment='',search='',status='',assignment='',playlist_filter_id=None,**kwargs)
html=env.get_template('videos.html').render(**base(videos=[video],playlists=[playlist],courses=[c1,c2],available_playlists=[playlist]))
soup=BeautifulSoup(html,'html.parser')
opts=soup.select('tr#playlist-11 .playlist-qr-course-select option')
assert len(opts)==3
assert not opts[0].get('data-qr-png')
assert opts[1]['data-qr-png'].startswith('/qr_png?qr_id=55')
assert opts[1]['data-qr-delete'].startswith('/delete_qr?qr_id=55')
assert not opts[2].get('data-qr-png')
assert soup.select_one('tr#playlist-11 .playlist-qr-download')
assert soup.select_one('tr#playlist-11 .playlist-qr-delete-form')
assert soup.select_one('tr#playlist-11 form.playlist-course-form')
assert 'window.scrollTo(oldScrollX, oldScrollY)' in html
assert 'row.replaceWith(newRow)' in html
assert not soup.select('form form'), 'Invalid nested forms'
print('PASS: playlist existing QR vs not-yet-created QR per subject, ajax save without rerender')
html=env.get_template('qr.html').render(**base(courses=[c1,c2],qrs=[playlist_qr],videos=[video],qr_needs_review=set(),selected_course=c1,selected_course_id=5,total_qrs=1))
soup=BeautifulSoup(html,'html.parser')
assert soup.select_one('a[href^="/qr_download_all?course_id=5"]')
assert soup.find(string=lambda x:x and 'Tải mã QR (PNG)' in x)
assert soup.find(string=lambda x:x and 'Mở thử' in x)
print('PASS: QR page filtered ZIP, playlist download/preview links restored')
html=env.get_template('errors.html').render(**base(error_rows=[dict(log=Obj(created_at=datetime(2026,10,20),message='Lỗi',details='Chi tiết'),actor_name='Nguyễn Văn An (123 – Lớp A)',action='Quét QR',course_module='Lập trình Python')]))
soup=BeautifulSoup(html,'html.parser')
assert soup.find(string=lambda x:x and 'Người thực hiện thất bại' in x)
assert soup.find(string=lambda x:x and 'Nguyễn Văn An (123 – Lớp A)' in x)
print('PASS: error log actor column')
html=env.get_template('identify.html').render(**base(qr=Obj(slug='abc'),message=None,class_choices=[dict(id=1,name='K66A')]))
assert "student.short_code" in html
assert 'student.id' in html
print('PASS: student UI shows 3 digits but POST uses database student id')
html=env.get_template('courses.html').render(**base(courses=[],available_school_classes=[],departments=[],faculties=[],all_courses=[], lecturers=[], course_transfers=[]))
assert 'course-creation-notice' in html
assert 'không tạo thêm môn học trùng tên' in html
print('PASS: course guidance prominent')
