from fastapi import APIRouter, Header, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
import json, time
from pathlib import Path

from ..core.security import get_current_user_optional
from ..core.audit import audit_log, EventType
from ..services.trust_layer import trust_layer, Chunk, _count_tokens
from ..services.evaluation import EvaluationEntry, evaluation_logger
from ..services.vector_service import vector_service
from ..core.config import get_settings

router = APIRouter(prefix="/tutoring", tags=["tutoring"])


# ── Config ─────────────────────────────────────────────────────────────────

MAX_CONTEXT_TOKENS = 6000   # Claude Haiku max context ~= 200k, use safe window
MAX_TOKENS_OUTPUT = 512     # Max tokens for AI response
RATE_LIMIT_PER_MIN = 20     # Max tutoring requests per minute per user
RATE_LIMIT_PER_HOUR = 100   # Max tutoring requests per hour per user


# ── Helpers ─────────────────────────────────────────────────────────────────

def files_index_path(uid):
    d = Path("data/users") / uid.replace("[^\w]", "_")
    return d / "files_index.json"


def load_json(path, default):
    try:
        if Path(path).exists():
            with open(path, encoding="utf-8") as f:
                return json.load(f)
    except:
        pass
    return default


def sanitize_output(text: str) -> str:
    """Sanitize AI output để chặn XSS/injection."""
    import bleach
    return bleach.clean(text, tags=[], strip=True)


# ── Rate limit helpers ──────────────────────────────────────────────────────

_rate_store: dict[str, list[float]] = {}


def check_rate_limit(user_id: str) -> tuple[bool, str]:
    """
    Simple in-memory rate limiter.
    Returns (allowed, reason_if_blocked).
    """
    now = time.time()
    minute_ago = now - 60
    hour_ago = now - 3600

    if user_id not in _rate_store:
        _rate_store[user_id] = []

    timestamps = [t for t in _rate_store[user_id] if t > minute_ago]
    hourly = [t for t in _rate_store[user_id] if t > hour_ago]
    _rate_store[user_id] = timestamps

    if len(timestamps) >= RATE_LIMIT_PER_MIN:
        return False, f"Quá nhiều yêu cầu. Vui lòng chờ {int(60 - (now - timestamps[0]))}s."
    if len(hourly) >= RATE_LIMIT_PER_HOUR:
        return False, "Đã đạt giới hạn 100 câu hỏi mỗi giờ. Vui lòng thử lại sau."
    return True, ""


# ── Claude API ──────────────────────────────────────────────────────────────

def call_claude_api(
    query: str,
    context: str,
    history: list[dict],
    api_key: str,
) -> tuple[str, Optional[str]]:
    """
    Gọi Claude API để generate tutoring response.
    Returns (response_text, error_message).
    """
    try:
        import anthropic
    except ImportError:
        return "", "Thư viện anthropic chưa được cài. Chạy: pip install anthropic"

    client = anthropic.Anthropic(api_key=api_key)

    system_prompt = f"""Bạn là gia sư AI của CobraQ — hệ thống ôn tập thông minh.

NGUYÊN TẮC:
1. Trả lời CHỈ dựa trên ngữ liệu được cung cấp trong context.
2. Nếu câu hỏi nằm ngoài ngữ liệu, nói rõ: "Câu hỏi này không có trong ngữ liệu được cung cấp."
3. Trả lời bằng tiếng Việt, rõ ràng, có trích dẫn nguồn.
4. Nếu cần, giải thích thêm để học sinh hiểu bản chất.
5. KHÔNG bịa đặt thông tin không có trong context.

FORMAT TRẢ LỜI:
Trả lời ngắn gọn (2-5 câu), sau đó nếu có nhiều nguồn thì liệt kê.
"""

    user_messages = []
    for h in history[-6:]:
        role = "user" if h.get("role") == "user" else "assistant"
        user_messages.append({
            "role": role,
            "content": h.get("content", ""),
        })

    user_messages.append({
        "role": "user",
        "content": f"Ngữ liệu:\n{context}\n\nCâu hỏi: {query}",
    })

    try:
        resp = client.messages.create(
            model="claude-haiku-4-20250514",
            max_tokens=MAX_TOKENS_OUTPUT,
            system=system_prompt,
            messages=user_messages,
        )
        text = resp.content[0].text.strip()
        return text, None
    except Exception as e:
        err = str(e)
        if "overloaded" in err.lower():
            return "", "Dịch vụ AI đang quá tải. Vui lòng thử lại sau."
        return "", f"Lỗi AI: {err[:100]}"


# ── Request/Response models ─────────────────────────────────────────────────

class TutoringChatBody(BaseModel):
    message: str
    file_id: str = ""
    session_id: str = ""
    history: list = []


class ChatMessage(BaseModel):
    role: str
    content: str


# ── Chat endpoint ────────────────────────────────────────────────────────────

