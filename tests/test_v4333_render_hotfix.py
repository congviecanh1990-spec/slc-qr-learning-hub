"""Guard against startup regressions after the failed v4.3.32 deploy."""
from pathlib import Path
import ast

ROOT=Path(__file__).resolve().parents[1]
src=(ROOT/'app.py').read_text(encoding='utf-8')
tree=ast.parse(src)
app_fn=next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name=='create_app')
fn=ast.get_source_segment(src, app_fn)
assert 'db.create_all()' in fn
assert 'ensure_schema_upgrades()' in fn
assert 'migrate_legacy_classes()' in fn
assert 'cleanup_initial_three_error_logs_once(db.engine)' in fn
assert 'prepare_database_once' not in src
assert not (ROOT/'services/startup.py').exists()
assert 'schema_initialized_v4332' not in src
conf=(ROOT/'config.py').read_text(encoding='utf-8')
assert '"pool_pre_ping": True' in conf
assert 'connect_timeout' not in conf
assert (ROOT/'VERSION.txt').read_text(encoding='utf-8').strip()=='4.3.33'
for name in ('viewer.html','playlist_viewer.html'):
    assert 'student_player_recovery.js' in (ROOT/'templates'/name).read_text(encoding='utf-8')
print('PASS v4.3.33 startup hotfix, single-use cleanup guard, mobile recovery retained')
