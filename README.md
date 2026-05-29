# CobraQ — Hệ thống Ôn tập Thông minh

## Tổng quan

Hệ thống quiz thông minh hỗ trợ học sinh ôn tập từ đề thi upload (Word/PDF), tích hợp AI để nhận dạng đáp án từ bảng tô màu và gia sư AI theo ngữ liệu.

## Kiến trúc hiện tại

```
CobraQ/
├── CobraQ_v3.html           # Frontend SPA (vanilla JS) — JWT auth ✅
├── backend/                 # ✅ Backend đã tách cấu trúc
│   ├── app/
│   │   ├── main.py        # FastAPI app entry point
│   │   ├── api/           # auth, quiz, files, config, tutoring, evaluation, users, admin
│   │   ├── core/          # config, security (JWT/bcrypt), audit
│   │   ├── services/      # trust_layer, evaluation, vector_service ✅
│   │   └── db/            # user_store (JSON)
│   └── requirements.txt
├── evaluation/              # ✅ Evaluation pipeline
│   ├── metrics/
│   │   ├── hallucination.py  # Hallucination, citation, block rate
│   │   ├── retrieval.py      # MRR, HitRate@k, Precision@k, NDCG@k
│   │   └── precision.py       # Quiz accuracy, score distribution, role perf
│   ├── dashboard.html         # ✅ Evaluation dashboard
│   └── __init__.py
├── data/                    # Uploads, audit logs, evaluation logs
│   ├── audit_log.jsonl     # Audit events
│   └── evaluation_logs.jsonl
└── venv/
```

**Frontend:** Single-page app vanilla JS, giao tiếp REST với backend tại `http://127.0.0.1:8000`.

**Backend:** FastAPI monolith — xử lý upload, quiz, AI Vision, session, history trong 1 file.

**Data:** SQLite nhẹ.

**AI:** Claude Vision API — hiện chỉ parse đáp án từ bảng tô màu.

**Auth:** JWT Bearer token + bcrypt — **bảo mật, backend `core/security.py` + frontend `CobraQ_v3.html` đã kết nối ✅**

## Roadmap Kiến trúc

### Giai đoạn 0 — Tái cấu trúc Backend (1-2 ngày) ✅ HOÀN THÀNH

```
backend/
├── app/
│   ├── api/           # Endpoints: auth, quiz, files, config, tutoring, evaluation, users, admin
│   ├── core/          # config, security, audit
│   ├── services/      # trust_layer, evaluation, vector_service
│   ├── models/        # Pydantic models
│   ├── db/            # JSON user store
│   └── main.py
├── requirements.txt
└── .env
```

### Giai đoạn 1 — Bảo mật (Tuần 1) ✅ HOÀN THÀNH

**Đã hoàn thành trước khi pilot trường học.**

- **JWT auth** — thay `btoa()` localStorage ✅
- **Password hashing** — `bcrypt` qua `passlib` ✅
- **Role-based access** — student / teacher / admin ✅
- **Audit log** — log mọi hành động (login, quiz, upload, AI query) ✅
- **Output sanitization** — chặn XSS trong AI response ✅

```python
# Role enum
class Role(str, Enum):
    STUDENT = "student"
    TEACHER = "teacher"
    ADMIN = "admin"

# Decorator RBAC
@require_role(Role.TEACHER, Role.ADMIN)
```

### Giai đoạn 2 — AI Pipeline & Trust Layer (Tuần 2-3) ✅ HOÀN THÀNH

**Mục tiêu:** AI tutoring chat theo ngữ liệu, mỗi câu trả lời phải có citation.

```
evaluation/
├── metrics/
│   ├── hallucination.py   # ✅ Hallucination rate, citation rate, block rate
│   ├── retrieval.py        # ✅ MRR, HitRate@k, Precision@k, NDCG@k
│   └── precision.py        # ✅ Quiz accuracy, score distribution, role perf
├── dashboard.html          # ✅ Evaluation dashboard (mở trong trình duyệt)
└── __init__.py
```

**Trust Layer đã implement (`backend/app/services/trust_layer.py`):**

```python
class TrustLayer:
    min_confidence: float = 0.5
    min_chunks: int = 1

    def should_block(self, chunks, confidence) -> bool:
        return len(chunks) < self.min_chunks or confidence < self.min_confidence
```

Mỗi AI response trả về:
- `source_chunks`: đoạn text gốc từ ngữ liệu
- `citations`: `{chunk_id, page, text, confidence}`
- `blocked`: True nếu không có evidence

**Dashboard:** Mở `evaluation/dashboard.html` trong trình duyệt, kết nối tới `http://127.0.0.1:8000`.

