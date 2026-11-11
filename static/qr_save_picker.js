// Chọn vị trí lưu do trình duyệt kiểm soát; không thể truy cập đường dẫn máy người dùng.
(() => {
  document.addEventListener('click', async (event) => {
    const link = event.target.closest('a.qr-save-picker');
    if (!link) return;
    if (link.classList.contains('disabled') || !link.href || link.getAttribute('href') === '#') {
      event.preventDefault();
      return;
    }
    if (typeof window.showSaveFilePicker !== 'function' || !window.isSecureContext) return;
    event.preventDefault();
    // showSaveFilePicker phải được gọi trực tiếp từ thao tác nhấp của người dùng.
    const isZip = new URL(link.href).pathname.toLowerCase().endsWith('.zip');
    const suggested = link.dataset.filename || (isZip ? 'Ma_QR_hoc_lieu.zip' : 'Ma_QR.png');
    const opts = isZip
      ? {suggestedName:suggested,types:[{description:'Tệp ZIP',accept:{'application/zip':['.zip']}}]}
      : {suggestedName:suggested,types:[{description:'Ảnh PNG',accept:{'image/png':['.png']}}]};
    try {
      const handle = await window.showSaveFilePicker(opts);
      const response = await fetch(link.href, {credentials:'same-origin'});
      if (!response.ok || !(response.headers.get('content-type') || '').includes(isZip ? 'zip' : 'png')) {
        throw new Error('Máy chủ chưa trả về tệp QR hợp lệ.');
      }
      const writable = await handle.createWritable();
      try { await writable.write(await response.blob()); await writable.close(); }
      catch (err) { try { await writable.abort(); } catch(_) {} throw err; }
    } catch (err) {
      if (err?.name === 'AbortError') return;
      window.alert('Không thể lưu vào vị trí đã chọn. Hãy tải lại hoặc kiểm tra quyền ghi tệp.');
    }
  });
})();
