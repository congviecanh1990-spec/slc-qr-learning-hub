"""Offline checks for Render Free cold starts and player fallbacks (v4.3.32)."""
from pathlib import Path
from sqlalchemy import create_engine, text
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from services.startup import prepare_database_once, SCHEMA_MARKER

class DB:
    def __init__(self):
        self.engine = create_engine('sqlite:///:memory:')
        self.creates = 0
    def create_all(self):
        self.creates += 1
        with self.engine.begin() as conn:
            conn.execute(text('CREATE TABLE IF NOT EXISTS test_data (id INTEGER PRIMARY KEY)'))

db = DB()
counts = {'upgrade':0,'migrate':0,'cleanup':0}
def upgrade():
    counts['upgrade'] += 1
    with db.engine.begin() as c:
        c.execute(text('INSERT INTO test_data(id) VALUES (12)'))
def migrate():
    counts['migrate'] += 1
def cleanup(engine):
    counts['cleanup'] += 1

assert prepare_database_once(db, upgrade, migrate, cleanup) is True
assert prepare_database_once(db, upgrade, migrate, cleanup) is False
assert db.creates == 1
assert counts == {'upgrade': 1, 'migrate': 1, 'cleanup':1}
with db.engine.connect() as c:
    assert c.execute(text('SELECT COUNT(*) FROM test_data')).scalar_one() == 1
    assert c.execute(text('SELECT COUNT(*) FROM app_one_time_maintenance WHERE key=:key'),
                     {'key':SCHEMA_MARKER}).scalar_one() == 1

for name in ('viewer.html', 'playlist_viewer.html'):
    tpl = (ROOT/'templates'/name).read_text()
    assert 'student_player_recovery.js' in tpl
    assert 'playerRecoveryYoutube' in tpl
    assert 'hệ thống không ghi nhận thời lượng xem' in tpl
for name in ('viewer.js', 'playlist_viewer.js'):
    script = (ROOT/'static'/name).read_text()
    assert 'onError:' in script and 'SLCPlayerRecovery' in script
script = (ROOT/'static/student_player_recovery.js').read_text()
assert 'setTimeout' in script and 'youtube.com/watch?v=' in script
src = (ROOT/'app.py').read_text()
assert 'prepare_database_once(db, ensure_schema_upgrades' in src
assert (ROOT/'VERSION.txt').read_text().strip() == '4.3.32'
print('PASS v4.3.32 startup marker (no repeated migration), player fallback on mobile')