**Vector DB:** ChromaDB / FAISS cho semantic search (TODO, hiện dùng keyword overlap).

### Giai đoạn 3 — AI Tutoring Module (Tuần 2-3) ✅ HOÀN THÀNH

Endpoint `/api/tutoring/chat` đã implement:

```
POST /api/tutoring/chat
Body: { message, file_id?, session_id?, history? }
Response: { message, blocked, block_reason, citations: [{text, chunk_id, source, score}], session_id }
```

- ✅ Retrieve chunks từ file_id (keyword search)
- ✅ Trust layer chặn nếu không đủ evidence
- ✅ Sanitize output bằng `bleach`
- ✅ Evaluation log ghi mọi query
- ⚠️ Placeholder: chưa gọi Claude/GPT API thực sự (TODO)
- ⚠️ Rate limiting per user (TODO)
- ⚠️ Giới hạn context window (TODO)

### Giai đoạn 4 — Evaluation Pipeline (Tuần 4+) ✅ HOÀN THÀNH

**Metrics đã implement:**

| Metric | Mô tả | Target | File |
|--------|--------|--------|------|
| Hallucination Rate | % câu trả lời không có citation | < 5% | `metrics/hallucination.py` |
| Citation Rate | % responses có citation | > 80% | `metrics/hallucination.py` |
| Block Rate | % queries bị trust layer chặn | < 5% | `metrics/hallucination.py` |
| MRR | Mean Reciprocal Rank retrieval | > 0.7 | `metrics/retrieval.py` |
| HitRate@5 | % queries có relevant doc trong top-5 | > 80% | `metrics/retrieval.py` |
| NDCG@5 | Normalized DCG | > 0.6 | `metrics/retrieval.py` |
| Quiz Accuracy | % đáp án đúng | theo baseline | `metrics/precision.py` |
| Answer Coverage | % câu hỏi có đáp án | > 70% | `metrics/precision.py` |
| Score Distribution | Bucket phân bố điểm | — | `metrics/precision.py` |
| Role Performance | Accuracy theo role | — | `metrics/precision.py` |

**API endpoints:**

```
GET /evaluation/metrics         # Quiz + overall metrics
GET /evaluation/logs            # Raw evaluation log entries
GET /evaluation/hallucination   # Hallucination metrics + high-violation entries
GET /evaluation/retrieval      # MRR, HitRate, Precision, NDCG
```

**Dashboard:** Mở `evaluation/dashboard.html` (auto-refresh 60s, KPI cards, charts, session list).

**Evaluation log structure:**

```json
{
  "session_id": "uuid",
  "timestamp": "ISO8601",
  "user_id": "email",
  "role": "student|teacher",
  "event_type": "quiz_answer|tutoring_query",
  "question_id": "q123",
  "student_answer": "A",
  "correct_answer": "B",
  "is_correct": false,
  "time_taken_ms": 15000,
  "ai_used": false,
  "retrieval_chunks": ["chunk_id"],
  "hallucination_detected": false,
  "citation_present": true
}
```

### Giai đoạn 5 — Frontend Module hóa (Tuần 5+)

Tách HTML thành module ESM hoặc chuyển sang React/Vue:
- `src/components/` — UI components
- `src/pages/` — Dashboard, Quiz, Upload, History
- `src/services/` — API service layer
- `src/stores/` — State management (Zustand)

### Giai đoạn 6 — Role-Based Access Control ✅ HOÀN THÀNH

**Vai trò:**

| Vai trò | Quyền |
|---------|-------|
| `student` (mặc định) | Làm bài quiz, xem lịch sử, upload đề cá nhân, tham gia nhóm |
| `teacher` | + Tạo/quản lý nhóm, gán đề cho nhóm, chat AI gia sư, xem đánh giá AI |
| `admin` | + Quản lý người dùng (đổi vai trò, xóa), xem thống kê hệ thống, nhật ký audit |

**Frontend pages theo vai trò:**

- **Tất cả:** Dashboard, Làm bài, Lịch sử, Tệp đã tải, Cài đặt
- **Teacher/Admin thêm:** Nhóm của tôi, 💬 Gia sư AI, 📚 Quản lý đề, 📊 Đánh giá AI
- **Admin thêm:** 👥 Người dùng, 📈 Thống kê hệ thống, 📋 Nhật ký hệ thống

**API endpoints mới:**

```
GET  /users/                  # List all users (admin)
PUT  /users/{email}/role     # Update role (admin)
DELETE /users/{email}         # Delete user (admin)
GET  /admin/stats             # System-wide stats (admin)
GET  /admin/audit             # Audit logs (admin)
GET  /admin/activity          # Daily activity (admin)
```

