from fastapi import FastAPI, UploadFile, File, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json, random, re, os, base64, io, traceback
from datetime import datetime
from pathlib import Path
import google.generativeai as genai

# ══ CẤU HÌNH - THAY KEY VÀO ĐÂY ══
GEMINI_API_KEY = "AIzaSyB13ZOCY6jrufnZu7OLuN7zdbb7o00YF48"
# ══════════════════════════════════

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

DATA_DIR = Path("data/users")
DATA_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_FILE = Path("data/config.json")
SESSIONS: dict = {}

def user_dir(uid):
    d = DATA_DIR / re.sub(r'[^\w]', '_', uid or "guest")
    d.mkdir(parents=True, exist_ok=True)
    return d

def files_index_path(uid): return user_dir(uid) / "files_index.json"
def history_path(uid):     return user_dir(uid) / "history.json"

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

def get_uid(x_user_id: str = "") -> str:
    return (x_user_id or "guest").strip()

def load_config():
    cfg = {"gemini_key": GEMINI_API_KEY, "ai_parse_enabled": True}
    try:
        if CONFIG_FILE.exists():
            saved = load_json(CONFIG_FILE, {})
            cfg["ai_parse_enabled"] = saved.get("ai_parse_enabled", True)
    except:
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


def split_choice_segments(text: str) -> list:
    if not text or not str(text).strip():
        return []
    s = str(text).strip()
    pat = re.compile(r"(?:^|(?<=\s))([A-D])[\.\)]\s*", re.IGNORECASE)
    matches = list(pat.finditer(s))
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


def normalize_merged_choices_in_question(q: dict) -> None:
    chs = q.get("choices") or []
    if not chs:
        return
    new_chs = []
    seen = set()
    for ch in chs:
        label = (ch.get("label") or "?").upper()
        t = (ch.get("text") or "").strip()
        parts = split_choice_segments(t)
        if len(parts) >= 2:
            for p in parts:
                lb = p["label"]
                if lb not in seen:
                    seen.add(lb)
                    new_chs.append(p)
        else:
            if label in "ABCD" and label not in seen:
                seen.add(label)
                new_chs.append({"label": label, "text": t})
    if new_chs:
        q["choices"] = sorted(new_chs, key=lambda x: "ABCD".index(x["label"]) if x["label"] in "ABCD" else 9)


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
    choice_pat = re.compile(r"(?:^|(?<=\s))([A-D])[\.\)]\s*", re.IGNORECASE)
    for item in lines:
        text, hl = item["text"], item["hl"]
        m = re.match(r"^(?:C[âa]u\s*)?(\d+)[\.\:\)]\s*(.+)", text, re.IGNORECASE)
        if m and not re.match(r"^[A-Da-d][\.\)]", m.group(2)):
            if cur and len(cur["choices"]) >= 2:
                questions.append(cur)
            rest = m.group(2).strip()
            embedded = split_choice_segments(rest)
            if len(embedded) >= 2:
                fm = choice_pat.search(rest)
                q_stem = rest[: fm.start()].strip() if fm else rest
                cur = {"id": int(m.group(1)), "question": q_stem, "choices": list(embedded), "answer": "", "explanation": ""}
            else:
                cur = {"id": int(m.group(1)), "question": rest, "choices": [], "answer": "", "explanation": ""}
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
            except: pass
        try: all_questions.extend(parse_pdf_inline(page, hl_rects))
        except: pass
    for i, q in enumerate(all_questions):
        q["id"] = i + 1
    for q in all_questions:
        normalize_merged_choices_in_question(q)
    return all_questions

# ══════════════════════════════════════════
#  WORD PARSER — (SIÊU CẤP - XỬ LÝ BẢNG GỘP DÒNG)
# ══════════════════════════════════════════

def _parse_lines(lines):
    questions, cur = [], None
    choice_pat = re.compile(r"(?:^|(?<=\s))([A-D])[\.\)]\s*", re.IGNORECASE)
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
                fm = choice_pat.search(rest)
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

