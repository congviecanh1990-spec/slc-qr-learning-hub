"""Offline checks for Render Free cold starts and player fallbacks (v4.3.32)."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

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
assert 'cleanup_initial_three_error_logs_once(db.engine)' in src
assert tuple(map(int, (ROOT/'VERSION.txt').read_text().strip().split('.'))) >= (4,3,32)
print('PASS v4.3.32 player fallback on mobile; v4.3.33 stable startup path')