**RBAC trên files:** Teacher/Admin có thể xem, chỉnh sửa, xóa đề của bất kỳ user nào qua header `x-file-for`.

### Giai đoạn 6b — Quản lý Nhóm / Lớp học ✅ HOÀN THÀNH

**Tính năng:**

| Hành động | Mô tả |
|-----------|-------|
| GV tạo nhóm | Tên nhóm + mã nhóm tự động 8 ký tự |
| GV gán đề | Upload file đã parse vào nhóm với **số câu hỏi** và **thời gian giới hạn** tùy chỉnh |
| HS tham gia nhóm | Nhập mã nhóm để tham gia (tham gia nhiều nhóm được) |
| HS làm bài nhóm | Làm đề được gán, thời gian và số câu theo cài đặt của GV |
| GV xem điểm | Bảng điểm chi tiết từng HS cho từng đề |
| Chỉnh sửa cài đặt | Popup UI cho GV thay đổi số câu / thời gian sau khi gán |

**Database files:**

```
backend/app/db/
├── group_store.py      # Lưu nhóm: thành viên, file đã gán + cài đặt
└── group_scores.py     # Lưu điểm HS: đáp án, thời gian, phần trăm
```

**API endpoints nhóm:**

```
POST /groups/              # Tạo nhóm (teacher)
GET  /groups/my            # Nhóm của tôi (teacher=own, student=joined)
POST /groups/join          # Tham gia nhóm (student)
DELETE /groups/leave/{code} # Rời nhóm (student)
PUT  /groups/{code}       # Sửa tên nhóm (teacher)
DELETE /groups/{code}      # Xóa nhóm (teacher)

POST   /groups/{code}/files              # Gán đề + cài đặt (teacher)
GET    /groups/{code}/files             # Danh sách đề + cài đặt (all)
PUT    /groups/{code}/files/{file_id}   # Chỉnh sửa cài đặt (teacher)
DELETE /groups/{code}/files/{file_id}   # Xóa đề khỏi nhóm (teacher)

GET /groups/{code}/files/{file_id}/scores      # Bảng điểm GV
GET /groups/{code}/files/{file_id}/scores/me   # Điểm của mình (HS)

GET /groups/{code}/members      # Danh sách thành viên
DELETE /groups/{code}/members/{email} # Xóa thành viên
```

**Cài đặt đề khi gán cho nhóm:**

| Tham số | Mặc định | Mô tả |
|---------|---------|-------|
| `num_questions` | 10 | Số câu hỏi random cho mỗi lần làm |
| `time_limit` | 0 (không giới hạn) | Thời gian làm bài (phút). 0 = không giới hạn |

Khi HS nhấn "Làm bài", backend tự đọc `num_questions` và `time_limit` từ cài đặt nhóm, bỏ qua tham số URL. GV có thể chỉnh sửa cài đặt bất kỳ lúc nào qua popup UI.

## Dependencies cần thêm

```txt
# Backend
fastapi==0.115.*
uvicorn[standard]>=0.30
python-jose[cryptography]   # JWT
passlib[bcrypt]             # Password hashing
bleach                      # Output sanitization
chromadb>=0.5.0             # Vector DB (Giai đoạn 2)
anthropic>=0.25.0            # Claude API
python-multipart            # File upload
pydantic>=2.0

# Tutoring
tiktoken>=0.7.0             # Token counting (context window)
slowapi>=0.1.9              # Rate limiting

# Evaluation
scikit-learn                # Metrics computation
pandas                      # Data analysis
```

## Cấu trúc Database mở rộng

```sql
-- Users (thêm role)
CREATE TABLE users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    name TEXT,
    password_hash TEXT NOT NULL,
    role TEXT DEFAULT 'student',  -- student | teacher | admin
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Audit log
CREATE TABLE audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    user_id TEXT,
    role TEXT,
    event_type TEXT,
    resource TEXT,
    action TEXT,
    ip_address TEXT,
    details TEXT
);

-- Document chunks (cho vector search)
CREATE TABLE document_chunks (
    id TEXT PRIMARY KEY,
    file_id TEXT,
    chunk_index INTEGER,
    text TEXT,
    page INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (file_id) REFERENCES files(id)
);

-- Tutoring sessions
CREATE TABLE tutoring_sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    file_id TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Evaluation logs
CREATE TABLE evaluation_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    event_type TEXT,
    query TEXT,
    response TEXT,
    chunks_used TEXT,  -- JSON array
    citation_present BOOLEAN,
    hallucination_detected BOOLEAN,
    retrieval_score REAL
);
```

## Quick wins (ĐÃ HOÀN THÀNH)

### ✅ Đã làm xong

