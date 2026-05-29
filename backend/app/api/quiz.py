from fastapi import APIRouter, Header, Depends, HTTPException
from pydantic import BaseModel
import json, random, re
from pathlib import Path
from datetime import datetime
from typing import Optional

from ..core.security import get_current_user_optional, get_current_user
from ..db.group_store import group_store
from ..db.group_scores import group_scores

router = APIRouter(prefix="/quiz", tags=["quiz"])


def user_dir(uid):
    d = Path("data/users") / re.sub(r'[^\w]', '_', uid or "guest")
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
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def files_index_path(uid): return user_dir(uid) / "files_index.json"
def history_path(uid):     return user_dir(uid) / "history.json"


SESSIONS: dict = {}


@router.get("/start")
def start_quiz(
    num: int = 10,
    file_id: str = "",
    group_code: str = "",
    x_user_id: str = Header(default="guest"),
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    uid = (current_user.get("sub") if current_user else None) or x_user_id
    group_settings = None  # num_questions, time_limit from group assignment

    if file_id:
        # If this is a group quiz, find the file from the teacher's directory
        if group_code:
            group = group_store.get_group(group_code)
            if group:
                for f in group.get("files", []):
                    if f["file_id"] == file_id:
                        group_settings = f
                        break
                all_qs = load_json(user_dir(group["teacher_email"]) / f"{file_id}.json", [])
            else:
                all_qs = load_json(user_dir(uid) / f"{file_id}.json", [])
        else:
            all_qs = load_json(user_dir(uid) / f"{file_id}.json", [])
    else:
        index = load_json(files_index_path(uid), {})
        all_qs = []
        for fid in index:
            all_qs.extend(load_json(user_dir(uid) / f"{fid}.json", []))

    valid = [q for q in all_qs if len(q.get("choices", [])) >= 2]
    if not valid:
        raise HTTPException(status_code=404, detail="Không có câu hỏi")

    # Use group settings if available, otherwise use request params
    actual_num = group_settings.get("num_questions", num) if group_settings else num
    actual_limit = group_settings.get("time_limit", 0) if group_settings else 0

    selected = random.sample(valid, min(actual_num, len(valid)))
    sid = f"s{random.randint(100000, 999999)}"
    quiz = []
    for i, q in enumerate(selected):
        choices = q["choices"].copy()
        random.shuffle(choices)
        correct_text = next((c["text"] for c in q["choices"]
                             if c["label"] == q.get("answer", "")), None)
        new_correct = next((c["label"] for c in choices
                            if c["text"] == correct_text), "") if correct_text else ""
        quiz.append({
            "id": i, "question": q["question"],
            "choices": choices, "_correct": new_correct,
        })
    SESSIONS[sid] = quiz
    return {
        "session_id": sid, "total": len(quiz), "file_id": file_id,
        "questions": [{"id": q["id"], "question": q["question"],
                       "choices": q["choices"]} for q in quiz],
        "time_limit": actual_limit,
        "num_questions": actual_num,
    }


class SubmitBody(BaseModel):
    session_id: str
    answers: dict
    time_taken: int = 0
    file_id: str = ""
    group_code: Optional[str] = None


@router.post("/submit")
def submit_quiz(
    body: SubmitBody,
    x_user_id: str = Header(default="guest"),
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    uid = (current_user.get("sub") if current_user else None) or x_user_id
    quiz = SESSIONS.get(body.session_id)
    if not quiz:
        raise HTTPException(status_code=404, detail="Session không tồn tại")

    details = []
    for q in quiz:
        user_ans = body.answers.get(str(q["id"]), "")
        ok = bool(user_ans and user_ans == q["_correct"])
        details.append({
            "id": q["id"], "question": q["question"],
            "user": user_ans, "correct": q["_correct"],
            "ok": ok, "choices": q["choices"],
        })
    score = sum(1 for d in details if d["ok"])
    pct = round(score / len(quiz) * 100)
    history = load_json(history_path(uid), [])
    history.append({
        "id": len(history)+1,
        "date": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "score": score, "total": len(quiz), "percent": pct,
        "time_taken": body.time_taken, "file_id": body.file_id or "all",
        "wrong_questions": [d["question"][:60] for d in details if not d["ok"]][:5],
    })
    save_json(history_path(uid), history)

    # Save to group scores if this is a group quiz
    if body.group_code and body.file_id:
        group = group_store.get_group(body.group_code)
        if group and body.file_id in [f["file_id"] for f in group.get("files", [])]:
            group_scores.save_score(body.group_code, body.file_id, uid,
                current_user.get("name", uid.split("@")[0]) if current_user else uid,
                {
                    "score": score,
                    "percent": pct,
                    "time_taken": body.time_taken,
                    "answers": body.answers,
                    "total_questions": len(quiz),
                })

    del SESSIONS[body.session_id]
    return {"score": score, "total": len(quiz), "percent": pct, "details": details}
