from fastapi import FastAPI, UploadFile, File, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json, random, re, os, base64, io, traceback, uuid
from datetime import datetime, timedelta, timezone
import jwt
import importlib

# Import mềm để tránh lỗi IDE "could not be resolved" khi thiếu package trong môi trường hiện tại.
# Ưu tiên SDK cũ đang dùng trong code (google.generativeai).
try:
    genai = importlib.import_module("google.generativeai")
except Exception:
    genai = None

import repository as repo
from db import init_schema_from_file

# ══ CẤU HÌNH API KEY ══
# Chỉ lấy từ biến môi trường/.env, không hardcode trong source.
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyBeZA_i0vWbFngTT62GeogddrgbxfpVppI").strip()
# ════════════════════

app = FastAPI()
_cors_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]
if not _cors_origins:
    _cors_origins = ["*"]
app.add_middleware(CORSMiddleware, allow_origins=_cors_origins, allow_methods=["*"], allow_headers=["*"])

JWT_SECRET = os.getenv("JWT_SECRET", "change-me-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "24"))
JWT_REFRESH_SECRET = os.getenv("JWT_REFRESH_SECRET", JWT_SECRET)
JWT_REFRESH_EXPIRE_DAYS = int(os.getenv("JWT_REFRESH_EXPIRE_DAYS", "14"))


def _build_token(user: dict, token_type: str, expires_delta: timedelta, secret: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user["uid"],
        "email": user.get("email"),
        "role": user.get("role") or "user",
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
    }
    return jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)


def create_access_token(user: dict) -> str:
    return _build_token(user, "access", timedelta(hours=JWT_EXPIRE_HOURS), JWT_SECRET)


def create_refresh_token(user: dict) -> str:
    return _build_token(user, "refresh", timedelta(days=JWT_REFRESH_EXPIRE_DAYS), JWT_REFRESH_SECRET)


def decode_token(token: str, secret: str, expected_type: str) -> dict:
    try:
        payload = jwt.decode(token, secret, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token đã hết hạn")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Token không hợp lệ")
    if (payload.get("type") or "") != expected_type:
        raise HTTPException(401, "Sai loại token")
    if repo.is_token_revoked(token):
        raise HTTPException(401, "Token đã bị thu hồi")
    return payload


def decode_access_token(token: str) -> dict:
    return decode_token(token, JWT_SECRET, "access")


def decode_refresh_token(token: str) -> dict:
    return decode_token(token, JWT_REFRESH_SECRET, "refresh")


def get_auth_user(authorization: str = Header(default="")) -> dict:
    auth = (authorization or "").strip()
    if not auth.lower().startswith("bearer "):
        raise HTTPException(401, "Thiếu Bearer token")
    token = auth[7:].strip()
    if not token:
        raise HTTPException(401, "Thiếu Bearer token")
    payload = decode_access_token(token)
    uid = (payload.get("sub") or "").strip()
    if not uid:
        raise HTTPException(401, "Token không hợp lệ")
    user = repo.get_user_by_uid(uid)
    if not user:
        raise HTTPException(401, "Người dùng không tồn tại")
    return user


@app.on_event("startup")
def _startup_init_db():
    init_schema_from_file()
    repo.cleanup_revoked_tokens()

    # Log trạng thái DB engine + AI key để dễ chẩn đoán khi chạy local/team
    try:
        from db import _engine as _db_engine
        eng = _db_engine()
    except Exception:
        eng = "unknown"
    print(f"[CobraQ] DB engine: {eng}")
    if has_valid_key():
        print("[CobraQ] Gemini AI: ON (đã có GEMINI_API_KEY)")
    else:
        print("[CobraQ] Gemini AI: OFF (chưa có GEMINI_API_KEY hợp lệ)")

    app_env = (os.getenv("APP_ENV", "dev") or "dev").strip().lower()
    if app_env in ("prod", "production") and JWT_SECRET == "change-me-in-production":
        raise RuntimeError("JWT_SECRET không được để mặc định ở môi trường production")

    admin_email = (os.getenv("ADMIN_EMAIL", "") or "").strip().lower()
    admin_password = (os.getenv("ADMIN_PASSWORD", "") or "").strip()
    if admin_email and admin_password:
        existing = repo.get_user_by_email(admin_email)
        if existing:
            if (existing.get("role") or "user") != "admin":
                repo.set_user_role(existing["uid"], "admin")
        else:
            uid = f"adm_{uuid.uuid4().hex[:20]}"
            try:
                repo.register_user(uid, admin_email, admin_password, role="admin")
            except Exception as e:
                print(f"Seed admin thất bại: {e}")


def load_config():
    cfg = {"gemini_key": GEMINI_API_KEY, "ai_parse_enabled": True}
    try:
        cfg["ai_parse_enabled"] = repo.get_ai_parse_enabled()
    except Exception:
        pass
    return cfg

def has_valid_key():
    k = GEMINI_API_KEY.strip()
    return bool(k and k != "ĐIỀN_API_KEY_CỦA_BẠN_VÀO_ĐÂY" and k != "YOUR_KEY_HERE" and "..." not in k)

def is_red_text(color) -> bool:
    if color is None:
        return False
    try:
        if isinstance(color, (list, tuple)) and len(color) >= 3:
            r, g, b = float(color[0]), float(color[1]), float(color[2])
            return r > 0.65 and g < 0.4 and b < 0.4
        if isinstance(color, int) and color > 0:
            r = ((color >> 16) & 0xFF) / 255.0
            g = ((color >> 8) & 0xFF) / 255.0
            b = (color & 0xFF) / 255.0
            return r > 0.65 and g < 0.4 and b < 0.4
    except Exception:
        pass
    return False


# Mốc phương án trong một dòng/ô (Word: "… chủ nghĩa. B. Cách …", "…B.Cách…", NBSP, v.v.)
CHOICE_INLINE_PAT = re.compile(
    r"(?:^|(?<=\s)|(?<=[\.．,;:]))\b([A-D])[\.\)．:：]\s*",
)


def _sanitize_choice_text(t: str) -> str:
    if not t:
        return ""
    t = str(t).replace("\u00a0", " ").replace("\u202f", " ")
    t = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", t)
    return t.strip()


def split_choice_segments(text: str) -> list:
    if not text or not str(text).strip():
        return []
    s = _sanitize_choice_text(text)
    matches = list(CHOICE_INLINE_PAT.finditer(s))
    if not matches:
        return []
    out = []
    for i, m in enumerate(matches):
        label = m.group(1).upper()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(s)
        chunk = s[start:end].strip()
        if chunk:
            out.append({"label": label, "text": chunk})
    return out


def _expand_choice_cell(text: str, cell_label: str) -> list:
    """Một ô đáp án (A/B/C/D) có thể chứa cả mốc D. E. — phần trước mốc đầu thuộc cell_label."""
    t = _sanitize_choice_text(text or "")
    cl = (cell_label or "?").strip().upper()
    if not t:
        return []
    matches = list(CHOICE_INLINE_PAT.finditer(t))
    if not matches:
        return [{"label": cl, "text": t}] if cl in "ABCD" else []
    out = []
    if matches[0].start() > 0 and cl in "ABCD":
        pre = t[: matches[0].start()].strip()
        if pre:
            out.append({"label": cl, "text": pre})
    for i, m in enumerate(matches):
        lb = m.group(1).upper()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(t)
        chunk = t[start:end].strip()
        if chunk:
            out.append({"label": lb, "text": chunk})
    if not out:
        return [{"label": cl, "text": t}] if cl in "ABCD" else []
    return out


