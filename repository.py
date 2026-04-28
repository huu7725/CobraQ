"""Data access layer — MySQL backend for CobraQ."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt

from db import get_connection


def _hash_password(password: str) -> str:
    return bcrypt.hashpw((password or "").encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw((password or "").encode("utf-8"), (password_hash or "").encode("utf-8"))
    except Exception:
        return False


def ensure_user(uid: str, email: Optional[str] = None) -> None:
    uid = (uid or "").strip()
    if not uid:
        raise ValueError("uid không hợp lệ")
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO users (uid, email) VALUES (%s, %s) ON DUPLICATE KEY UPDATE email = COALESCE(%s, email)",
            (uid, email, email),
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()


def register_user(uid: str, email: str, password: str, role: str = "user") -> dict:
    uid = (uid or "").strip()
    email = (email or "").strip().lower()
    password = (password or "").strip()
    role = (role or "user").strip().lower()
    if not uid:
        raise ValueError("uid không hợp lệ")
    if not email:
        raise ValueError("email không hợp lệ")
    if len(password) < 6:
        raise ValueError("mật khẩu phải tối thiểu 6 ký tự")
    if role not in ("user", "admin"):
        role = "user"

    conn = get_connection()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT uid FROM users WHERE email = %s LIMIT 1", (email,))
        if cur.fetchone() is not None:
            raise ValueError("Email đã tồn tại")
        cur.execute(
            "INSERT INTO users (uid, email, password_hash, role) VALUES (%s, %s, %s, %s)",
            (uid, email, _hash_password(password), role),
        )
        conn.commit()
        return {
            "uid": uid,
            "email": email,
            "role": role,
            "display_name": None,
            "avatar_url": None,
        }
    finally:
        cur.close()
        conn.close()


def authenticate_user(email: str, password: str) -> Optional[dict]:
    email = (email or "").strip().lower()
    password = (password or "").strip()
    if not email or not password:
        return None

    conn = get_connection()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT uid, email, role, display_name, avatar_url, password_hash FROM users WHERE email = %s LIMIT 1",
            (email,),
        )
        row = cur.fetchone()
        if not row:
            return None
        if not _verify_password(password, row.get("password_hash") or ""):
            return None
        return {
            "uid": row["uid"],
            "email": row.get("email"),
            "role": row.get("role") or "user",
            "display_name": row.get("display_name"),
            "avatar_url": row.get("avatar_url"),
        }
    finally:
        cur.close()
        conn.close()


def get_user_by_uid(uid: str) -> Optional[dict]:
    uid = (uid or "").strip()
    if not uid:
        return None
    conn = get_connection()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT uid, email, role, display_name, avatar_url, created_at FROM users WHERE uid = %s LIMIT 1", (uid,))
        return cur.fetchone()
    finally:
        cur.close()
        conn.close()


def get_user_by_email(email: str) -> Optional[dict]:
    email = (email or "").strip().lower()
    if not email:
        return None
    conn = get_connection()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT uid, email, role, display_name, avatar_url, created_at FROM users WHERE email = %s LIMIT 1", (email,))
        return cur.fetchone()
    finally:
        cur.close()
        conn.close()


def list_users() -> list:
    conn = get_connection()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT uid, email, role, display_name, avatar_url, created_at FROM users ORDER BY created_at DESC")
        return cur.fetchall() or []
    finally:
        cur.close()
        conn.close()


def set_user_role(uid: str, role: str) -> bool:
    uid = (uid or "").strip()
    role = (role or "user").strip().lower()
    if not uid or role not in ("user", "admin"):
        return False
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE users SET role = %s WHERE uid = %s", (role, uid))
        conn.commit()
        return cur.rowcount > 0
    finally:
        cur.close()
        conn.close()


def update_user_profile(uid: str, display_name: Optional[str] = None, avatar_url: Optional[str] = None) -> Optional[dict]:
    uid = (uid or "").strip()
    if not uid:
        return None
    dn = (display_name or "").strip() if display_name is not None else None
    av = (avatar_url or "").strip() if avatar_url is not None else None
    if dn is not None and len(dn) > 120:
        dn = dn[:120]
    # Avatar có thể là data URL base64 (ảnh <=2MB phía client vẫn dài > 4096 ký tự).
    # Giữ ngưỡng đủ lớn để không bị cắt cụt, tránh mất ảnh sau khi đăng xuất/đăng nhập lại.
    if av is not None and len(av) > 4_200_000:
        av = av[:4_200_000]

    conn = get_connection()
    try:
        cur = conn.cursor()
        sets = []
        vals = []
        if dn is not None:
            sets.append("display_name = %s")
            vals.append(dn)
        if av is not None:
            sets.append("avatar_url = %s")
            vals.append(av)
        if not sets:
            return get_user_by_uid(uid)
        vals.append(uid)
        cur.execute(f"UPDATE users SET {', '.join(sets)} WHERE uid = %s", tuple(vals))
        conn.commit()
    finally:
        cur.close()
        conn.close()
    return get_user_by_uid(uid)


def get_ai_parse_enabled() -> bool:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT ai_parse_enabled FROM app_config WHERE id = 1")
        row = cur.fetchone()
        if row is None:
            return True
        return bool(row[0])
    finally:
        cur.close()
        conn.close()


def set_ai_parse_enabled(enabled: bool) -> None:
    set_config_value("ai_parse_enabled", 1 if enabled else 0)


def set_config_value(key: str, value) -> None:
    """Generic config setter using INSERT ON DUPLICATE KEY UPDATE."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            f"INSERT INTO app_config (id, {key}) VALUES (1, %s) ON DUPLICATE KEY UPDATE {key} = %s",
            (value, value),
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()


