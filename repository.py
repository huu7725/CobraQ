"""Data access layer — MySQL backend for CobraQ."""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any, Optional

from db import get_connection


def ensure_user(uid: str, email: Optional[str] = None) -> None:
    uid = (uid or "guest").strip() or "guest"
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
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO app_config (id, ai_parse_enabled) VALUES (1, %s) ON DUPLICATE KEY UPDATE ai_parse_enabled = %s",
            (1 if enabled else 0, 1 if enabled else 0),
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()


def get_files_index(uid: str) -> dict:
    ensure_user(uid)
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
    ensure_user(uid)
    conn = get_connection()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT q_id, question_text, choices_json, answer, explanation FROM questions WHERE user_uid = %s AND file_id = %s ORDER BY q_id",
            (uid, file_id),
        )
        rows = cur.fetchall()
        out = []
        for r in rows:
            ch = r["choices_json"]
            if isinstance(ch, str):
                ch = json.loads(ch)
            out.append(
                {
                    "id": r["q_id"],
                    "question": r["question_text"],
                    "choices": ch,
                    "answer": r["answer"] or "",
                    "explanation": r["explanation"] or "",
                }
            )
        return out
    finally:
        cur.close()
        conn.close()


def get_all_questions(uid: str) -> list:
    ensure_user(uid)
    index = get_files_index(uid)
    all_q = []
    for fid in index:
        all_q.extend(get_questions_json(uid, fid))
    return all_q


def _row_to_question(r: dict) -> dict:
    ch = r["choices_json"]
    if isinstance(ch, str):
        ch = json.loads(ch)
    return {
        "id": r["q_id"],
        "question": r["question_text"],
        "choices": ch,
        "answer": r["answer"] or "",
        "explanation": r["explanation"] or "",
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
            cur.execute(
                """INSERT INTO questions (user_uid, file_id, q_id, question_text, choices_json, answer, explanation)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (
                    uid,
                    file_id,
                    int(q.get("id", 0)),
                    q.get("question") or "",
                    ch,
                    (q.get("answer") or "")[:16],
                    q.get("explanation") or "",
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


def update_question_row(uid: str, file_id: str, q_id: int, question: str, choices: list, answer: str) -> Optional[dict]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """UPDATE questions SET question_text = %s, choices_json = %s, answer = %s WHERE user_uid = %s AND file_id = %s AND q_id = %s""",
            (question, json.dumps(choices, ensure_ascii=False), answer[:16], uid, file_id, q_id),
        )
        if cur.rowcount == 0:
            conn.commit()
            return None
        conn.commit()
    finally:
        cur.close()
        conn.close()
    _reindex_file_counts(uid, file_id)
    conn = get_connection()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT q_id, question_text, choices_json, answer, explanation FROM questions WHERE user_uid = %s AND file_id = %s AND q_id = %s",
            (uid, file_id, q_id),
        )
        r = cur.fetchone()
        return _row_to_question(r) if r else None
    finally:
        cur.close()
        conn.close()


def insert_question(uid: str, file_id: str, q: dict) -> dict:
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """INSERT INTO questions (user_uid, file_id, q_id, question_text, choices_json, answer, explanation)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (
                uid,
                file_id,
                int(q["id"]),
                q.get("question") or "",
                json.dumps(q.get("choices") or [], ensure_ascii=False),
                (q.get("answer") or "")[:16],
                q.get("explanation") or "",
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
) -> None:
    ensure_user(uid)
    date_display = datetime.now().strftime("%d/%m/%Y %H:%M")
    conn = get_connection()
    try:
        cur = conn.cursor()
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
                json.dumps(wrong_questions, ensure_ascii=False),
                date_display,
            ),
        )
        conn.commit()
    finally:
        cur.close()
        conn.close()


def get_history_list(uid: str) -> list:
    ensure_user(uid)
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
            wq = r["wrong_questions_json"]
            if isinstance(wq, str):
                wq = json.loads(wq) if wq else []
            out.append(
                {
                    "id": r["id"],
                    "date": r["date_display"],
                    "score": r["score"],
                    "total": r["total"],
                    "percent": r["percent"],
                    "time_taken": r["time_taken"] or 0,
                    "file_id": r["file_id"] or "all",
                    "wrong_questions": wq or [],
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
    exp = datetime.utcnow() + timedelta(hours=hours)
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
            now = datetime.utcnow()
            exp_naive = exp.replace(tzinfo=None) if getattr(exp, "tzinfo", None) else exp
            if now > exp_naive:
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
    ensure_user(uid)
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
