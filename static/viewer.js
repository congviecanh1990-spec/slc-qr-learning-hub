let player=null, watchKey=null, heartbeatTimer=null;
const cfg=window.SLC_VIEWER;

async function api(path,payload){
  const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':cfg.csrf},body:JSON.stringify(payload)});
  if(!r.ok){throw new Error(await r.text());}
  return await r.json();
}

window.onYouTubeIframeAPIReady=function(){
  player=new YT.Player('player',{
    width:'100%',height:'100%',videoId:cfg.videoId,
    host:'https://www.youtube-nocookie.com',
    playerVars:{playsinline:1,rel:0,modestbranding:1,enablejsapi:1},
    events:{onReady:onReady,onStateChange:onStateChange}
  });
};

async function onReady(){
  if(cfg.trackingEnabled===false)return;
  try{const data=await api('/api/watch/start',{slug:cfg.slug,duration:player.getDuration()||0});watchKey=data.session_key;}catch(e){console.error(e);}
}

function stateName(n){if(n===YT.PlayerState.PLAYING)return 'playing';if(n===YT.PlayerState.PAUSED)return 'paused';if(n===YT.PlayerState.ENDED)return 'ended';if(n===YT.PlayerState.BUFFERING)return 'buffering';if(n===YT.PlayerState.CUED)return 'cued';return 'unstarted';}

async function sendEvent(type,state){
  if(cfg.trackingEnabled===false||!watchKey||!player)return;
  try{await api('/api/watch/event',{session_key:watchKey,event_type:type,state:state,position:player.getCurrentTime()||0,duration:player.getDuration()||0});}catch(e){console.error(e);}
}

function onStateChange(ev){
  const st=stateName(ev.data);
  if(ev.data===YT.PlayerState.PLAYING){
    document.getElementById('endedOverlay').classList.remove('show');
    sendEvent('play',st);
    clearInterval(heartbeatTimer);
    heartbeatTimer=setInterval(()=>sendEvent('heartbeat','playing'),cfg.heartbeat*1000);
  }else if(ev.data===YT.PlayerState.PAUSED){clearInterval(heartbeatTimer);sendEvent('pause',st);}
  else if(ev.data===YT.PlayerState.ENDED){clearInterval(heartbeatTimer);sendEvent('ended',st);document.getElementById('endedOverlay').classList.add('show');}
  else{sendEvent('state',st);}
}

function replayVideo(){document.getElementById('endedOverlay').classList.remove('show');player.seekTo(0,true);player.playVideo();}
window.replayVideo=replayVideo;
window.addEventListener('pagehide',()=>{if(watchKey&&player){fetch('/api/watch/event',{method:'POST',keepalive:true,headers:{'Content-Type':'application/json','X-CSRFToken':cfg.csrf},body:JSON.stringify({session_key:watchKey,event_type:'leave',state:stateName(player.getPlayerState()),position:player.getCurrentTime()||0,duration:player.getDuration()||0})}).catch(()=>{});}});
