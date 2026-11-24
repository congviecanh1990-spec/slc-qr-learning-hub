/* Nút Bỏ lọc riêng playlist/video trong Kho học liệu.
 * Chỉ xóa lựa chọn của danh mục được đặt lại, thuộc tài khoản đang đăng nhập.
 * Không chạm dữ liệu máy chủ, mã QR, phân công môn hoặc bộ lọc danh mục khác.
 * URL Bỏ lọc được máy chủ tạo sẵn và bỏ cả tham số phân trang danh mục đó.
 */
(function () {
  'use strict';
  function clearOwnSelections(prefix, userId) {
    if (!userId) return;
    try {
      const candidates=[];
      for(let i=0;i<sessionStorage.length;i++){
        const key=sessionStorage.key(i);
        if(!key || !key.startsWith(prefix)) continue;
        // Cấu trúc khóa: prefix + JSON.stringify([userId, ...scope]).
        const scope=JSON.parse(key.slice(prefix.length));
        if(Array.isArray(scope) && String(scope[0])===String(userId)){
          candidates.push(key);
        }
      }
      for(const key of candidates) sessionStorage.removeItem(key);
    }catch(_){
      // Trong cửa sổ chặn sessionStorage, link Bỏ lọc vẫn hoạt động.
    }
  }
  document.addEventListener('click', event=>{
    const link=event.target.closest('a[data-library-filter-reset]');
    if(!link || event.defaultPrevented || event.button!==0 ||
       event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    if(link.dataset.libraryFilterReset==='playlist'){
      const userId=document.getElementById('playlistBulkActions')?.dataset.userId;
      clearOwnSelections('slc-playlist-selection-v4:',userId);
    }else if(link.dataset.libraryFilterReset==='video'){
      const userId=document.getElementById('assignVideoForm')?.dataset.userId;
      clearOwnSelections('slc-video-selection-v1:',userId);
    }
    // Để trình duyệt mở URL do server cung cấp: các ô lọc trở về mặc định.
  });
})();