@router.post("/chat")
def tutoring_chat(
    request: Request,
    body: TutoringChatBody,
    x_user_id: str = Header(default="guest"),
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    uid = (current_user.get("sub") if current_user else None) or x_user_id
    user_id = uid
    role = current_user.get("role", "student") if current_user else "guest"

    # Rate limit
    allowed, reason = check_rate_limit(user_id)
    if not allowed:
        raise HTTPException(429, reason)
    _rate_store.setdefault(user_id, []).append(time.time())

    # Sanitize input
    query = sanitize_output(body.message)
    if not query.strip():
        raise HTTPException(400, "Tin nhắn không được trống")
    if len(query) > 1000:
        raise HTTPException(400, "Câu hỏi quá dài (tối đa 1000 ký tự)")

    # Load & store chunks
    chunks: list[Chunk] = []
    if body.file_id:
        q_file = Path("data/users") / uid.replace("[^\w]", "_") / f"{body.file_id}.json"
        if q_file.exists():
            questions = load_json(q_file, [])
            chunks = []
            for i, q in enumerate(questions):
                text = q.get("question", "")
                if q.get("answer"):
                    text += f" | Đáp án: {q['answer']}"
                chunks.append(Chunk(
                    id=f"chunk_{i+1}",
                    text=text,
                    source=body.file_id,
                    page=0,
                    score=0.8,
                ))
            trust_layer.store_chunks(body.file_id, chunks)
            vector_service.upsert_chunks(body.file_id, chunks)

    # Retrieve relevant chunks (vector or keyword)
    retrieved = vector_service.search(query, doc_id=body.file_id or None, top_k=5)

    # Update scores from vector service
    for i, chunk in enumerate(retrieved):
        if chunk.score == 0.0 and i > 0:
            chunk.score = max(0.3, 1.0 - i * 0.15)

    # Trust layer check
    blocked, block_reason = trust_layer.should_block(retrieved, "")

    # Build response
    if blocked:
        response_text = f"Không tìm thấy thông tin liên quan trong ngữ liệu. {block_reason}"
    else:
        context = trust_layer.build_context(
            retrieved,
            max_tokens=MAX_CONTEXT_TOKENS,
        )
        context_tokens = _count_tokens(context)

        # Call Claude API
        cfg = get_settings()
        if cfg.anthropic_api_key and cfg.anthropic_api_key != "YOUR_KEY_HERE":
            response_text, ai_error = call_claude_api(
                query=query,
                context=context,
                history=body.history,
                api_key=cfg.anthropic_api_key,
            )
            if ai_error:
                response_text = f"Không thể gọi AI: {ai_error}"
            elif not response_text:
                response_text = _fallback_response(query, retrieved)
        else:
            response_text = _fallback_response(query, retrieved)

    response_text = sanitize_output(response_text)

    # Hallucination evaluation
    hall_result = trust_layer.evaluate(response_text, retrieved)

    # Log evaluation
    entry = EvaluationEntry(
        session_id=body.session_id or f"tut_{uid}_{len(body.history)}",
        timestamp="",
        user_id=user_id,
        role=role,
        event_type="tutoring_query",
        query=query,
        response=response_text,
        ai_used=True,
        retrieval_chunks=[c.id for c in retrieved],
        hallucination_detected=hall_result["blocked"],
        citation_present=len(retrieved) > 0,
        hallucination_rate=hall_result.get("hallucination_rate", 0.0),
    )
    evaluation_logger.log(entry)
    audit_log.log(
        EventType.TUTORING_QUERY,
        user_id=user_id,
        role=role,
        details={
            "query": query[:80],
            "blocked": hall_result["blocked"],
            "chunks_used": len(retrieved),
            "context_tokens": _count_tokens(context) if not hall_result["blocked"] else 0,
        },
    )

    return {
        "message": response_text,
        "blocked": hall_result["blocked"],
        "block_reason": hall_result["block_reason"] if hall_result["blocked"] else "",
        "citations": [
            {
                "text": c.text[:200],
                "chunk_id": c.id,
                "source": c.source,
                "page": c.page,
                "score": c.score,
            }
            for c in retrieved
        ],
        "session_id": entry.session_id,
        "hallucination_rate": hall_result.get("hallucination_rate", 0.0),
    }


def _fallback_response(query: str, chunks: list[Chunk]) -> str:
    """Fallback response when no Claude API key configured."""
    if not chunks:
        return ("Tôi không tìm thấy thông tin nào liên quan đến câu hỏi của bạn "
                "trong ngữ liệu. Hãy thử hỏi theo cách khác hoặc kiểm tra lại ngữ liệu.")

    top = chunks[0]
    answer = f"Dựa trên ngữ liệu, câu hỏi của bạn liên quan đến:\n\n"
    answer += f'"{top.text[:300]}{"..." if len(top.text) > 300 else ""}"\n\n'
    answer += f"📄 Nguồn: {top.source}\n\n"
    answer += "Để được giải thích chi tiết hơn, hãy cài đặt Claude API key trong cấu hình hệ thống."
    return answer


# ── Feedback ────────────────────────────────────────────────────────────────

class TutoringFeedbackBody(BaseModel):
    helpful: bool
    session_id: str
    query: str


@router.post("/feedback")
def tutoring_feedback(
    body: TutoringFeedbackBody,
    x_user_id: str = Header(default="guest"),
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    uid = (current_user.get("sub") if current_user else None) or x_user_id
    audit_log.log(
        EventType.TUTORING_QUERY,
        user_id=uid,
        role=current_user.get("role", "guest") if current_user else "guest",
        details={
            "feedback": "helpful" if body.helpful else "not_helpful",
            "session_id": body.session_id,
        },
    )
    return {"message": "Cảm ơn phản hồi của bạn!"}


# ── Status ─────────────────────────────────────────────────────────────────

@router.get("/status")
def tutoring_status():
    """Return tutoring service status including rate limits."""
    return {
        "rate_limit_per_min": RATE_LIMIT_PER_MIN,
        "rate_limit_per_hour": RATE_LIMIT_PER_HOUR,
        "max_context_tokens": MAX_CONTEXT_TOKENS,
        "max_output_tokens": MAX_TOKENS_OUTPUT,
        "vector_enabled": vector_service.is_vector_enabled,
        "vector_stats": vector_service.get_stats(),
    }
