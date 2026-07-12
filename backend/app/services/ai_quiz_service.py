"""
AI Quiz Generation Service — generates high-quality multiple-choice quizzes
from historical events that a user has explored on the map.
"""
from typing import Optional
import json
import time
import uuid

from sqlalchemy.orm import Session
from app.core.config import get_settings


def generate_map_quiz(
    events: list,
    user_id: str,
    num_questions: int,
    difficulty: int = 2,
    time_limit_minutes: Optional[int] = 15,
    db: Session = None,
) -> dict:
    """
    Generate a map-based quiz using Claude Sonnet.
    Saves the session and questions to the database.

    Returns:
        dict with session_token, total_questions, questions[]
    """
    from app.models.map_quiz_session import MapQuizSession
    from app.models.map_quiz_question import MapQuizQuestion
    from app.models.historical_event import HistoricalEvent

    settings = get_settings()

    # Build rich context from events
    events_context = "\n\n".join([
        f"--- Sự kiện {i+1}: {e.title} ---\n"
        f"Thời gian: {e.year_range or 'Không rõ'}\n"
        f"Thời kỳ: {e.period or 'Không rõ'}\n"
        f"Khu vực: {e.region or 'Không rõ'}\n"
        f"Loại: {e.event_type or 'Không rõ'}\n"
        f"Nội dung: {e.full_content[:1500]}{'...' if len(e.full_content) > 1500 else ''}\n"
        for i, e in enumerate(events)
    ])

    difficulty_labels = {1: "Dễ", 2: "Trung bình", 3: "Khó"}
    diff_text = difficulty_labels.get(difficulty, "Trung bình")

    prompt = f"""Bạn là giáo viên Lịch sử Việt Nam chuyên nghiệp, có 15 năm kinh nghiệm giảng dạy.

NHIỆM VỤ: Sinh ra đúng {num_questions} câu hỏi trắc nghiệm đa lựa chọn (4 đáp án A/B/C/D) dựa trên các sự kiện lịch sử Việt Nam mà học sinh vừa tìm hiểu trên bản đồ.

QUY TẮC VÀNG:
1. Mỗi sự kiện phải có ít nhất 1 câu hỏi. Nếu có {num_questions} sự kiện trở lên, phân bổ đều.
2. Độ khó: {diff_text} (level {difficulty}/3)
   - Dễ (1): hỏi trực tiếp sự kiện, ngày tháng, nhân vật
   - Trung bình (2): hỏi nguyên nhân, ý nghĩa, so sánh
   - Khó (3): hỏi phân tích, đánh giá, liên hệ nhiều sự kiện
3. Mỗi câu có đúng 4 lựa chọn A/B/C/D, chỉ 1 đáp án đúng duy nhất
4. Đáp án nhiễu phải hợp lý, không phải thông tin sai hoàn toàn
5. Cung cấp giải thích ngắn (1-3 câu) cho mỗi đáp án đúng
6. Không được bịa đặt thông tin nằm ngoài ngữ liệu được cung cấp

CÁC SỰ KIỆN HỌC SINH ĐÃ TÌM HIỂU:
{events_context}

FORMAT OUTPUT — JSON thuần (không markdown code block, không giải thích gì thêm):
{{
  "questions": [
    {{
      "question_text": "Nội dung câu hỏi rõ ràng, ngắn gọn?",
      "choices": [
        {{"label": "A", "text": "Đáp án A"}},
        {{"label": "B", "text": "Đáp án B"}},
        {{"label": "C", "text": "Đáp án C"}},
        {{"label": "D", "text": "Đáp án D"}}
      ],
      "correct_answer": "B",
      "source_event_id": {events[0].id if events else 0},
      "explanation": "Giải thích tại sao đáp án B đúng...",
      "difficulty": {difficulty}
    }}
  ]
}}"""

    # Create DB session record first
    session_token = str(uuid.uuid4())
    session_record = MapQuizSession(
        user_id=user_id,
        session_token=session_token,
        source_type="map_events",
        num_questions_requested=num_questions,
        num_questions_generated=0,
        time_limit_minutes=time_limit_minutes,
        difficulty_level=difficulty,
        context_event_ids=json.dumps([e.id for e in events]),
    )
    db.add(session_record)
    db.commit()
    db.refresh(session_record)

    ai_error = None
    generated_questions = []
    ai_prompt_tokens = 0
    ai_completion_tokens = 0
    generation_time_ms = 0

    # Call Claude Sonnet
    if settings.anthropic_api_key and settings.anthropic_api_key != "YOUR_KEY_HERE":
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
            start_time = time.time()

            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                temperature=0.7,
                system="Bạn là giáo viên Lịch sử Việt Nam chuyên nghiệp. Luôn trả lời bằng JSON hợp lệ, đúng format.",
                messages=[{"role": "user", "content": prompt}]
            )

            generation_time_ms = int((time.time() - start_time) * 1000)
            response_text = response.content[0].text.strip()

            # Strip markdown code fences
            if response_text.startswith("```"):
                lines = response_text.split("\n")
                response_text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
                if response_text.startswith("json"):
                    response_text = response_text[4:].strip()

            ai_prompt_tokens = response.usage.input_tokens
            ai_completion_tokens = response.usage.output_tokens

            quiz_data = json.loads(response_text)
            generated_questions = quiz_data.get("questions", [])

        except json.JSONDecodeError as e:
            ai_error = f"AI trả về dữ liệu không hợp lệ: {str(e)}"
        except Exception as e:
            ai_error = f"Lỗi gọi AI: {str(e)}"
    else:
        ai_error = "Chưa cấu hình Anthropic API key"

    # Fallback: generate simple questions if AI fails
    if not generated_questions:
        generated_questions = _generate_fallback_questions(events, num_questions, difficulty)
        session_record.ai_model_used = "fallback"
    else:
        session_record.ai_model_used = "claude-sonnet-4-20250514"

    # Save questions to DB
    saved_questions = []
    for i, q_data in enumerate(generated_questions[:num_questions]):
        choices_json = json.dumps(q_data.get("choices", []), ensure_ascii=False)
        question = MapQuizQuestion(
            session_id=session_record.id,
            question_text=q_data.get("question_text", ""),
            question_type="multiple_choice",
            difficulty=q_data.get("difficulty", difficulty),
            choices=choices_json,
            correct_answer=q_data.get("correct_answer", "A"),
            explanation=q_data.get("explanation", ""),
            source_event_id=q_data.get("source_event_id") or (events[i % len(events)].id if events else None),
            question_order=i + 1,
        )
        db.add(question)
        saved_questions.append({
            "id": None,
            "question_text": q_data.get("question_text", ""),
            "choices": q_data.get("choices", []),
            "question_order": i + 1,
        })

    # Update session
    session_record.num_questions_generated = len(saved_questions)
    session_record.ai_prompt_tokens = ai_prompt_tokens
    session_record.ai_completion_tokens = ai_completion_tokens
    session_record.generation_time_ms = generation_time_ms
    db.commit()

    # Refresh to get real question IDs
    for saved_q in db.query(MapQuizQuestion).filter(
        MapQuizQuestion.session_id == session_record.id
    ).order_by(MapQuizQuestion.question_order).all():
        for q in generated_questions[:num_questions]:
            if q.get("question_text") == saved_q.question_text:
                q["id"] = saved_q.id
                break

    # Rebuild questions list for response (without correct answer)
    questions_response = []
    for i, q_data in enumerate(generated_questions[:num_questions]):
        import random
        choices = q_data.get("choices", [])
        shuffled = choices.copy()
        random.shuffle(shuffled)
        questions_response.append({
            "id": q_data.get("id") or (i + 1000),
            "question_text": q_data.get("question_text", ""),
            "choices": shuffled,
            "question_order": i + 1,
        })

    return {
        "session_token": session_token,
        "total": len(questions_response),
        "time_limit_minutes": time_limit_minutes,
        "difficulty": difficulty,
        "ai_model": session_record.ai_model_used,
        "generation_time_ms": generation_time_ms,
        "questions": questions_response,
        "ai_error": ai_error,
    }


