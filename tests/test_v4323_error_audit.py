"""v4.3.23: kiểm thử ngoại tuyến thông tin người thực hiện lỗi và nguyên nhân.
Không thay thế kiểm thử Google OAuth/YouTube API thật trên Render.
"""
from pathlib import Path
import sys, types, json
import sqlalchemy as sa
from sqlalchemy.orm import declarative_base, relationship, backref, sessionmaker
from jinja2 import Environment, FileSystemLoader

ROOT = Path(__file__).resolve().parents[1]
assert (ROOT/'VERSION.txt').read_text().strip() == '4.3.23'

# Phân loại lỗi đăng nhập không chứa OAuth URL hoặc token.
sys.path.insert(0, str(ROOT))
from services.error_reporting import login_failure_reason, safe_error_diagnostic
assert 'phiên' in login_failure_reason(Exception('mismatching_state')).lower()
assert 'hủy' in login_failure_reason(Exception('access_denied')).lower()
assert 'cấu hình' in login_failure_reason(Exception('redirect_uri_mismatch')).lower()
assert 'quá thời gian' in login_failure_reason(Exception('Read Timeout')).lower()
assert 'token_is_secret' not in safe_error_diagnostic(Exception('access_token=token_is_secret'))

class SQLAlchemy:
    def __init__(self):
        self.Model = declarative_base()
        for key in ('Column', 'Integer', 'String', 'Text', 'Date', 'DateTime', 'Boolean', 'Float', 'ForeignKey'):
            setattr(self, key, getattr(sa, key))
        self.relationship = relationship
        self.backref = backref

sys.modules['flask_sqlalchemy'] = types.SimpleNamespace(SQLAlchemy=SQLAlchemy)
sys.modules['flask'] = types.SimpleNamespace(current_app=None)
sys.modules['security'] = types.SimpleNamespace(decrypt_json=lambda x:{}, encrypt_json=lambda x:'')
import models
from services import youtube
engine = sa.create_engine('sqlite:///:memory:')
models.db.Model.metadata.create_all(engine)
models.db.session = sessionmaker(bind=engine)()
class Query:
    def __get__(self, obj, owner):
        return models.db.session.query(owner)
for mapper in models.db.Model.registry.mappers:
    mapper.class_.query = Query()

s = models.db.session
teacher = models.User(email='gv@example.edu.vn', name='Giảng viên A')
s.add(teacher); s.commit()

# Bất kể YouTube lỗi 403 hoặc timeout, đồng bộ từng bước ghi email đã biết + nguyên nhân.
def deny_catalog(user, credential):
    raise youtube.YouTubeSyncError('permission', 'YouTube từ chối cấp quyền truy cập cho kênh.')
youtube._sync_channel_catalog = deny_catalog
youtube.start_incremental_sync(teacher)
finished = youtube.step_incremental_sync(teacher)
assert finished['status'] == 'done', finished
assert finished['failures'] == 1 and finished['videos_found'] == 0
assert 'gv@example.edu.vn' in finished['failure_reasons'][0]
log = models.ErrorLog.query.order_by(models.ErrorLog.id.desc()).first()
assert log.actor_user_id == teacher.id
assert log.actor_email == 'gv@example.edu.vn'
assert 'quyền' in log.reason.lower()
assert 'Loại lỗi' in log.details and 'YouTubeSyncError' in log.details
assert log.created_at

# Bước tiếp theo không tạo thêm nhật ký thất bại cho cùng lượt đồng bộ kết thúc.
youtube.step_incremental_sync(teacher)
assert models.ErrorLog.query.count() == 1

# Mất quyền một tài khoản phụ phải có nhật ký gốc ở email GV, không ghi nhầm người.
youtube.start_incremental_sync(teacher, force=True)
job = models.YouTubeSyncJob.query.filter_by(user_id=teacher.id).first()
p = json.loads(job.payload_json)
p['accounts'] = [99999]
job.payload_json = json.dumps(p)
s.commit()
state = youtube.step_incremental_sync(teacher)
assert state['status'] == 'done' and state['failures'] == 1
assert models.ErrorLog.query.count() == 2
last = models.ErrorLog.query.order_by(models.ErrorLog.id.desc()).first()
assert last.actor_email == teacher.email and 'ngắt kết nối' in last.reason

# Tất cả template có thể parse và cột giải thích được hiển thị.
env = Environment(loader=FileSystemLoader(str(ROOT/'templates')))
for path in (ROOT/'templates').glob('*.html'):
    env.parse(path.read_text())
errors = (ROOT/'templates/errors.html').read_text()
assert 'Người thực hiện thất bại' in errors and 'Nguyên nhân có thể' in errors
assert 'e.reason' in errors
source = (ROOT/'app.py').read_text()
assert 'ADD COLUMN actor_email VARCHAR(255)' in source
assert 'ADD COLUMN reason VARCHAR(500)' in source
assert 'verified_google_email = None' in source
assert 'actor_email=verified_google_email' in source
assert 'Nguyên nhân có thể:' in source
assert 'Hệ thống tự động xử lý' in source
print('PASS v4.3.23: email actor, lý do login/OAuth, nhật ký sync, không lặp, migration, giao diện')