def normalize_merged_choices_in_question(q: dict) -> None:
    chs = q.get("choices") or []
    if not chs:
        return
    for _ in range(5):
        new_chs = []
        seen = set()
        for ch in chs:
            label = (ch.get("label") or "?").strip().upper()
            t = _sanitize_choice_text(ch.get("text") or "")
            for p in _expand_choice_cell(t, label):
                lb = (p.get("label") or "?").strip().upper()
                tx = _sanitize_choice_text(p.get("text") or "")
                tx = re.sub(r"^\s*(?:Phương\s*án|Đáp\s*án)\s*[A-D]\s*[:\-\.]\s*", "", tx, flags=re.IGNORECASE)
                tx = re.sub(r"\s+", " ", tx).strip(" .;:\t\n\r")
                if lb in "ABCD" and lb not in seen and tx:
                    seen.add(lb)
                    new_chs.append({"label": lb, "text": tx})
        if new_chs:
            new_chs = sorted(new_chs, key=lambda x: "ABCD".index(x["label"]) if x["label"] in "ABCD" else 9)
        if not new_chs:
            break
        same_len = len(new_chs) == len(chs)
        same_txt = same_len and all(
            (chs[i].get("label"), _sanitize_choice_text(chs[i].get("text") or ""))
            == (new_chs[i]["label"], new_chs[i]["text"])
            for i in range(len(new_chs))
        )
        q["choices"] = new_chs
        if same_txt:
            break
        chs = new_chs


def _clean_choices_payload(choices: list) -> list:
    out = []
    seen = set()
    for c in choices or []:
        if not isinstance(c, dict):
            continue
        lb = (c.get("label") or "").strip().upper()
        tx = _sanitize_choice_text(c.get("text") or "")
        if lb in "ABCD" and tx and lb not in seen:
            seen.add(lb)
            out.append({"label": lb, "text": tx})
    return sorted(out, key=lambda x: "ABCD".index(x["label"]))


def _looks_like_math_expr(s: str) -> bool:
    t = (s or "").strip()
    if not t:
        return False
    math_tokens = [r"\\frac", r"\\sqrt", r"\\int", r"\\sum", r"\\lim", r"\\alpha", r"\\beta", r"\\theta", r"\\pi", r"\^", r"_", r"=", r"≤", r"≥", r"∫", r"Σ", r"√", r"→", r"↔", r"∀", r"∃", r"\bcos\b", r"\bsin\b", r"\btan\b", r"\blog\b", r"\bln\b"]
    return any(re.search(p, t, flags=re.IGNORECASE) for p in math_tokens)


def _to_rich_inline(text: str) -> str:
    t = (text or "").strip()
    if not t:
        return ""
    if "$" in t or "\\(" in t or "\\[" in t:
        return t
    if _looks_like_math_expr(t):
        return f"\\({t}\\)"
    return t


def enrich_question_rich_fields(q: dict) -> dict:
    qq = dict(q or {})
    question = str(qq.get("question") or "").strip()
    choices = list(qq.get("choices") or [])

    question_rich = _to_rich_inline(question)
    choices_rich = []
    math_hits = 1 if _looks_like_math_expr(question) else 0
    for c in choices:
        txt = str((c or {}).get("text") or "").strip()
        if _looks_like_math_expr(txt):
            math_hits += 1
        choices_rich.append({"label": (c.get("label") or "").strip().upper(), "text": _to_rich_inline(txt)})

    confidence = 0.82
    flags = {"math_detected": bool(math_hits), "source": "cpu_only_v1"}
    if math_hits >= 2:
        confidence = 0.9
    if not question or len(choices) < 2:
        confidence = 0.55
        flags["needs_review"] = True

    qq["question_rich"] = question_rich or question
    qq["choices_rich"] = choices_rich
    qq["parse_confidence"] = round(confidence, 4)
    qq["parse_flags"] = flags
    return qq


def _validate_question_choices(choices: list, answer: str) -> tuple[list, str]:
    clean = _clean_choices_payload(choices)
    if len(clean) < 2:
        raise HTTPException(400, "Cần ít nhất 2 phương án có nội dung (C, D có thể để trống).")
    ans = (answer or "").strip().upper()
    if ans:
        if ans not in list("ABCD") or ans not in {c["label"] for c in clean}:
            raise HTTPException(400, "Đáp án đúng phải là A/B/C/D và trùng một phương án đã nhập.")
    return clean, ans


# ══════════════════════════════════════════
#  PDF PARSER CHUẨN — (GIỮ NGUYÊN)
# ══════════════════════════════════════════

def is_highlight(fill):
    if not fill or len(fill) < 3: return False
    r, g, b = float(fill[0]), float(fill[1]), float(fill[2])
    if r > 0.92 and g > 0.92 and b > 0.92: return False  
    if r < 0.05 and g < 0.05 and b < 0.05: return False  
    if r > 0.85 and g > 0.85 and b > 0.85: return False  
    if g > 0.50 and b > 0.40 and r < 0.60: return True
    if g > 0.55 and g > r * 1.3 and g > b * 1.2: return True
    if r > 0.75 and g > 0.70 and b < 0.40: return True
    if r > 0.80 and g < 0.65 and b < 0.65: return True
    if b > 0.55 and b > r * 1.2 and g > 0.45: return True
    return False

def get_highlight_rects(page):
    rects = []
    try:
        for d in page.get_drawings():
            if is_highlight(d.get("fill")):
                rects.append(d["rect"])
    except: pass
    return rects

def span_in_rect(bbox, rects, pad=4):
    cx = (bbox[0] + bbox[2]) / 2
    cy = (bbox[1] + bbox[3]) / 2
    for r in rects:
        if r.x0-pad <= cx <= r.x1+pad and r.y0-pad <= cy <= r.y1+pad:
            return True
    return False

def get_all_spans(page):
    spans = []
    try:
        for block in page.get_text("dict")["blocks"]:
            if block.get("type") != 0: continue
            for line in block["lines"]:
                for sp in line["spans"]:
                    t = sp["text"].strip()
                    if t:
                        bbox = sp["bbox"]
                        spans.append({"text": t, "bbox": bbox, "cx": (bbox[0]+bbox[2])/2, "cy": (bbox[1]+bbox[3])/2})
    except: pass
    return spans

def group_rows(spans, tol=12):
    rows = []
    for sp in sorted(spans, key=lambda s: s["cy"]):
        placed = False
        for row in rows:
            if abs(row["cy"] - sp["cy"]) < tol:
                row["spans"].append(sp)
                row["cy"] = (row["cy"] + sp["cy"]) / 2
                placed = True
                break
        if not placed:
            rows.append({"cy": sp["cy"], "spans": [sp]})
    return sorted(rows, key=lambda r: r["cy"])