def _generate_fallback_questions(events: list, num_questions: int, difficulty: int) -> list:
    """Fallback question generator when AI is unavailable."""
    questions = []
    for i, event in enumerate(events):
        if i >= num_questions:
            break

        q_num = i + 1
        difficulty_map = {
            1: f"{event.title} diễn ra vào năm nào?",
            2: f"Nguyên nhân chính của sự kiện {event.title} là gì?",
            3: f"Ý nghĩa lịch sử của {event.title} đối với Việt Nam là gì?",
        }

        questions.append({
            "question_text": difficulty_map.get(difficulty, difficulty_map[1]),
            "choices": [
                {"label": "A", "text": event.year_range or "Không rõ năm"},
                {"label": "B", "text": f"Năm {random_year(event.year_range)}" if event.year_range else "Năm 1919"},
                {"label": "C", "text": f"Thế kỷ {random_century(event.year_range)}" if event.year_range else "Thế kỷ 20"},
                {"label": "D", "text": "Không xác định được"},
            ],
            "correct_answer": "A",
            "source_event_id": event.id,
            "explanation": f"Sự kiện {event.title} {f'được ghi nhận vào {event.year_range}' if event.year_range else ''}.",
            "difficulty": difficulty,
        })

    # Pad with generic questions if needed
    while len(questions) < num_questions and events:
        questions.append({
            "question_text": f"Sự kiện nào sau đây thuộc thời kỳ {events[0].period or 'lịch sử Việt Nam'}?",
            "choices": [
                {"label": "A", "text": events[0].title},
                {"label": "B", "text": f"Sự kiện khác thời {events[0].period or 'lịch sử'}"},
                {"label": "C", "text": "Không có sự kiện nào phù hợp"},
                {"label": "D", "text": "Tất cả đều đúng"},
            ],
            "correct_answer": "A",
            "source_event_id": events[0].id,
            "explanation": f"{events[0].title} {f'thuộc thời kỳ {events[0].period}' if events[0].period else ''}.",
            "difficulty": difficulty,
        })

    return questions[:num_questions]


def random_year(year_range: str = None) -> str:
    """Extract or generate a plausible year from year_range."""
    if not year_range:
        import random
        return str(random.choice([1919, 1945, 1954, 1975, 1986]))
    import random
    nums = []
    for s in str(year_range).replace("-", " ").replace("/", " ").split():
        try:
            nums.append(int(s))
        except ValueError:
            continue
    if nums:
        return str(nums[0] + random.randint(-10, 10))
    return "1945"


def random_century(year_range: str = None) -> str:
    """Extract century from year_range."""
    if not year_range:
        return "20"
    nums = []
    for s in str(year_range).replace("-", " ").replace("/", " ").split():
        try:
            nums.append(int(s))
        except ValueError:
            continue
    if nums:
        return str((nums[0] - 1) // 100 + 1)
    return "20"
