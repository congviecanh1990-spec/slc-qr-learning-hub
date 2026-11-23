/* Đo QR trực tiếp trong Kho video học liệu.
   Bộ đếm thao tác ghi số lần chọn/nhấn trên Web App, không ghi nội dung biểu mẫu,
   không đọc đường dẫn hoặc nội dung thư mục người dùng. Máy chủ đo thời gian.
   Tệp lưu trực tiếp qua showDirectoryPicker được ghi riêng với trường hợp
   người dùng xác nhận tải/giải nén ZIP (không thể tự xác thực trên máy khách). */
(() => {
  'use strict';
  const api=window.researchMeasurement;
  if(!api)return;
  const panel=document.getElementById('thuc-nghiem-qr');
  const modeInputs=[...document.querySelectorAll('input[name="qrWorkMode"]')];
  const course=document.getElementById('researchQrCourse');
  const statusText=document.getElementById('researchQrStatus');
  const saveArea=document.getElementById('researchQrSaveArea');
  const saveReady=document.getElementById('researchQrReady');
  const saveDirectory=document.getElementById('researchQrSaveDirectory');
  const zipButton=document.getElementById('researchQrSaveFallback');
  const confirmBox=document.getElementById('researchQrManualConfirm');
  const confirmCheckbox=document.getElementById('researchQrConfirmedFiles');
  const confirmButton=document.getElementById('researchQrConfirmDone');
  const bulkForm=document.getElementById('videoBulkQrForm');
  const bulkCourse=document.getElementById('videoBulkQrCourse');
  const bulkCount=document.getElementById('researchBulkCount');
  const STATE_KEY='slc-research-ui-v2:'+String(panel?.dataset.userId||'');
  let active=null,operations=0,lastSent=-1,pendingStartOperations=0;
  let chosenVideos=new Set(),fallbackFiles=null,interactionsOn=false;
  const csrf=document.querySelector('meta[name="csrf-token"]')?.content||'';
  const selectedMode=()=>modeInputs.find(i=>i.checked)?.value||'QR_TUNG_VIDEO_PLAYLIST';
  const fileKey=()=> 'slc-research-ops:'+active?.id+':'+active?.nonce;
  const canFileSave=typeof window.showDirectoryPicker==='function'&&window.isSecureContext;
  function info(message,warning=false){
    if(statusText){statusText.textContent=message;statusText.className='small '+(warning?'text-warning-emphasis':'text-muted');}
  }
  function persistUi(){
    if(!panel)return;
    try{sessionStorage.setItem(STATE_KEY,JSON.stringify({
      mode:selectedMode(),course:course?.value||'',videos:[...chosenVideos]
    }));}catch(_){}
  }
  function restoreUi(){
    if(!panel)return;
    try {
      const state=JSON.parse(sessionStorage.getItem(STATE_KEY)||'{}');
      if(state.mode)modeInputs.forEach(i=>i.checked=i.value===state.mode);
      if(state.course&&course?.querySelector('option[value="'+Number(state.course)+'"]'))course.value=String(Number(state.course));
      if(Array.isArray(state.videos))chosenVideos=new Set(state.videos.filter(x=>Number.isSafeInteger(x)&&x>0));
    }catch(_){}
  }
  function setModeVisibility(){
    const bulk=selectedMode()==='QR_VIDEO_HANG_LOAT';
    if(bulkForm){bulkForm.hidden=!bulk;bulkForm.style.display=bulk?'':'none';}
    document.querySelectorAll('.video-qr-actions,.playlist-qr-actions').forEach(el=>{
      el.hidden=bulk;
      if(bulk)el.style.setProperty('display','none','important');
      else el.style.removeProperty('display');
    });
    // Các nút gán học liệu, lọc, phân trang vẫn giữ nguyên.
    if(bulkCourse)bulkCourse.value=course?.value||'';
    if(bulkCount)bulkCount.textContent='Đã chọn '+chosenVideos.size+' video ở các trang.';
    for(const check of document.querySelectorAll('.video-check')){
      check.checked=chosenVideos.has(Number(check.value))||(!bulk&&check.checked);
    }
  }
  function countOperation(){
    if(!active||!interactionsOn||!document.querySelector('main'))return;
    operations=Math.min(100000,operations+1);
    try{sessionStorage.setItem(fileKey(),String(operations));}catch(_){}
  }
  function activate(state){
    active=state;
    if(!active?.nonce)active.nonce=api.nonce||'';
    try{operations=Math.max(state.operations||0,Number(sessionStorage.getItem(fileKey()))||0);}catch(_){operations=state.operations||0;}
    interactionsOn=true;
    if(pendingStartOperations){
      operations+=pendingStartOperations;
      pendingStartOperations=0;
      try{sessionStorage.setItem(fileKey(),String(operations));}catch(_){}
    }
    if(course)course.value=String(state.course_id);
    modeInputs.forEach(i=>i.checked=i.value===state.kind);
    setModeVisibility();
    persistUi();
    renderStatus(state);
  }
  function renderStatus(state){
    if(!state?.active)return;
    if(state.ready_to_save){
      info('Đã tạo đủ '+state.created+'/'+state.expected+' QR mới. Hãy lưu các tệp đúng tên vào thư mục trước khi kết thúc phép đo.');
      if(saveArea)saveArea.hidden=false;
      if(saveReady)saveReady.textContent='Đủ '+state.created+' mã QR mới – còn bước lưu tệp vào thư mục.';
    }else{
      info('Đang tự đo lượt '+state.code+': '+state.created+'/'+state.expected+
           ' QR mới. Hệ thống ghi thời gian từ khi chọn chức năng/môn đến khi lưu xong tệp.');
      if(saveArea)saveArea.hidden=true;
    }
  }
  async function post(url,fields={}){
    const data=new FormData();
    data.set('csrf_token',csrf);
    for(const [k,v] of Object.entries(fields))data.set(k,String(v));
    const response=await fetch(url,{method:'POST',body:data,credentials:'same-origin',cache:'no-store'});
    let result={};
    try{result=await response.json();}catch(_){}
    if(!response.ok)throw Error(result.message||result.reason||'Không thể xác nhận thao tác trên máy chủ.');
    return result;
  }
  async function refresh(){
    if(!active)return;
    try{
      const response=await fetch(api.statusUrl,{credentials:'same-origin',cache:'no-store'});
      if(!response.ok)return;
      const result=await response.json();
      if(result.active){active={...active,...result};renderStatus(result);}
      else{active=null;interactionsOn=false;if(saveArea)saveArea.hidden=true;}
    }catch(_){}
  }
  async function startSelectedMeasurement(){
    if(!panel||!course?.value)return;
    persistUi();
    if(active){
      if(String(active.course_id)===course.value&&active.kind===selectedMode())return;
      info('Có lượt đo khác đang thực hiện. Hãy hoàn tất lưu QR của lượt hiện tại.',true);
      if(course)course.value=String(active.course_id);
      modeInputs.forEach(i=>i.checked=i.value===active.kind);
      setModeVisibility();
      return;
    }
    info('Đang kiểm tra nhiệm vụ đối chứng đã được giao…');
    try{
      const result=await post(api.startUrl,{course_id:course.value,task_kind:selectedMode()});
      if(result.active)activate(result);
      else info(result.message||'Có thể tạo QR bình thường; chưa có lượt đối chứng tương ứng.');
    }catch(e){info(e.message,true);}
  }
  async function fetchFiles(){
    const response=await fetch(api.filesUrl,{credentials:'same-origin',cache:'no-store'});
    if(!response.ok)throw Error('Chưa có đủ mã QR mới để lưu.');
    const data=await response.json();
    if(!data.ok||!Array.isArray(data.files)||!data.files.length)throw Error('Không nhận được danh sách mã QR.');
    return data.files;
  }
  async function finishSave(method,files,userConfirmed=false){
    const result=await post(api.completeUrl,{
      save_method:method,
      saved_qr_ids:JSON.stringify(files.map(f=>f.id)),
      user_confirmed:userConfirmed?'yes':'no',
      operations_count:Math.max(1,operations)
    });
    const label=method==='directory_picker'?'Trình duyệt đã ghi tệp vào thư mục đã chọn.'
      :'Người dùng xác nhận đã tải/giải nén và lưu đúng thư mục; không tự xác minh thao tác Windows.';
    info('Đã kết thúc đo: '+result.qr_count+' QR; '+result.elapsed_seconds+
      ' giây; '+result.operations+' thao tác Web App. '+label);
    const previousKey=fileKey();
    active=null;interactionsOn=false;
    if(saveArea)saveArea.hidden=true;
    fallbackFiles=null;
    try{sessionStorage.removeItem(previousKey);}catch(_){}
  }
  async function saveDirect(){
    if(!active)return;
    if(!canFileSave){
      info('Trình duyệt không hỗ trợ chọn thư mục trực tiếp; sử dụng Tải ZIP và xác nhận sau khi giải nén.',true);
      return;
    }
    // Phải gọi picker NGAY từ click người dùng; không await API trước picker.
    let handle;
    try{handle=await window.showDirectoryPicker({mode:'readwrite'});}
    catch(e){if(e?.name!=='AbortError')info('Không thể chọn thư mục: '+e.message,true);return;}
    if(!handle)return;
    countOperation();
    try{
      const files=await fetchFiles(),names=new Set();
      if(saveDirectory)saveDirectory.disabled=true;
      for(const file of files){
        let name=(file.name||'Ma_QR.png').replace(/[\\/:*?"<>|]/g,'_');
        if(names.has(name)){
          const dot=name.lastIndexOf('.');
          name=name.slice(0,dot<0?name.length:dot)+'_'+file.id+(dot<0?'':name.slice(dot));
        }
        names.add(name);
        // Không ghi đè file QR cũ nếu tên đã tồn tại trong thư mục.
        try{await handle.getFileHandle(name,{create:false});
          const dot=name.lastIndexOf('.');
          name=name.slice(0,dot<0?name.length:dot)+'_qr'+file.id+(dot<0?'':name.slice(dot));
        }catch(e){if(e.name!=='NotFoundError')throw e;}
        const response=await fetch(file.url,{credentials:'same-origin',cache:'no-store'});
        if(!response.ok)throw Error('Không tải được tệp QR '+file.id);
        const target=await handle.getFileHandle(name,{create:true});
        const writer=await target.createWritable();
        try{await writer.write(await response.blob());await writer.close();}
        catch(error){try{await writer.abort();}catch(_){}throw error;}
      }
      countOperation();
      await finishSave('directory_picker',files);
    }catch(e){info('Chưa kết thúc đo: '+e.message+'. Hãy kiểm tra tệp đã lưu và thử lại.',true);}
    finally{if(saveDirectory)saveDirectory.disabled=false;}
  }
  async function fallbackZip(){
    if(!active)return;
    let handle=null;
    // showSaveFilePicker cũng cần gọi trực tiếp trong sự kiện click.
    if(typeof window.showSaveFilePicker==='function'&&window.isSecureContext){
      try{handle=await window.showSaveFilePicker({
        suggestedName:'QR_thuc_nghiem_'+active.code+'.zip',
        types:[{description:'Tệp ZIP',accept:{'application/zip':['.zip']}}]
      });}
      catch(e){if(e.name==='AbortError')return;info(e.message,true);return;}
    }
    try{
      const files=await fetchFiles();
      const response=await fetch(api.zipUrl,{credentials:'same-origin',cache:'no-store'});
      if(!response.ok)throw Error('Tệp ZIP chưa sẵn sàng.');
      const blob=await response.blob();
      if(handle){
        const writer=await handle.createWritable();
        try{await writer.write(blob);await writer.close();}catch(e){try{await writer.abort();}catch(_){}throw e;}
      }else{
        const tmp=URL.createObjectURL(blob);
        const link=document.createElement('a');
        link.href=tmp;link.download='QR_thuc_nghiem_'+active.code+'.zip';
        document.body.appendChild(link);link.click();link.remove();
        window.setTimeout(()=>URL.revokeObjectURL(tmp),30000);
      }
      countOperation();
      fallbackFiles=files;
      if(confirmBox)confirmBox.hidden=false;
      info('Đã yêu cầu tải ZIP. Hãy giải nén đủ các ảnh PNG vào thư mục mong muốn và kiểm tra tên, sau đó tích xác nhận. Lượt này sẽ được ghi nhận theo xác nhận người dùng.');
    }catch(e){info('Không thể tải ZIP: '+e.message,true);}
  }
  async function confirmFallback(){
    if(!fallbackFiles||!confirmCheckbox?.checked){
      info('Bạn cần giải nén và kiểm tra đủ các tệp trong thư mục trước khi xác nhận.',true);
      return;
    }
    countOperation();
    try{await finishSave('manual_confirmed',fallbackFiles,true);}
    catch(e){info('Chưa thể kết thúc đo: '+e.message,true);}
  }

  // Giao diện và theo dõi thao tác; không thu nội dung chữ gõ hay đường dẫn thư mục.
  document.addEventListener('click',event=>{
    if(!active)return;
    const target=event.target.closest('button,a,input[type="checkbox"],input[type="radio"],input[type="submit"]');
    if(target&&document.querySelector('main')?.contains(target)&&!target.disabled)countOperation();
  },true);
  document.addEventListener('change',event=>{
    if(!active)return;
    if(event.target.matches('input:not([type="checkbox"]):not([type="radio"]),select,textarea'))countOperation();
  },true);
  document.addEventListener('change',event=>{
    const target=event.target;
    if(target.matches('input[name="qrWorkMode"]')){
      if(!active)pendingStartOperations++;
      setModeVisibility();startSelectedMeasurement();
    }
    if(target===course){
      if(!active)pendingStartOperations++;
      setModeVisibility();startSelectedMeasurement();
    }
    if(target.matches('.video-check')){
      const id=Number(target.value);
      if(Number.isSafeInteger(id)&&id>0){
        if(target.checked)chosenVideos.add(id);else chosenVideos.delete(id);
        persistUi();setModeVisibility();
      }
    }
    if(target.id==='selectAllVideos'){
      document.querySelectorAll('.video-check').forEach(x=>{
        const id=Number(x.value);
        if(x.checked)chosenVideos.add(id);else chosenVideos.delete(id);
      });
      persistUi();setModeVisibility();
    }
  });
  if(bulkForm)bulkForm.addEventListener('submit',event=>{
    if(!course?.value){event.preventDefault();info('Hãy chọn môn học/mô đun trước khi tạo QR.',true);return;}
    if(!chosenVideos.size){event.preventDefault();info('Chưa tích chọn video để tạo QR hàng loạt.',true);return;}
    bulkForm.querySelectorAll('[data-research-video-id]').forEach(x=>x.remove());
    bulkCourse.value=course.value;
    for(const id of chosenVideos){
      const hidden=document.createElement('input');
      hidden.type='hidden';hidden.name='video_ids';hidden.value=String(id);
      hidden.dataset.researchVideoId='1';bulkForm.appendChild(hidden);
    }
    countOperation();persistUi();
  });
  document.addEventListener('submit',event=>{
    if(!active||active.kind!=='QR_TUNG_VIDEO_PLAYLIST')return;
    const form=event.target.closest('.video-qr-actions,.playlist-qr-actions');
    if(!form)return;
    const targetCourse=form.querySelector('[name="course_id"]')?.value;
    if(targetCourse&&Number(targetCourse)!==Number(active.course_id)){
      event.preventDefault();info('Đang đo môn học khác. Chỉ tạo QR cho đúng môn đã chọn.',true);
    }
  },true);
  window.addEventListener('qr-library-row-updated',()=>{
    setModeVisibility();
    if(active)window.setTimeout(refresh,200);
  });
  window.addEventListener('pageshow',()=>{if(active)refresh();});
  saveDirectory?.addEventListener('click',saveDirect);
  zipButton?.addEventListener('click',fallbackZip);
  confirmButton?.addEventListener('click',confirmFallback);
  const sendProgress=(beacon=false)=>{
    if(!active||operations===lastSent)return;
    lastSent=operations;
    const data=new FormData();
    data.set('csrf_token',csrf);
    data.set('operations_count',String(operations));
    if(beacon&&navigator.sendBeacon){navigator.sendBeacon(api.progressUrl,data);return;}
    fetch(api.progressUrl,{method:'POST',body:data,credentials:'same-origin',keepalive:true})
      .catch(()=>{lastSent=-1;});
  };
  window.setInterval(()=>{sendProgress();if(active)refresh();},4500);
  window.addEventListener('pagehide',()=>sendProgress(true));
  // Khôi phục danh sách video được chọn giữa các trang (không đụng ô gán môn của GV).
  restoreUi();
  setModeVisibility();
  if(api.id){
    fetch(api.statusUrl,{credentials:'same-origin',cache:'no-store'}).then(r=>r.json()).then(x=>{
      if(x.active)activate(x);
    }).catch(()=>{});
  }
})();