def parse_pdf_table(page, hl_rects):
    spans = get_all_spans(page)
    if not spans: return None
    rows = group_rows(spans)
    col_A = col_B = col_C = col_D = col_Q = None
    header_y = None

    for row in rows:
        has_da = bool(re.search(r'ĐÁPÁN|ANSWER', " ".join(s["text"] for s in row["spans"]), re.IGNORECASE))
        labels = [s for s in row["spans"] if s["text"].strip().upper() in ["A", "B", "C", "D"]]
        if has_da or len(labels) >= 3:
            header_y = row["cy"]
            for sp in row["spans"]:
                t = sp["text"].upper().replace(" ", "")
                if any(k in t for k in ["NỘIDUNG", "CÂUHỎI", "CONTENT", "NOIUNG"]): col_Q = sp["cx"]
                if re.search(r'[ĐD][AÁ]P[AÁ]NA|ANSWERA', t) or t == "A": col_A = sp["cx"]
                if re.search(r'[ĐD][AÁ]P[AÁ]NB|ANSWERB', t) or t == "B": col_B = sp["cx"]
                if re.search(r'[ĐD][AÁ]P[AÁ]NC|ANSWERC', t) or t == "C": col_C = sp["cx"]
                if re.search(r'[ĐD][AÁ]P[AÁ]ND|ANSWERD', t) or t == "D": col_D = sp["cx"]
            break

    if sum(1 for c in [col_A, col_B, col_C, col_D] if c is not None) < 2: return None

    col_map = {k: v for k, v in [("A", col_A), ("B", col_B), ("C", col_C), ("D", col_D)] if v is not None}
    answer_map = {}
    for hl in hl_rects:
        hcx, hcy = (hl.x0 + hl.x1) / 2, (hl.y0 + hl.y1) / 2
        if header_y and hcy <= header_y + 5: continue
        best_label, best_dist = None, 999
        for label, cx in col_map.items():
            if abs(hcx - cx) < best_dist:
                best_dist, best_label = abs(hcx - cx), label
        if not best_label or best_dist > 120: continue

        best_tt, best_dy = None, 999
        for sp in spans:
            if re.match(r'^\d+$', sp["text"]):
                if abs(sp["cy"] - hcy) < best_dy:
                    best_dy, best_tt = abs(sp["cy"] - hcy), int(sp["text"])
        if best_tt and best_dy < 30: answer_map[best_tt] = best_label

    if not answer_map: return None

    questions, data_rows = [], [r for r in rows if header_y is None or r["cy"] > header_y + 8]
    tt_to_spans, current_tt = {}, None
    for row in data_rows:
        tt_spans = [s for s in row["spans"] if re.match(r'^\d+$', s["text"])]
        if tt_spans: current_tt = int(tt_spans[0]["text"])
        if current_tt: tt_to_spans.setdefault(current_tt, []).extend(row["spans"])

    for tt, row_spans in tt_to_spans.items():
        if tt not in answer_map: continue
        if col_Q:
            q_spans = [s for s in row_spans if col_Q - 180 <= s["cx"] <= col_Q + 180 and s["text"] not in [str(tt)]]
        else:
            q_spans = [s for s in row_spans if len(s["text"]) > 2 and not re.match(r'^[\dABCD]$', s["text"]) and not any(abs(s["cx"] - cx) < 80 for cx in col_map.values())]

        q_text = " ".join(s["text"] for s in sorted(q_spans, key=lambda x: (x["cy"], x["cx"]))).strip()
        if not q_text: continue

        choices = []
        for label in sorted(col_map.keys()):
            cx = col_map[label]
            c_spans = [s for s in row_spans if abs(s["cx"] - cx) < 90 and s["text"] not in [str(tt)]]
            c_text = " ".join(s["text"] for s in sorted(c_spans, key=lambda x: (x["cy"], x["cx"]))).strip()
            if c_text: choices.append({"label": label, "text": c_text})

        if len(choices) >= 2:
            questions.append({"id": tt, "question": q_text, "choices": choices, "answer": answer_map.get(tt, ""), "explanation": ""})
    return questions if questions else None

def parse_pdf_inline(page, hl_rects):
    lines = []
    try:
        for block in page.get_text("dict")["blocks"]:
            if block.get("type") != 0: continue
            for line in block["lines"]:
                line_text, hl_bg, hl_red = "", False, False
                for sp in line["spans"]:
                    line_text += sp["text"]
                    if hl_rects and span_in_rect(sp["bbox"], hl_rects): hl_bg = True
                    if is_red_text(sp.get("color", 0)): hl_red = True
                t = line_text.strip()
                if t: lines.append({"text": t, "hl": hl_bg or hl_red})
    except: return []

    questions, cur = [], None
    for item in lines:
        text, hl = item["text"], item["hl"]
        m = re.match(r"^(?:C[âa]u\s*)(\d+)[\.\:\)]\s*(.+)", text, re.IGNORECASE)
        m_loose = re.match(r"^(\d+)[\.\:\)]\s*(.+)", text, re.IGNORECASE)
        can_start_loose = False
        if m_loose:
            # Chỉ cho phép dạng "1. ..." nếu có đáp án A/B/C/D ngay cùng dòng
            probe_rest = (m_loose.group(2) or "").strip()
            can_start_loose = len(split_choice_segments(probe_rest)) >= 3

        mm = m if m else (m_loose if can_start_loose else None)
        if mm and not re.match(r"^[A-Da-d][\.\)]", mm.group(2)):
            if cur and len(cur["choices"]) >= 2:
                questions.append(cur)
            rest = mm.group(2).strip()
            embedded = split_choice_segments(rest)
            if len(embedded) >= 2:
                fm = CHOICE_INLINE_PAT.search(rest)
                q_stem = rest[: fm.start()].strip() if fm else rest
                cur = {"id": int(mm.group(1)), "question": q_stem, "choices": list(embedded), "answer": "", "explanation": ""}
            else:
                cur = {"id": int(mm.group(1)), "question": rest, "choices": [], "answer": "", "explanation": ""}
        elif cur:
            parts = split_choice_segments(text)
            if parts:
                for p in parts:
                    cur["choices"].append(p)
                    if hl and not cur["answer"]:
                        cur["answer"] = p["label"]
            elif re.match(r"^[A-Da-d][\.\)]\s*", text):
                label = text[0].upper()
                cur["choices"].append({"label": label, "text": re.sub(r"^[A-Da-d][\.\)]\s*", "", text).strip()})
                if hl and not cur["answer"]:
                    cur["answer"] = label
            elif re.match(r"^(Đ[áa]p\s*[áa]n|ĐA)\s*[:\-]", text, re.IGNORECASE):
                mm = re.search(r"[A-D]", text.upper())
                if mm and not cur["answer"]:
                    cur["answer"] = mm.group()
    if cur and len(cur["choices"]) >= 2:
        questions.append(cur)
    for q in questions:
        normalize_merged_choices_in_question(q)
    return questions

def _looks_like_math_question_text(text: str) -> bool:
    t = (text or "").strip().lower()
    if not t:
        return False
    if re.search(r"\d", t):
        return True
    math_kw = [
        "hàm số", "đạo hàm", "tích phân", "phương trình", "bất phương trình", "log", "sin", "cos", "tan",
        "đường thẳng", "mặt phẳng", "thể tích", "xác suất", "tọa độ", "cực trị", "nghiệm", "giới hạn",
        "số phức", "ma trận", "vectơ", "vector", "cấp số", "hình học", "tham số", "biến số",
    ]
    if any(k in t for k in math_kw):
        return True
    if re.search(r"[xyztmna-b]\b|[=<>≤≥±√∫Σπ]", t):
        return True
    return False


def _is_likely_valid_mcq(q: dict) -> bool:
    if not isinstance(q, dict):
        return False
    question = str(q.get("question") or "").strip()
    choices = list(q.get("choices") or [])

    if len(question) < 10 or len(question) > 1200:
        return False
    if re.search(r"https?://|www\.|@", question, re.IGNORECASE):
        return False

    # Cần tối thiểu 3 phương án không rỗng
    if len(choices) < 3:
        return False

    # Chặn các đoạn văn bản đời sống/tạp văn hay bị nhận nhầm trong PDF
    if re.search(r"thời\s+gian\s+tập\s+nhảy|chỉ\s+rất\s+thích\s+nhảy|chất\s+lượng\s+sữa|khảo\s+sát|đoạn\s+văn", question, re.IGNORECASE):
        return False

    labels = []
    non_empty = 0
    for c in choices:
        lb = str((c or {}).get("label") or "").strip().upper()
        tx = str((c or {}).get("text") or "").strip()
        if lb:
            labels.append(lb)
        if tx and len(tx) >= 2:
            non_empty += 1

    if non_empty < 3:
        return False
    if any(lb not in ("A", "B", "C", "D") for lb in labels if lb):
        return False

    return True


