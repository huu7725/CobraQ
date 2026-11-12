/* History 12: approved practice and teacher review. */
function researchEscape(value) {
  return String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}
async function researchApi(path, options = {}) {
  const response = await fetch(`${API}/research${path}`, {...options,
    headers: {...authHeaders(), ...(options.body ? {'Content-Type':'application/json'} : {})}});
  if (!response.ok) {
    let detail = `Lỗi ${response.status}`;
    try { const d = await response.json(); detail = typeof d.detail === 'string' ? d.detail : detail; } catch {}
    throw new Error(detail);
  }
  return response.json();
}
function researchTeacher() { return ['teacher','admin'].includes(S.user?.role); }
function researchError(el, error) { if (el) el.textContent = error.message || String(error); }
function researchSourceButton(page) {
  return `<button class="btn bsm" type="button" onclick="researchPage(${Number(page)})">Xem SGK trang ${Number(page)}</button>`;
}
async function researchPage(page) {
  try {
    const response = await fetch(`${API}/research/source-pages/${Number(page)}`, {headers:authHeaders()});
    if (!response.ok) throw new Error('Không mở được trang SGK. Kiểm tra quyền và trạng thái duyệt nguồn.');
    const url = URL.createObjectURL(await response.blob());
    const dialog = document.createElement('dialog');
    dialog.style.cssText = 'position:fixed;inset:3vh 0 auto;margin:0 auto;width:min(900px,96vw);max-height:94vh;overflow:auto;border:0;border-radius:16px;padding:16px';
    dialog.innerHTML = `<button class="btn" type="button">Đóng trang nguồn</button><img alt="SGK trang ${page}" style="width:100%;display:block;margin-top:12px">`;
    dialog.querySelector('img').src = url;
    dialog.querySelector('button').style.cssText = 'position:sticky;top:0;z-index:1';
    dialog.querySelector('button').onclick = () => dialog.close();
    dialog.onclose = () => { URL.revokeObjectURL(url); dialog.remove(); };
    document.body.append(dialog); dialog.showModal();
  } catch (error) { tst(error.message, 'err'); }
}
async function rsgk(m) {
  m.innerHTML = '<div class="research-page"><p id="sgk-status" role="status">Đang tải học liệu…</p></div>';
  try {
    const [status, lessons] = await Promise.all([researchApi('/status'), researchApi('/lessons')]);
    if (S.pg !== 'sgk') return;
    m.innerHTML = `<div class="research-page"><div class="tb"><div><div class="eyebrow">Học liệu / Sách giáo khoa</div><h1 class="pt">Lịch sử 12</h1><p class="ps">Kết nối tri thức với cuộc sống. Đọc nguồn sách và luyện tập theo từng bài.</p></div></div>
      <div class="research-tabs"><span>Học liệu và luyện tập</span></div>
      <div class="research-layout"><aside class="card research-search"><h2>Chọn nội dung học</h2>
      <label for="sgk-lesson">Bài học</label><select class="fi" id="sgk-lesson"><option value="">Tất cả ${lessons.length} bài học</option>${lessons.map(l => `<option value="${l.id}">Bài ${l.id}: ${researchEscape(l.title)}</option>`).join('')}</select>
      <form id="sgk-search-form"><label for="sgk-query">Tìm sự kiện hoặc nội dung</label><input class="fi" id="sgk-query" minlength="3" maxlength="1000" required placeholder="Ví dụ: sự ra đời của Liên hợp quốc">
      <label for="sgk-mode">Cách tra cứu</label><select class="fi" id="sgk-mode"><option value="keyword">Theo từ khóa</option><option value="hybrid">Từ khóa và nội dung liên quan</option><option value="dense">Theo nội dung liên quan</option></select>
      <button class="btn bp" type="submit">Tra cứu SGK</button></form><p class="auth-hint">Kết quả chỉ sử dụng nguồn đã được giáo viên kiểm tra.</p></aside>
      <section><p id="sgk-status" class="research-status">${status.practice_questions} câu hỏi sẵn sàng · ${status.approved_chunks}/${status.chunks} đoạn nguồn đã được kiểm tra</p><div id="sgk-sources" aria-live="polite"></div>
      <h2 class="research-results-title">Câu hỏi luyện tập</h2><div id="sgk-practice" aria-live="polite"></div></section></div></div>`;
    $('sgk-lesson').onchange = researchPractice;
    $('sgk-search-form').onsubmit = async event => {
      event.preventDefault();
      const target = $('sgk-sources'); target.textContent = 'Đang tìm nguồn…';
      const params = new URLSearchParams({query:$('sgk-query').value, mode:$('sgk-mode').value});
      if ($('sgk-lesson').value) params.set('lesson_id', $('sgk-lesson').value);
      try {
        const data = await researchApi(`/search?${params}`);
        if (!target.isConnected) return;
        target.innerHTML = data.results.length ? '<h2 class="research-results-title">Nguồn đối chiếu</h2>' + data.results.map(({chunk:c}) =>
          `<article class="source-result"><p>${researchEscape(c.text)}</p><p class="source-meta">${researchEscape(c.source)}</p>${researchSourceButton(c.book_page)}</article>`).join('') : '<div class="research-results-empty" style="margin-bottom:20px"><h3>Chưa tìm thấy nguồn phù hợp</h3><p>Thử từ khóa khác hoặc chọn một bài học cụ thể. Những đoạn chưa duyệt chưa được đưa vào kết quả.</p></div>';
      } catch (error) { researchError(target, error); }
    };
    await researchPractice();
  } catch (error) { researchError($('sgk-status'), error); }
}
async function researchPractice() {
  const target = $('sgk-practice'); if (!target) return;
  target.textContent = 'Đang tải câu hỏi…';
  try {
    const lesson = $('sgk-lesson').value;
    const data = await researchApi(`/practice${lesson ? '?lesson_id='+lesson : ''}`);
    if (!target.isConnected) return;
    target.replaceChildren();
    if (!data.questions.length) {
      target.innerHTML = `<div class="research-results-empty"><div class="eyebrow">Đang kiểm tra học liệu</div><h3>Câu hỏi sẽ được mở sau khi duyệt</h3><p>Giáo viên đang đối chiếu nguồn và kiểm tra nội dung cho bài học này. Bạn có thể làm bài từ các đề đã tải trong thời gian chờ.</p><button class="bo" style="margin-top:18px" onclick="nv('${researchTeacher()?'research-review':'quiz-start'}')">${researchTeacher()?'Mở danh sách cần duyệt':'Chọn đề làm bài'}</button></div>`;
      return;
    }
    for (const q of data.questions) {
      const article = document.createElement('article'); article.className = 'card'; article.style.marginBottom = '16px';
      const form = document.createElement('form');
      form.innerHTML = `<p style="font-weight:700;margin-bottom:14px">${researchEscape(q.stem)}</p>` +
        (q.question_type === 'multiple_choice' ? Object.entries(q.choices).map(([key,value]) =>
          `<label style="display:block;padding:10px"><input type="radio" name="answer" value="${key}" required> ${key}. ${researchEscape(value)}</label>`).join('') :
          '<label>Câu trả lời của bạn<textarea class="fi" name="answer" style="padding:10px" required maxlength="6000"></textarea></label>') +
        '<button class="btn bp" style="margin-top:12px" type="submit">Đối chiếu đáp án</button><div role="status" style="margin-top:14px"></div>';
      form.onsubmit = async event => {
        event.preventDefault(); const button = form.querySelector('button'), result = form.querySelector('[role="status"]');
        button.disabled = true;
        try {
          const d = await researchApi(`/practice/${encodeURIComponent(q.id)}/answer`, {method:'POST',body:JSON.stringify({answer:new FormData(form).get('answer')})});
          result.innerHTML = `<strong>${d.correct === null ? 'Tự luận cần giáo viên chấm' : d.correct ? 'Đúng' : 'Chưa đúng'}</strong><p>Đáp án: ${researchEscape(d.correct_answer)}</p><p>${researchEscape(d.explanation)}</p><blockquote style="margin:12px 0">${researchEscape(d.quote)}</blockquote>${researchSourceButton(d.book_page)}`;
        } catch (error) { researchError(result, error); } finally { button.disabled = false; }
      };
      article.append(form); target.append(article);
    }
  } catch (error) { researchError(target, error); }
}
let researchReviewRows = [], researchReviewChunks = new Map();
async function rresearchReview(m) {
  if (!researchTeacher()) { m.textContent = 'Cần quyền giáo viên để duyệt học liệu.'; return; }
  m.innerHTML = `<div class="research-page"><div class="tb"><div><div class="eyebrow">Giáo viên / Kiểm tra nội dung</div><h1 class="pt">Duyệt học liệu</h1><p class="ps">Đối chiếu nguồn sách, chỉnh nội dung và lưu quyết định cho từng mục.</p></div></div>
    <div class="review-controls"><div><label for="review-kind">Nội dung cần kiểm tra</label><select class="fi" id="review-kind"><option value="chunks">Nguồn sách giáo khoa</option><option value="questions">Câu hỏi ôn tập</option><option value="gold">Truy vấn và nguồn đối chiếu</option></select></div>
    <div><label for="review-row">Chọn mục cần duyệt</label><select class="fi" id="review-row"></select></div></div><div id="review-progress"></div><section class="card review-card"><div id="review-editor"></div></section></div>`;
  $('review-kind').onchange = researchLoadReview; $('review-row').onchange = researchEditReview;
  await researchLoadReview();
}
function researchRowLabel(row,kind) {
  const ordinal=researchReviewRows.findIndex(r=>r.id===row.id)+1;
  return kind === 'chunks' ? `Đoạn ${ordinal} · Bài ${row.lesson_id} · Trang ${row.book_page}` : `${kind==='questions'?'Câu':'Truy vấn'} ${row.id} · Bài ${row.lesson_id}`;
}
function researchProgress() {
  const target=$('review-progress'); if (!target) return;
  const approved=researchReviewRows.filter(r=>r.review_status==='teacher_approved').length;
  const pending=researchReviewRows.filter(r=>r.review_status==='review_required').length;
  const total=researchReviewRows.length;
  target.innerHTML=`<div class="review-progress"><strong>${approved}/${total} đã duyệt</strong><div class="track" aria-hidden="true"><span style="width:${total?approved/total*100:0}%"></span></div><span>${pending} chờ kiểm tra</span></div>`;
}
async function researchLoadReview() {
  const editor = $('review-editor'); editor.textContent = 'Đang tải…';
  try {
    const kind = $('review-kind').value;
    const [data, sources] = await Promise.all([researchApi(`/reviews/${kind}`), researchApi('/reviews/chunks')]);
    if (!editor.isConnected || $('review-kind').value !== kind) return;
    researchReviewRows = data.rows; researchReviewChunks = new Map(sources.rows.map(c => [c.id,c]));
    $('review-row').innerHTML = data.rows.map((r,i) => `<option value="${i}">${researchEscape(researchRowLabel(r,kind))} · ${r.review_status === 'teacher_approved' ? 'Đã duyệt' : r.review_status === 'rejected' ? 'Loại' : 'Chờ duyệt'}</option>`).join('');
    researchProgress(); researchEditReview();
  } catch (error) { researchError(editor, error); }
}
function researchEditReview() {
  const kind = $('review-kind').value, row = researchReviewRows[Number($('review-row').value)], editor = $('review-editor');
  if (!row) { editor.textContent = 'Danh sách trống.'; return; }
  const field = (label,id,value) => `<label style="display:block;margin:12px 0">${label}<textarea class="fi" style="padding:10px;min-height:80px" id="${id}">${researchEscape(value)}</textarea></label>`;
  let html = `<div class="eyebrow">${kind==='chunks'?'Đối chiếu nguồn':kind==='questions'?'Nội dung câu hỏi':'Xác nhận nguồn trả lời'}</div><h2 style="font-size:19px;margin:0 0 22px">${researchEscape(researchRowLabel(row,kind))}</h2>`;
  if (kind === 'chunks') html += field('Nội dung trích từ sách giáo khoa','review-source',row.text) + researchSourceButton(row.book_page);
  if (kind === 'questions') {
    const q = row.question;
    html += '<div class="review-question-layout"><section>' + field('Câu hỏi','review-stem',q.stem);
    if (q.question_type === 'multiple_choice') {
      html += '<div class="review-choice-grid">';
      for (const key of Object.keys(q.choices)) html += field(`Phương án ${key}`,`review-choice-${key}`,q.choices[key]);
      html += '</div><label class="review-answer-label" for="review-answer">Đáp án đúng</label><select class="fi" id="review-answer">' + Object.keys(q.choices).map(key => `<option value="${key}" ${key===q.correct_answer?'selected':''}>${key}</option>`).join('') + '</select>';
    } else html += field('Đáp án mẫu','review-answer',q.correct_answer);
    html += field('Lời giải / hướng dẫn chấm','review-explanation',q.explanation) + '</section><aside class="review-source-aside">';
    html += `<div class="source-note"><div class="eyebrow">Nguồn sách đối chiếu</div><p>${researchEscape(row.quote)}</p><div style="margin-top:12px">${researchSourceButton(row.book_page)}</div></div><p class="source-state">Kiểm tra nguồn trước khi duyệt câu hỏi.</p>`;
    for (const id of row.chunk_ids) html += `<p class="source-state">SGK trang ${researchReviewChunks.get(id)?.book_page || row.book_page}: ${researchReviewChunks.get(id)?.review_status === 'teacher_approved' ? 'Đã duyệt' : 'Chưa duyệt'}</p>`;
    html += '</aside></div>';
  }
  if (kind === 'gold') {
    html += `<p style="font-weight:700">${researchEscape(row.query)}</p><p style="margin:10px 0">Chọn đoạn thực sự đủ trả lời; duyệt đoạn nguồn trước khi lưu xác nhận.</p>`;
    const selected = JSON.parse(row.relevant_chunk_ids);
    for (const [letter,id] of Object.entries(JSON.parse(row.candidate_chunk_ids))) {
      const c = researchReviewChunks.get(id);
      html += `<div class="review-candidate"><label><input type="checkbox" name="review-gold" value="${researchEscape(id)}" ${selected.includes(id)?'checked':''}> ${letter}. ${researchEscape(c?.text || id)}</label>${researchSourceButton(c?.book_page)}<p>${c?.review_status === 'teacher_approved' ? 'Nguồn đã duyệt' : 'Nguồn chưa duyệt'}</p></div>`;
    }
  }
  html += field('Ghi chú nhận xét','review-notes','') + '<div class="review-actions"><button class="btn bp" onclick="researchSaveReview(\'teacher_approved\')">Duyệt và lưu</button><button class="btn reject" onclick="researchSaveReview(\'rejected\')">Không sử dụng</button><button class="btn" onclick="researchSaveReview(\'review_required\')">Lưu bản nháp</button></div><p role="status" id="review-message" style="margin-top:14px"></p>';
  editor.innerHTML = html;
}
async function researchSaveReview(decision) {
  const kind = $('review-kind').value, index = Number($('review-row').value), row = researchReviewRows[index];
  const editor = $('review-editor');
  const body = {decision, expected_hash:row.revision_hash, notes:$('review-notes').value};
  if (kind === 'chunks') body.source_text = $('review-source').value;
  if (kind === 'questions' && decision !== 'rejected') body.question = {...row.question, stem:$('review-stem').value,
    correct_answer:$('review-answer').value, explanation:$('review-explanation').value,
    choices:Object.fromEntries(Object.keys(row.question.choices).map(k => [k,$(`review-choice-${k}`).value]))};
  if (kind === 'gold') body.relevant_chunk_ids = [...document.querySelectorAll('input[name="review-gold"]:checked')].map(el => el.value);
  const buttons = [...editor.querySelectorAll('button'), $('review-kind'), $('review-row')]; buttons.forEach(b => b.disabled = true);
  try {
    const updated = await researchApi(`/reviews/${kind}/${encodeURIComponent(row.id)}`, {method:'POST', body:JSON.stringify(body)});
    if (!editor.isConnected) return;
    researchReviewRows[index] = updated;
    $('review-message').textContent = 'Đã lưu nội dung và quyết định của bạn.';
    $('review-row').selectedOptions[0].textContent = `${researchRowLabel(row,kind)} · ${decision === 'teacher_approved' ? 'Đã duyệt' : decision === 'rejected' ? 'Loại' : 'Chờ duyệt'}`;
    researchProgress();
  } catch (error) { researchError($('review-message'), error); } finally { buttons.forEach(b => b.disabled = false); }
}
