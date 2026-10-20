/* Theo dõi một video: ghi sự kiện theo đúng thứ tự và chỉ xác nhận hoàn thành từ máy chủ. */
let player = null, watchKey = null, heartbeatTimer = null;
let startPromise = null, eventQueue = Promise.resolve();
const cfg = window.SLC_VIEWER;

async function api(path, payload) {
  const r = await fetch(path, {
    method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRFToken': cfg.csrf},
    body: JSON.stringify(payload), credentials: 'same-origin'
  });
  if (!r.ok) throw new Error(await r.text());
  return await r.json();
}
function stateName(n) {
  if (n === YT.PlayerState.PLAYING) return 'playing';
  if (n === YT.PlayerState.PAUSED) return 'paused';
  if (n === YT.PlayerState.ENDED) return 'ended';
  if (n === YT.PlayerState.BUFFERING) return 'buffering';
  if (n === YT.PlayerState.CUED) return 'cued';
  return 'unstarted';
}
function playerNumber(getter) {
  try { const n = Number(getter()); return Number.isFinite(n) && n >= 0 ? n : 0; }
  catch (_) { return 0; }
}
function snapshot(key, type, state) {
  return {session_key: key, event_type: type, state,
    position: playerNumber(() => player.getCurrentTime()),
    duration: playerNumber(() => player.getDuration())};
}
async function startWatch() {
  if (cfg.trackingEnabled === false || !player || watchKey) return;
  if (!startPromise) {
    startPromise = api('/api/watch/start', {slug: cfg.slug,
      duration: playerNumber(() => player.getDuration())})
      .then(data => { watchKey = data.session_key; })
      .catch(err => console.error('Không thể bắt đầu ghi nhận xem video:', err))
      .finally(() => { startPromise = null; });
  }
  await startPromise;
}
async function sendEvent(type, state) {
  if (cfg.trackingEnabled === false || !watchKey || !player) return null;
  // Chốt vị trí tại thời điểm sự kiện xảy ra, không đọc lại sau khi đã tua/đổi trạng thái.
  const data = snapshot(watchKey, type, state);
  const pending = eventQueue.catch(() => {}).then(() => api('/api/watch/event', data));
  eventQueue = pending.catch(err => console.error('Lỗi ghi nhận tiến trình:', err));
  return pending.catch(() => null);
}
function showEndResult(verified) {
  const overlay = document.getElementById('endedOverlay');
  const heading = overlay.querySelector('h3');
  const description = overlay.querySelector('p');
  if (verified) {
    heading.textContent = 'Đã hoàn thành học liệu';
    description.textContent = 'Hệ thống đã xác nhận thời lượng xem đạt yêu cầu.';
  } else {
    heading.textContent = 'Chưa xác nhận hoàn thành';
    description.textContent = 'Hệ thống chưa ghi nhận đủ thời lượng xem. Vui lòng xem lại video; không tua bỏ qua nội dung.';
  }
  overlay.classList.add('show');
}
window.onYouTubeIframeAPIReady = function() {
  player = new YT.Player('player', {
    width: '100%', height: '100%', videoId: cfg.videoId,
    host: 'https://www.youtube-nocookie.com',
    playerVars: {playsinline: 1, rel: 0, modestbranding: 1, enablejsapi: 1},
    events: {onReady: () => { void startWatch(); }, onStateChange}
  });
};
async function onStateChange(ev) {
  const st = stateName(ev.data);
  if (ev.data === YT.PlayerState.PLAYING) {
    document.getElementById('endedOverlay').classList.remove('show');
    await startWatch();
    await sendEvent('play', st);
    clearInterval(heartbeatTimer);
    heartbeatTimer = setInterval(() => { void sendEvent('heartbeat', 'playing'); }, cfg.heartbeat * 1000);
  } else if (ev.data === YT.PlayerState.PAUSED) {
    clearInterval(heartbeatTimer);
    await startWatch();
    await sendEvent('pause', st);
  } else if (ev.data === YT.PlayerState.ENDED) {
    clearInterval(heartbeatTimer);
    await startWatch();
    const result = await sendEvent('ended', st);
    showEndResult(Boolean(result && result.completed));
  } else {
    await startWatch();
    await sendEvent('state', st);
  }
}
function replayVideo() {
  document.getElementById('endedOverlay').classList.remove('show');
  player.seekTo(0, true);
  player.playVideo();
}
window.replayVideo = replayVideo;
window.addEventListener('pagehide', () => {
  if (cfg.trackingEnabled === false || !watchKey || !player) return;
  const data = snapshot(watchKey, 'leave', stateName(player.getPlayerState()));
  fetch('/api/watch/event', {method: 'POST', keepalive: true, credentials: 'same-origin',
    headers: {'Content-Type': 'application/json', 'X-CSRFToken': cfg.csrf}, body: JSON.stringify(data)}).catch(() => {});
});