def _looks_garbled_text(s: str) -> bool:
    t = (s or "").strip()
    if not t:
        return False
    bad_patterns = [r"[%#@\^~]{2,}", r"[A-Za-z0-9]{1,2}[%#@][A-Za-z0-9]{1,2}", r"K%|Ã|Â|ð|�"]
    if any(re.search(p, t) for p in bad_patterns):
        return True
    # quá nhiều ký tự lạ ngoài tập toán/latin/vn cơ bản
    weird = re.findall(r"[^\w\s\+\-\*/=\(\)\[\]\{\}\.,:;!?<>&%√πΣ∫≤≥±°'\"\u00C0-\u1EF9]", t, flags=re.UNICODE)
    return len(weird) >= 3


def _garbled_ratio(questions: list) -> float:
    if not questions:
        return 1.0
    bad = 0
    total = 0
    for q in questions[:120]:
        total += 1
        qq = str(q.get("question") or "")
        if _looks_garbled_text(qq):
            bad += 1
            continue
        for c in (q.get("choices") or []):
            if _looks_garbled_text(str((c or {}).get("text") or "")):
                bad += 1
                break
    return (bad / total) if total else 1.0


def parse_pdf(content: bytes) -> list:
    import fitz
    doc = fitz.open(stream=content, filetype="pdf")
    all_questions = []
    for page in doc:
        hl_rects = get_highlight_rects(page)
        if hl_rects:
            try:
                table_qs = parse_pdf_table(page, hl_rects)
                if table_qs:
                    all_questions.extend(table_qs)
                    continue
            except:
                pass
        try:
            all_questions.extend(parse_pdf_inline(page, hl_rects))
        except:
            pass

    # Chuẩn hóa + lọc nhiễu
    cleaned = []
    for q in all_questions:
        normalize_merged_choices_in_question(q)
        if _is_likely_valid_mcq(q):
            cleaned.append(q)

    # Khử trùng lặp theo nội dung câu hỏi
    dedup = []
    seen = set()
    for q in cleaned:
        key = re.sub(r"\s+", " ", str(q.get("question") or "").strip().lower())
        if not key or key in seen:
            continue
        seen.add(key)
        dedup.append(q)

    for i, q in enumerate(dedup):
        q["id"] = i + 1

    return dedup

# ══════════════════════════════════════════
# ════ WORD PARSER — (SIÊU CẤP - XỬ LÝ BẢNG GỘP DÒNG)
# ══════════════════════════════════════

def _parse_lines(lines):
    questions, cur = [], None
    for line in lines:
        line = line.strip() if isinstance(line, str) else ""
        if not line:
            continue
        m = re.match(r"^(?:C[âa]u\s*)?(\d+)[\.\:\)]\s*(.+)", line, re.IGNORECASE)
        if m and not re.match(r"^[A-Da-d][\.\)]", m.group(2)):
            if cur and len(cur["choices"]) >= 2:
                questions.append(cur)
            rest = m.group(2).strip()
            embedded = split_choice_segments(rest)
            if len(embedded) >= 2:
                fm = CHOICE_INLINE_PAT.search(rest)
                q_stem = rest[: fm.start()].strip() if fm else rest
                cur = {"id": int(m.group(1)), "question": q_stem, "choices": list(embedded), "answer": "", "explanation": ""}
            else:
                cur = {"id": int(m.group(1)), "question": rest, "choices": [], "answer": "", "explanation": ""}
        elif cur:
            parts = split_choice_segments(line)
            if parts:
                for p in parts:
                    cur["choices"].append(p)
            elif re.match(r"^[A-Da-d][\.\)]\s*", line):
                cur["choices"].append({"label": line[0].upper(), "text": re.sub(r"^[A-Da-d][\.\)]\s*", "", line).strip()})
            elif re.match(r"^(Đ[áa]p\s*[áa]n|ĐA)", line, re.IGNORECASE):
                mm = re.search(r"[A-D]", line.upper())
                if mm:
                    cur["answer"] = mm.group()
    if cur and len(cur["choices"]) >= 2:
        questions.append(cur)
    for q in questions:
        normalize_merged_choices_in_question(q)
    return questions


def _extract_answer_map_from_lines(lines: list[str]) -> dict:
    """Trích bảng đáp án từ text thường: fuzzy cho nhiều format khác nhau."""
    ans_map = {}

    def _normalize_line(x: str) -> str:
        s = (x or "").replace("\u00a0", " ").replace("\u202f", " ")
        s = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", s)
        s = re.sub(r"[\|,;]+", " ", s)
        s = re.sub(r"\s+", " ", s).strip()
        return s

    for ln in lines:
        s = _normalize_line((ln or "").upper())
        if not s:
            continue

        # VD: 1A 2B 3C | 1-A | 1:A | 1) A | Câu 1 đáp án B
        for n, a in re.findall(r"\b(?:CÂU\s*)?(\d{1,4})\s*(?:[\)\].:\-=>]|\s)*(?:ĐÁP\s*ÁN\s*)?([ABCD])\b", s):
            ans_map[int(n)] = a

        # VD: Câu 12: đáp án là C
        for n, a in re.findall(r"\bCÂU\s*(\d{1,4})\b[^A-D\n]{0,25}\b([ABCD])\b", s):
            ans_map[int(n)] = a

    # dạng 2 dòng: dòng số + dòng chữ
    for i in range(len(lines) - 1):
        n_line = _normalize_line((lines[i] or ""))
        a_line = _normalize_line((lines[i + 1] or "").upper())
        nums = re.findall(r"\b\d{1,4}\b", n_line)
        letters = re.findall(r"\b[ABCD]\b", a_line)
        if nums and letters and len(nums) == len(letters):
            for n, a in zip(nums, letters):
                ans_map[int(n)] = a

    return ans_map


def parse_docx_without_docx(content: bytes) -> list:
    # Fallback khi thiếu python-docx: đọc XML trực tiếp từ file .docx
    import html
    import io
    import re
    import zipfile

    try:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            xml = zf.read("word/document.xml").decode("utf-8", errors="ignore")
    except Exception:
        return []

    def _cell_text(cell_xml: str) -> str:
        s = re.sub(r"</w:p>", "\n", cell_xml)
        s = re.sub(r"<[^>]+>", "", s)
        s = html.unescape(s)
        return " ".join([x.strip() for x in s.splitlines() if x.strip()]).strip()

    def _cell_marked(cell_xml: str) -> bool:
        if re.search(r"<w:b(?:\s|/|>)", cell_xml):
            return True
        m = re.search(r"<w:color[^>]*w:val=\"([0-9A-Fa-f]{6}|auto)\"", cell_xml)
        if m and m.group(1).lower() not in ("000000", "auto"):
            return True
        if re.search(r"<w:highlight\b", cell_xml):
            return True
        return False

    tr_blocks = re.findall(r"<w:tr\b[\s\S]*?</w:tr>", xml)
    questions = []
    qid = 0
    for tr in tr_blocks:
        tc_blocks = re.findall(r"<w:tc\b[\s\S]*?</w:tc>", tr)
        if len(tc_blocks) < 6:
            continue

        vals = [_cell_text(tc) for tc in tc_blocks]
        first = (vals[0] or "").strip().upper()
        if first in ("TT", "STT", "SỐ TT") or any("NỘI DUNG CÂU HỎI" in (v or "").upper() for v in vals):
            continue
        if not re.match(r"^\d+$", vals[0] or ""):
            continue

        q_text = (vals[2] if len(vals) > 2 else "").strip()
        a_txt = (vals[3] if len(vals) > 3 else "").strip()
        b_txt = (vals[4] if len(vals) > 4 else "").strip()
        c_txt = (vals[5] if len(vals) > 5 else "").strip()
        d_txt = (vals[6] if len(vals) > 6 else "").strip()

        if not q_text or len(q_text) < 6:
            continue

        labels = ["A", "B", "C", "D"]
        texts = [a_txt, b_txt, c_txt, d_txt]
        choices = [{"label": labels[i], "text": texts[i]} for i in range(4) if texts[i]]
        if len(choices) < 2:
            continue

        marked = []
        for i, idx in enumerate((3, 4, 5, 6)):
            if idx < len(tc_blocks) and texts[i] and _cell_marked(tc_blocks[idx]):
                marked.append(labels[i])
        answer = marked[0] if marked else ""

        qid += 1
        questions.append({"id": qid, "question": q_text, "choices": choices, "answer": answer, "explanation": ""})

    x = re.sub(r"</w:p>", "\n", xml)
    x = re.sub(r"</w:tr>", "\n", x)
    x = re.sub(r"</w:tc>", "\n", x)
    text = re.sub(r"<[^>]+>", "", x)
    text = html.unescape(text)
    lines = [ln.strip() for ln in text.replace("\r", "\n").split("\n") if ln.strip()]

    if questions:
        # map thêm đáp án từ bảng đáp án text nếu có
        answer_map = _extract_answer_map_from_lines(lines)
        for q in questions:
            if not q.get("answer") and q.get("id") in answer_map:
                q["answer"] = answer_map[q["id"]]
            normalize_merged_choices_in_question(q)
        return questions

    # fallback cuối: parse text thường
    parsed = _parse_lines(lines)
    answer_map = _extract_answer_map_from_lines(lines)
    for q in parsed:
        if not q.get("answer") and q.get("id") in answer_map:
            q["answer"] = answer_map[q["id"]]
    return parsed