def get_config_value(key: str, default=None):
    """Generic config getter."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT {key} FROM app_config WHERE id = 1")
        row = cur.fetchone()
        return row[0] if row else default
    finally:
        cur.close()
        conn.close()


def get_files_index(uid: str) -> dict:
    conn = get_connection()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT file_id, name, filename, parse_method, uploaded_at, file_count AS count, with_answer FROM question_files WHERE user_uid = %s",
            (uid,),
        )
        rows = cur.fetchall()
        out = {}
        for r in rows:
            fid = r["file_id"]
            out[fid] = {
                "name": r["name"],
                "filename": r["filename"],
                "count": r["count"],
                "with_answer": r["with_answer"],
                "uploaded_at": r["uploaded_at"],
                "file_id": fid,
                "parse_method": r.get("parse_method") or "normal",
            }
        return out
    finally:
        cur.close()
        conn.close()


def get_questions_json(uid: str, file_id: str) -> list:
    conn = get_connection()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT q_id, question_text, question_rich, choices_json, choices_rich, answer, explanation, parse_confidence, parse_flags, reviewed, reviewed_at FROM questions WHERE user_uid = %s AND file_id = %s ORDER BY q_id",
            (uid, file_id),
        )
        rows = cur.fetchall()
        out = []
        for r in rows:
            out.append(_row_to_question(r))
        return out
    finally:
        cur.close()
        conn.close()


def get_all_questions(uid: str) -> list:
    conn = get_connection()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT q_id, question_text, question_rich, choices_json, choices_rich, answer, explanation, parse_confidence, parse_flags, reviewed, reviewed_at FROM questions WHERE user_uid = %s ORDER BY file_id, q_id",
            (uid,),
        )
        rows = cur.fetchall() or []
        return [_row_to_question(r) for r in rows]
    finally:
        cur.close()
        conn.close()


def _row_to_question(r: dict) -> dict:
    ch = r["choices_json"]
    if isinstance(ch, str):
        ch = json.loads(ch)

    ch_rich = r.get("choices_rich") if isinstance(r, dict) else None
    if isinstance(ch_rich, str):
        ch_rich = json.loads(ch_rich) if ch_rich else []
    if ch_rich is None:
        ch_rich = []

    # map rich text back into choices for frontend convenience
    rich_map = {}
    for rc in ch_rich if isinstance(ch_rich, list) else []:
        if not isinstance(rc, dict):
            continue
        lb = (rc.get("label") or "").strip().upper()
        tx = rc.get("text") or ""
        if lb in "ABCD":
            rich_map[lb] = tx
    merged_choices = []
    for c in ch if isinstance(ch, list) else []:
        if not isinstance(c, dict):
            continue
        lb = (c.get("label") or "").strip().upper()
        merged_choices.append({
            "label": lb,
            "text": c.get("text") or "",
            "text_rich": rich_map.get(lb) or c.get("text") or "",
        })

    p_flags = r.get("parse_flags") if isinstance(r, dict) else None
    if isinstance(p_flags, str):
        p_flags = json.loads(p_flags) if p_flags else {}
    if p_flags is None:
        p_flags = {}

    q_rich = (r.get("question_rich") if isinstance(r, dict) else None) or r["question_text"]

    return {
        "id": r["q_id"],
        "question": r["question_text"],
        "question_rich": q_rich,
        "choices": merged_choices,
        "choices_rich": ch_rich,
        "answer": r["answer"] or "",
        "explanation": r["explanation"] or "",
        "parse_confidence": float(r.get("parse_confidence") or 0),
        "parse_flags": p_flags,
        "reviewed": bool(r.get("reviewed") or 0),
        "reviewed_at": r.get("reviewed_at"),
    }


def replace_file_questions(
    uid: str,
    file_id: str,
    questions: list,
    name: str,
    filename: str,
    uploaded_at: str,
    parse_method: str,
) -> None:
    ensure_user(uid)
    has_ans = sum(1 for q in questions if (q.get("answer") or "") in list("ABCD"))
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM questions WHERE user_uid = %s AND file_id = %s",
            (uid, file_id),
        )
        for q in questions:
            ch = json.dumps(q.get("choices") or [], ensure_ascii=False)
            ch_rich = json.dumps(q.get("choices_rich") or [], ensure_ascii=False)
            p_flags = json.dumps(q.get("parse_flags") or {}, ensure_ascii=False)
            cur.execute(
                """INSERT INTO questions (user_uid, file_id, q_id, question_text, question_rich, choices_json, choices_rich, answer, explanation, parse_confidence, parse_flags)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    uid,
                    file_id,
                    int(q.get("id", 0)),
                    q.get("question") or "",
                    q.get("question_rich") or q.get("question") or "",
                    ch,
                    ch_rich,
                    (q.get("answer") or "")[:16],
                    q.get("explanation") or "",
                    float(q.get("parse_confidence") or 0),
                    p_flags,
                ),
            )
        cur.execute(
            """INSERT INTO question_files (user_uid, file_id, name, filename, parse_method, uploaded_at, file_count, with_answer)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
               ON DUPLICATE KEY UPDATE name=VALUES(name), filename=VALUES(filename), parse_method=VALUES(parse_method),
               uploaded_at=VALUES(uploaded_at), file_count=VALUES(file_count), with_answer=VALUES(with_answer)""",
            (
                uid,
                file_id,
                name,
                filename,
                parse_method,
                uploaded_at,
                len(questions),
                has_ans,
            ),
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()


def upsert_file_index_row(
    uid: str,
    file_id: str,
    name: str,
    filename: str,
    uploaded_at: str,
    parse_method: str,
    count: int,
    with_answer: int,
) -> None:
    ensure_user(uid)
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO question_files (user_uid, file_id, name, filename, parse_method, uploaded_at, file_count, with_answer)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
               ON DUPLICATE KEY UPDATE name=VALUES(name), filename=VALUES(filename), parse_method=VALUES(parse_method),
               uploaded_at=VALUES(uploaded_at), file_count=VALUES(file_count), with_answer=VALUES(with_answer)""",
            (uid, file_id, name, filename, parse_method, uploaded_at, count, with_answer),
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()


def delete_questions_file(uid: str, file_id: str) -> None:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM questions WHERE user_uid = %s AND file_id = %s", (uid, file_id))
        cur.execute("DELETE FROM question_files WHERE user_uid = %s AND file_id = %s", (uid, file_id))
        conn.commit()
    finally:
        cur.close()
        conn.close()


def delete_question_by_qid(uid: str, file_id: str, q_id: int) -> bool:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM questions WHERE user_uid = %s AND file_id = %s AND q_id = %s",
            (uid, file_id, q_id),
        )
        deleted = cur.rowcount > 0
        if deleted:
            _reindex_file_counts(uid, file_id, cur, conn)
        conn.commit()
        return deleted
    finally:
        cur.close()
        conn.close()


def _reindex_file_counts(uid: str, file_id: str, cur=None, conn=None) -> None:
    own_conn = conn is None
    if own_conn:
        conn = get_connection()
        cur = conn.cursor()
    try:
        cur.execute(
            "SELECT COUNT(*), COALESCE(SUM(CASE WHEN answer IN ('A','B','C','D') THEN 1 ELSE 0 END), 0) FROM questions WHERE user_uid = %s AND file_id = %s",
            (uid, file_id),
        )
        cnt, wa = cur.fetchone()
        wa = int(wa or 0)
        cur.execute(
            "UPDATE question_files SET file_count = %s, with_answer = %s WHERE user_uid = %s AND file_id = %s",
            (int(cnt), wa, uid, file_id),
        )
        if own_conn:
            conn.commit()
    finally:
        if own_conn:
            cur.close()
            conn.close()


def save_questions_replace(uid: str, file_id: str, questions: list) -> None:
    """Replace all questions for file; update index counts."""
    meta = get_file_meta(uid, file_id)
    if not meta:
        return
    replace_file_questions(
        uid,
        file_id,
        questions,
        meta["name"],
        meta["filename"],
        meta["uploaded_at"],
        meta.get("parse_method") or "normal",
    )


def get_file_meta(uid: str, file_id: str) -> Optional[dict]:
    conn = get_connection()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT name, filename, uploaded_at, parse_method FROM question_files WHERE user_uid = %s AND file_id = %s",
            (uid, file_id),
        )
        return cur.fetchone()
    finally:
        cur.close()
        conn.close()


def set_question_reviewed(uid: str, file_id: str, q_id: int, reviewed: bool) -> Optional[dict]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        if reviewed:
            cur.execute(
                "UPDATE questions SET reviewed = %s, reviewed_at = CURRENT_TIMESTAMP WHERE user_uid = %s AND file_id = %s AND q_id = %s",
                (1, uid, file_id, q_id),
            )
        else:
            cur.execute(
                "UPDATE questions SET reviewed = %s, reviewed_at = NULL WHERE user_uid = %s AND file_id = %s AND q_id = %s",
                (0, uid, file_id, q_id),
            )
        if cur.rowcount == 0:
            conn.commit()
            return None
        conn.commit()
    finally:
        cur.close()
        conn.close()

    conn = get_connection()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT q_id, question_text, question_rich, choices_json, choices_rich, answer, explanation, parse_confidence, parse_flags, reviewed, reviewed_at FROM questions WHERE user_uid = %s AND file_id = %s AND q_id = %s",
            (uid, file_id, q_id),
        )
        r = cur.fetchone()
        return _row_to_question(r) if r else None
    finally:
        cur.close()
        conn.close()


def update_question_row(uid: str, file_id: str, q_id: int, question: str, choices: list, answer: str) -> Optional[dict]:
    conn = get_connection()
    cur = None
    try:
        cur = conn.cursor()
        cur.execute(
            """UPDATE questions SET question_text = %s, question_rich = %s, choices_json = %s, choices_rich = %s, answer = %s, parse_confidence = %s, parse_flags = %s WHERE user_uid = %s AND file_id = %s AND q_id = %s""",
            (
                question,
                question,
                json.dumps(choices, ensure_ascii=False),
                json.dumps(choices, ensure_ascii=False),
                answer[:16],
                1.0,
                json.dumps({"edited": True}, ensure_ascii=False),
                uid,
                file_id,
                q_id,
            ),
        )
        conn.commit()
        if cur.rowcount == 0:
            return None
        _reindex_file_counts(uid, file_id)
    finally:
        if cur:
            cur.close()
        conn.close()

    # Fetch updated row
    conn2 = get_connection()
    try:
        cur2 = conn2.cursor(dictionary=True)
        cur2.execute(
            "SELECT q_id, question_text, question_rich, choices_json, choices_rich, answer, explanation, parse_confidence, parse_flags, reviewed, reviewed_at FROM questions WHERE user_uid = %s AND file_id = %s AND q_id = %s",
            (uid, file_id, q_id),
        )
        r = cur2.fetchone()
        return _row_to_question(r) if r else None
    finally:
        cur2.close()
        conn2.close()


def insert_question(uid: str, file_id: str, q: dict) -> dict:
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """INSERT INTO questions (user_uid, file_id, q_id, question_text, question_rich, choices_json, choices_rich, answer, explanation, parse_confidence, parse_flags)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                uid,
                file_id,
                int(q["id"]),
                q.get("question") or "",
                q.get("question_rich") or q.get("question") or "",
                json.dumps(q.get("choices") or [], ensure_ascii=False),
                json.dumps(q.get("choices_rich") or q.get("choices") or [], ensure_ascii=False),
                (q.get("answer") or "")[:16],
                q.get("explanation") or "",
                float(q.get("parse_confidence") or 1.0),
                json.dumps(q.get("parse_flags") or {"manual": True}, ensure_ascii=False),
            ),
        )
        conn.commit()
        _reindex_file_counts(uid, file_id)
        return q
    finally:
        cur.close()
        conn.close()


