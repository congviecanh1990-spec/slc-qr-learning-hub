/* Thực nghiệm QR: chỉ đếm tương tác Web App khi GIẢNG VIÊN tự bắt đầu.
   Chỉ ghi tổng số thao tác; không đọc/ghi nội dung biểu mẫu hay phím đã gõ.
   Thời gian đo chính thức lấy từ dấu thời gian máy chủ, không từ JavaScript. */
(function () {
  'use strict';
  const cfg=window.researchMeasurement;
  if(!cfg || !cfg.id || !cfg.nonce)return;
  const key='slc-research-ops:'+cfg.id+':'+cfg.nonce;
  let count=0;
  try{count=Math.max(0,Number(sessionStorage.getItem(key))||0)}catch(_){}
  const csrf=document.querySelector('meta[name="csrf-token"]')?.getAttribute('content')||'';
  let lastSent=-1;
  function submitProgress(beacon=false) {
    if(count===lastSent)return;
    const data=new FormData();
    data.append('csrf_token',csrf);
    data.append('operations_count',String(count));
    lastSent=count;
    if(beacon && navigator.sendBeacon){
      navigator.sendBeacon(cfg.progressUrl,data);
      return;
    }
    fetch(cfg.progressUrl,{method:'POST',body:data,credentials:'same-origin',
      keepalive:true}).catch(()=>{lastSent=-1});
  }
  function countOperation(){
    count=Math.min(100000,count+1);
    try{sessionStorage.setItem(key,String(count))}catch(_){}
  }
  const scope=location.pathname;
  const onWorkPage=(scope==='/qr'||scope==='/courses'||scope==='/videos'||
                    scope.startsWith('/courses/'));
  if(onWorkPage){
    document.addEventListener('click',ev=>{
      const el=ev.target.closest('button,a,input[type="checkbox"],input[type="radio"],input[type="submit"]');
      if(el && !el.disabled)countOperation();
    },true);
    document.addEventListener('change',ev=>{
      const el=ev.target;
      if(el && el.matches('input:not([type="checkbox"]):not([type="radio"]):not([type="submit"]),select,textarea')){
        countOperation();
      }
    },true);
  }
  document.querySelectorAll('form[data-research-finish]').forEach(form=>{
    form.addEventListener('submit',()=>{
      form.querySelector('[data-operations-result]').value=String(count);
    });
  });
  setInterval(()=>submitProgress(false),4000);
  window.addEventListener('pagehide',()=>submitProgress(true));
  document.addEventListener('visibilitychange',()=>{
    if(document.hidden)submitProgress(true);
  });
})();