1. **Di chuyển `main.py`** vào `backend/app/` — cấu trúc package đầy đủ
2. **JWT + bcrypt** — `backend/app/core/security.py`
   - `hash_password()`, `verify_password()`, `create_access_token()`
   - Role enum: student / teacher / admin
   - `require_role()` decorator
3. **Audit log cơ bản** — `backend/app/core/audit.py`
   - Ghi `event_type`, `user_id`, `role`, `timestamp`, `details` vào JSONL
   - Event types: auth.*, quiz.*, file.*, tutoring.*, config.*
4. **Trust layer** — `backend/app/services/trust_layer.py`
   - `should_block()` — chặn nếu không đủ evidence
   - `retrieve_chunks()` — keyword search
   - `build_context()` — ghép chunks
   - `evaluate()` — hallucination rate
5. **Sanitize output** — `bleach.clean()` trong `tutoring.py`
6. **Evaluation pipeline** — `evaluation/metrics/`
   - `hallucination.py`: hallucination rate, citation rate, block rate, citation diversity
   - `retrieval.py`: MRR, HitRate@k, Precision@k, NDCG@k
   - `precision.py`: quiz accuracy, score distribution, role performance, improvement trend
7. **Evaluation dashboard** — `evaluation/dashboard.html`
   - KPI cards: hallucination rate, citation rate, quiz accuracy, MRR, block rate
   - Retrieval metrics table với progress bars vs targets
   - Quiz score distribution chart, citation donut, session list, role performance
8. **API endpoints** — `/evaluation/metrics`, `/evaluation/logs`, `/evaluation/hallucination`, `/evaluation/retrieval`
9. **Claude API integration** — `call_claude_api()` trong `tutoring.py`
   - Model: `claude-haiku-4`, system prompt yêu cầu citation bắt buộc
   - Falls back gracefully khi không có API key
10. **ChromaDB vector search** — `services/vector_service.py`
    - Semantic search thay thế keyword overlap
    - Keyword fallback khi ChromaDB unavailable
    - Persistent storage ở `data/chroma_db/`
11. **Rate limiting** — 20 req/min, 100 req/hour per user trong `tutoring.py`
12. **Context window limit** — `MAX_CONTEXT_TOKENS=6000`, token count bằng `tiktoken`
13. **SlowAPI rate limiter** — registered trong `main.py` app state
14. **Role-based access control** — 3 vai trò: student / teacher / admin
    - `auth.py`: role selection khi register
    - `users.py`: list, update role, delete user (admin)
    - `admin.py`: system-wide stats, audit logs, activity
15. **Frontend role-based pages** — `CobraQ_v3.html`
    - Role selection UI khi đăng ký (🎓 Sinh viên / 👨‍🏫 Giáo viên)
    - Sidebar menu động theo vai trò
    - Admin panel: user management, role assignment, system stats, audit logs
    - Evaluation dashboard: inline KPIs + charts trong app
    - Teacher/Admin: quản lý đề mọi user, AI tutoring chat
16. **RBAC trên files API** — Teacher/Admin xem/chỉnh sửa đề của mọi user qua `x-file-for` header
17. **Quan ly nhom / Lop hoc** — `app/db/group_store.py`, `app/db/group_scores.py`, `app/api/groups.py`
    - GV tao nhom, gan de voi `num_questions` va `time_limit` tuy chinh
    - HS tham gia nhieu nhom, lam bai nhom voi thoi gian va so cau theo cai dat GV
    - GV xem bang diem chi tiet, chinh sua cai dat qua popup UI
    - Modal chinh sua (`efm`) voi nut tang/giam so cau va thoi gian

### Còn lại (triển khai khi cần)

- **Giới hạn context window cho tutoring** — đã implement với `MAX_CONTEXT_TOKENS=6000` ✅
- **Vector DB (ChromaDB)** — đã implement trong `services/vector_service.py`, keyword fallback khi ChromaDB unavailable ✅
- **Claude API cho tutoring chat** — đã implement, gọi `claude-haiku-4` với system prompt và citation requirement ✅
- **Rate limiting per user** — đã implement: 20 req/min, 100 req/hour trong `tutoring.py` ✅

## Không nên làm

- **Viết lại frontend từ đầu khi chưa ổn định backend** — Backend da on dinh (JWT, trust layer, evaluation pipeline, Claude API deu da implement). Neu frontend can refactor, nen giu backend nhu cu.
- Thêm nhiều tính năng mới vào `main_updated.py` — nó đã quá dài
- Bỏ qua security để nhanh pilot — đã hoàn thành JWT + bcrypt ✅
- Import vector DB khi chưa có trust layer — tốc độ không thay thế được độ chính xác
- Bỏ qua evaluation khi build AI features — hallucination rate khong the uoc tinh bang cam tinh