def append_history(
    uid: str,
    score: int,
    total: int,
    percent: int,
    time_taken: int,
    file_id: str,
    wrong_questions: list,
    anti_cheat: Optional[dict] = None,
    review_details: Optional[list] = None,
) -> None:
    ensure_user(uid)
    date_display = datetime.now().strftime("%d/%m/%Y %H:%M")
    conn = get_connection()
    try:
        cur = conn.cursor()
        history_payload = {
            "wrong_questions": wrong_questions or [],
            "anti_cheat": anti_cheat or {},
            "review_details": review_details or [],
        }
        cur.execute(
            """INSERT INTO quiz_history (user_uid, file_id, score, total, percent, time_taken, wrong_questions_json, date_display)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                uid,
                file_id or None,
                score,
                total,
                percent,
                time_taken,
                json.dumps(history_payload, ensure_ascii=False),
                date_display,
            ),
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()


def get_history_list(uid: str) -> list:
    conn = get_connection()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """SELECT id, file_id, score, total, percent, time_taken, wrong_questions_json, date_display, created_at
               FROM quiz_history WHERE user_uid = %s ORDER BY id ASC""",
            (uid,),
        )
        rows = cur.fetchall()
        out = []
        for r in rows:
            raw = r["wrong_questions_json"]
            parsed = raw
            if isinstance(parsed, str):
                parsed = json.loads(parsed) if parsed else []

            wrong_questions = []
            anti_cheat = {}
            review_details = []
            if isinstance(parsed, dict):
                wrong_questions = parsed.get("wrong_questions") or []
                anti_cheat = parsed.get("anti_cheat") or {}
                review_details = parsed.get("review_details") or []
            elif isinstance(parsed, list):
                wrong_questions = parsed

            out.append(
                {
                    "id": r["id"],
                    "date": r["date_display"],
                    "score": r["score"],
                    "total": r["total"],
                    "percent": r["percent"],
                    "time_taken": r["time_taken"] or 0,
                    "file_id": r["file_id"] or "all",
                    "wrong_questions": wrong_questions,
                    "anti_cheat": anti_cheat,
                    "review_details": review_details,
                }
            )
        return out
    finally:
        cur.close()
        conn.close()


def clear_history(uid: str) -> None:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM quiz_history WHERE user_uid = %s", (uid,))
        conn.commit()
    finally:
        cur.close()
        conn.close()


def save_quiz_session(uid: str, session_id: str, file_id: str, quiz: list, hours: int = 48) -> None:
    ensure_user(uid)
    exp = datetime.now(timezone.utc) + timedelta(hours=hours)
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO quiz_sessions (session_id, user_uid, file_id, payload_json, expires_at)
               VALUES (%s, %s, %s, %s, %s)
               ON DUPLICATE KEY UPDATE payload_json = VALUES(payload_json), file_id = VALUES(file_id), expires_at = VALUES(expires_at)""",
            (
                session_id,
                uid,
                file_id or None,
                json.dumps(quiz, ensure_ascii=False),
                exp,
            ),
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()


def get_quiz_session(session_id: str) -> Optional[list]:
    conn = get_connection()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT payload_json, expires_at FROM quiz_sessions WHERE session_id = %s",
            (session_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        exp = row["expires_at"]
        if exp is not None:
            now = datetime.now(timezone.utc)
            exp_dt = None
            if isinstance(exp, datetime):
                exp_dt = exp
            elif isinstance(exp, str):
                # SQLite thường trả DATETIME dạng chuỗi
                try:
                    exp_dt = datetime.fromisoformat(exp.replace("Z", "+00:00"))
                except Exception:
                    exp_dt = None
            if exp_dt is not None:
                exp_aware = exp_dt if getattr(exp_dt, "tzinfo", None) else exp_dt.replace(tzinfo=timezone.utc)
                if now > exp_aware:
                    cur2 = conn.cursor()
                    cur2.execute("DELETE FROM quiz_sessions WHERE session_id = %s", (session_id,))
                    conn.commit()
                    cur2.close()
                    return None
        p = row["payload_json"]
        if isinstance(p, str):
            p = json.loads(p)
        return p
    finally:
        cur.close()
        conn.close()


def delete_quiz_session(session_id: str) -> None:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM quiz_sessions WHERE session_id = %s", (session_id,))
        conn.commit()
    finally:
        cur.close()
        conn.close()


def get_stats_aggregate(uid: str) -> dict:
    conn = get_connection()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT COALESCE(SUM(file_count),0) AS tq, COALESCE(SUM(with_answer),0) AS wa FROM question_files WHERE user_uid = %s",
            (uid,),
        )
        r1 = cur.fetchone()
        cur.execute("SELECT COUNT(*) AS c FROM quiz_history WHERE user_uid = %s", (uid,))
        r2 = cur.fetchone()
        cur.execute(
            "SELECT AVG(percent) AS a, MAX(percent) AS m FROM quiz_history WHERE user_uid = %s",
            (uid,),
        )
        r3 = cur.fetchone()
        avg = 0
        if r3 and r3.get("a") is not None:
            avg = round(float(r3["a"]))
        return {
            "total_questions": int(r1["tq"] or 0),
            "with_answer": int(r1["wa"] or 0),
            "total_sessions": int(r2["c"] or 0),
            "avg_score": avg,
            "best_score": int(r3["m"] or 0) if r3 and r3.get("m") is not None else 0,
        }
    finally:
        cur.close()
        conn.close()


def revoke_token(token: str, token_type: str, user_uid: Optional[str], expires_at: Optional[datetime]) -> None:
    token = (token or "").strip()
    if not token:
        return
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO revoked_tokens (token_hash, token_type, user_uid, expires_at)
               VALUES (%s, %s, %s, %s)
               ON DUPLICATE KEY UPDATE token_type=VALUES(token_type), user_uid=VALUES(user_uid), expires_at=VALUES(expires_at)""",
            (token_hash, (token_type or "").strip()[:16], user_uid, expires_at),
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()


def is_token_revoked(token: str) -> bool:
    token = (token or "").strip()
    if not token:
        return True
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM revoked_tokens WHERE token_hash = %s LIMIT 1", (token_hash,))
        return cur.fetchone() is not None
    finally:
        cur.close()
        conn.close()


def cleanup_revoked_tokens() -> None:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM revoked_tokens WHERE expires_at IS NOT NULL AND expires_at < UTC_TIMESTAMP()")
        conn.commit()
    finally:
        cur.close()
        conn.close()


def file_exists(uid: str, file_id: str) -> bool:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT 1 FROM question_files WHERE user_uid = %s AND file_id = %s LIMIT 1",
            (uid, file_id),
        )
        return cur.fetchone() is not None
    finally:
        cur.close()
        conn.close()
