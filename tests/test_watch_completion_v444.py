"""v4.3.14: Mọi báo cáo dùng cùng một mốc 95%, hiển thị đúng trạng thái."""
import ast
import re
import math
from pathlib import Path
from types import SimpleNamespace
from sqlalchemy import and_, Column, Boolean, Float, Integer, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Session

P = Path(__file__).resolve().parents[1]
source = (P/'app.py').read_text(encoding='utf8')
conf = (P/'config.py').read_text(encoding='utf8')
style = (P/'static/app.css').read_text(encoding='utf8')
template = (P/'templates/analytics.html').read_text(encoding='utf8')
assert re.search(r'^\s*COMPLETION_THRESHOLD\s*=\s*0\.95\s*$',conf,re.M)
assert 'value: "0.95"' in (P/'render.yaml').read_text(encoding='utf8')
assert re.search(r'\.navbar \.nav-link\{font-weight:400!important;',style)
assert re.search(r'\.navbar \.nav-link\.nav-current:focus\{color:#dc3545!important;font-weight:700!important}',style)
assert 'font-weight:400!important' in style[style.find('.btn:not(.btn-close){'):]
assert 'watch_status_label(watch, current_app.config["COMPLETION_THRESHOLD"])' in source
assert 'valid_watch_completion_expr(current_app.config["COMPLETION_THRESHOLD"])' in source
assert 'Chưa đủ dữ liệu xác nhận' not in source
assert "WatchSession.estimated_watch_seconds <= 0.5" in source
assert 'row.watch_status' in template

class Base(DeclarativeBase): pass
class WatchSession(Base):
    __tablename__='watch_sessions'
    id=Column(Integer,primary_key=True)
    completed=Column(Boolean,nullable=False)
    estimated_watch_seconds=Column(Float,nullable=False)
    duration_seconds=Column(Float,nullable=False)

names = {'safe_watch_number', 'valid_watch_completion', 'valid_watch_completion_expr', 'watch_status_label'}
tree = ast.parse(source)
functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
assert {n.name for n in functions}==names
scope = {'math':math, 'and_':and_, 'WatchSession':WatchSession}
exec(compile(ast.Module(body=functions,type_ignores=[]),str(P/'app.py'),'exec'),scope)
valid=scope['valid_watch_completion']
status=scope['watch_status_label']
sql=scope['valid_watch_completion_expr']
threshold=0.95
cases=[
    # Không xem 00:00, dù cờ completed ở bản cũ là True.
    (0,335,True,'Chưa xem',False),
    (0,335,False,'Chưa xem',False),
    # 03:50 của video 05:35 (68,66%)
    (230,335,True,'Chưa hoàn thành',False),
    (230,335,False,'Chưa hoàn thành',False),
    # Đến gần 95% nhưng chưa đủ.
    (318.24,335,True,'Chưa hoàn thành',False),
    (318.25,335,False,'Hoàn thành',True),
    (319,335,True,'Hoàn thành',True),
    # Độ dài không được xác định: không tự cho hoàn thành.
    (200,0,True,'Chưa hoàn thành',False),
    (0,0,True,'Chưa xem',False),
]
assert status(None,threshold)=='Chưa xem'
engine=create_engine('sqlite+pysqlite:///:memory:')
Base.metadata.create_all(engine)
with Session(engine) as session:
    for watched,duration,oldflag,expected,finished in cases:
        row=WatchSession(estimated_watch_seconds=watched,duration_seconds=duration,completed=oldflag)
        session.add(row)
        session.flush()
        assert status(row,threshold)==expected,(watched,expected,status(row,threshold))
        assert valid(row,threshold)==finished,(watched,finished)
        result=session.scalar(select(sql(threshold)).where(WatchSession.id==row.id))
        assert result==finished,(watched,finished,result)
        # Đồng nhất cả lọc SQL và báo cáo không phụ thuộc cờ oldflag.
print('PASS v4.3.14: 00:00, 03:50/05:35, ranh giới 95%, dữ liệu lịch sử, truy vấn SQL, menu đỏ đậm')
