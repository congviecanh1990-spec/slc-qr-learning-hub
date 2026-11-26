// Chọn video xuyên trang như playlist; áp dụng chung cho GÁN MÔN và QR HÀNG LOẠT.
// Có từ khóa sau khi bấm Lọc video -> mặc định chọn mọi video khớp tất cả trang.
// Không có từ khóa -> mặc định bỏ chọn. Ô tiêu đề chủ động chọn/bỏ mọi kết quả.
// all: mọi video khớp trừ những ID đã bỏ tích; none: chỉ ID được tích riêng.
(function(){
  'use strict';
  const form=document.getElementById('assignVideoForm');
  const filterForm=document.getElementById('videoLibraryFilterForm');
  const qrForm=document.getElementById('videoBulkQrForm');
  const master=document.getElementById('selectAllVideos');
  const summary=document.getElementById('videoBulkSelectedSummary');
  const count=document.getElementById('selectedVideoCount');
  const qrCount=document.getElementById('researchBulkCount');
  if(!form)return;
  const storagePrefix='slc-video-selection-v2:';
  const total=Math.max(0,Number(form.dataset.videoTotal)||0);
  const snapshot={
    q:(form.querySelector('[name="q"]')?.value||'').trim(),
    status:form.querySelector('[name="status"]')?.value||'',
    assignment:form.querySelector('[name="assignment"]')?.value||'',
    playlist:form.querySelector('[name="playlist_id"]')?.value||''
  };
  const defaultMode=filter=>filter.q?'all':'none';
  const scopeKey=filter=>storagePrefix+JSON.stringify([
    form.dataset.userId||'',filter.q,filter.status,filter.assignment,filter.playlist
  ]);
  const currentKey=scopeKey(snapshot);
  function read(){
    try{
      const value=JSON.parse(sessionStorage.getItem(currentKey)||'null');
      if(value&&(value.mode==='all'||value.mode==='none')){
        return {mode:value.mode,ids:new Set(Array.isArray(value.ids)
          ?value.ids.filter(id=>Number.isSafeInteger(id)&&id>0):[])};
      }
    }catch(_){}
    return {mode:defaultMode(snapshot),ids:new Set()};
  }
  let selected=read(),mode=selected.mode,overrides=selected.ids;
  const contains=id=>mode==='all'?!overrides.has(id):overrides.has(id);
  const selectedCount=()=>mode==='all'?Math.max(0,total-overrides.size):overrides.size;
  const persist=()=>{
    try{sessionStorage.setItem(currentKey,JSON.stringify({mode,ids:[...overrides]}));}catch(_){}
  };
  function refresh(){
    const checks=[...document.querySelectorAll('.video-check')];
    for(const check of checks)check.checked=contains(Number(check.value));
    if(master){
      const n=selectedCount();
      master.checked=total>0&&n===total;
      master.indeterminate=n>0&&n<total;
    }
    const n=selectedCount();
    const detail=mode==='all'
      ?overrides.size?'Đã chọn toàn bộ video khớp bộ lọc, trừ '+overrides.size+' video đã bỏ tích.':
          'Đã tích chọn TẤT CẢ '+total+' video trong kết quả lọc trên mọi trang.'
      :overrides.size?'Đã tích riêng '+overrides.size+' video, kể cả ở những trang khác.':
          'Chưa chọn video nào trong kết quả lọc.';
    const pageSelected=checks.filter(c=>c.checked).length;
    if(summary)summary.textContent=detail+' Trang này: '+pageSelected+'/'+checks.length+' được tích.';
    if(count)count.textContent='Đã chọn: '+n+'/'+total+' video (tất cả trang)';
    if(qrCount)qrCount.textContent='Đã chọn '+n+'/'+total+' video từ mọi trang để tạo QR hàng loạt.';
  }
  document.addEventListener('change',e=>{
    if(e.target===master){
      mode=master.checked?'all':'none';
      overrides=new Set();persist();refresh();
    }else if(e.target.matches('.video-check')){
      const id=Number(e.target.value);
      if(!Number.isSafeInteger(id)||id<=0)return;
      if(mode==='all'){
        if(e.target.checked)overrides.delete(id);else overrides.add(id);
      }else{
        if(e.target.checked)overrides.add(id);else overrides.delete(id);
      }
      persist();refresh();
    }
  });
  filterForm?.addEventListener('submit',()=>{
    const next={
      q:(filterForm.querySelector('[name="q"]')?.value||'').trim(),
      status:filterForm.querySelector('[name="status"]')?.value||'',
      assignment:filterForm.querySelector('[name="assignment"]')?.value||'',
      playlist:filterForm.querySelector('[name="playlist_id"]')?.value||''
    };
    // Nhấn Lọc video luôn khởi tạo lượt chọn mới như nút Lọc playlist.
    try{sessionStorage.setItem(scopeKey(next),
      JSON.stringify({mode:defaultMode(next),ids:[]}));}catch(_){}
  });
  function appendSelection(target){
    target.querySelectorAll('[data-video-selection]').forEach(el=>el.remove());
    const hidden=(name,value)=>{
      const el=document.createElement('input');
      el.type='hidden';el.name=name;el.value=String(value);
      el.dataset.videoSelection='1';target.append(el);
    };
    hidden('video_selection_mode',mode);
    for(const id of overrides){
      hidden(mode==='all'?'excluded_video_ids':'selected_video_ids',id);
    }
  }
  // Mỗi lựa chọn ở cột Mã QR được lưu ngay trong input hidden form-associated
  // ở chính dòng đó. Không đợi tới sự kiện submit (có thể bị preflight chặn).
  // Chỉ gửi các dòng mà giảng viên chủ động đổi môn; không áp dụng lựa chọn
  // mặc định khi chưa hề thay đổi.
  function qrCourseSelections(){
    return [...document.querySelectorAll('input[data-video-row-assign]')]
      .filter(input=>!input.disabled && input.value).map(input=>input.value);
  }
  function appendRowCourseAssignments(target){
    // Bản mới đã dùng form="assignVideoForm": input hidden tự tham gia POST.
    // Xóa các phần tử sinh từ phiên bản JS cũ để không gửi bản ghi trùng.
    target.querySelectorAll('[data-video-qr-assignment]').forEach(el=>el.remove());
  }
  const api={
    selectedCount,refresh,
    appendSelection,
    selectedQrCourseCount:()=>qrCourseSelections().length,
    hasAny:()=>selectedCount()>0
  };
  window.videoBulkSelection=api;
  for(const target of [form,qrForm].filter(Boolean)){
    target.addEventListener('submit',event=>{
      const endpoint=new URL(event.submitter?.formAction||target.action,window.location.href).pathname;
      const isAssignment=endpoint==='/videos/assign-course';
      const isCreateAllQr=endpoint==='/videos/qr/bulk-selected';
      if(!isCreateAllQr && !api.hasAny() && !(isAssignment && api.selectedQrCourseCount()>0)){
        event.preventDefault();
        if(summary)summary.textContent='Hãy chọn video hoặc môn học ở cột Mã QR trước khi thực hiện.';
        return;
      }
      appendSelection(target);
      if(isAssignment)appendRowCourseAssignments(target);
    });
  }
  window.syncVideoBulkSelection=refresh;
  refresh();
})();
