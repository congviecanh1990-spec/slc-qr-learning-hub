/* v4.3.22: Các bước đồng bộ do trình duyệt chủ động; không có luồng nền trên Render. */
(() => {
  'use strict';
  const notice = document.getElementById('yt-sync-notice');
  const message = document.getElementById('yt-sync-message');
  const resume = document.getElementById('yt-sync-resume');
  if (!notice || !message || !resume) return;
  const csrf = document.querySelector('meta[name="csrf-token"]')?.content || '';
  const post = async path => {
    const body = new FormData(); body.set('csrf_token', csrf);
    const controller = new AbortController();
    const guard = setTimeout(() => controller.abort(), 28000);
    try {
      const response = await fetch(path, {method: 'POST', body, credentials: 'same-origin', signal: controller.signal});
      if (!response.ok) throw new Error('Không thể tiếp tục ở bước này.');
      return await response.json();
    } finally { clearTimeout(guard); }
  };
  const getState = async () => {
    const response = await fetch('/youtube/sync/state', {credentials: 'same-origin'});
    if (!response.ok) throw new Error('Không kiểm tra được tiến độ');
    return await response.json();
  };
  let running = false;
  let stopped = false;
  // Ngăn hai tab cùng tài khoản đẩy hai bước đồng bộ trùng nhau.
  const lockKey = 'slc_youtube_sync_lock';
  const lockOwner = String(Date.now()) + ':' + Math.random().toString(36).slice(2);
  const acquire = () => {
    try {
      const old = JSON.parse(localStorage.getItem(lockKey) || '{}');
      if (old.until > Date.now() && old.owner !== lockOwner) return false;
      localStorage.setItem(lockKey, JSON.stringify({owner: lockOwner, until: Date.now() + 35000}));
      return true;
    } catch { return true; }
  };
  const release = () => {
    try {
      const old = JSON.parse(localStorage.getItem(lockKey) || '{}');
      if (old.owner === lockOwner) localStorage.removeItem(lockKey);
    } catch { /* Tab vẫn hoạt động khi trình duyệt cấm localStorage. */ }
  };
  const show = (value, level='info') => {
    notice.classList.remove('d-none', 'alert-info', 'alert-warning', 'alert-success');
    notice.classList.add('alert-' + level);
    message.textContent = value;
  };
  const update = state => {
    if (state.status === 'running') {
      const processed = Number(state.done || 0);
      const remaining = Number(state.remaining || 0);
      show(`Đang cập nhật video theo từng phần (${processed} phần hoàn tất, ${remaining} phần còn lại). ` +
           'Bạn có thể dùng hệ thống bình thường.');
    } else if (state.status === 'done') {
      show((state.message || 'Đã kết thúc đồng bộ.') +
           (state.failures ? ' Có phần chưa đồng bộ được; hãy kiểm tra lại.' : ''),
           state.failures ? 'warning' : 'success');
      resume.classList.add('d-none');
      document.dispatchEvent(new Event('youtube-sync-finished'));
    }
  };
  async function run() {
    if (running) return;
    if (!acquire()) return;
    running = true; stopped = false;
    resume.classList.add('d-none');
    try {
      let state = await getState();
      if (window.youtubeSyncAutoStart) {
        state = await post('/youtube/sync/start');
        window.youtubeSyncAutoStart = false;
      }
      // Kết quả lượt trước chỉ cần hiện tại trang Kênh YouTube.
      if (state.status === 'idle' || (state.status === 'done' && !window.youtubeSyncAutoStart)) return;
      update(state);
      // Mỗi lời gọi chỉ đọc một tài khoản hoặc một trang playlist tối đa 50 video.
      // Không có thời gian chờ đồng bộ toàn bộ danh sách ở bước đăng nhập.
      for (let i = 0; state.status === 'running' && i < 1000; i++) {
        if (document.hidden || stopped) break;
        if (!acquire()) break;
        state = await post('/youtube/sync/step');
        update(state);
      }
      if (state.status === 'running') resume.classList.remove('d-none');
    } catch (error) {
      show('Đồng bộ tạm dừng do kết nối phản hồi chậm. Dữ liệu đã xử lý được giữ nguyên; chọn Tiếp tục để thử lại.', 'warning');
      resume.classList.remove('d-none');
    } finally { running = false; release(); }
  }
  resume.addEventListener('click', run);
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) stopped = true;
    if (!document.hidden && !running) run();
  });
  window.addEventListener('pagehide', release);
  run();
})();
