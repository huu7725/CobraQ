"""
Map API — interactive Vietnam history map endpoints.
Provides historical event browsing, view tracking, and AI quiz generation.
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import json

from ..core.security import get_current_user_optional, get_current_user
from ..core.audit import audit_log, EventType
from ..db.database import get_db
from ..models.historical_event import HistoricalEvent
from ..models.user_map_progress import UserMapProgress
from ..models.map_quiz_session import MapQuizSession
from ..models.map_quiz_question import MapQuizQuestion
from ..models.map_quiz_answer import MapQuizAnswer
from ..models.quiz_history import QuizHistory
from ..services.ai_quiz_service import generate_map_quiz

router = APIRouter(prefix="/map", tags=["map"])


# ── Request/Response models ─────────────────────────────────────────────

class TrackViewBody(BaseModel):
    session_id: Optional[str] = None
    view_duration_seconds: int = 0
    scrolled_to_content: bool = False
    watched_video: bool = False


class GenerateQuizBody(BaseModel):
    event_ids: list[int]
    num_questions: int = 10
    time_limit_minutes: Optional[int] = 15
    difficulty: int = 2


class SubmitQuizBody(BaseModel):
    answers: dict  # {question_id: selected_choice}
    time_taken_seconds: int = 0


# ── Public endpoints ─────────────────────────────────────────────────────

@router.get("/events")
def get_events(
    event_type: Optional[str] = None,
    period: Optional[str] = None,
    region: Optional[str] = None,
    difficulty: Optional[int] = None,
    featured_only: bool = False,
    q: Optional[str] = None,  # search query
):
    """List all active historical events as map markers."""
    db = next(get_db())
    query = db.query(HistoricalEvent).filter(HistoricalEvent.is_active == True)

    if event_type:
        query = query.filter(HistoricalEvent.event_type == event_type)
    if period:
        query = query.filter(HistoricalEvent.period == period)
    if region:
        query = query.filter(HistoricalEvent.region == region)
    if difficulty:
        query = query.filter(HistoricalEvent.difficulty_level == difficulty)
    if featured_only:
        query = query.filter(HistoricalEvent.is_featured == True)
    if q:
        search = f"%{q}%"
        query = query.filter(
            (HistoricalEvent.title.ilike(search)) |
            (HistoricalEvent.short_description.ilike(search)) |
            (HistoricalEvent.period.ilike(search))
        )

    events = query.order_by(HistoricalEvent.year_range).all()
    return {"events": [e.to_marker_dict() for e in events]}


@router.get("/events/types")
def get_event_types():
    """Return all distinct event types and periods for filter UI."""
    db = next(get_db())
    types = db.query(HistoricalEvent.event_type).filter(
        HistoricalEvent.is_active == True
    ).distinct().all()
    periods = db.query(HistoricalEvent.period).filter(
        HistoricalEvent.is_active == True,
        HistoricalEvent.period.isnot(None)
    ).distinct().all()
    regions = db.query(HistoricalEvent.region).filter(
        HistoricalEvent.is_active == True,
        HistoricalEvent.region.isnot(None)
    ).distinct().all()
    return {
        "types": sorted(set(t[0] for t in types if t[0])),
        "periods": sorted(set(p[0] for p in periods if p[0])),
        "regions": sorted(set(r[0] for r in regions if r[0])),
    }


@router.get("/events/{slug}")
def get_event_detail(slug: str):
    """Get full detail of one historical event."""
    db = next(get_db())
    event = db.query(HistoricalEvent).filter(
        HistoricalEvent.slug == slug,
        HistoricalEvent.is_active == True
    ).first()
    if not event:
        raise HTTPException(404, "Sự kiện không tồn tại")
    return event.to_detail_dict()


# ── Authenticated endpoints ──────────────────────────────────────────────

@router.post("/events/{slug}/view")
def track_event_view(
    slug: str,
    body: TrackViewBody,
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    """Record that the user viewed an event detail page."""
    db = next(get_db())
    event = db.query(HistoricalEvent).filter(
        HistoricalEvent.slug == slug,
        HistoricalEvent.is_active == True
    ).first()
    if not event:
        raise HTTPException(404, "Sự kiện không tồn tại")

    uid = current_user.get("sub") if current_user else None

    if uid:
        # Resolve email -> user.id (numeric)
        from ..models.user import User
        user_row = db.query(User).filter(User.email == uid).first()
        if not user_row:
            raise HTTPException(401, "Người dùng không hợp lệ")
        db_uid = user_row.id

        # Upsert progress
        existing = db.query(UserMapProgress).filter(
            UserMapProgress.session_id == body.session_id,
            UserMapProgress.user_id == db_uid,
            UserMapProgress.event_id == event.id
        ).first()

        if not existing:
            progress = UserMapProgress(
                user_id=db_uid,
                event_id=event.id,
                session_id=body.session_id,
                view_duration_seconds=body.view_duration_seconds,
                scrolled_to_content=body.scrolled_to_content,
                watched_video=body.watched_video,
            )
            db.add(progress)
        else:
            existing.view_duration_seconds = max(
                existing.view_duration_seconds or 0, body.view_duration_seconds
            )
            existing.scrolled_to_content = existing.scrolled_to_content or body.scrolled_to_content
            existing.watched_video = existing.watched_video or body.watched_video
            existing.viewed_at = datetime.now()

        db.commit()

        audit_log.log(
            EventType.VIEW_EVENT,
            user_id=uid,
            role=current_user.get("role", "guest") if current_user else "guest",
            details={"event_id": event.id, "event_title": event.title, "slug": slug}
        )

    return {"message": "Đã ghi nhận", "event_id": event.id, "title": event.title}


@router.get("/progress/me")
def get_my_progress(
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    """Get all events the current user has viewed."""
    uid = current_user.get("sub") if current_user else None
    if not uid:
        return {"viewed_events": [], "total": 0, "can_quiz": False}

    db = next(get_db())

    # Get user ID (email -> numeric id)
    from ..models.user import User
    user = db.query(User).filter(User.email == uid).first()

    if not user:
        return {"viewed_events": [], "total": 0, "can_quiz": False}

    progresses = db.query(
        UserMapProgress.event_id,
        UserMapProgress.viewed_at,
        HistoricalEvent.title,
        HistoricalEvent.slug,
        HistoricalEvent.year_range,
        HistoricalEvent.event_type,
    ).join(
        HistoricalEvent, UserMapProgress.event_id == HistoricalEvent.id
    ).filter(
        UserMapProgress.user_id == user.id
    ).order_by(UserMapProgress.viewed_at.desc()).all()

    viewed = [
        {
            "event_id": p.event_id,
            "title": p.title,
            "slug": p.slug,
            "year_range": p.year_range,
            "event_type": p.event_type,
            "viewed_at": str(p.viewed_at),
        }
        for p in progresses
    ]

    event_ids = [v["event_id"] for v in viewed]

    return {
        "viewed_events": viewed,
        "event_ids": event_ids,
        "total": len(event_ids),
        "can_quiz": len(event_ids) >= 2,
    }


@router.post("/quiz/generate")
def create_map_quiz(
    body: GenerateQuizBody,
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    """Generate an AI-powered quiz from viewed historical events."""
    if not current_user:
        raise HTTPException(401, "Vui lòng đăng nhập để sử dụng tính năng này")

    if len(body.event_ids) < 2:
        raise HTTPException(400, "Cần xem ít nhất 2 sự kiện trước khi tạo quiz")
    if not (5 <= body.num_questions <= 50):
        raise HTTPException(400, "Số câu hỏi phải từ 5 đến 50")
    if body.difficulty not in (1, 2, 3):
        raise HTTPException(400, "Độ khó phải là 1 (Dễ), 2 (Trung bình), hoặc 3 (Khó)")

    db = next(get_db())

    # Resolve email -> user.id (numeric)
    from ..models.user import User
    user_row = db.query(User).filter(User.email == current_user["sub"]).first()
    if not user_row:
        raise HTTPException(401, "Người dùng không hợp lệ")

    events = db.query(HistoricalEvent).filter(
        HistoricalEvent.id.in_(body.event_ids),
        HistoricalEvent.is_active == True
    ).all()

    if not events:
        raise HTTPException(404, "Không tìm thấy sự kiện hợp lệ")

    # Generate quiz via AI service
    result = generate_map_quiz(
        events=events,
        user_id=user_row.id,
        num_questions=body.num_questions,
        difficulty=body.difficulty,
        time_limit_minutes=body.time_limit_minutes,
        db=db,
    )

    audit_log.log(
        EventType.QUIZ_START,
        user_id=current_user["sub"],
        role=current_user.get("role", "student"),
        details={
            "quiz_type": "map",
            "event_ids": body.event_ids,
            "num_questions": body.num_questions,
        }
    )

    return result


@router.get("/quiz/{session_token}")
def get_quiz(session_token: str):
    """Retrieve a quiz session with its questions (no answers)."""
    db = next(get_db())
    session = db.query(MapQuizSession).filter(
        MapQuizSession.session_token == session_token
    ).first()
    if not session:
        raise HTTPException(404, "Phiên quiz không tồn tại")

    questions = db.query(MapQuizQuestion).filter(
        MapQuizQuestion.session_id == session.id
    ).order_by(MapQuizQuestion.question_order).all()

    return {
        "session_token": session.session_token,
        "total": session.num_questions_generated,
        "time_limit_minutes": session.time_limit_minutes,
        "difficulty": session.difficulty_level,
        "questions": [
            {
                "id": q.id,
                "question_text": q.question_text,
                "question_type": q.question_type,
                "difficulty": q.difficulty,
                "choices": json.loads(q.choices),
                "question_order": q.question_order,
            }
            for q in questions
        ],
    }


@router.post("/quiz/{session_token}/submit")
def submit_map_quiz(
    session_token: str,
    body: SubmitQuizBody,
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    """Submit a map quiz and get results."""
    if not current_user:
        raise HTTPException(401, "Vui lòng đăng nhập")

    db = next(get_db())

    from ..models.user import User
    user = db.query(User).filter(User.email == current_user["sub"]).first()
    if not user:
        raise HTTPException(401, "Người dùng không hợp lệ")

    session = db.query(MapQuizSession).filter(
        MapQuizSession.session_token == session_token,
        MapQuizSession.user_id == user.id
    ).first()

    if not session:
        raise HTTPException(404, "Phiên quiz không tồn tại")

    if session.is_submitted:
        raise HTTPException(400, "Bạn đã nộp bài này rồi")

    questions = db.query(MapQuizQuestion).filter(
        MapQuizQuestion.session_id == session.id
    ).all()

    score = 0
    results = []

    for q in questions:
        user_ans = body.answers.get(str(q.id), "")
        is_correct = user_ans == q.correct_answer
        if is_correct:
            score += 1

        # Record answer
        answer = MapQuizAnswer(
            session_id=session.id,
            question_id=q.id,
            user_id=user.id,
            selected_choice=user_ans,
            is_correct=is_correct,
            time_spent_seconds=body.time_taken_seconds // len(questions) if questions else 0,
        )
        db.add(answer)

        results.append({
            "id": q.id,
            "question_text": q.question_text,
            "user_answer": user_ans,
            "correct_answer": q.correct_answer,
            "is_correct": is_correct,
            "choices": json.loads(q.choices),
            "explanation": q.explanation,
        })

    total = len(questions)
    percentage = round(score / total * 100, 1) if total > 0 else 0

    # Update session
    session.score = score
    session.total_questions = total
    session.percentage = percentage
    session.completed_at = datetime.now()
    session.time_taken_seconds = body.time_taken_seconds
    session.is_submitted = True

    # Record in quiz history
    history = QuizHistory(
        user_id=user.id,
        quiz_type="map",
        quiz_session_id=session.id,
        score=score,
        total_questions=total,
        percentage=percentage,
        time_taken_seconds=body.time_taken_seconds,
        difficulty_level=session.difficulty_level,
        tags=session.context_event_ids[:200],
    )
    db.add(history)
    db.commit()

    audit_log.log(
        EventType.QUIZ_SUBMIT,
        user_id=current_user["sub"],
        role=current_user.get("role", "student"),
        details={
            "quiz_type": "map",
            "score": score,
            "total": total,
            "percentage": percentage,
        }
    )

    return {
        "score": score,
        "total": total,
        "percentage": percentage,
        "results": results,
    }
