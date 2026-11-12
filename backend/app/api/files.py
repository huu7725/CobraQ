from ..core.storage import question_path
from ..core.config import data_path
from fastapi import APIRouter, HTTPException, Header, Depends, UploadFile, File
from pydantic import BaseModel, Field, model_validator
import json, random, re, base64, io, traceback, sys

from datetime import datetime
from pathlib import Path
from typing import Optional

from ..core.security import get_current_user_optional, Role
from ..core.audit import audit_log, EventType
from ..services.evaluation import EvaluationEntry, evaluation_logger
from ..services.document_store import storage_write_lock

router = APIRouter(prefix="/files", tags=["files"])


def resolve_uid(current_user, x_user_id: str):
    """Teacher/Admin có thể truy cập file của mọi user."""
    if current_user and current_user.get("role") in (Role.TEACHER.value, Role.ADMIN.value):
        return current_user.get("sub")  # Teacher/admin dùng user_id của mình
    return (current_user.get("sub") if current_user else None) or x_user_id


def _resolve_file_uid(current_user, x_user_id: str, x_file_for: str = ""):
    """Resolve which user's files to access. Teacher/Admin can access any user's files."""
    is_privileged = current_user and current_user.get("role") in (Role.TEACHER.value, Role.ADMIN.value)
    if is_privileged and x_file_for:
        return x_file_for
    if is_privileged:
        return current_user.get("sub")
    return (current_user.get("sub") if current_user else None) or x_user_id


def user_dir(uid):
    d = data_path("users") / re.sub(r'[^\w]', '_', uid or "guest")
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_json(path, default):
    try:
        if Path(path).exists():
            with open(path, encoding="utf-8") as f:
                return json.load(f)
    except:
        pass
    return default


def save_json(path, data):
    from ..services.document_store import atomic_json
    atomic_json(Path(path),data)


def files_index_path(uid): return user_dir(uid) / "files_index.json"


# Compatibility helpers use the same extraction engine as background ingestion.
def parse_pdf(content: bytes) -> list:
    from ..services.document_extraction import extract_document
    return extract_document(content,'document.pdf')['questions']


def parse_word(content: bytes) -> list:
    from ..services.document_extraction import extract_document
    return extract_document(content,'document.docx')['questions']


def smart_parse(content: bytes, filename: str, api_key: str = '', force_ai: bool = False) -> dict:
    from ..services.document_extraction import extract_document
    result=extract_document(content,filename)
    summary=result['summary']
    return {'questions':result['questions'],'method':'local_ocr' if summary['ocr_pages'] else 'local_text',
            'total':summary['questions'],'has_ans':summary['with_answer'],
            'ans_rate':round(summary['with_answer']/summary['questions']*100) if summary['questions'] else 0,
            'ai_available':False,'error':'','extraction':result}


def parse_with_vision_ai(content: bytes, filetype: str, api_key: str) -> list:
    from ..core.config import get_settings
    if not get_settings().external_ai_enabled:
        raise HTTPException(503, "AI bên ngoài đã tắt trong môi trường này")
    try:
        import anthropic
        from pdf2image import convert_from_bytes
    except ImportError:
        raise HTTPException(500, "Cần: pip install anthropic pdf2image")

    client = anthropic.Anthropic(api_key=api_key)
    if filetype != "pdf":
        return parse_word(content)

    try:
        images = convert_from_bytes(content, dpi=150)
    except Exception as e:
        raise HTTPException(500, f"Lỗi convert PDF→ảnh: {e}")

    VISION_PROMPT = """Đây là ảnh trang đề thi trắc nghiệm tiếng Việt.
Đáp án ĐÚNG = ô được TÔ MÀU (cyan, xanh, vàng, hồng...).
Nếu là bảng (TT | Nội dung | Đáp án A | B | C | D): cột tô màu = đáp án đúng.
Trả về JSON THUẦN TÚY không có markdown:
[{"id":1,"question":"...","choices":[{"label":"A","text":"..."},{"label":"B","text":"..."},{"label":"C","text":"..."},{"label":"D","text":"..."}],"answer":"A"}]
answer="" nếu không xác định."""

    all_qs = []
    for i, img in enumerate(images):
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=90)
        img_b64 = base64.b64encode(buf.getvalue()).decode()
        try:
            resp = client.messages.create(
                model="claude-opus-4-5", max_tokens=4096,
                messages=[{"role": "user", "content": [
                    {"type": "image", "source": {
                        "type": "base64", "media_type": "image/jpeg", "data": img_b64}},
                    {"type": "text", "text": VISION_PROMPT}
                ]}]
            )
            raw = resp.content[0].text.strip()
            m = re.search(r'\[.*\]', raw, re.DOTALL)
            if m:
                page_qs = json.loads(m.group())
                for q in page_qs:
                    q["id"] = len(all_qs) + page_qs.index(q) + 1
                all_qs.extend(page_qs)
        except Exception as e:
            print(f"Vision AI p{i+1}: {e}")
    return all_qs


