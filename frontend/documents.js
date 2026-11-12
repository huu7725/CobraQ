/* Local document ingestion with persisted jobs. User data is always rendered as text. */
const DOCUMENT_UPLOADS={items:[],busy:false,generation:0};
function documentResetUploads(){DOCUMENT_UPLOADS.generation++;DOCUMENT_UPLOADS.items=[];DOCUMENT_UPLOADS.busy=false;}
let documentMaxUpload=100*1024*1024;
async function documentApi(path,options={}){
  const response=await fetch(`${API}/documents${path}`,{...options,headers:{...authHeaders(),...(options.headers||{})}});
  const data=await response.json();
  if(!response.ok){const detail=data.detail;throw new Error(typeof detail==='string'?detail:detail?.message||'Không xử lý được tài liệu.');}
  return data;
}
function documentStatusLabel(status){return {queued:'Đang chờ',processing:'Đang trích xuất',completed:'Đã trích xuất',needs_review:'Cần kiểm tra',failed:'Không đọc được',interrupted:'Bị gián đoạn'}[status]||status;}
function documentRenderUploads(){
  const target=$('flist3');if(!target)return;
  target.replaceChildren();
  for(const item of DOCUMENT_UPLOADS.items){
    const card=document.createElement('article');card.className='fitem';
    const percent=item.status==='completed'||item.status==='needs_review'?100:item.total_pages?Math.round((item.processed_pages||0)/item.total_pages*100):0;
    card.innerHTML=`<div class="fitem-top"><span class="file-type">${uiText(item.name.split('.').pop().toUpperCase())}</span><div class="fitem-name">${uiText(item.name)}</div><span class="document-status ${item.status}">${documentStatusLabel(item.status)}</span></div><p class="document-progress-text" role="status">${uiText(item.message||'Đang gửi tài liệu…')}${item.total_pages?' · '+item.processed_pages+'/'+item.total_pages+' trang':''}</p>${['queued','processing'].includes(item.status)?`<progress class="document-progress" ${item.total_pages?`value="${percent}" max="100"`:''} aria-label="Tiến độ trích xuất"></progress>`:''}<div class="document-upload-actions"></div>`;
    if(item.summary){
      const p=document.createElement('p');p.className='document-progress-text';
      p.textContent=`${item.summary.characters.toLocaleString('vi-VN')} ký tự · ${item.summary.questions} câu hỏi · ${item.summary.with_answer} đáp án${item.summary.ocr_pages?' · OCR '+item.summary.ocr_pages+' trang':''}`;
      card.append(p);
      const b=document.createElement('button');b.className='bo';b.textContent='Xem nội dung trích xuất';b.onclick=()=>documentPreview(item.id);
      card.querySelector('.document-upload-actions').append(b);
    }
    target.append(card);
  }
  const summary=$('upok');if(summary){
    const done=DOCUMENT_UPLOADS.items.filter(i=>['completed','needs_review'].includes(i.status)).length;
    const failed=DOCUMENT_UPLOADS.items.filter(i=>i.status==='failed').length;
    summary.classList.toggle('show',!DOCUMENT_UPLOADS.busy&&!!DOCUMENT_UPLOADS.items.length);
    summary.textContent=`${done} tài liệu đã trích xuất${failed?' · '+failed+' tài liệu cần tải lại':''}. Mở kết quả để kiểm tra trước khi sử dụng.`;
  }
}
async function documentPoll(item,generation){
  let failures=0;
  while(['queued','processing'].includes(item.status)&&generation===DOCUMENT_UPLOADS.generation){
    await new Promise(resolve=>setTimeout(resolve,1000));
    try{const status=await documentApi('/'+item.id);if(generation!==DOCUMENT_UPLOADS.generation)return;failures=0;Object.assign(item,status);documentRenderUploads();}
    catch(error){if(generation!==DOCUMENT_UPLOADS.generation)return;item.message='Đang chờ kết nối lại để theo dõi tài liệu…';if(++failures>=10){item.status='interrupted';item.message='Chưa kết nối lại được. Tệp đã gửi vẫn được lưu; mở lại thư viện để kiểm tra.';}documentRenderUploads();await new Promise(resolve=>setTimeout(resolve,4000));}
  }
}
async function documentUploadFiles(files){
  if(!files?.length)return;
  if(DOCUMENT_UPLOADS.busy){tst('Đang đưa một nhóm tài liệu vào hệ thống. Hãy chờ gửi xong.','info');return;}
  DOCUMENT_UPLOADS.items=[];DOCUMENT_UPLOADS.busy=true;
  const generation=++DOCUMENT_UPLOADS.generation;
  const polls=[];
  for(const file of files){
    if(generation!==DOCUMENT_UPLOADS.generation)return;
    const item={name:file.name,status:'queued',message:'Đang tải tệp lên…'};DOCUMENT_UPLOADS.items.push(item);documentRenderUploads();
    if(!/\.(pdf|docx)$/i.test(file.name)||!file.size||file.size>documentMaxUpload){
      Object.assign(item,{status:'failed',message:!file.size?'Tệp rỗng.':file.size>documentMaxUpload?`Tệp vượt giới hạn ${Math.round(documentMaxUpload/1024/1024)} MB.`:'Chỉ hỗ trợ .docx và .pdf.'});documentRenderUploads();continue;
    }
    try{
      const form=new FormData();form.append('file',file);
      Object.assign(item,await documentApi('/upload',{method:'POST',body:form}));
      if(item.already_exists)item.message='Tài liệu đã có trong thư viện; giữ nguyên nội dung đã sửa.';
      documentRenderUploads();polls.push(documentPoll(item,generation));
    }catch(error){Object.assign(item,{status:'failed',message:error.message});documentRenderUploads();}
  }
  await Promise.all(polls);if(generation!==DOCUMENT_UPLOADS.generation)return;DOCUMENT_UPLOADS.busy=false;
  await lst();
  if(S.pg==='upload')rp2();
  else tst('Tài liệu đã xử lý xong. Xem kết quả trong Tài liệu và đề thi.','info');
}
async function documentLibrary(){
  documentRenderUploads();const target=$('document-library');if(!target)return;
  try{const capabilities=await documentApi('/capabilities');documentMaxUpload=capabilities.max_upload_bytes;const limit=$('document-limit');if(limit)limit.textContent=`Kéo thả Word hoặc PDF · Tối đa ${Math.round(documentMaxUpload/1024/1024)} MB · ${capabilities.ocr.available?'Hỗ trợ OCR scan':'OCR scan chưa sẵn sàng'}`;}catch{}
  try{
    const data=await documentApi('');if(!target.isConnected)return;
    if(!data.documents.length){target.textContent='Các tài liệu mới sẽ xuất hiện tại đây sau khi tải lên.';return;}
    target.innerHTML='<div class="section-heading"><h2>Thư viện trích xuất</h2><span class="metric-note">Văn bản, trang nguồn và kết quả nhận dạng</span></div>';
    for(const row of data.documents){
      const article=document.createElement('article');article.className='document-row';
      article.innerHTML=`<div class="document-main"><h3>${uiText(row.filename)}</h3><p>${uiText(row.summary?`${row.summary.characters.toLocaleString('vi-VN')} ký tự · ${row.summary.questions} câu · ${row.summary.with_answer} đáp án`:row.message)}</p></div><span class="document-status ${row.status}">${documentStatusLabel(row.status)}</span>`;
      const button=document.createElement('button');button.className='bo';button.textContent='Xem trích xuất';
      button.disabled=!['completed','needs_review'].includes(row.status);button.onclick=()=>documentPreview(row.id);article.append(button);target.append(article);
    }
    if(data.documents.some(d=>['queued','processing'].includes(d.status)))setTimeout(()=>{if(target.isConnected)documentLibrary();},3000);
  }catch(error){target.textContent=error.message;}
}
async function documentPreview(id){
  const dialog=document.createElement('dialog');dialog.className='document-dialog';
  dialog.innerHTML='<header><div><div class="eyebrow">Kết quả trích xuất</div><h2>Tài liệu</h2></div><button class="bo" type="button">Đóng</button></header><div class="document-dialog-content"><p role="status">Đang tải nội dung…</p></div>';
  dialog.querySelector('button').onclick=()=>dialog.close();dialog.onclose=()=>dialog.remove();document.body.append(dialog);dialog.showModal();
  const target=dialog.querySelector('.document-dialog-content');let offset=0;
  async function load(){
    try{
      const data=await documentApi(`/${id}/content?offset=${offset}&limit=20`);if(!dialog.isConnected)return;
      dialog.querySelector('h2').textContent=data.filename;
      if(!offset){
        target.replaceChildren();
        const summary=document.createElement('p');summary.className='document-result-summary';summary.textContent=`${data.summary.pages??'Word: không có trang cố định'}${data.summary.pages?' trang':''} · ${data.summary.characters.toLocaleString('vi-VN')} ký tự · ${data.total_chunks} đoạn nguồn · ${data.summary.questions} câu hỏi`;
        target.append(summary);
        const actions=document.createElement('div');actions.className='document-upload-actions';
        const download=document.createElement('button');download.className='bo';download.textContent='Tải tệp nguồn';download.onclick=()=>documentDownload(id,data.filename);actions.append(download);
        if(data.summary.questions){const questions=document.createElement('button');questions.className='bp';questions.textContent='Kiểm tra câu hỏi và đáp án';questions.onclick=()=>{dialog.close();openPreview(id,data.filename);};actions.append(questions);}
        target.append(actions);
        if(data.warnings.length){const warnings=document.createElement('div');warnings.className='document-warnings';warnings.innerHTML='<h3>Các mục cần kiểm tra</h3>';for(const w of data.warnings.slice(0,20)){const p=document.createElement('p');p.textContent=(w.page?'Trang '+w.page+': ':'')+w.message;warnings.append(p);}target.append(warnings);}
        const notice=document.createElement('p');notice.className='auth-hint';notice.textContent='Nội dung được trích xuất cục bộ. Chưa được tự động phê duyệt làm học liệu hay kết quả nghiên cứu.';target.append(notice);
      }
      target.querySelector('.document-more')?.remove();
      for(const chunk of data.chunks){
        const article=document.createElement('article');article.className='extracted-chunk';
        const heading=document.createElement('div');heading.className='eyebrow';heading.textContent=chunk.pages.length?'Trang '+chunk.pages.join(', '):'Đoạn '+(offset+1);
        const text=document.createElement('p');text.textContent=chunk.text;article.append(heading,text);
        if(chunk.pages.length){const b=document.createElement('button');b.className='text-button';b.textContent='Xem ảnh trang '+chunk.pages[0];b.onclick=()=>documentPage(id,chunk.pages[0]);article.append(b);}
        target.append(article);offset++;
      }
      if(offset<data.total_chunks){const more=document.createElement('button');more.className='bo document-more';more.textContent=`Xem thêm (${offset}/${data.total_chunks} đoạn)`;more.onclick=load;target.append(more);}
    }catch(error){const p=document.createElement('p');p.textContent=error.message;target.append(p);}
  }
  await load();
}
async function documentDownload(id,filename){
  try{const r=await fetch(`${API}/documents/${id}/source`,{headers:authHeaders()});if(!r.ok)throw new Error('Không tải được tệp nguồn.');const url=URL.createObjectURL(await r.blob());const a=document.createElement('a');a.href=url;a.download=filename;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}catch(error){tst(error.message,'err');}
}
async function documentPage(id,page){
  try{
    const r=await fetch(`${API}/documents/${id}/pages/${page}`,{headers:authHeaders()});if(!r.ok)throw new Error('Không mở được trang nguồn.');
    const url=URL.createObjectURL(await r.blob()),dialog=document.createElement('dialog');dialog.className='document-dialog document-page-image';
    dialog.innerHTML=`<header><h2>Trang ${page}</h2><button class="bo">Đóng trang nguồn</button></header><img alt="Trang nguồn ${page}">`;
    dialog.querySelector('img').src=url;dialog.querySelector('button').onclick=()=>dialog.close();dialog.onclose=()=>{URL.revokeObjectURL(url);dialog.remove();};document.body.append(dialog);dialog.showModal();
  }catch(error){tst(error.message,'err');}
}
