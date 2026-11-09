"""v4.3.25: filter is re-applied to persisted assignment; routine success notices removed.
Run offline with SQLAlchemy/Jinja2, no Google or PostgreSQL access.
"""
from pathlib import Path
import ast
import sys
import types
import sqlalchemy as sa
from sqlalchemy.orm import declarative_base, relationship, backref, sessionmaker
from jinja2 import Environment, FileSystemLoader
from bs4 import BeautifulSoup

root = Path(__file__).resolve().parents[1]
app_source = (root / 'app.py').read_text()
html = (root / 'templates/videos.html').read_text()
row_html = (root / 'templates/_playlist_library_row.html').read_text()

# Verify the exact SQLAlchemy expression used by the live /videos route,
# rather than testing only a separately written approximation.
parsed = ast.parse(app_source)
route = next(n for n in ast.walk(parsed) if isinstance(n, ast.FunctionDef) and n.name == 'videos_page')
assigned = next(n for n in ast.walk(route) if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == 'playlist_has_assignment' for t in n.targets))
expr_code = compile(ast.fix_missing_locations(ast.Expression(body=assigned.value)), '<route-filter>', 'eval')

# Reuse real ORM classes with an isolated, in-memory DB and a mocked Flask-SQLAlchemy layer.
class SQLAlchemy:
    def __init__(self):
        self.Model = declarative_base()
        for name in ('Column','Integer','String','Text','Date','DateTime','Boolean','Float','ForeignKey'):
            setattr(self, name, getattr(sa, name))
        self.relationship = relationship
        self.backref = backref

sys.modules['flask_sqlalchemy'] = types.SimpleNamespace(SQLAlchemy=SQLAlchemy)
sys.path.insert(0, str(root))
import models
engine = sa.create_engine('sqlite:///:memory:')
models.db.Model.metadata.create_all(engine)
s = sessionmaker(bind=engine)()

user = models.User(email='own@example.test',name='GV',role='lecturer')
other = models.User(email='other@example.test',name='GV khác',role='lecturer')
s.add_all([user,other]); s.flush()
channel = models.YouTubeChannel(user_id=user.id,channel_id='ch-test',title='Kênh lớp')
s.add(channel); s.flush()
p1=models.Playlist(channel_id=channel.id,youtube_playlist_id='pl-one',title='Đã gán',is_available=True)
p2=models.Playlist(channel_id=channel.id,youtube_playlist_id='pl-two',title='Chưa gán',is_available=True)
p3=models.Playlist(channel_id=channel.id,youtube_playlist_id='pl-three',title='Gán khóa học khác',is_available=True)
s.add_all([p1,p2,p3]); s.flush()
c1=models.Course(owner_id=user.id,code='C1',name='Lập trình Python',active=True)
c2=models.Course(owner_id=other.id,code='C2',name='Môn khác',active=True)
s.add_all([c1,c2]);s.flush()
link=models.CoursePlaylist(course_id=c1.id,playlist_id=p1.id,active=True,added_by=user.id)
other_link=models.CoursePlaylist(course_id=c2.id,playlist_id=p3.id,active=True,added_by=other.id)
s.add_all([link,other_link]);s.commit()

scope={'select':sa.select,'CoursePlaylist':models.CoursePlaylist,'Course':models.Course,
       'Playlist':models.Playlist, 'user':user}
condition=eval(expr_code,scope)

def fetch(mode):
    q=s.query(models.Playlist).join(models.YouTubeChannel).filter(models.YouTubeChannel.user_id==user.id)
    if mode=='unassigned': q=q.filter(~condition)
    elif mode=='assigned': q=q.filter(condition)
    return [p.id for p in q.order_by(models.Playlist.id).all()]

assert fetch('unassigned')==[p2.id,p3.id],fetch('unassigned')
assert fetch('assigned')==[p1.id]
# From the actual persisted relationship, the just-saved playlist must disappear
# when user clicks "Lọc playlist" with "Chưa gán" selected.
link.active=False;s.commit()
assert p1.id in fetch('unassigned') and p1.id not in fetch('assigned')
link.active=True;s.commit()
assert p1.id not in fetch('unassigned') and p1.id in fetch('assigned')
# If the course is archived, it is not an applicable active assignment.
c1.active=False;s.commit()
assert p1.id in fetch('unassigned')
c1.active=True;s.commit()

# Check server filter branch and cache invalidation.
route_src=ast.get_source_segment(app_source,route)
assert 'pq = pq.filter(~playlist_has_assignment)' in route_src
assert 'pq = pq.filter(playlist_has_assignment)' in route_src
assert '"private, no-store, max-age=0"' in route_src
# Browser GET form must submit the actual selected dropdown and not re-submit stale paging.
soup=BeautifulSoup(html,'html.parser')
form=soup.select_one('form#playlistLibraryFilterForm')
assert form and form.get('method')=='get'
assert form.select_one('select[name="p_assignment"]')
assert not form.select_one('[name="p_page"]')
assert form.select_one('button').get_text(strip=True)=='Lọc playlist'
# Success is represented by actual updated controls. Error alerts remain.
for stale in ('Đã xử lý. Trạng thái mã QR đã được cập nhật.',
              'Đã thực hiện thao tác. Có thể cần điều chỉnh bộ lọc',
              'Đã lưu. Môn học/mô đun và mã QR đã được cập nhật.',
              'Đang áp dụng cho {{ active_course_ids|length }} môn học/ mô đun'):
    assert stale not in html+row_html,stale
assert 'Chưa xác nhận được kết quả lưu' in html
assert 'qr-action-error' in html
assert 'row.replaceWith(newRow)' in html
assert 'playlist-qr-create' in row_html
assert 'playlist-qr-download' in row_html
assert "selectattr('course.owner_id', 'equalto', me.id)" in row_html
assert 'course-picker-summary' in row_html
print('PASS v4.3.25: persisted class filter, reassign/remove, unrelated owners, cache, silent success UI, immediate QR.')
