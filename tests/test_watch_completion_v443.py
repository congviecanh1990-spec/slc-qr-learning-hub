"""Hồi quy xem video v4.3.13: xác nhận hoàn thành cần chứng cứ thời lượng.
Chạy độc lập với Flask, Google OAuth hoặc PostgreSQL thật.
"""
import ast
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
import math
from sqlalchemy import and_

ROOT = Path(__file__).resolve().parents[1]
tree = ast.parse((ROOT/'app.py').read_text(encoding='utf8'))
names = {'youtube_duration_seconds', 'safe_watch_number', 'valid_watch_completion', 'apply_watch_event', 'valid_watch_completion_expr'}
functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
assert {x.name for x in functions} == names
scope = {'re':__import__('re'), 'math':math, 'and_':and_}
exec(compile(ast.Module(body=functions, type_ignores=[]), str(ROOT/'app.py'), 'exec'), scope)
parse = scope['youtube_duration_seconds']
safe = scope['safe_watch_number']
apply = scope['apply_watch_event']
verified = scope['valid_watch_completion']
assert parse('PT4M12S') == 252
assert parse('PT1H2M3S') == 3723
assert parse('PT0S') == 0 and parse('nonsense') == 0
assert safe('NaN') == safe('inf') == safe(-15) == 0
start = datetime(2026,10,20,14,0,0,tzinfo=timezone.utc)
def new(duration=252):
    return SimpleNamespace(last_event_at=start, last_position=0, last_state='unstarted',
        estimated_watch_seconds=0, duration_seconds=duration, max_position=0,
        completion_percent=0, completed=False, ended_at=None)
def event(w, action, state, t, p, dur=0):
    return apply(w,action,state,p,dur,start+timedelta(seconds=t),5,0.95)

# Lỗi cũ: chỉ bấm tới cuối là ended dù thời lượng xem bằng 0.
w=new();event(w,'ended','ended',1,252)
assert not w.completed and w.estimated_watch_seconds == 0 and verified(w,0.95) is False
# Video dài 4 phút, trình phát trả về getDuration=0 phải không tự chứng nhận.
w=new(0);event(w,'ended','ended',1,0,0)
assert not w.completed and w.duration_seconds == 0 and w.completion_percent == 0
# Một lượt tua từ giây 0 lên 247 rồi ended: không được tính phần tua là thời gian xem.
w=new();event(w,'play','playing',1,0)
event(w,'heartbeat','playing',6,5)
event(w,'heartbeat','playing',11,245)
event(w,'ended','ended',13,252)
assert w.estimated_watch_seconds < 12 and not w.completed
# Dừng hình với trạng thái playing phải không tự tăng thời lượng.
w=new();event(w,'play','playing',1,0)
for t in range(6,126,5): event(w,'heartbeat','playing',t,0)
assert w.estimated_watch_seconds == 0 and not w.completed
# Xem thật 240 giây của video 252 giây: đạt 95%.
w=new();event(w,'play','playing',1,0)
for seconds in range(5,241,5): event(w,'heartbeat','playing',seconds+1,seconds)
event(w,'ended','ended',254,252)
assert w.estimated_watch_seconds >= 239.4, w.estimated_watch_seconds
assert w.completed and verified(w,0.95)
# Kết thúc trình phát có thể đến sau khi tab nghỉ > 15 giây, không tính bù thời gian không xác minh.
w=new();event(w,'play','playing',1,0)
event(w,'ended','ended',254,252)
assert w.estimated_watch_seconds == 0 and not w.completed
# Phiên đã ghi sai ở phiên bản trước không được tính hoàn thành trong thống kê hiện tại.
old=new();old.completed=True
assert not verified(old,0.95)
# Không thay đổi lịch sử cũ trong PostgreSQL.
print('PASS v4.3.14: ended=0, tua, đóng băng, xem đủ 95%, thời lượng 0 và dữ liệu cũ')
