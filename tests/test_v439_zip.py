import ast, io, zipfile
from pathlib import Path
from PIL import Image
src=(Path(__file__).resolve().parents[1]/'app.py').read_text()
tree=ast.parse(src)
register=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='register_routes')
fn=next(n for n in register.body if isinstance(n,ast.FunctionDef) and n.name=='qr_download_all')
fn.decorator_list=[]
fn_ast=ast.Module(body=[fn],type_ignores=[])
ast.fix_missing_locations(fn_ast)
class Expr:
 def is_(self, val):return ('ACTIVE',val)
class Column:
 def __eq__(self, x):return ('EQ',x)
 def is_(self,x):return ('IS',x)
class FakeQrCode:
 active=Expr();course_id=Column();created_at='created_at';id='id'
class Args(dict):
 def get(self,k,type=None):
  r=super().get(k)
  try:return type(r) if type and r is not None else r
  except:return None
class Req:args=Args()
class Person:id=7
class Course:
 def __init__(self, id,name,code):self.id=id;self.name=name;self.code=code;self.active=True
courses={1:Course(1,'Lập trình Python','HP000001'),2:Course(2,'Kỹ thuật điện','HP000002')}
class Qr:
 def __init__(self,id,course,title):self.id=id;self.course=course;self.course_id=course.id if course else None;self.title=title;self.slug='qr'+str(id);self.created_at=id
qrs=[Qr(1,courses[1],'Bài 1'),Qr(2,courses[1],'Bài 2'),Qr(3,courses[2],'Bài 3'),Qr(4,None,'Bài 4')]
class DBSession:
 def get(self,cls,id):return courses.get(id)
class DB:session=DBSession()
class Query:
 def __init__(self):self.cs=list(qrs)
 def filter(self,*clauses):
  for c in clauses:
   if c[0]=='EQ':self.cs=[q for q in self.cs if q.course_id == c[1]]
   if c[0]=='IS':self.cs=[q for q in self.cs if q.course_id is c[1]]
  return self
 def order_by(self,*_):return self
 def all(self):return self.cs
class StubDb:session=DBSession()
FakeQrCode.query=Query()
class ErrorSignal(Exception):pass
def abort(code):raise ErrorSignal(code)
def send_file(data,**kw):return data.getvalue(),kw['download_name']
env=dict(QrCode=FakeQrCode,Course=Course,current_user=lambda:Person(),managed_qr_scope=lambda uid:('OK',uid),db=StubDb(), request=Req, io=io,zipfile=zipfile,generate_branded_qr=lambda qr:Image.new('RGB',(5,5),'white'),qr_download_name=lambda qr:qr.title+'.png',safe_filename=lambda x:x,send_file=send_file,abort=abort,course_owned_by_user=lambda c,u:c.id!=2,os=__import__('os'))
exec(compile(fn_ast,'<qr>', 'exec'),env)
def run(filter):
 Req.args=Args(filter)
 FakeQrCode.query=Query()
 data,name=env['qr_download_all']()
 with zipfile.ZipFile(io.BytesIO(data)) as zf:
  return name,zf.namelist()
name,names=run({})
assert len(names)==4 and names == ['HP000001_Lập trình Python/Bài 1.png','HP000001_Lập trình Python/Bài 2.png','HP000002_Kỹ thuật điện/Bài 3.png','Chua_gan_mon_hoc/Bài 4.png'],names
print('PASS all folders',names)
name,names=run({'course_id':'1'})
assert len(names)==2 and all(s.startswith('HP000001_') for s in names)
print('PASS selected course',name,names)
name,names=run({'course_id':'0'})
assert names==['Chua_gan_mon_hoc/Bài 4.png']
print('PASS unassigned',names)
try:
 run({'course_id':'2'})
 raise Exception('Failed permission')
except ErrorSignal as e:
 assert e.args==(403,)
 print('PASS permission guard')
try:
 run({'course_id':'abc'})
 raise Exception('Bad input accepted')
except ErrorSignal as e:
 assert e.args==(400,)
 print('PASS bad input guard')