def parse_word(content: bytes) -> list:
    import docx, io
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
                
                # Quét tìm text bôi đậm hoặc tô màu (Nhận diện đáp án)
                correct_keywords = [[], [], [], []]
                for j in range(4):
                    idx = 3 + j
                    if idx < len(cells):
                        for p in cells[idx].paragraphs:
                            for run in p.runs:
                                rt = run.text.strip()
                                if rt and (run.bold or (run.font.color and run.font.color.rgb and str(run.font.color.rgb) != "000000")):
                                    if len(rt) > 1: correct_keywords[j].append(rt)
                
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
                                # Kiểm tra xem đáp án có nằm trong phần chữ in đậm/tô màu không
                                if any(k in ans_text for k in correct_keywords[j]):
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
            import docx, io
            doc = docx.Document(io.BytesIO(content))
            text_lines = [p.text for p in doc.paragraphs if p.text.strip()]
            for table in doc.tables:
                for row in table.rows:
                    text_lines.append(" | ".join(c.text.replace('\n', ' ').strip() for c in row.cells))
            
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

def smart_parse(content: bytes, filename: str, force_ai: bool = False) -> dict:
    fname_lower = filename.lower()
    filetype = "pdf" if fname_lower.endswith(".pdf") else "docx"
    cfg = load_config()
    ai_key = cfg.get("gemini_key", "").strip()
    ai_ok = bool(ai_key and ai_key != "ĐIỀN_API_KEY_CỦA_BẠN_VÀO_ĐÂY")
    ai_enabled = cfg.get("ai_parse_enabled", True) and ai_ok

    method, error_msg = "normal", ""
    try:
        questions = parse_pdf(content) if filetype == "pdf" else parse_word(content)
    except Exception as e:
        questions = []
        error_msg = str(e)
        print(f"Parse error:\n{traceback.format_exc()}")

    total = len(questions)
    has_ans = sum(1 for q in questions if q.get("answer") in list("ABCD"))
    ans_rate = round(has_ans / total * 100) if total > 0 else 0

    need_ai = force_ai or (ai_enabled and ((total > 0 and ans_rate < 30) or total == 0))
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


# ══════════════════════════════════════════
#  API ENDPOINTS (GIỮ NGUYÊN 100%)
# ══════════════════════════════════════════

@app.get("/config")
def get_config():
    ok = has_valid_key()
    cfg = load_config()
class ConfigBody(BaseModel):
    gemini_key: str = ""
    ai_parse_enabled: bool = True

@app.post("/config")
def update_config(body: ConfigBody):
    save_json(CONFIG_FILE, {"ai_parse_enabled": body.ai_parse_enabled})
    return {"message": "Đã lưu cài đặt", "has_key": has_valid_key()}

@app.delete("/config/key")
def delete_api_key():
    save_json(CONFIG_FILE, {"ai_parse_enabled": True})
    return {"message": "Đã reset config"}

@app.get("/stats")
def get_stats(x_user_id: str = Header(default="guest")):
    uid = get_uid(x_user_id)
    index = load_json(files_index_path(uid), {})
    history = load_json(history_path(uid), [])
    ok = has_valid_key()
    cfg = load_config()
    return {
        "total_questions": sum(f["count"] for f in index.values()),
        "with_answer": sum(f["with_answer"] for f in index.values()),
        "total_sessions": len(history),
        "avg_score": round(sum(h["percent"] for h in history)/len(history)) if history else 0,
        "best_score": max((h["percent"] for h in history), default=0),
        "ai_available": ok,
        "ai_enabled": cfg.get("ai_parse_enabled", True),
        "files": [{"id": fid, "name": f["name"], "count": f["count"], "with_answer": f["with_answer"], "uploaded_at": f["uploaded_at"], "parse_method": f.get("parse_method", "normal")} for fid, f in index.items()]
    }