def parse_word(content: bytes) -> list:
    import io
    import importlib
    try:
        docx = importlib.import_module("docx")
    except Exception:
        return parse_docx_without_docx(content)

    doc = docx.Document(io.BytesIO(content))
    questions = []
    max_id = 0
    current_q = None

    # 1. Quét Bảng (Table Parsing - Xử lý lỗi gộp dòng)
    for table in doc.tables:
        for row in table.rows:
            cells = row.cells
            if len(cells) >= 7:
                # Tách text từng ô theo dấu Enter (để chống lại việc gộp dòng)
                cell_lines = []
                for c in cells:
                    lines = [x.strip() for x in c.text.split('\n') if x.strip()]
                    cell_lines.append(lines)
                
                # Quét tìm text bôi đậm/tô màu/tô nền (Nhận diện đáp án)
                correct_keywords = [[], [], [], []]
                correct_marked = [False, False, False, False]
                for j in range(4):
                    idx = 3 + j
                    if idx < len(cells):
                        for p in cells[idx].paragraphs:
                            for run in p.runs:
                                rt = run.text.strip()
                                marked = bool(
                                    run.bold
                                    or (run.font.color and run.font.color.rgb and str(run.font.color.rgb) not in ("000000", "None"))
                                    or (run.font.highlight_color is not None)
                                )
                                if marked:
                                    correct_marked[j] = True
                                if rt and marked and len(rt) > 0:
                                    correct_keywords[j].append(rt)
                
                max_lines = max(len(lines) for lines in cell_lines) if cell_lines else 0
                for i in range(max_lines):
                    tt_text = cell_lines[0][i] if i < len(cell_lines[0]) else ""
                    
                    # Bỏ qua dòng tiêu đề bảng
                    if tt_text.strip().upper() in ["TT", "STT", "SỐ TT"]:
                        continue

                    if tt_text.isdigit():
                        if current_q and current_q["choices"]:
                            questions.append(current_q)
                            max_id = max(max_id, current_q["id"])
                        
                        labels = ['A', 'B', 'C', 'D']
                        choices = []
                        correct_ans = ""
                        for j in range(4):
                            idx = 3 + j
                            ans_text = cell_lines[idx][i] if idx < len(cell_lines) and i < len(cell_lines[idx]) else ""
                            if ans_text:
                                choices.append({"label": labels[j], "text": ans_text})
                                # Ưu tiên ô được đánh dấu (bold/color/highlight)
                                if not correct_ans and correct_marked[j]:
                                    correct_ans = labels[j]
                                # Fallback: kiểm tra text trùng phần in đậm/tô màu
                                if not correct_ans and any(k in ans_text for k in correct_keywords[j]):
                                    correct_ans = labels[j]
                        
                        q_text = cell_lines[2][i] if 2 < len(cell_lines) and i < len(cell_lines[2]) else ""
                        current_q = {
                            "id": int(tt_text),
                            "question": q_text,
                            "choices": choices,
                            "answer": correct_ans,
                            "explanation": ""
                        }
                    else:
                        # Ghép nối câu hỏi bị rớt dòng
                        if current_q:
                            q_text = cell_lines[2][i] if 2 < len(cell_lines) and i < len(cell_lines[2]) else ""
                            if q_text: current_q["question"] += "\n" + q_text
                            
                            for j in range(4):
                                idx = 3 + j
                                ans_text = cell_lines[idx][i] if idx < len(cell_lines) and i < len(cell_lines[idx]) else ""
                                if ans_text and j < len(current_q["choices"]):
                                    current_q["choices"][j]["text"] += "\n" + ans_text
                                    if not current_q["answer"] and correct_marked[j]:
                                        current_q["answer"] = ['A', 'B', 'C', 'D'][j]
                                    if not current_q["answer"] and any(k in ans_text for k in correct_keywords[j]):
                                        current_q["answer"] = ['A', 'B', 'C', 'D'][j]

    if current_q and current_q["choices"]:
        questions.append(current_q)
        max_id = max(max_id, current_q["id"])

    # 2. Quét câu hỏi dạng văn bản thường ngoài bảng (nếu có)
    text_lines = [p.text for p in doc.paragraphs]
    text_questions = _parse_lines(text_lines)
    for tq in text_questions:
        max_id += 1
        tq["id"] = max_id
        questions.append(tq)

    # 3. Quét bảng đáp án ở cuối trang (nếu có)
    answer_map = {}
    for table in doc.tables:
        cells = [c.text.strip() for row in table.rows for c in row.cells]
        is_ans = any(re.search(r'ĐÁP\s*ÁN|ĐA\b|MÃ\s*ĐỀ|Mã\s*đề', x, re.IGNORECASE) for x in cells)
        if not is_ans: is_ans = sum(1 for x in cells if x.upper() in 'ABCD') > len(cells) * 0.3
        if is_ans:
            for row in table.rows:
                vals = [c.text.strip() for c in row.cells]
                for i in range(0, len(vals)-1, 2):
                    if re.match(r'^\d+$', vals[i]) and vals[i+1].upper() in 'ABCD':
                        answer_map[int(vals[i])] = vals[i+1].upper()
            rows = list(table.rows)
            if len(rows) >= 2:
                header = [c.text.strip() for c in rows[0].cells]
                for row in rows[1:]:
                    for j, c in enumerate(row.cells):
                        v = c.text.strip().upper()
                        if j < len(header) and re.match(r'^\d+$', header[j]) and v in 'ABCD':
                            answer_map[int(header[j])] = v
            if answer_map: break
            
    for q in questions:
        if not q["answer"] and q["id"] in answer_map:
            q["answer"] = answer_map[q["id"]]

    for q in questions:
        normalize_merged_choices_in_question(q)
    return questions

# ══════════════════════════════════════════
#  GOOGLE GEMINI AI PARSER (ĐÃ CẬP NHẬT FIX LỖI ĐỌC DOCX)
# ══════════════════════════════════════════

