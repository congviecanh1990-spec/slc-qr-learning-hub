/* Đo đối chứng ngay trong Kho học liệu.
   Nhiệm vụ được PHÂN LOẠI BẰNG NÚT TẢI QR THỰC TẾ, không bằng checkbox.
   Tải ở từng dòng -> từng QR; lưu tất cả >=2 QR -> hàng loạt.
   Không đọc/ghi đường dẫn cá nhân. Với tải native của Chrome, chỉ chốt
   sau khi GV xác nhận đã lưu; giữ tách biệt dữ liệu tự xác nhận và
   dữ liệu hệ thống kiểm chứng độc lập. */
(() => {
  'use strict';
  const api=window.researchMeasurement;
  if(!api || !document.getElementById('videos'))return;
  const csrf=document.querySelector('meta[name="csrf-token"]')?.content||'';
  const status=document.getElementById('researchQrStatus');
  let active=null,ops=0,lastSent=-1,preflight=null,confirming=false;
  const pendingKey='slc-qr-pending-confirmations-v2';
  function readPending(){
    try{
      const list=JSON.parse(sessionStorage.getItem(pendingKey)||'[]');
      if(!Array.isArray(list))return [];
      return list.filter(item=>
        ['bulk','row'].includes(item.style) &&
        Array.isArray(item.ids) && item.ids.length>0 &&
        item.ids.length<=1000 && item.ids.every(id=>Number.isSafeInteger(id)&&id>0)
      ).slice(-50);
    }catch(_){return [];}
  }
  let pendingDownloads=readPending();
  function persistPending(){
    try{
      if(pendingDownloads.length)sessionStorage.setItem(pendingKey,JSON.stringify(pendingDownloads));
      else sessionStorage.removeItem(pendingKey);
    }catch(_){}
  }
  function queuePending(style,ids){
    if(!ids?.length)return;
    const key=style+':'+ids.join(',');
    if(!pendingDownloads.some(item=>item.key===key))
      pendingDownloads.push({style,ids,key});
    persistPending();
    showPendingConfirmation();
  }
  let idleConfirmationMessage='Chưa có lượt tải QR mới cần xác nhận. Nút sẽ bật sau khi tải mã thuộc lượt đo.';
  // Hai vị trí cố định trong giao diện: gần playlist và gần danh sách video.
  // Không tạo nút động trong thông báo, vì nội dung thông báo có thể bị thay thế
  // khi tải QR hoặc khi bộ đếm đồng bộ làm nút biến mất.
  function showPendingConfirmation(){
    const total=pendingDownloads.reduce((n,item)=>n+item.ids.length,0);
    for(const panel of document.querySelectorAll('.research-qr-confirmation')){
      const button=panel.querySelector('.research-qr-confirm-button');
      const cancel=panel.querySelector('.research-qr-confirm-cancel');
      const state=panel.querySelector('.research-qr-confirm-state');
      if(button)button.disabled=confirming||pendingDownloads.length===0;
      if(cancel)cancel.hidden=pendingDownloads.length===0;
      if(state){
        state.textContent=pendingDownloads.length
          ? 'Đã ghi nhận yêu cầu tải '+total+' mã QR trong '+
            pendingDownloads.length+' lượt. Sau khi kiểm tra tệp đã lưu trên máy, nhấn xác nhận để chốt lượt đo.'
          : idleConfirmationMessage;
        state.classList.toggle('text-muted',pendingDownloads.length===0);
        state.classList.toggle('text-primary',pendingDownloads.length>0);
      }
    }
  }
  async function confirmPendingDownloads(){
    if(confirming||!pendingDownloads.length)return;
    confirming=true;showPendingConfirmation();
    let completed=0,failedMessage='';
    for(const item of [...pendingDownloads]){
      const result=await recordDownload(item.style,item.ids,'manual_confirmed',true);
      if(!result?.measured){
        failedMessage=result?.message||'Lượt tải chưa khớp với phiên tạo QR mới.';
        break;
      }
      pendingDownloads=pendingDownloads.filter(x=>x.key!==item.key);
      completed+=1;
      persistPending();
    }
    confirming=false;
    if(failedMessage){
      idleConfirmationMessage='Chưa chốt được: '+failedMessage;
      announce(idleConfirmationMessage,true);
    }else if(completed){
      idleConfirmationMessage='Đã ghi nhận xác nhận lưu '+completed+
        ' lượt QR. Thời gian và số thao tác được chốt theo xác nhận của giảng viên, '+
        'chưa phải bằng chứng lưu tệp đã xác minh độc lập.';
      announce(idleConfirmationMessage);
    }
    showPendingConfirmation();
  }
  function cancelPendingDownloads(){
    if(confirming)return;
    pendingDownloads=[];persistPending();
    idleConfirmationMessage='Đã hủy yêu cầu xác nhận. Lượt đo chưa được chốt vì chưa xác nhận lưu tệp.';
    announce(idleConfirmationMessage,true);
    showPendingConfirmation();
  }
  document.addEventListener('click',event=>{
    if(event.target.closest('.research-qr-confirm-button')){
      // Đếm chính nút xác nhận TRƯỚC khi gửi số thao tác chốt lên máy chủ.
      if(!confirming && pendingDownloads.length && active)addOperation();
      confirmPendingDownloads();
    }else if(event.target.closest('.research-qr-confirm-cancel')){
      cancelPendingDownloads();
    }
  });

  const sessionKey=()=>active?'slc-qr-ops:'+active.id+':'+active.nonce:'';
  const labels={
    QR_TUNG_VIDEO_PLAYLIST:'Tạo QR cho từng video hoặc playlist',
    QR_VIDEO_HANG_LOAT:'Tạo QR hàng loạt'
  };
  function announce(message,warning=false){
    if(!status)return;
    status.textContent=message;
    status.classList.remove('d-none','alert-info','alert-warning');
    status.classList.add(warning?'alert-warning':'alert-info');
  }
  async function post(url,fields={},extraHeaders={}){
    const data=new FormData();
    if(csrf)data.set('csrf_token',csrf);
    for(const [key,value] of Object.entries(fields))data.set(key,String(value));
    const response=await fetch(url,{
      method:'POST',body:data,credentials:'same-origin',
      headers:extraHeaders,cache:'no-store'
    });
    let value={};
    try{value=await response.json();}catch(_){}
    if(!response.ok)throw Error(value.message||value.reason||'Không thể xác nhận tác vụ trên máy chủ.');
    return value;
  }
  async function refresh(){
    try{
      const response=await fetch(api.statusUrl,{credentials:'same-origin',cache:'no-store'});
      if(!response.ok)return;
      const data=await response.json();
      if(data.active){
        active=data;
        try{ops=Math.max(data.operations||0,Number(sessionStorage.getItem(sessionKey()))||0);}catch(_){ops=data.operations||0;}
        if(data.created && !pendingDownloads.length){
          announce('Đang đo tự động: '+data.code+' · đã tạo '+data.created+'/'+data.expected+
            ' QR. Kết quả được phân loại khi bạn tải QR ở từng dòng hoặc tải tất cả.');
        }
      }else active=null;
    }catch(_){}
  }
  function addOperation(){
    if(!active)return;
    ops=Math.min(100000,ops+1);
    try{sessionStorage.setItem(sessionKey(),String(ops));}catch(_){}
  }
  async function begin(course,kind,selectedCount=null){
    if(!course)return;
    if(active && String(active.course_id)===String(course))return;
    if(preflight)return preflight;
    preflight=(async()=>{
      try{
        const fields={course_id:course,task_kind:kind};
        if(selectedCount!==null)fields.selected_count=selectedCount;
        const result=await post(api.startUrl,fields);
        if(result.active){
          active=result;ops=Math.max(1,result.operations||0);
          try{sessionStorage.setItem(sessionKey(),String(ops));}catch(_){}
          announce('Bắt đầu đo lượt '+result.code+'. Phân loại nhiệm vụ sẽ theo cách tải QR thực tế.');
        }
      }catch(e){
        announce('Phép đo chưa bắt đầu: '+e.message,true);
      }finally{preflight=null;}
    })();
    return preflight;
  }
  const pickCourse=form=>{
    if(form.id==='playlistBulkActions'||form.id==='assignVideoForm')
      return form.querySelector('[name="course_id"]')?.value||'';
    if(form.matches('.video-qr-actions,.playlist-qr-actions'))
      return form.querySelector('[name="course_id"]')?.value||'';
    if(form.matches('.playlist-course-form')){
      const checked=[...form.querySelectorAll('[name="course_ids"]:checked')];
      return checked.length===1?checked[0].value:'';
    }
    return '';
  };
  const isPlaylistBulk=form=>form.id==='playlistBulkActions';
  const isVideoBulk=form=>form.id==='assignVideoForm';
  const isDownloadButton=button=>Boolean(button?.matches(
    '#assignVideoForm button[formaction*="/videos/qr/download-selected"]'));
  function selectedNumber(form,submitter=null){
    if(isPlaylistBulk(form))return window.playlistBulkSelection?.selectedCount()||0;
    if(isVideoBulk(form)){
      // QR theo môn áp dụng cho mọi video độc lập đã gán môn trên mọi trang.
      if(submitter?.formAction?.includes('/videos/qr/bulk-selected')){
        const choice=form.querySelector('[name="course_id"]')?.selectedOptions?.[0];
        return Math.max(0,Number(choice?.dataset.assignedVideoCount)||0);
      }
      const checked=window.videoBulkSelection?.selectedCount()||0;
      if(!submitter || submitter.formAction?.includes('/videos/qr/download-selected'))return checked;
      // Nút Gán môn còn áp dụng cho môn được chọn ở cột QR từng dòng.
      return checked+(window.videoBulkSelection?.selectedQrCourseCount?.()||0);
    }
    return 1;
  }
  // Khởi động trước POST gán môn/tạo QR để thời gian chạy trên máy chủ bao gồm
  // cả thao tác tạo và lưu, không chỉ thời gian sinh ảnh QR.
  document.addEventListener('submit',async event=>{
    const form=event.target;
    if(!form.matches('#playlistBulkActions,#assignVideoForm,.playlist-course-form,.playlist-qr-actions,.video-qr-actions'))
      return;
    if(isDownloadButton(event.submitter)){
      event.preventDefault();event.stopImmediatePropagation();
      await downloadAll(form,event.submitter.formAction);
      return;
    }
    // Tạo QR cho TẤT CẢ video đã gán môn: không có course_id duy nhất.
    // Đưa thẳng biểu mẫu đến máy chủ; máy chủ tự ghi nhận lượt tạo QR
    // cho tất cả môn, tránh chặn thao tác vì phép đo chỉ nhận một môn.
    if((isVideoBulk(form) &&
        event.submitter?.formAction?.includes('/videos/qr/bulk-selected')) ||
       (isPlaylistBulk(form) &&
        event.submitter?.formAction?.includes('/playlists/bulk-create-course-qrs')))return;
    if(form.dataset.researchPreflight==='done'){
      delete form.dataset.researchPreflight;
      return; // Rời quyền xử lý cho handler Gán môn / Tạo QR vốn có.
    }
    const course=pickCourse(form);
    if(!course)return;
    event.preventDefault();event.stopImmediatePropagation();
    const btn=event.submitter;
    const n=selectedNumber(form,event.submitter);
    if(n<1 && (isPlaylistBulk(form)||isVideoBulk(form))){
      announce('Chưa chọn video hoặc playlist; không khởi động lượt đo đối chứng.',true);
      return;
    }
    const kind=(n>=2 && (isPlaylistBulk(form)||isVideoBulk(form)))
      ?'QR_VIDEO_HANG_LOAT':'QR_TUNG_VIDEO_PLAYLIST';
    await begin(course,kind,n>=2?n:null);
    form.dataset.researchPreflight='done';
    try{form.requestSubmit(btn||undefined);}
    catch(e){delete form.dataset.researchPreflight;announce('Không tiếp tục được thao tác: '+e.message,true);}
  },true);

  // Chỉ đếm các thao tác trong Web App khi một cặp đo đã được giao và khởi động.
  document.addEventListener('click',event=>{
    if(active && !event.target.closest('.research-qr-confirm-button') &&
       event.target.closest('main button,main a,main input[type="checkbox"]'))
      addOperation();
    const rowLink=event.target.closest('a.playlist-qr-download,a.video-qr-download');
    // Tải PNG thành công qua HTTP chưa chứng minh người dùng đã lưu file.
    // Ghi nhận lượt tải rồi đề nghị chính GV xác nhận đã lưu vào máy.
    if(rowLink && rowLink.href && rowLink.getAttribute('href')!=='#'){
      const match=new URL(rowLink.href,location.href).pathname.match(/\/qr\/(\d+)\/png$/);
      if(match){
        const ids=[Number(match[1])];
        recordDownload('row',ids,'not_verified').then(result=>{
          if(result?.matched>0)queuePending('row',ids);
          else{
            idleConfirmationMessage='Đã tải QR, nhưng mã này chưa thuộc lượt đo tạo QR mới. '+
              'Hãy tạo QR trong lượt đo mới để kích hoạt xác nhận.';
            showPendingConfirmation();
          }
        });
      }
    }
  },true);
  document.addEventListener('change',event=>{
    if(active && event.target.matches('main select,main input,main textarea'))
      addOperation();
  },true);

  async function recordDownload(style,ids,method,manual=false){
    if(!Array.isArray(ids)||!ids.length)return null;
    const classification=(style==='bulk'&&ids.length>=2)?
      'QR_VIDEO_HANG_LOAT':'QR_TUNG_VIDEO_PLAYLIST';
    try{
      const result=await post(api.savedUrl,{
        download_style:classification==='QR_VIDEO_HANG_LOAT'?'bulk':'row',
        qr_ids:JSON.stringify(ids),save_method:method,
        user_confirmed:manual?'yes':'no',operations_count:Math.max(1,ops)
      });
      if(result.measured){
        if(result.completed){
          announce('Đã chốt lượt đo '+labels[result.kind]+': '+
            result.seconds+' giây, '+result.operations+' thao tác'+
            (result.verified
              ?' (tệp PNG được hệ thống xác minh).'
              :' (GV đã tự xác nhận lưu; chưa kiểm chứng độc lập).'));
          const key=sessionKey();
          active=null;ops=0;lastSent=-1;
          try{sessionStorage.removeItem(key);}catch(_){}
        }else announce('Đã ghi nhận '+labels[result.kind]+': lưu '+result.saved+
          '/'+result.expected+' QR của lượt đo.');
      }else{
        announce(labels[classification]+'. '+(result.message||
          'Không có lượt đo đối chứng đã giao cho thao tác này.'));
      }
      if(result.measured&&!result.completed)await refresh();
      return result;
    }catch(e){
      announce('Chưa ghi được phép đo: '+e.message,true);
      return {ok:false,message:e.message};
    }
  }
  document.addEventListener('qr-download-complete',event=>{
    const a=event.target.closest('a.playlist-qr-download,a.video-qr-download');
    if(!a)return;
    const match=new URL(a.href,location.href).pathname.match(/\/qr\/(\d+)\/png$/);
    if(match)recordDownload('row',[Number(match[1])],'directory_picker');
  });

  async function downloadAll(form,endpoint){
    // Chrome không cho trang web ghi vào thư mục do người dùng chọn mà không
    // cấp quyền, đặc biệt là thư mục hệ thống (Downloads, Program Files...).
    // Vì vậy tải ONE ZIP bằng download thông thường; Chrome có thể hỏi nơi
    // lưu theo tùy chọn Settings > Downloads > Ask where to save each file.
    const allVideoQrs=isVideoBulk(form) &&
      form.querySelector('[name="download_scope"]')?.value==='all_assigned';
    const allPlaylistQrs=isPlaylistBulk(form) &&
      form.querySelector('[name="download_scope"]')?.value==='all_assigned';
    const allAssignedQrs=allVideoQrs||allPlaylistQrs;
    if(!allAssignedQrs){
      const course=pickCourse(form);
      if(!course){announce('Hãy chọn môn học/mô đun để tải QR.',true);return;}
      const n=selectedNumber(form);
      if(n<1){announce('Hãy tích chọn video hoặc playlist để tải QR.',true);return;}
    }
    announce('Đang đóng gói các mã QR thành tệp ZIP...');
    try{
      if(isPlaylistBulk(form) && !allPlaylistQrs)
        window.playlistBulkSelection?.appendSelection(form);
      else if(isVideoBulk(form) && !allVideoQrs)
        window.videoBulkSelection?.appendSelection(form);
      const data=new FormData(form);
      // Truy vấn danh sách trước để thông báo lỗi và số lượng mã chính xác.
      const apiResponse=await fetch(endpoint,{
        method:'POST',body:data,credentials:'same-origin',cache:'no-store',
        headers:{'Accept':'application/json'}
      });
      let parsed={};
      try{parsed=await apiResponse.json();}catch(_){}
      if(!apiResponse.ok||!parsed.ok)
        throw Error(parsed.message||'Không có mã QR đã tạo để tải.');
      const files=parsed.files||[];
      if(!files.length)throw Error('Chưa có mã QR hợp lệ để tải.');
      const ids=files.map(file=>Number(file.id));
      // Trả lại ZIP chuẩn với mỗi PNG đã được đặt tên theo video/playlist
      // ở phía máy chủ. Không sử dụng showDirectoryPicker/createWritable.
      const zip=await fetch(endpoint,{
        method:'POST',body:data,credentials:'same-origin',cache:'no-store'
      });
      if(!zip.ok || !(zip.headers.get('content-type')||'').includes('zip'))
        throw Error('Máy chủ không trả về tệp ZIP hợp lệ.');
      const blob=await zip.blob(),url=URL.createObjectURL(blob);
      const a=document.createElement('a');
      a.href=url;
      a.download=allVideoQrs?'Ma_QR_video_da_tao_tat_ca.zip':
        (allPlaylistQrs?'Ma_QR_playlist_da_tao_tat_ca.zip':'Ma_QR_hoc_lieu_da_chon.zip');
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.setTimeout(()=>URL.revokeObjectURL(url),30000);
      // Trình duyệt không báo lại cho web khi người dùng thực sự lưu ZIP:
      // không ghi nhận là tệp PNG đã được xác minh.
      const style=ids.length>=2?'bulk':'row';
      const tracked=await recordDownload(style,ids,'not_verified');
      if(tracked?.matched>0)queuePending(style,ids);
      else{
        idleConfirmationMessage='Đã gửi ZIP '+ids.length+
          ' mã QR tới Chrome, nhưng chưa có QR mới thuộc lượt đo đang mở. '+
          'Nút xác nhận chỉ kích hoạt với QR mới của lượt đo.';
        announce(idleConfirmationMessage);
        showPendingConfirmation();
      }
    }catch(e){announce('Không tải được QR: '+e.message,true);}
  }

  const playlistButton=document.getElementById('playlistBulkDownloadQr');
  playlistButton?.addEventListener('click',event=>{
    if(playlistButton.disabled)return;
    event.preventDefault();
    const form=document.getElementById('playlistBulkActions');
    if(form)downloadAll(form,playlistButton.dataset.filesUrl);
  });
  const sendProgress=()=>{
    if(!active||ops===lastSent)return;
    lastSent=ops;
    post(api.progressUrl,{operations_count:ops}).catch(()=>{lastSent=-1;});
  };
  window.setInterval(()=>{sendProgress();if(active)refresh();},4500);
  window.addEventListener('pagehide',()=>{
    if(!active)return;
    const data=new FormData();
    if(csrf)data.set('csrf_token',csrf);
    data.set('operations_count',String(ops));
    navigator.sendBeacon?.(api.progressUrl,data);
  });
  refresh().finally(()=>{if(pendingDownloads.length)showPendingConfirmation();});
})();