@app.post("/upload")
async def upload_file(file: UploadFile = File(...), x_user_id: str = Header(default="guest"), x_force_ai: str = Header(default="false")):
    uid = get_uid(x_user_id)
    content = await file.read()
    fname = file.filename or "file"

    if not (fname.lower().endswith(".docx") or fname.lower().endswith(".pdf")):
        raise HTTPException(400, "Chỉ hỗ trợ .docx và .pdf")

    force_ai = x_force_ai.lower() == "true"
    try:
        result = smart_parse(content, fname, force_ai=force_ai)
    except HTTPException: raise
    except Exception as e: raise HTTPException(500, f"Lỗi xử lý: {e}")

    questions = result["questions"]
    if not questions:
        err = result.get("error", "")
        raise HTTPException(400, f"Không tìm thấy câu hỏi.{' Chi tiết: '+err if err else ' Thử bật AI Vision.'}")

    base_name = re.sub(r'\.(docx|pdf)$', '', fname, flags=re.IGNORECASE)
    file_id = re.sub(r'[^\w\-]', '_', base_name)[:50]

    index = load_json(files_index_path(uid), {})
    q_file = user_dir(uid) / f"{file_id}.json"
    existing = load_json(q_file, [])
    exist_keys = {q["question"][:60].lower() for q in existing}
    added, max_id = 0, max((q.get("id", 0) for q in existing), default=0)
    for q in questions:
        key = q["question"][:60].lower()
        if key not in exist_keys:
            max_id += 1
            q["id"] = max_id
            existing.append(q)
            exist_keys.add(key)
            added += 1

    save_json(q_file, existing)
    has_ans = sum(1 for q in existing if q.get("answer") in list("ABCD"))
    index[file_id] = {"name": base_name, "filename": fname, "count": len(existing), "with_answer": has_ans, "uploaded_at": datetime.now().strftime("%d/%m/%Y %H:%M"), "file_id": file_id, "parse_method": result["method"]}
    save_json(files_index_path(uid), index)

    return {"file_id": file_id, "name": base_name, "parsed": result["total"], "added": added, "total_in_file": len(existing), "with_answer": has_ans, "ans_rate": result["ans_rate"], "parse_method": result["method"], "ai_available": result["ai_available"], "message": "Upload thành công"}

@app.delete("/files/{file_id}")
def delete_file(file_id: str, x_user_id: str = Header(default="guest")):
    uid = get_uid(x_user_id)
    index = load_json(files_index_path(uid), {})
    if file_id not in index: raise HTTPException(404, "Không tìm thấy file")
    q_file = user_dir(uid) / f"{file_id}.json"
    if q_file.exists(): q_file.unlink()
    del index[file_id]
    save_json(files_index_path(uid), index)
    return {"message": "Đã xóa"}

@app.get("/quiz/start")
def start_quiz(num: int = 10, file_id: str = "", x_user_id: str = Header(default="guest")):
    uid = get_uid(x_user_id)
    if file_id:
        all_qs = load_json(user_dir(uid) / f"{file_id}.json", [])
    else:
        index = load_json(files_index_path(uid), {})
        all_qs = []
        for fid in index: all_qs.extend(load_json(user_dir(uid) / f"{fid}.json", []))

    valid = [q for q in all_qs if len(q.get("choices", [])) >= 2]
    if not valid: raise HTTPException(404, "Không có câu hỏi")

    selected = random.sample(valid, min(num, len(valid)))
    sid = f"s{random.randint(100000, 999999)}"
    quiz = []
    for i, q in enumerate(selected):
        choices = q["choices"].copy()
        random.shuffle(choices)
        correct_text = next((c["text"] for c in q["choices"] if c["label"] == q.get("answer", "")), None)
        new_correct = next((c["label"] for c in choices if c["text"] == correct_text), "") if correct_text else ""
        quiz.append({"id": i, "question": q["question"], "choices": choices, "_correct": new_correct})
    SESSIONS[sid] = quiz
    return {"session_id": sid, "total": len(quiz), "file_id": file_id, "questions": [{"id": q["id"], "question": q["question"], "choices": q["choices"]} for q in quiz]}

class SubmitBody(BaseModel):
    session_id: str
    answers: dict
    time_taken: int = 0
    file_id: str = ""