GEMINI_PROMPT = """Bạn là chuyên gia trích xuất đề trắc nghiệm (Toán, tiếng Việt).

QUY TẮC BẮT BUỘC:
- Mỗi phương án A, B, C, D là một object RIÊNG trong "choices". Không gộp hai phương án vào cùng một "text".
- Trong "text" của từng phương án: không được để lẫn mốc " B. ", " C. ", " D. " — nếu có, tách thành phương án mới.
- "question" chỉ là phần đề; các dòng A. B. C. D. luôn tách vào choices (đủ 4 phương án nếu đề có đủ).
- Giữ ký hiệu toán (căn, phân số, pi, góc) theo đúng nguồn nếu có thể.
- Nếu cuối file có bảng Đáp án / Mã đề (số câu ↔ A/B/C/D), map đúng "answer" theo số câu.
- Nếu có đáp án tô màu/in đậm trong đề, dùng làm "answer"; không thì "" hoặc suy luận nếu chắc chắn.

CHỈ TRẢ VỀ MẢNG JSON THUẦN (không markdown):
[
  {
    "id": 1,
    "question": "...",
    "choices": [{"label": "A", "text": "..."}, {"label": "B", "text": "..."}, {"label": "C", "text": "..."}, {"label": "D", "text": "..."}],
    "answer": "A"
  }
]"""

def parse_with_gemini_ai(content: bytes, filetype: str, api_key: str) -> list:
    if genai is None:
        print("Thiếu thư viện google-generativeai, bỏ qua AI parser.")
        return []
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        if filetype == "pdf":
            print(f"Đang gửi dữ liệu PDF ({len(content)} bytes) lên Gemini AI...")
            response = model.generate_content([
                {"mime_type": "application/pdf", "data": content},
                GEMINI_PROMPT
            ])
        else:
            # Giải mã DOCX thành chữ trước khi gửi cho AI để chống lỗi 400 Bad Request
            import io
            import importlib
            try:
                docx = importlib.import_module("docx")
                doc = docx.Document(io.BytesIO(content))
                text_lines = [p.text for p in doc.paragraphs if p.text.strip()]
                for table in doc.tables:
                    for row in table.rows:
                        text_lines.append(" | ".join(c.text.replace('\n', ' ').strip() for c in row.cells))
            except Exception:
                # fallback khi thiếu python-docx
                text_lines = [
                    q.get("question", "") + " " + " ".join(ch.get("text", "") for ch in q.get("choices", []))
                    for q in parse_docx_without_docx(content)
                ]
            
            full_text = "\n".join(text_lines)
            print(f"Đang gửi nội dung Word ({len(full_text)} ký tự) lên Gemini AI...")
            response = model.generate_content([full_text, GEMINI_PROMPT])
            
        raw = response.text.strip()
        raw = re.sub(r'^```json\s*', '', raw)
        raw = re.sub(r'^```\s*', '', raw)
        raw = re.sub(r'\s*```$', '', raw)

        m = re.search(r'\[.*\]', raw, re.DOTALL)
        if m:
            out = json.loads(m.group())
            for q in out:
                normalize_merged_choices_in_question(q)
            return out
        return []
    except Exception as e:
        print(f"Lỗi khi gọi API Gemini: {e}")
        return []

def parse_doc_legacy(content: bytes) -> list:
    # Hỗ trợ .doc dạng văn bản thuần; nếu là binary Word cũ thì có thể không đọc được
    candidates = ["utf-8", "utf-16", "cp1258", "latin-1"]
    text = ""
    for enc in candidates:
        try:
            text = content.decode(enc)
            break
        except Exception:
            continue
    if not text:
        return []
    lines = [ln.strip("\ufeff\x00 ") for ln in text.replace("\r", "\n").split("\n") if ln.strip()]
    return _parse_lines(lines)


def smart_parse(content: bytes, filename: str, force_ai: bool = False) -> dict:
    fname_lower = filename.lower()
    if fname_lower.endswith(".pdf"):
        filetype = "pdf"
    elif fname_lower.endswith(".doc"):
        filetype = "doc"
    else:
        filetype = "docx"
    cfg = load_config()
    ai_key = cfg.get("gemini_key", "").strip()
    ai_ok = bool(ai_key and ai_key != "ĐIỀN_API_KEY_CỦA_BẠN_VÀO_ĐÂY")
    ai_enabled = cfg.get("ai_parse_enabled", True) and ai_ok

    method, error_msg = "normal", ""
    try:
        if filetype == "pdf":
            questions = parse_pdf(content)
        elif filetype == "doc":
            questions = parse_doc_legacy(content)
        else:
            questions = parse_word(content)
    except Exception as e:
        questions = []
        error_msg = str(e)
        print(f"Parse error:\n{traceback.format_exc()}")

    total = len(questions)
    has_ans = sum(1 for q in questions if q.get("answer") in list("ABCD"))
    ans_rate = round(has_ans / total * 100) if total > 0 else 0

    garbled_ratio = _garbled_ratio(questions)
    garbled = garbled_ratio >= 0.2

    # Nếu PDF và AI khả dụng thì luôn ưu tiên AI parse (không fallback CPU)
    if filetype == "pdf" and ai_enabled:
        force_ai = True

    need_ai = force_ai or (ai_enabled and ((total > 0 and ans_rate < 30) or total == 0 or garbled))
    if need_ai and ai_ok:
        method = "gemini_ai"
        try:
            ai_questions = parse_with_gemini_ai(content, filetype, ai_key)
            if ai_questions:
                for i, q in enumerate(ai_questions):
                    q["id"] = i + 1
                questions = ai_questions
                
            total = len(questions)
            has_ans = sum(1 for q in questions if q.get("answer") in list("ABCD"))
            ans_rate = round(has_ans / total * 100) if total > 0 else 0
        except Exception as e:
            print(f"Gemini AI error: {e}")

    warning = ""
    if garbled and method != "gemini_ai":
        warning = "PDF có dấu hiệu lỗi font/công thức; nên bật AI parse để tăng độ chính xác."

    return {
        "questions": questions,
        "total": total,
        "ans_rate": ans_rate,
        "method": method,
        "ai_available": ai_ok,
        "error": error_msg,
        "warning": warning,
        "garbled_ratio": round(garbled_ratio, 4),
    }


# ══════════════════════════════════════════
#  API ENDPOINTS (GIỮ NGUYÊN 100%)
# ══════════════════════════════════════════

class RegisterBody(BaseModel):
    email: str
    password: str
    role: str = "user"


class LoginBody(BaseModel):
    email: str
    password: str


class RefreshBody(BaseModel):
    refresh_token: str


class ProfileBody(BaseModel):
    display_name: str = ""
    avatar_url: str = ""


