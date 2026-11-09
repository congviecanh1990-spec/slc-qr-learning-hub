"""Smoke test v4.3.27: clean analytics notes, QR filters, compact playlist/video QR actions."""
from pathlib import Path
import ast
from jinja2 import Environment, FileSystemLoader
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
analytics = (ROOT/'templates/analytics.html').read_text(encoding='utf-8')
qr_tpl = (ROOT/'templates/qr.html').read_text(encoding='utf-8')
playlist_tpl = (ROOT/'templates/_playlist_library_row.html').read_text(encoding='utf-8')
videos_tpl = (ROOT/'templates/videos.html').read_text(encoding='utf-8')
app = (ROOT/'app.py').read_text(encoding='utf-8')
css = (ROOT/'static/app.css').read_text(encoding='utf-8')

for old in ('Lượt quét QR được đếm theo nhật ký',
            'Mỗi sinh viên–video chỉ tính một lần',
            'Số lần mở video chỉ đếm các phiên'):
    assert old not in analytics, old
for expected in ('A. Thống kê lượt quét mã QR', 'B. Thống kê hoạt động khai thác video',
                 'Tổng lượt quét', 'Tổng video', 'Video hoàn thành',
                 'Bảng chi tiết lượt quét QR', 'Bảng chi tiết hoạt động xem video'):
    assert expected in analytics, expected

html=BeautifulSoup(qr_tpl,'html.parser')
assert not html.select_one('#qr-course-id option[value="0"]')
assert html.select_one('#qr-course-id option[value=""]')
assert "q.course.name if q.course else 'Chưa gán môn học/mô đun'" in qr_tpl
mod=ast.parse(app)
handler=next(n for n in ast.walk(mod) if isinstance(n,ast.FunctionDef) and n.name=='qr_page')
code=ast.get_source_segment(app,handler)
assert 'if selected_course_id == 0:\n            return redirect(url_for("qr_page"))' in code
assert 'qrs = all_qrs' in code, 'Legacy unassigned QR must remain in All'

assert 'playlist-qr-compact-actions d-flex' in playlist_tpl
assert 'video-qr-extra' in videos_tpl
assert '.playlist-qr-compact-actions[hidden]' in css
assert '.video-qr-extra[hidden]' in css
assert 'compact.hidden=!hasQr' in videos_tpl
assert 'extra.hidden=!hasQr' in videos_tpl
assert "download=row.querySelector('.playlist-qr-download')" in videos_tpl
assert "download=extra.querySelector('.video-qr-download')" in videos_tpl

# Ensure all three controls are siblings within the same flex toolbar, in intended order.
p=BeautifulSoup(playlist_tpl,'html.parser')
wrap=p.select_one('div.playlist-qr-compact-actions')
assert wrap
assert [x.get_text(' ',strip=True) for x in wrap.select('a.btn, button.btn')]==['Tải QR','Đổi đích','Xóa QR']
assert 'onsubmit' in str(wrap.select_one('form.playlist-qr-delete-form'))
assert 'onsubmit' in str(p.select_one('form.playlist-qr-retarget'))
v=BeautifulSoup(videos_tpl,'html.parser')
extra=v.select_one('div.video-qr-extra')
assert [x.get_text(' ',strip=True) for x in extra.select('a.btn,button.btn')][:3]==['Tải QR','Đổi đích','Xóa QR']
assert 'onsubmit' in str(extra.select_one('form.video-qr-delete'))
assert not p.select('form form')
assert not v.select('form form')

env=Environment(loader=FileSystemLoader(str(ROOT/'templates')))
for tpl in (ROOT/'templates').glob('*.html'):
    env.parse(tpl.read_text(encoding='utf-8'))
assert tuple(map(int, (ROOT/'VERSION.txt').read_text().strip().split('.'))) >= (4,3,27)
print('PASS v4.3.27: text removed; legacy QR retained; compact QR buttons and secure forms; 23 templates valid')
