let player=null, watchKey=null, heartbeatTimer=null, currentIndex=0;
const cfg=window.SLC_PLAYLIST_VIEWER;

async function api(path,payload){
  const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':cfg.csrf},body:JSON.stringify(payload)});
  if(!r.ok){throw new Error(await r.text());}
  return await r.json();
}

function currentVideo(){return cfg.videos[currentIndex];}
function stateName(n){if(n===YT.PlayerState.PLAYING)return 'playing';if(n===YT.PlayerState.PAUSED)return 'paused';if(n===YT.PlayerState.ENDED)return 'ended';if(n===YT.PlayerState.BUFFERING)return 'buffering';if(n===YT.PlayerState.CUED)return 'cued';return 'unstarted';}

async function startWatch(){
  if(!player||watchKey)return;
  const v=currentVideo();
  try{
    const data=await api('/api/watch/start',{slug:cfg.slug,video_id:v.id,duration:player.getDuration()||0});
    watchKey=data.session_key;
  }catch(e){console.error(e);}
}

async function sendEvent(type,state){
  if(!watchKey||!player)return;
  try{await api('/api/watch/event',{session_key:watchKey,event_type:type,state:state,position:player.getCurrentTime()||0,duration:player.getDuration()||0});}catch(e){console.error(e);}
}

async function closeCurrentWatch(){
  clearInterval(heartbeatTimer);
  if(watchKey&&player){await sendEvent('leave',stateName(player.getPlayerState()));}
  watchKey=null;
}

window.onYouTubeIframeAPIReady=function(){
  const first=currentVideo();
  player=new YT.Player('player',{
    width:'100%',height:'100%',videoId:first.youtubeId,
    host:'https://www.youtube-nocookie.com',
    playerVars:{playsinline:1,rel:0,modestbranding:1,enablejsapi:1},
    events:{onReady:onReady,onStateChange:onStateChange}
  });
};

async function onReady(){await startWatch();}

async function onStateChange(ev){
  const st=stateName(ev.data);
  if(ev.data===YT.PlayerState.PLAYING){
    document.getElementById('endedOverlay').classList.remove('show');
    await startWatch();
    sendEvent('play',st);
    clearInterval(heartbeatTimer);
    heartbeatTimer=setInterval(()=>sendEvent('heartbeat','playing'),cfg.heartbeat*1000);
  }else if(ev.data===YT.PlayerState.PAUSED){clearInterval(heartbeatTimer);sendEvent('pause',st);}
  else if(ev.data===YT.PlayerState.ENDED){clearInterval(heartbeatTimer);sendEvent('ended',st);document.getElementById('endedOverlay').classList.add('show');}
  else{sendEvent('state',st);}
}

async function selectVideo(index){
  if(index===currentIndex&&player){return;}
  await closeCurrentWatch();
  currentIndex=index;
  const v=currentVideo();
  document.getElementById('currentVideoTitle').textContent=v.title;
  document.getElementById('endedOverlay').classList.remove('show');
  document.querySelectorAll('.playlist-video-item').forEach((el,i)=>el.classList.toggle('active',i===index));
  if(player){player.loadVideoById(v.youtubeId);setTimeout(()=>startWatch(),400);}
}

document.querySelectorAll('.playlist-video-item').forEach((el)=>el.addEventListener('click',()=>selectVideo(Number(el.dataset.index))));
function replayVideo(){document.getElementById('endedOverlay').classList.remove('show');player.seekTo(0,true);player.playVideo();}
window.replayVideo=replayVideo;
window.addEventListener('pagehide',()=>{if(watchKey&&player){fetch('/api/watch/event',{method:'POST',keepalive:true,headers:{'Content-Type':'application/json','X-CSRFToken':cfg.csrf},body:JSON.stringify({session_key:watchKey,event_type:'leave',state:stateName(player.getPlayerState()),position:player.getCurrentTime()||0,duration:player.getDuration()||0})}).catch(()=>{});}});
