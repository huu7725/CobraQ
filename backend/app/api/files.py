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