@app.post("/quiz/submit")
def submit_quiz(body: SubmitBody, x_user_id: str = Header(default="guest")):
    uid = get_uid(x_user_id)
    quiz = SESSIONS.get(body.session_id)
    if not quiz: raise HTTPException(404, "Session không tồn tại")
    details = []
    for q in quiz:
        user = body.answers.get(str(q["id"]), "")
        ok = bool(user and user == q["_correct"])
        details.append({"id": q["id"], "question": q["question"], "user": user, "correct": q["_correct"], "ok": ok, "choices": q["choices"]})
    score = sum(1 for d in details if d["ok"])
    pct = round(score / len(quiz) * 100)
    history = load_json(history_path(uid), [])
    history.append({"id": len(history)+1, "date": datetime.now().strftime("%d/%m/%Y %H:%M"), "score": score, "total": len(quiz), "percent": pct, "time_taken": body.time_taken, "file_id": body.file_id or "all", "wrong_questions": [d["question"][:60] for d in details if not d["ok"]][:5]})
    save_json(history_path(uid), history)
    del SESSIONS[body.session_id]
    return {"score": score, "total": len(quiz), "percent": pct, "details": details}

@app.get("/history")
def get_history(x_user_id: str = Header(default="guest")):
    return load_json(history_path(get_uid(x_user_id)), [])

@app.delete("/history/clear")
def clear_history(x_user_id: str = Header(default="guest")):
    save_json(history_path(get_uid(x_user_id)), [])
    return {"message": "Đã xóa lịch sử"}

@app.get("/files/{file_id}/questions")
def get_file_questions(file_id: str, x_user_id: str = Header(default="guest")):
    uid = get_uid(x_user_id)
    q_file = user_dir(uid) / f"{file_id}.json"
    if not q_file.exists(): raise HTTPException(404, "Không tìm thấy file")
    questions = load_json(q_file, [])
    return {"questions": questions, "total": len(questions)}

class QuestionUpdateBody(BaseModel):
    question: str
    choices: list
    answer: str = ""

@app.put("/files/{file_id}/questions/{q_id}")
def update_question(file_id: str, q_id: int, body: QuestionUpdateBody, x_user_id: str = Header(default="guest")):
    uid = get_uid(x_user_id)
    q_file = user_dir(uid) / f"{file_id}.json"
    if not q_file.exists(): raise HTTPException(404, "Không tìm thấy file")
    questions = load_json(q_file, [])
    for i, q in enumerate(questions):
        if q.get("id") == q_id:
            questions[i]["question"] = body.question
            questions[i]["choices"] = body.choices
            questions[i]["answer"] = body.answer
            save_json(q_file, questions)
            _update_index(uid, file_id, questions)
            return {"message": "Đã cập nhật", "question": questions[i]}
    raise HTTPException(404, "Không tìm thấy câu hỏi")

@app.delete("/files/{file_id}/questions/{q_id}")
def delete_question(file_id: str, q_id: int, x_user_id: str = Header(default="guest")):
    uid = get_uid(x_user_id)
    q_file = user_dir(uid) / f"{file_id}.json"
    if not q_file.exists(): raise HTTPException(404, "Không tìm thấy file")
    questions = load_json(q_file, [])
    new_qs = [q for q in questions if q.get("id") != q_id]
    if len(new_qs) == len(questions): raise HTTPException(404, "Không tìm thấy câu hỏi")
    save_json(q_file, new_qs)
    _update_index(uid, file_id, new_qs)
    return {"message": "Đã xóa câu hỏi"}

class NewQuestionBody(BaseModel):
    question: str
    choices: list
    answer: str = ""

@app.post("/files/{file_id}/questions")
def add_question(file_id: str, body: NewQuestionBody, x_user_id: str = Header(default="guest")):
    uid = get_uid(x_user_id)
    q_file = user_dir(uid) / f"{file_id}.json"
    if not q_file.exists(): raise HTTPException(404, "Không tìm thấy file")
    questions = load_json(q_file, [])
    max_id = max((q.get("id", 0) for q in questions), default=0)
    new_q = {"id": max_id + 1, "question": body.question, "choices": body.choices, "answer": body.answer}
    questions.append(new_q)
    save_json(q_file, questions)
    _update_index(uid, file_id, questions)
    return {"message": "Đã thêm câu hỏi", "question": new_q}

def _update_index(uid, file_id, questions):
    index = load_json(files_index_path(uid), {})
    if file_id in index:
        index[file_id]["count"] = len(questions)
        index[file_id]["with_answer"] = sum(1 for q in questions if q.get("answer") in list("ABCD"))
        save_json(files_index_path(uid), index)