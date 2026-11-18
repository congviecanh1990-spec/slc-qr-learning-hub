"""v4.3.31: one-use bulk course redirect and secure merge of organization labels.

The application relies on Flask in production; validate the exact application
helpers against real SQLAlchemy data in SQLite without needing OAuth/Render.
"""
import ast
import re
import sys
import types
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, parse_qs

import sqlalchemy as sa
from sqlalchemy.orm import declarative_base, relationship, backref, sessionmaker
from jinja2 import Environment, FileSystemLoader

ROOT=Path(__file__).resolve().parents[1]
src=(ROOT/'app.py').read_text(encoding='utf-8')
module=ast.parse(src)
funcs={n.name:n for n in ast.walk(module) if isinstance(n,ast.FunctionDef)}

class SQLAlchemy:
    def __init__(self):
        self.Model=declarative_base()
        for attr in ('Column','Integer','String','Text','Date','DateTime','Boolean','Float','ForeignKey'):
            setattr(self,attr,getattr(sa,attr))
        self.relationship=relationship
        self.backref=backref
sys.modules['flask_sqlalchemy']=types.SimpleNamespace(SQLAlchemy=SQLAlchemy)
sys.path.insert(0,str(ROOT))
import models as m
engine=sa.create_engine('sqlite:///:memory:')
m.db.Model.metadata.create_all(engine)
m.db.session=sessionmaker(bind=engine)()
class Query:
    def __get__(self, obj, owner):return m.db.session.query(owner)
for mp in m.db.Model.registry.mappers:mp.class_.query=Query()
s=m.db.session

admin=m.User(email='admin@example.com',name='Admin',role='admin',faculty_name='KTCN',department_name='CNTT')
u1=m.User(email='a@example.com',role='lecturer',faculty_name='KTCN',department_name='CNTT')
u2=m.User(email='b@example.com',role='lecturer',faculty_name='Kỹ thuật công nghệ',department_name='Công nghệ thông tin')
s.add_all([admin,u1,u2]);s.flush()
c1=m.Course(owner_id=u1.id,code='A',name='Môn A',faculty_name='KTCN',unit_name='KTCN',department_name='CNTT',active=True)
c2=m.Course(owner_id=u2.id,code='B',name='Môn B',faculty_name='Kỹ thuật công nghệ',unit_name='Kỹ thuật công nghệ',department_name='Công nghệ thông tin',active=True)
c3=m.Course(owner_id=u1.id,code='C',name='Môn cũ',faculty_name=None,unit_name='KTCN',department_name='CNTT',active=False)
s.add_all([c1,c2,c3]);s.commit()

scope={"re":re,"db":m.db,"User":m.User,"Course":m.Course,"EditHistory":m.EditHistory,
       "parse_qsl":parse_qsl,"urlencode":urlencode,"url_for":lambda x:'/videos'}

def load(name):
    n=funcs[name]
    clone=ast.FunctionDef(name=n.name,args=n.args,body=n.body,decorator_list=[],returns=n.returns,type_comment=None)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[clone],type_ignores=[])),
                 f'<{name}>','exec'),scope)
for name in ['normalized_catalog_name','videos_library_return','videos_library_return_with_bulk_course',
             'audit_edit','catalog_admin_statistics','apply_catalog_name_change']:
    load(name)

before=scope['catalog_admin_statistics']()
assert len(before['faculty_name'])==2, before
assert {row['value'] for row in before['department_name']}=={'CNTT','Công nghệ thông tin'}
assert next(row['courses_count'] for row in before['faculty_name'] if row['value']=='KTCN')==2
assert next(row['users_count'] for row in before['faculty_name'] if row['value']=='KTCN')==2

changed=scope['apply_catalog_name_change'](admin,'faculty_name','KTCN','Kỹ thuật công nghệ')
assert changed==(2,2),changed
changed2=scope['apply_catalog_name_change'](admin,'department_name','CNTT','Công nghệ thông tin')
assert changed2==(2,2),changed2
s.commit()
assert c1.unit_name=='Kỹ thuật công nghệ' and c3.unit_name=='Kỹ thuật công nghệ'
assert c1.faculty_name=='Kỹ thuật công nghệ' and c3.faculty_name=='Kỹ thuật công nghệ'
assert u1.department_name=='Công nghệ thông tin' and c3.department_name=='Công nghệ thông tin'
assert len(scope['catalog_admin_statistics']()['faculty_name'])==1
assert len(scope['catalog_admin_statistics']()['department_name'])==1
assert m.User.query.count()==3 and m.Course.query.count()==3
assert m.EditHistory.query.count()>=6

# Invalid and absent source cannot create phantom entries.
try:scope['apply_catalog_name_change'](admin,'faculty_name','Không tồn tại','A')
except ValueError:pass
else:raise AssertionError('Missing source accepted')
try:scope['apply_catalog_name_change'](admin,'role','Công nghệ thông tin','Admin')
except ValueError:pass
else:raise AssertionError('Arbitrary model field accepted')
# Rename an existing canonical label: users and courses stay linked.
assert scope['apply_catalog_name_change'](admin,'department_name','Công nghệ thông tin','Bộ môn CNTT')==(3,3)
assert len(scope['catalog_admin_statistics']()['department_name'])==1

# The POST return points to the same filtered page and supplies a single-use marker.
url=scope['videos_library_return_with_bulk_course'](
    'p_q=Python&p_assignment=unassigned&p_page=2&foo=bad', c1.id)
assert url.startswith('/videos?') and url.endswith('#playlists'),url
query=parse_qs(urlsplit(url).query)
assert query['bulk_course_id']==[str(c1.id)] and 'foo' not in query
assert query['p_assignment']==['unassigned']
assert 'bulk_course_id' not in scope['videos_library_return']('playlists', urlsplit(url).query)

video_ui=(ROOT/'templates/videos.html').read_text()
assert 'bulkRedirectUrl.searchParams.delete(\'bulk_course_id\')' in video_ui
assert 'window.history.replaceState' in video_ui
assert "bulkDownload?.addEventListener('qr-download-complete'" in video_ui
save_script=(ROOT/'static/qr_save_picker.js').read_text()
assert "new CustomEvent('qr-download-complete'" in save_script
assert "await writable.close()" in save_script

admin_ui=(ROOT/'templates/organization_catalog.html').read_text()
base_ui=(ROOT/'templates/base.html').read_text()
assert "organization_catalog_page" in base_ui
assert "catalog.faculty_name|length" in admin_ui and "catalog.department_name|length" in admin_ui
assert "csrf_token" in admin_ui and "rename_shared_catalog" in admin_ui
assert "window.confirm" in admin_ui
j=Environment(loader=FileSystemLoader(str(ROOT/'templates')))
for f in (ROOT/'templates').glob('*.html'):j.parse(f.read_text())
assert tuple(map(int,(ROOT/'VERSION.txt').read_text().strip().split('.'))) >= (4,3,31)
print('PASS v4.3.31: PRG state one-use, merge faculty/department across user/course including legacy, CSRF and UI/Jinja')