# ── ENDPOINTS ──

@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    x_user_id: str = Header(default="guest"),
    x_force_ai: str = Header(default="false"),
    x_file_for: str = Header(default=""),
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    # Teacher/Admin có thể upload cho user khác
    is_privileged = current_user and current_user.get("role") in (Role.TEACHER.value, Role.ADMIN.value)
    uid = (current_user.get("sub") if current_user else None) or x_user_id
    if is_privileged and x_file_for:
        uid = x_file_for
    elif is_privileged:
        uid = current_user.get("sub")
    from ..core.config import get_settings
    cfg = get_settings()
    content = await file.read(cfg.max_upload_bytes + 1)
    if len(content) > cfg.max_upload_bytes:
        raise HTTPException(413, "Tệp vượt giới hạn dung lượng cho phép")
    fname = file.filename or "file"

    if not (fname.lower().endswith(".docx") or fname.lower().endswith(".pdf")):
        raise HTTPException(400, "Chỉ hỗ trợ .docx và .pdf")

    force_ai = x_force_ai.lower() == "true"
    from ..core.config import get_settings
    cfg = get_settings()
    ai_key = cfg.anthropic_api_key if cfg.cloud_ai_available else ""
    if force_ai and not cfg.cloud_ai_available:
        raise HTTPException(503, "AI bên ngoài chưa được bật hoặc cấu hình")

    from ..services.document_store import document_jobs
    from ..services.document_extraction import ExtractionError
    import asyncio
    try:
        row=document_jobs().submit(uid,content,fname)
    except ExtractionError as exc:
        raise HTTPException(429 if exc.code=='queue_full' else 422, {'code':exc.code,'message':str(exc)}) from exc
    deadline=asyncio.get_running_loop().time()+cfg.extraction_timeout+60
    while row['status'] in {'queued','processing'}:
        if asyncio.get_running_loop().time()>deadline:
            raise HTTPException(202, {'document_id':row['id'],'message':'Tài liệu vẫn đang xử lý. Theo dõi trong danh sách tài liệu.'})
        await asyncio.sleep(.1)
        row=document_jobs().store.status(uid,row['id'])
    if row['status'] not in {'completed','needs_review'}:
        raise HTTPException(422, {'code':row.get('error_code','interrupted'),'message':row['message'],'document_id':row['id']})
    summary=row['summary']
    return {'file_id':row['id'],'document_id':row['id'],'name':Path(row['filename']).stem,
            'parsed':summary['questions'],'added':0 if row.get('already_exists') else summary['questions'], 'total_in_file':summary['questions'],
            'with_answer':summary['with_answer'],'ans_rate':round(summary['with_answer']/summary['questions']*100) if summary['questions'] else 0,
            'parse_method':'local_ocr' if summary['ocr_pages'] else 'local_text','ai_available':False,
            'message':'Đã trích xuất tài liệu. Kiểm tra nội dung trước khi sử dụng.','for_user':uid,
            'summary':summary,'warnings':row.get('warnings',[])}



