/* Đo đối chứng ngay trong Kho học liệu.
   Nhiệm vụ được PHÂN LOẠI BẰNG NÚT TẢI QR THỰC TẾ, không bằng checkbox.
   Tải ở từng dòng -> từng QR; lưu tất cả >=2 QR -> hàng loạt.
   Không đọc/ghi đường dẫn cá nhân. Chỉ chốt "đã xác minh" khi PNG được
   ghi trực tiếp thành công bằng File System Access API. */
(() => {
  'use strict';
  const api=window.researchMeasurement;
  if(!api || !document.getElementById('videos'))return;
  const csrf=document.querySelector('meta[name="csrf-token"]')?.content||'';
  const status=document.getElementById('researchQrStatus');
  const canWriteDirectory=Boolean(window.showDirectoryPicker && window.isSecureContext);
  const canWriteFile=Boolean(window.showSaveFilePicker && window.isSecureContext);
  let active=null,ops=0,lastSent=-1,preflight=null;
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
        if(data.created){
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
    if(active && event.target.closest('main button,main a,main input[type="checkbox"]'))
      addOperation();
    const rowLink=event.target.closest('a.playlist-qr-download,a.video-qr-download');
    if(rowLink && !canWriteFile){
      const match=new URL(rowLink.href,location.href).pathname.match(/\/qr\/(\d+)\/png$/);
      if(match)recordDownload('row',[Number(match[1])],'not_verified');
    }
  },true);
  document.addEventListener('change',event=>{
    if(active && event.target.matches('main select,main input,main textarea'))
      addOperation();
  },true);

  async function recordDownload(style,ids,method,manual=false){
    if(!Array.isArray(ids)||!ids.length)return;
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
          announce('Đã hoàn thành đo '+labels[result.kind]+': '+
            result.seconds+' giây, '+result.operations+' thao tác'+
            (result.verified?' (đã xác minh tệp PNG).':' (lưu ZIP do người dùng xác nhận).'));
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
    }catch(e){announce('Đã tải mã QR nhưng chưa ghi được phép đo: '+e.message,true);}
  }
  document.addEventListener('qr-download-complete',event=>{
    const a=event.target.closest('a.playlist-qr-download,a.video-qr-download');
    if(!a)return;
    const match=new URL(a.href,location.href).pathname.match(/\/qr\/(\d+)\/png$/);
    if(match)recordDownload('row',[Number(match[1])],'directory_picker');
  });

  async function downloadAll(form,endpoint){
    const course=pickCourse(form);
    if(!course){announce('Hãy chọn môn học/mô đun để tải QR.',true);return;}
    const n=selectedNumber(form);
    if(n<1){announce('Hãy tích chọn video hoặc playlist để tải QR.',true);return;}
    // Picker phải được gọi trực tiếp trong submit/click của người dùng,
    // trước bất kỳ await nào, nếu không Chrome sẽ chặn quyền chọn thư mục.
    let handle=null;
    if(canWriteDirectory){
      try{handle=await window.showDirectoryPicker({mode:'readwrite'});}
      catch(e){
        if(e?.name!=='AbortError')announce('Không thể chọn thư mục: '+e.message,true);
        return;
      }
    }
    try{
      if(isPlaylistBulk(form))window.playlistBulkSelection?.appendSelection(form);
      else window.videoBulkSelection?.appendSelection(form);
      const data=new FormData(form);
      const apiResponse=await fetch(endpoint,{
        method:'POST',body:data,credentials:'same-origin',cache:'no-store',
        headers:{'Accept':'application/json'}
      });
      const parsed=await apiResponse.json();
      if(!apiResponse.ok||!parsed.ok)throw Error(parsed.message||'Không có QR đã tạo để tải.');
      const files=parsed.files;
      if(!files?.length)throw Error('Chưa có QR hợp lệ trong các mục đã chọn.');
      const ids=files.map(f=>Number(f.id));
      const isBulk=ids.length>=2;
      if(handle){
        const names=new Set();
        for(const file of files){
          let filename=(file.name||'Ma_QR.png').replace(/[\\/:*?"<>|]/g,'_');
          if(names.has(filename)){
            const dot=filename.lastIndexOf('.');
            filename=filename.slice(0,dot<0?filename.length:dot)+'_qr'+file.id+
              (dot<0?'':filename.slice(dot));
          }
          names.add(filename);
          try{
            await handle.getFileHandle(filename,{create:false});
            const dot=filename.lastIndexOf('.');
            filename=filename.slice(0,dot<0?filename.length:dot)+'_qr'+file.id+
              (dot<0?'':filename.slice(dot));
          }catch(e){if(e.name!=='NotFoundError')throw e;}
          const qr=await fetch(file.url,{credentials:'same-origin'});
          if(!qr.ok||!(qr.headers.get('content-type')||'').includes('image/png'))
            throw Error('Không nhận được ảnh QR hợp lệ: '+file.id);
          const writer=await (await handle.getFileHandle(filename,{create:true})).createWritable();
          try{await writer.write(await qr.blob());await writer.close();}
          catch(e){try{await writer.abort();}catch(_){}throw e;}
        }
        addOperation();
        await recordDownload(isBulk?'bulk':'row',ids,'directory_picker');
        const btn=document.getElementById('playlistBulkDownloadQr');
        if(isPlaylistBulk(form))btn?.dispatchEvent(new CustomEvent(
          'qr-download-complete',{bubbles:true,detail:{method:'directory_picker'}}));
      }else{
        // Trình duyệt không hỗ trợ lưu PNG từng tệp vào thư mục:
        // tải ZIP và ghi nhận không tự xác minh, KHÔNG đưa vào tỷ lệ nghiệm thu.
        const zip=await fetch(endpoint,{
          method:'POST',body:data,credentials:'same-origin',cache:'no-store'
        });
        if(!zip.ok||!(zip.headers.get('content-type')||'').includes('zip'))
          throw Error('Không tải được tệp ZIP đã chọn.');
        const blob=await zip.blob(),url=URL.createObjectURL(blob);
        const a=document.createElement('a');
        a.href=url;a.download='Ma_QR_hoc_lieu_da_chon.zip';
        document.body.appendChild(a);a.click();a.remove();
        window.setTimeout(()=>URL.revokeObjectURL(url),30000);
        await recordDownload(isBulk?'bulk':'row',ids,'not_verified');
        announce('Đã tải ZIP ('+ids.length+' QR). Sau khi giải nén và kiểm tra đủ PNG, '+
          'lượt này chưa được hệ thống xác minh tự động nên không cộng vào tỷ lệ nghiệm thu.');
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
  refresh();
})();
