/* v4.3.32: friendly mobile fallback when YouTube's embedded player is blocked.
   This cannot override Render's own loading page during a Free cold start. */
(function () {
  'use strict';
  const panel = document.getElementById('playerRecovery');
  const youtubeLink = document.getElementById('playerRecoveryYoutube');
  const message = document.getElementById('playerRecoveryMessage');
  const retry = document.getElementById('playerRecoveryRetry');
  if (!panel || !youtubeLink || !message || !retry) return;
  let timer = null;
  let initialized = false;
  let currentId = '';

  function youtubeUrl(id) {
    return 'https://www.youtube.com/watch?v=' + encodeURIComponent(id);
  }
  function setVideo(id) {
    currentId = typeof id === 'string' ? id : '';
    youtubeLink.href = currentId ? youtubeUrl(currentId) : 'https://www.youtube.com/';
    panel.hidden = true;
  }
  function show(text) {
    message.textContent = text;
    panel.hidden = false;
  }
  function ready() {
    initialized = true;
    if (timer !== null) clearTimeout(timer);
    timer = null;
    panel.hidden = true;
  }
  function error() {
    // Embedded playback can be blocked for an individual video even if the
    // player API loaded; show an explicit, non-tracked YouTube fallback.
    show('Không thể phát video trong trang học liệu trên thiết bị này.');
  }
  retry.addEventListener('click', function () { window.location.reload(); });
  window.SLCPlayerRecovery = {setVideo, ready, error};
  const initialVideo = (window.SLC_VIEWER && window.SLC_VIEWER.videoId) ||
    (window.SLC_PLAYLIST_VIEWER && window.SLC_PLAYLIST_VIEWER.videos &&
     window.SLC_PLAYLIST_VIEWER.videos[0] && window.SLC_PLAYLIST_VIEWER.videos[0].youtubeId) || '';
  setVideo(initialVideo);
  timer = window.setTimeout(function () {
    if (!initialized) {
      show('Trình phát YouTube chưa tải được. Bạn có thể thử lại hoặc mở video trên YouTube.');
    }
  }, 14000);
})();
