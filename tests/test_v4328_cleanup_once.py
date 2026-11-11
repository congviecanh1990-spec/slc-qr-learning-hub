"""Offline tests: v4.3.28 deletes only 3 current errors, exactly once."""
import json
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from services.one_time_maintenance import (ONE_TIME_ERROR_CLEANUP_KEY,
                                           cleanup_initial_three_error_logs_once)

assert tuple(map(int,(ROOT/'VERSION.txt').read_text().strip().split('.'))) >= (4,3,28)


def fresh_engine():
    engine = create_engine('sqlite:///:memory:')
    with engine.begin() as conn:
        conn.execute(text('CREATE TABLE error_logs (id INTEGER PRIMARY KEY, message TEXT NOT NULL)'))
        conn.execute(text('CREATE TABLE scan_logs (id INTEGER PRIMARY KEY, success BOOLEAN)'))
        conn.execute(text('CREATE TABLE functional_test_runs (id INTEGER PRIMARY KEY, passed BOOLEAN)'))
        conn.execute(text('INSERT INTO scan_logs VALUES (11, 1)'))
        conn.execute(text('INSERT INTO functional_test_runs VALUES (15, 1)'))
    return engine


def insert_errors(engine, count, start_id=1):
    with engine.begin() as conn:
        for i in range(start_id, start_id + count):
            conn.execute(text('INSERT INTO error_logs (id, message) VALUES (:id, :message)'),
                         {'id': i, 'message': 'Lỗi thử nghiệm'})


def count_logs(engine):
    with engine.connect() as conn:
        return conn.execute(text('SELECT COUNT(*) FROM error_logs')).scalar_one()


# Exactly three logs: delete those records and no other table's rows.
e = fresh_engine()
insert_errors(e, 3)
result = cleanup_initial_three_error_logs_once(e)
assert result['status'] == 'deleted' and result['deleted'] == 3 and result['ids'] == [1, 2, 3]
assert count_logs(e) == 0
with e.connect() as c:
    assert c.execute(text('SELECT COUNT(*) FROM scan_logs')).scalar_one() == 1
    assert c.execute(text('SELECT COUNT(*) FROM functional_test_runs')).scalar_one() == 1
    marker = c.execute(text('SELECT result FROM app_one_time_maintenance WHERE key=:key'),
                       {'key': ONE_TIME_ERROR_CLEANUP_KEY}).scalar_one()
    assert json.loads(marker)['deleted'] == 3
insert_errors(e, 3, 10)
assert cleanup_initial_three_error_logs_once(e)['status'] == 'already_processed'
assert count_logs(e) == 3  # Do not delete subsequent errors on restart.

# Fewer than 3: skip forever. Never wait until new errors appear to reach three.
e = fresh_engine()
insert_errors(e, 2)
r = cleanup_initial_three_error_logs_once(e)
assert r['status'] == 'skipped' and r['found'] == 2 and count_logs(e) == 2
insert_errors(e, 1, 3)
assert cleanup_initial_three_error_logs_once(e)['status'] == 'already_processed'
assert count_logs(e) == 3

# More than 3: never select an arbitrary oldest/newest triple.
e = fresh_engine()
insert_errors(e, 4)
r = cleanup_initial_three_error_logs_once(e)
assert r['status'] == 'skipped' and r['found'] == 4 and count_logs(e) == 4
assert cleanup_initial_three_error_logs_once(e)['status'] == 'already_processed'
assert count_logs(e) == 4

# Empty new installation: no latent cleanup that could run later.
e = fresh_engine()
r = cleanup_initial_three_error_logs_once(e)
assert r['status'] == 'skipped' and r['found'] == 0
insert_errors(e, 3)
assert cleanup_initial_three_error_logs_once(e)['status'] == 'already_processed'
assert count_logs(e) == 3

# The persistent one-time marker table is deliberately excluded from the
# application's backup/restore list; restoring an older backup won't re-arm.
src = (ROOT/'app.py').read_text(encoding='utf-8')
assert 'cleanup_initial_three_error_logs_once(db.engine)' in src
backup_fragment = src.split('def backup_table_specs():', 1)[1].split('def build_backup_zip():', 1)[0]
assert 'app_one_time_maintenance' not in backup_fragment
print('PASS v4.3.28: exact 3-only, skipped on mismatch, persisted marker, unaffected scans/tests')