@router.get("/{file_id}")
def get_file(
    file_id: str,
    x_user_id: str = Header(default="guest"),
    x_file_for: str = Header(default=""),
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    uid = _resolve_file_uid(current_user, x_user_id, x_file_for)
    index = load_json(files_index_path(uid), {})
    if file_id not in index:
        raise HTTPException(404, "Không tìm thấy file")
    index[file_id]["for_user"] = uid
    return index[file_id]


@router.delete("/{file_id}")
@storage_write_lock
def delete_file(
    file_id: str,
    x_user_id: str = Header(default="guest"),
    x_file_for: str = Header(default=""),
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    uid = _resolve_file_uid(current_user, x_user_id, x_file_for)
    index = load_json(files_index_path(uid), {})
    if file_id not in index:
        raise HTTPException(404, "Không tìm thấy file")
    q_file = question_path(user_dir(uid), file_id)
    if q_file.exists():
        q_file.unlink()
    del index[file_id]
    save_json(files_index_path(uid), index)

    audit_log.log(EventType.FILE_DELETE, user_id=uid, resource=file_id,
                  details={"deleted_by": current_user.get("sub") if current_user else "guest"})

    return {"message": "Đã xóa"}


@router.get("/{file_id}/questions")
def get_file_questions(
    file_id: str,
    x_user_id: str = Header(default="guest"),
    x_file_for: str = Header(default=""),
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    uid = _resolve_file_uid(current_user, x_user_id, x_file_for)
    q_file = question_path(user_dir(uid), file_id)
    if not q_file.exists():
        raise HTTPException(404, "Không tìm thấy file")
    questions = load_json(q_file, [])
    return {"questions": questions, "total": len(questions), "for_user": uid}


class QuestionUpdateBody(BaseModel):
    question: str = Field(min_length=1,max_length=20000)
    choices: list[dict[str,str]] = Field(min_length=4,max_length=4)
    answer: str = Field(default='',max_length=1)

    @model_validator(mode='after')
    def check_question(self):
        from ..services.question_parser import norm
        if not self.question.strip():raise ValueError('Câu hỏi không được để trống')
        if len(self.choices)!=4 or {c.get('label') for c in self.choices if isinstance(c,dict)}!=set('ABCD'):
            raise ValueError('Cần bốn phương án A/B/C/D')
        values=[norm(c.get('text','')) for c in self.choices]
        if len(set(values))!=4 or any(not value for value in values):raise ValueError('Phương án phải có nội dung và khác nhau')
        if self.answer and self.answer not in set('ABCD'):raise ValueError('Đáp án phải là A/B/C/D hoặc để trống')
        return self


@router.put("/{file_id}/questions/{q_id}")
@storage_write_lock
def update_question(
    file_id: str, q_id: int, body: QuestionUpdateBody,
    x_user_id: str = Header(default="guest"),
    x_file_for: str = Header(default=""),
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    uid = _resolve_file_uid(current_user, x_user_id, x_file_for)
    q_file = question_path(user_dir(uid), file_id)
    if not q_file.exists():
        raise HTTPException(404, "Không tìm thấy file")
    questions = load_json(q_file, [])
    for i, q in enumerate(questions):
        if q.get("id") == q_id:
            questions[i]["question"] = body.question
            questions[i]["choices"] = body.choices
            questions[i]["answer"] = body.answer
            questions[i]['extraction_issues']=[] if body.answer else ['answer_not_found']
            questions[i]['answer_origin']='manual' if body.answer else ''
            save_json(q_file, questions)
            update_file_counts(uid,file_id,questions)
            audit_log.log(EventType.QUESTION_UPDATE, user_id=uid,
                          resource=file_id, details={
                              "q_id": q_id,
                              "updated_by": current_user.get("sub") if current_user else "guest",
                          })
            return {"message": "Đã cập nhật", "question": questions[i]}
    raise HTTPException(404, "Không tìm thấy câu hỏi")


@router.delete("/{file_id}/questions/{q_id}")
@storage_write_lock
def delete_question(
    file_id: str, q_id: int,
    x_user_id: str = Header(default="guest"),
    x_file_for: str = Header(default=""),
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    uid = _resolve_file_uid(current_user, x_user_id, x_file_for)
    q_file = question_path(user_dir(uid), file_id)
    if not q_file.exists():
        raise HTTPException(404, "Không tìm thấy file")
    questions = load_json(q_file, [])
    new_qs = [q for q in questions if q.get("id") != q_id]
    if len(new_qs) == len(questions):
        raise HTTPException(404, "Không tìm thấy câu hỏi")
    save_json(q_file, new_qs)
    update_file_counts(uid,file_id,new_qs)
    audit_log.log(EventType.QUESTION_DELETE, user_id=uid,
                  resource=file_id, details={
                      "q_id": q_id,
                      "deleted_by": current_user.get("sub") if current_user else "guest",
                  })
    return {"message": "Đã xóa câu hỏi"}


class NewQuestionBody(QuestionUpdateBody):
    pass


@router.post("/{file_id}/questions")
@storage_write_lock
def add_question(
    file_id: str, body: NewQuestionBody,
    x_user_id: str = Header(default="guest"),
    x_file_for: str = Header(default=""),
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    uid = _resolve_file_uid(current_user, x_user_id, x_file_for)
    q_file = question_path(user_dir(uid), file_id)
    if not q_file.exists():
        raise HTTPException(404, "Không tìm thấy file")
    questions = load_json(q_file, [])
    max_id = max((q.get("id", 0) for q in questions), default=0)
    new_q = {
        "id": max_id + 1, "question": body.question,
        "choices": body.choices, "answer": body.answer,
    }
    questions.append(new_q)
    save_json(q_file, questions)
    update_file_counts(uid,file_id,questions)
    audit_log.log(EventType.QUESTION_CREATE, user_id=uid,
                  resource=file_id, details={
                      "q_id": new_q["id"],
                      "added_by": current_user.get("sub") if current_user else "guest",
                  })
    return {"message": "Đã thêm câu hỏi", "question": new_q}


def update_file_counts(uid,file_id,questions):
    from ..services.document_store import LOCK
    with LOCK:
        index=load_json(files_index_path(uid),{})
        if file_id in index:
            index[file_id].update(count=len(questions),with_answer=sum(q.get('answer') in 'ABCD' if q.get('answer') else False for q in questions))
            save_json(files_index_path(uid),index)


class AIFillBody(BaseModel):
    question: str
    choices: list = []  # [{label, text}] — user-typed partial choices (optional)
    file_name: str = ""
    difficulty: int = 2  # 1=Dễ, 2=TB, 3=Khó


@router.post("/ai/fill-answer")
def ai_fill_answer(
    body: AIFillBody,
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    """
    Gọi AI để sinh đáp án đúng + các lựa chọn nhiễu cho 1 câu hỏi.
    - Input: câu hỏi + (optional) một vài lựa chọn user đã gõ sẵn.
    - Output: {correct_answer, choices[4], explanation, source}
    """
    from ..core.config import get_settings

    if not (current_user or {}).get("sub"):
        raise HTTPException(401, "Vui lòng đăng nhập để dùng AI Fill")

    if not body.question or len(body.question.strip()) < 5:
        raise HTTPException(400, "Câu hỏi quá ngắn (cần ≥ 5 ký tự)")

    # Validate difficulty
    if body.difficulty not in (1, 2, 3):
        body.difficulty = 2

    # Normalize user-provided choices: filter non-empty, only keep text
    user_choices = []
    for c in (body.choices or []):
        if isinstance(c, dict):
            txt = (c.get("text") or "").strip()
            lbl = (c.get("label") or "").strip().upper()
            if txt:
                user_choices.append({"label": lbl or "", "text": txt})
        elif isinstance(c, str):
            txt = c.strip()
            if txt:
                user_choices.append({"label": "", "text": txt})
    # Keep only first 4 user choices (preserve labels if present)
    user_choices = user_choices[:4]

    diff_text = {1: "Dễ", 2: "Trung bình", 3: "Khó"}[body.difficulty]

    user_ctx = ""
    if user_choices:
        labels = "ABCDEFGH"[:len(user_choices)]
        ctx_lines = []
        for i, c in enumerate(user_choices):
            lbl = c.get("label") or labels[i]
            ctx_lines.append(f"- {lbl}: {c['text']}")
        user_ctx = "\n\nLỰA CHỌN NGƯỜI DÙNG ĐÃ NHẬP (giữ nguyên nếu hợp lý):\n" + "\n".join(ctx_lines)

    prompt = f"""Bạn là giáo viên Lịch sử Việt Nam chuyên nghiệp, có 15 năm kinh nghiệm.

NHIỆM VỤ: Sinh đáp án đúng + các lựa chọn nhiễu cho câu hỏi trắc nghiệm dưới đây.

CÂU HỎI: {body.question.strip()}
{f"FILE/NGỮ CẢNH: {body.file_name}" if body.file_name else ""}
ĐỘ KHÓ: {diff_text} (level {body.difficulty}/3)
{user_ctx}

QUY TẮC:
1. Trả về đúng 4 lựa chọn A/B/C/D, chỉ 1 đáp án đúng.
2. Nếu người dùng đã nhập sẵn lựa chọn → ƯU TIÊN GIỮ NGUYÊN nếu đúng. Chỉ thêm/sửa nếu cần để đủ 4 đáp án và đảm bảo chính xác.
3. Đáp án nhiễu phải hợp lý (kiểu người nhầm lẫn), không phải sai hoàn toàn vô lý.
4. Cung cấp giải thích ngắn (1-2 câu) tại sao đáp án đúng.
5. Tiếng Việt, ngắn gọn, chính xác.
6. Nếu câu hỏi mơ hồ/kiến thức chung → vẫn cố gắng trả lời, không từ chối.

FORMAT OUTPUT (JSON thuần, không markdown, không giải thích gì thêm):
{{
  "correct_answer": "A",
  "choices": [
    {{"label": "A", "text": "..."}},
    {{"label": "B", "text": "..."}},
    {{"label": "C", "text": "..."}},
    {{"label": "D", "text": "..."}}
  ],
  "explanation": "..."
}}"""

    settings = get_settings()
    if not settings.external_ai_enabled:
        raise HTTPException(503,"AI ben ngoai da tat trong moi truong nay")
    ai_error = None
    result = None
    ai_model = "fallback"
    latency_ms = 0

    # Resolve API key: Grok preferred, then AI_API_KEY, then legacy Anthropic
    api_key = settings.grok_api_key or settings.ai_api_key or settings.anthropic_api_key
    if api_key and api_key not in ("YOUR_KEY_HERE", ""):
        try:
            from openai import OpenAI
            import time as _t
            base_url = getattr(settings, "ai_base_url", None) or "https://api.x.ai/v1"
            model = getattr(settings, "ai_model", None) or "grok-3-mini"
            client = OpenAI(api_key=api_key, base_url=base_url)
            t0 = _t.time()
            response = client.chat.completions.create(
                model=model,
                max_tokens=1024,
                temperature=0.5,
                messages=[
                    {"role": "system", "content": "Bạn là giáo viên Lịch sử Việt Nam. Luôn trả lời bằng JSON hợp lệ."},
                    {"role": "user", "content": prompt},
                ],
            )
            latency_ms = int((_t.time() - t0) * 1000)
            txt = response.content[0].text.strip()
            # Strip markdown code fences if any
            if txt.startswith("```"):
                lines = txt.split("\n")
                txt = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
                if txt.startswith("json"):
                    txt = txt[4:].strip()
            data = json.loads(txt)
            result = {
                "correct_answer": (data.get("correct_answer") or "A").upper()[:1],
                "choices": data.get("choices") or [],
                "explanation": data.get("explanation") or "",
            }
            ai_model = "claude-sonnet-4-20250514"
        except json.JSONDecodeError as e:
            ai_error = f"AI trả về JSON không hợp lệ: {e}"
        except Exception as e:
            ai_error = f"Lỗi gọi AI: {e}"

    # Fallback if AI fails or no key: build from user_choices + dummy distractors
    if not result:
        labels = ["A", "B", "C", "D"]
        choices = []
        for i, c in enumerate(user_choices[:4]):
            choices.append({"label": labels[i], "text": c["text"]})
        while len(choices) < 4:
            choices.append({"label": labels[len(choices)], "text": f"(Đáp án {labels[len(choices)]} - cần AI để điền)"})
        # Pick first non-empty as correct_answer
        correct = "A"
        result = {
            "correct_answer": correct,
            "choices": choices,
            "explanation": "AI chưa khả dụng — vui lòng tự chọn đáp án đúng.",
        }
        if not ai_error:
            ai_error = "Chưa cấu hình API key"

    # Validate: ensure 4 choices & correct_answer is in A-D
    chs = result.get("choices") or []
    if len(chs) < 4:
        labels = ["A", "B", "C", "D"]
        existing_labels = {c.get("label") for c in chs if c.get("label")}
        for i, lbl in enumerate(labels):
            if lbl not in existing_labels and len(chs) < 4:
                chs.append({"label": lbl, "text": f"(Đáp án {lbl})"})
    result["choices"] = chs[:4]
    corr = (result.get("correct_answer") or "A").upper()[:1]
    if corr not in "ABCD":
        corr = "A"
    result["correct_answer"] = corr

    return {
        "result": result,
        "ai_model": ai_model,
        "latency_ms": latency_ms,
        "ai_error": ai_error,
    }
