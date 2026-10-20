"""Jinja2 render checks for admin-only transfer controls (offline)."""
from pathlib import Path
from datetime import datetime
from types import SimpleNamespace as X
import ast
from bs4 import BeautifulSoup
from jinja2 import Environment, FileSystemLoader, StrictUndefined

ROOT=Path(__file__).resolve().parents[1]
app_ast=ast.parse((ROOT/'app.py').read_text())
routes={n.name for n in ast.walk(app_ast) if isinstance(n,ast.FunctionDef)}
assert 'transfer_course_owner' in routes
url_for=lambda endpoint,**kwargs:'/'+endpoint

env=Environment(loader=FileSystemLoader(str(ROOT/'templates')))
env.globals.update(url_for=url_for,csrf_token=lambda:'valid-csrf',get_flashed_messages=lambda **k: [])
a=X(id=1,name='GV A',email='a@school.example',role='lecturer',lecturer_code='GV0001')
b=X(id=2,name='GV B',email='b@school.example',role='lecturer',lecturer_code='GV0002')
admin=X(id=3,name='QT',email='qt@school.example',role='admin',lecturer_code='GV0003')
c=X(id=5,code='HP000005',name='Lập trình',owner=a, owner_id=a.id,video_links=[],playlist_links=[],school_class_links=[],department_name='CNTT',faculty_name='KT')
transfer=X(effective_on=datetime(2026,10,20),course=c,previous_owner=a,new_owner=b,administrator=admin)

def render(me):
    html=env.get_template('courses.html').render(me=me,courses=[c] if me==a else [],
      transfer_courses=[c] if me==admin else [],transfer_lecturers=[a,b,admin] if me==admin else [],
      transfer_history=[transfer] if me==admin else [],department_options=[],faculty_options=[],available_school_classes=[])
    return BeautifulSoup(html,'html.parser')

s=render(admin)
assert s.select_one('#admin-course-transfer form[action="/transfer_course_owner"]')
assert s.select_one('#admin-course-transfer select[name="new_owner_id"]')
assert s.select_one('#admin-course-transfer input[name="csrf_token"]')
assert s.select_one('#admin-course-transfer input[name="confirm_transfer"][required]')
assert len(s.select('form form'))==0
assert 'GV A' in s.select_one('#admin-course-transfer details').get_text()
assert s.select_one('option[value="5"]')
s=render(a)
assert not s.select_one('#admin-course-transfer')
assert len(s.select('form form'))==0
print('PASS: Quản trị viên có bàn giao và lịch sử; GV thường không có; biểu mẫu hợp lệ')
