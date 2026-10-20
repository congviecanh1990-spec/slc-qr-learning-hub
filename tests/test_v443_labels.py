"""Offline regression for v4.3.13 label scopes with normal-weight buttons, active nav bold."""
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from bs4 import BeautifulSoup
import tinycss2
import re
P = Path(__file__).resolve().parents[1]
assert (P/'VERSION.txt').read_text().strip()=='4.3.14'
css=(P/'static/app.css').read_text()
parsed=tinycss2.parse_stylesheet(css, skip_comments=True, skip_whitespace=True)
assert not [t for t in parsed if t.type=='error']
assert '.navbar .nav-link{font-weight:400!important;' in css
assert '.navbar .nav-link.nav-current:focus{color:#dc3545!important;font-weight:700!important}' in css
assert '.btn:not(.btn-close){' in css
assert 'font-weight:400!important;' in css
assert 'font-weight:800!important;' not in css[css.index('/* v4.3.14:'):]
assert 'color:#111111!important;' in css 
html=(P/'templates/qr.html').read_text()
assert '>Tải tất cả mã QR</a>' in html
assert '>Xóa tất cả mã QR</button>' in html
assert 'qr_download_all' in html
assert 'delete_all_qrs' in html
assert 'title="Xóa tất cả mã QR thuộc phạm vi quản lý, không phụ thuộc bộ lọc hiện tại"' in html
# Avoid using bulk labels on single QR actions.
assert re.search(r'url_for\(\'qr_png\', qr_id=q.id\).*?>Tải mã QR</a>',html)
assert re.search(r'url_for\(\'delete_qr\', qr_id=q.id\).*?Xóa mã QR</button>',html,re.S)
# Ensure all menu labels inherit nav-link font-weight in common base template.
base=(P/'templates/base.html').read_text()
menu=['Kênh YouTube','Giảng viên','Môn học/ mô đun','Danh sách lớp đang dạy','Kho video học liệu','Mã QR động','Thống kê khai thác','Đánh giá nghiệm thu']
for item in menu:
    assert re.search(r'class="nav-link[^"]*"[^>]*>'+re.escape(item)+r'</a>',base),item
assert all('btn btn-' in x for x in re.findall(r'<(?:a|button)[^>]*class="btn btn-[^"]*"',html))
print('PASS v4.3.14: CSS, normal buttons/other menus, bold/red active menu and bulk/single QR labels and scope')