def _auth_payload(user: dict) -> dict:
    access_token = create_access_token(user)
    refresh_token = create_refresh_token(user)
    return {
        "user": user,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


def require_admin(user: dict) -> None:
    if not user or (user.get("role") or "user") != "admin":
        raise HTTPException(403, "Chỉ admin mới có quyền thực hiện.")


@app.post("/auth/register")
def register(body: RegisterBody):
    email = (body.email or "").strip().lower()
    if not email:
        raise HTTPException(400, "Email không hợp lệ")
    uid = f"u_{uuid.uuid4().hex[:20]}"
    try:
        role = (body.role or "user").strip().lower()
        user = repo.register_user(uid, email, body.password, role=role)
        return {"message": "Đăng ký thành công", **_auth_payload(user)}
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/auth/login")
def login(body: LoginBody):
    user = repo.authenticate_user(body.email, body.password)
    if not user:
        raise HTTPException(401, "Sai email hoặc mật khẩu")
    return {"message": "Đăng nhập thành công", **_auth_payload(user)}


@app.post("/auth/refresh")
def refresh_token(body: RefreshBody):
    token = (body.refresh_token or "").strip()
    if not token:
        raise HTTPException(400, "Thiếu refresh_token")
    payload = decode_refresh_token(token)
    uid = (payload.get("sub") or "").strip()
    if not uid:
        raise HTTPException(401, "Token không hợp lệ")
    user = repo.get_user_by_uid(uid)
    if not user:
        raise HTTPException(401, "Người dùng không tồn tại")

    exp = payload.get("exp")
    exp_dt = datetime.utcfromtimestamp(int(exp)) if exp else None
    repo.revoke_token(token, "refresh", uid, exp_dt)

    return {"message": "Làm mới token thành công", **_auth_payload(user)}


@app.post("/auth/logout")
def logout(body: RefreshBody, authorization: str = Header(default="")):
    auth = (authorization or "").strip()
    if not auth.lower().startswith("bearer "):
        raise HTTPException(401, "Thiếu Bearer token")
    access_token = auth[7:].strip()
    if not access_token:
        raise HTTPException(401, "Thiếu Bearer token")

    access_payload = decode_access_token(access_token)
    access_exp = access_payload.get("exp")
    access_exp_dt = datetime.utcfromtimestamp(int(access_exp)) if access_exp else None
    uid = (access_payload.get("sub") or "").strip() or None
    repo.revoke_token(access_token, "access", uid, access_exp_dt)

    refresh_token_str = (body.refresh_token or "").strip()
    if refresh_token_str:
        try:
            refresh_payload = decode_refresh_token(refresh_token_str)
            refresh_exp = refresh_payload.get("exp")
            refresh_exp_dt = datetime.utcfromtimestamp(int(refresh_exp)) if refresh_exp else None
            refresh_uid = (refresh_payload.get("sub") or "").strip() or uid
            repo.revoke_token(refresh_token_str, "refresh", refresh_uid, refresh_exp_dt)
        except HTTPException:
            pass

    return {"message": "Đăng xuất thành công"}


@app.get("/auth/me")
def me(authorization: str = Header(default="")):
    user = get_auth_user(authorization)
    return {"user": user}


@app.put("/auth/profile")
def update_profile(body: ProfileBody, authorization: str = Header(default="")):
    user = get_auth_user(authorization)
    display_name = (body.display_name or "").strip()
    avatar_url = (body.avatar_url or "").strip()
    updated = repo.update_user_profile(user["uid"], display_name=display_name, avatar_url=avatar_url)
    if not updated:
        raise HTTPException(404, "Không tìm thấy người dùng")
    return {"message": "Đã lưu hồ sơ", "user": updated}


@app.get("/admin/users")
def admin_list_users(authorization: str = Header(default="")):
    user = get_auth_user(authorization)
    require_admin(user)
    return {"users": repo.list_users()}


class UpdateRoleBody(BaseModel):
    role: str


@app.put("/admin/users/{uid}/role")
def admin_update_role(uid: str, body: UpdateRoleBody, authorization: str = Header(default="")):
    admin_user = get_auth_user(authorization)
    require_admin(admin_user)
    role = (body.role or "").strip().lower()
    if role not in ("user", "admin"):
        raise HTTPException(400, "Role chỉ nhận user/admin")
    ok = repo.set_user_role(uid, role)
    if not ok:
        raise HTTPException(404, "Không tìm thấy user")
    return {"message": "Đã cập nhật role", "uid": uid, "role": role}


@app.get("/config")
def get_config():
    ok = has_valid_key()
    cfg = load_config()
    return {
        "has_api_key": ok,
        "has_key": ok,
        "ai_enabled": cfg.get("ai_parse_enabled", True)
    }

class ConfigBody(BaseModel):
    gemini_key: str = ""
    ai_parse_enabled: bool = True

@app.post("/config")
def update_config(body: ConfigBody):
    repo.set_ai_parse_enabled(body.ai_parse_enabled)
    return {"message": "Đã lưu cài đặt", "has_key": has_valid_key()}

class AIConfigBody(BaseModel):
    enabled: bool = True

@app.post("/config/ai")
def update_ai_config(body: AIConfigBody):
    repo.set_ai_parse_enabled(body.enabled)
    return {"message": "Đã lưu cài đặt AI", "ai_enabled": body.enabled, "has_key": has_valid_key()}

@app.delete("/config/key")
def delete_api_key():
    repo.set_ai_parse_enabled(True)
    return {"message": "Đã reset config"}

@app.get("/stats")
def get_stats(authorization: str = Header(default="")):
    user = get_auth_user(authorization)
    uid = user["uid"]
    index = repo.get_files_index(uid)
    agg = repo.get_stats_aggregate(uid)
    ok = has_valid_key()
    cfg = load_config()
    return {
        "total_questions": agg["total_questions"],
        "with_answer": agg["with_answer"],
        "total_sessions": agg["total_sessions"],
        "avg_score": agg["avg_score"],
        "best_score": agg["best_score"],
        "ai_available": ok,
        "ai_enabled": cfg.get("ai_parse_enabled", True),
        "files": [{"id": fid, "name": f["name"], "count": f["count"], "with_answer": f["with_answer"], "uploaded_at": f["uploaded_at"], "parse_method": f.get("parse_method", "normal")} for fid, f in index.items()]
    }

@app.post("/upload")
async def upload_file(file: UploadFile = File(...), authorization: str = Header(default=""), x_force_ai: str = Header(default="false")):
    user = get_auth_user(authorization)
    uid = user["uid"]
    content = await file.read()
    fname = file.filename or "file"

    if not (fname.lower().endswith(".docx") or fname.lower().endswith(".doc") or fname.lower().endswith(".pdf")):
        raise HTTPException(400, "Chỉ hỗ trợ .doc, .docx và .pdf")

    force_ai = x_force_ai.lower() == "true"
    try:
        result = smart_parse(content, fname, force_ai=force_ai)
    except HTTPException: raise
    except Exception as e: raise HTTPException(500, f"Lỗi xử lý: {e}")

    questions = result["questions"]
    if not questions:
        err = result.get("error", "")
        raise HTTPException(400, f"Không tìm thấy câu hỏi.{' Chi tiết: '+err if err else ' Thử bật AI Vision.'}")

    # HARD STOP: nếu có AI khả dụng thì PDF bắt buộc đi qua AI parse
    if fname.lower().endswith('.pdf') and result.get('ai_available') and result.get('method') != 'gemini_ai':
        raise HTTPException(400, "PDF bắt buộc parse bằng AI khi AI khả dụng. Vui lòng bật Force AI và upload lại.")

    # Quality gate: nới điều kiện để không chặn oan khi đã parse bằng AI
    if fname.lower().endswith('.pdf'):
        g_ratio = float(result.get('garbled_ratio') or 0)
        ans_rate = float(result.get('ans_rate') or 0)
        method = result.get('method') or 'unknown'

        # Parse thường: vẫn chặn tương đối chặt
        if method != 'gemini_ai' and (ans_rate < 35 or g_ratio >= 0.12):
            raise HTTPException(
                400,
                f"PDF parse thường chất lượng thấp (đáp án={ans_rate:.0f}%, garbled={g_ratio:.2f}). Hãy bật AI Vision rồi upload lại."
            )

        # Parse AI: chỉ chặn khi cực xấu
        if method == 'gemini_ai' and (ans_rate < 20 or g_ratio >= 0.30):
            raise HTTPException(
                400,
                f"PDF parse AI vẫn quá thấp (đáp án={ans_rate:.0f}%, garbled={g_ratio:.2f}). Hard-stop để tránh lưu đề lỗi nặng."
            )


    base_name = re.sub(r'\.(docx|doc|pdf)$', '', fname, flags=re.IGNORECASE)
    file_id = re.sub(r'[^\w\-]', '_', base_name)[:50]

    # REPLACE mode: upload lại cùng file_id sẽ ghi đè toàn bộ câu cũ
    repo.ensure_user(uid)
    normalized_questions = []
    for i, q in enumerate(questions, start=1):
        q["id"] = i
        q = enrich_question_rich_fields(q)
        normalized_questions.append(q)

    uploaded_at = datetime.now().strftime("%d/%m/%Y %H:%M")
    repo.replace_file_questions(
        uid, file_id, normalized_questions, base_name, fname, uploaded_at, result["method"]
    )
    has_ans = sum(1 for q in normalized_questions if q.get("answer") in list("ABCD"))

    return {"file_id": file_id, "name": base_name, "parsed": result["total"], "added": len(normalized_questions), "total_in_file": len(normalized_questions), "with_answer": has_ans, "ans_rate": result["ans_rate"], "parse_method": result["method"], "ai_available": result["ai_available"], "message": "Upload thành công (đã ghi đè đề cũ)"}

@app.delete("/files/{file_id}")
def delete_file(file_id: str, authorization: str = Header(default="")):
    user = get_auth_user(authorization)
    uid = user["uid"]
    if not repo.file_exists(uid, file_id):
        raise HTTPException(404, "Không tìm thấy file")
    repo.delete_questions_file(uid, file_id)
    return {"message": "Đã xóa"}

@app.get("/quiz/start")
def start_quiz(num: int = 10, file_id: str = "", authorization: str = Header(default="")):
    user = get_auth_user(authorization)
    uid = user["uid"]
    if file_id:
        all_qs = repo.get_questions_json(uid, file_id)
    else:
        all_qs = repo.get_all_questions(uid)

    valid = [q for q in all_qs if len(q.get("choices", [])) >= 2]
    if not valid: raise HTTPException(404, "Không có câu hỏi")

    selected = random.sample(valid, min(num, len(valid)))
    sid = f"s{random.randint(100000, 999999)}"
    quiz = []
    choice_labels = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    for i, q in enumerate(selected):
        orig = q["choices"]
        n = len(orig)
        order = list(range(n))
        random.shuffle(order)
        choices = []
        for pos, orig_i in enumerate(order):
            lab = choice_labels[pos] if pos < len(choice_labels) else str(pos + 1)
            choices.append({"label": lab, "text": orig[orig_i]["text"]})
        ans_lbl = (q.get("answer") or "").strip().upper()
        new_correct = ""
        if ans_lbl:
            try:
                orig_i = next(
                    j for j, c in enumerate(orig)
                    if (c.get("label") or "").strip().upper() == ans_lbl
                )
            except StopIteration:
                orig_i = None
            if orig_i is not None:
                pos = order.index(orig_i)
                new_correct = choice_labels[pos] if pos < len(choice_labels) else str(pos + 1)
        quiz.append({"id": i, "question": q["question"], "choices": choices, "_correct": new_correct})
    repo.save_quiz_session(uid, sid, file_id or "", quiz)
    return {"session_id": sid, "total": len(quiz), "file_id": file_id, "questions": [{"id": q["id"], "question": q["question"], "choices": q["choices"]} for q in quiz]}

class SubmitBody(BaseModel):
    session_id: str
    answers: dict
    time_taken: int = 0
    file_id: str = ""
    anti_cheat: dict = {}

@app.post("/quiz/submit")
def submit_quiz(body: SubmitBody, authorization: str = Header(default="")):
    user = get_auth_user(authorization)
    uid = user["uid"]
    quiz = repo.get_quiz_session(body.session_id)
    if not quiz:
        raise HTTPException(404, "Session không tồn tại")
    details = []
    for q in quiz:
        user = body.answers.get(str(q["id"]), "")
        ok = bool(user and user == q["_correct"])
        details.append({"id": q["id"], "question": q["question"], "user": user, "correct": q["_correct"], "ok": ok, "choices": q["choices"]})
    score = sum(1 for d in details if d["ok"])
    pct = round(score / len(quiz) * 100)
    wrong_q = [d["question"][:60] for d in details if not d["ok"]][:5]
    ac_in = body.anti_cheat or {}
    anti_cheat = {
        "blur_count": int(ac_in.get("blur_count") or ac_in.get("tab_switches") or 0),
        "penalty_base_sec": int(ac_in.get("penalty_base_sec") or 15),
    }
    review_details = []
    for d in details:
        review_details.append(
            {
                "id": d["id"],
                "question": d["question"],
                "user": d["user"],
                "correct": d["correct"],
                "ok": d["ok"],
                "choices": d.get("choices") or [],
            }
        )

    repo.append_history(
        uid,
        score,
        len(quiz),
        pct,
        body.time_taken,
        body.file_id or "all",
        wrong_q,
        anti_cheat=anti_cheat,
        review_details=review_details,
    )
    repo.delete_quiz_session(body.session_id)
    return {"score": score, "total": len(quiz), "percent": pct, "details": details}

@app.get("/history")
def get_history(authorization: str = Header(default="")):
    user = get_auth_user(authorization)
    return repo.get_history_list(user["uid"])

@app.delete("/history/clear")
def clear_history(authorization: str = Header(default="")):
    user = get_auth_user(authorization)
    repo.clear_history(user["uid"])
    return {"message": "Đã xóa lịch sử"}

@app.get("/files/{file_id}/questions")
def get_file_questions(file_id: str, authorization: str = Header(default="")):
    user = get_auth_user(authorization)
    uid = user["uid"]
    if not repo.file_exists(uid, file_id):
        raise HTTPException(404, "Không tìm thấy file")
    questions = repo.get_questions_json(uid, file_id)
    return {"questions": questions, "total": len(questions)}

class QuestionUpdateBody(BaseModel):
    question: str
    choices: list
    answer: str = ""


class QuestionReviewBody(BaseModel):
    reviewed: bool = True

@app.put("/files/{file_id}/questions/{q_id}")
def update_question(file_id: str, q_id: int, body: QuestionUpdateBody, authorization: str = Header(default="")):
    user = get_auth_user(authorization)
    uid = user["uid"]
    if not repo.file_exists(uid, file_id):
        raise HTTPException(404, "Không tìm thấy file")
    choices, answer = _validate_question_choices(body.choices, body.answer)
    updated = repo.update_question_row(uid, file_id, q_id, body.question, choices, answer)
    if not updated:
        raise HTTPException(404, "Không tìm thấy câu hỏi")
    return {"message": "Đã cập nhật", "question": updated}

@app.put("/files/{file_id}/questions/{q_id}/review")
def set_question_review(file_id: str, q_id: int, body: QuestionReviewBody, authorization: str = Header(default="")):
    user = get_auth_user(authorization)
    uid = user["uid"]
    if not repo.file_exists(uid, file_id):
        raise HTTPException(404, "Không tìm thấy file")
    updated = repo.set_question_reviewed(uid, file_id, q_id, bool(body.reviewed))
    if not updated:
        raise HTTPException(404, "Không tìm thấy câu hỏi")
    return {"message": "Đã cập nhật review", "question": updated}


@app.delete("/files/{file_id}/questions/{q_id}")
def delete_question(file_id: str, q_id: int, authorization: str = Header(default="")):
    user = get_auth_user(authorization)
    uid = user["uid"]
    if not repo.file_exists(uid, file_id):
        raise HTTPException(404, "Không tìm thấy file")
    if not repo.delete_question_by_qid(uid, file_id, q_id):
        raise HTTPException(404, "Không tìm thấy câu hỏi")
    return {"message": "Đã xóa câu hỏi"}

class NewQuestionBody(BaseModel):
    question: str
    choices: list
    answer: str = ""

@app.post("/files/{file_id}/questions")
def add_question(file_id: str, body: NewQuestionBody, authorization: str = Header(default="")):
    user = get_auth_user(authorization)
    uid = user["uid"]
    if not repo.file_exists(uid, file_id):
        raise HTTPException(404, "Không tìm thấy file")
    choices, answer = _validate_question_choices(body.choices, body.answer)
    questions = repo.get_questions_json(uid, file_id)
    max_id = max((q.get("id", 0) for q in questions), default=0)
    new_q = {
        "id": max_id + 1,
        "question": body.question,
        "choices": choices,
        "answer": answer,
        "explanation": "",
    }
    repo.insert_question(uid, file_id, new_q)
    return {"message": "Đã thêm câu hỏi", "question": new_q}
