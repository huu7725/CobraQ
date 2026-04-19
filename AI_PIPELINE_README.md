# 🤖 AI Pipeline - RAG + MRC cho CobraQ

Hệ thống tự động trả lời đề trắc nghiệm sử dụng **RAG (Retrieval-Augmented Generation)** và **MRC (Machine Reading Comprehension)**.

---

## 📋 Tổng quan

### Mục tiêu
- **Input**: File đề trắc nghiệm (PDF/Word) **không có đáp án**
- **Output**: Đề có đáp án tự động + giải thích chi tiết
- **Cơ chế**:
  1. **RAG**: Tìm câu hỏi tương tự trong vector DB (cache các đề đã có đáp án)
  2. **MRC**: Gọi LLM (Gemini) để đọc và hiểu câu hỏi, chọn đáp án
  3. **Cache**: Lưu kết quả vào DB để tái sử dụng, giảm chi phí

---

## 🏗️ Kiến trúc

```
┌─────────────────────────────────────────────────────────┐
│  1. Upload file (PDF/Word) → Parse câu hỏi (chưa đáp án)│
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│  2. AI Pipeline (/ai/answer-file)                       │
│     ├─ Step 1: Embedding câu hỏi                         │
│     ├─ Step 2: RAG retrieval (tìm trong vector DB)      │
│     ├─ Step 3: Nếu tìm thấy → trả về từ DB (cached)    │
│     └─ Step 4: Nếu không → gọi Gemini LLM (MRC)         │
│     └─ Step 5: Cache kết quả vào vector DB              │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│  3. Kết quả:                                             │
│     • answer: A/B/C/D                                    │
│     • confidence: 0.0-1.0                                │
│     • explanation: Giải thích chi tiết                   │
│     • source: "vector_db" | "llm" | "existing"          │
│     • similar_questions: [... danh sách câu tương tự ]  │
└─────────────────────────────────────────────────────────┘
```

---

## 📁 Cấu trúc dự án (đã thêm)

```
CobraQ/
├── services/                    # ← MỚI - AI Pipeline services
│   ├── __init__.py
│   ├── embedding_service.py     # SentenceTransformer embeddings
│   ├── vector_store.py          # ChromaDB vector database
│   ├── rag_service.py           # Retrieval-Augmented Generation
│   ├── mrc_service.py           # Machine Reading Comprehension (Gemini)
│   └── pipeline_service.py      # Orchestrator (RAG + MRC)
├── main_updated.py              # ← Đã thêm endpoints AI mới
├── db.py                        # ← Đã thêm bảng ai_cache, ai_llm_logs
├── schema.sql                   # ← Đã thêm bảng cho MySQL
├── repository.py                # (chưa cần sửa)
└── requirements.txt             # ← Đã thêm dependencies
```

---

## 📦 Dependencies cần cài đặt

### 1. Cài đặt packages mới

```bash
# Từ thư mục CobraQ
pip install -r requirements.txt
```

Các package quan trọng:
- `sentence-transformers`: Tạo embeddings đa ngôn ngữ (hỗ trợ tiếng Việt)
- `chromadb`: Vector database local
- `scikit-learn`: Cosine similarity
- `google-generativeai`: LLM Gemini (đã có)

### 2. Tải embedding model (lần đầu chạy)

Lần đầu import `EmbeddingService`, code sẽ tự động tải model về cache:

```python
from services.embedding_service import EmbeddingService
embedder = EmbeddingService()  # Tải model paraphrase-multilingual-MiniLM-L12-v2
```

Model sẽ được lưu tại:
- Linux/Mac: `~/.cache/torch/sentence_transformers/`
- Windows: `C:\Users\<user>\.cache\torch\sentence_transformers\`

**Model khuyến nghị**:
- `paraphrase-multilingual-MiniLM-L12-v2` (mặc định): Nhẹ, nhanh, đủ tốt
- `paraphrase-multilingual-mpnet-base-v2`: Chất lượng cao hơn, nặng hơn
- `intfloat/multilingual-e5-large`: Rất tốt nhưng nặng, cần GPU

---

## 🔧 Cấu hình Environment Variables

Thêm vào file `.env`:

```env
# Gemini AI (đã có)
GEMINI_API_KEY=your_gemini_api_key_here

# AI Pipeline config
EMBEDDING_MODEL=paraphrase-multilingual-MiniLM-L12-v2
VECTOR_DB_PATH=./chroma_db
RAG_SIMILARITY_THRESHOLD=0.85

# Optional: Rate limiting
# MAX_LLM_CALLS_PER_MINUTE=10
```

---

## 🌐 API Endpoints mới

### 1. POST `/ai/answer-question`

Trả lời 1 câu hỏi đơn lẻ (không cần upload file).

**Request**:
```json
{
  "question": "Hàm số f(x) = x² có miền xác định là?",
  "choices": [
    {"label": "A", "text": "R"},
    {"label": "B", "text": "R⁺"},
    {"label": "C", "text": "R⁺ ∪ {0}"},
    {"label": "D", "text": "R \\ {0}"}
  ],
  "subject": "toán",
  "context": ""
}
```

**Response**:
```json
{
  "answer": "A",
  "confidence": 0.95,
  "explanation": "Hàm số bậc 2 có miền xác định là tập số thực.",
  "reasoning": "Hàm số đa thức bậc 2 xác định với mọi x ∈ R...",
  "source": "llm",
  "processing_time_ms": 1234
}
```

---

### 2. POST `/ai/answer-file` ⭐ **QUAN TRỌNG**

Tự động trả lời **tất cả câu hỏi** trong 1 file đã upload.

**Use case**:
- User upload đề PDF (không đáp án) → `/upload`
- Gọi `/ai/answer-file` để AI trả lời toàn bộ
- Lấy kết quả → hiển thị đáp án + giải thích

**Request**:
```json
{
  "file_id": "de_toan_10",
  "use_rag": true,
  "force_llm": false,
  "subject": "toán"
}
```

**Response**:
```json
{
  "file_id": "de_toan_10",
  "total": 50,
  "subject": "toán",
  "results": [
    {
      "question_id": 1,
      "question": "Giải phương trình x² - 5x + 6 = 0",
      "answer": "C",
      "confidence": 0.92,
      "explanation": "Phương trình có Δ = 1, nghiệm x₁=2, x₂=3...",
      "source": "llm",
      "similar_questions": [],
      "processing_time_ms": 1500
    },
    ...
  ],
  "summary": {
    "from_vector_db": 5,
    "from_llm": 45,
    "existing": 0,
    "errors": 0,
    "avg_confidence": 0.87
  },
  "rag_enabled": true,
  "vector_db_total": 1200
}
```

---

### 3. GET `/ai/similar-questions/{question_id}`

Tìm câu hỏi tương tự trong vector DB (cross-user).

**Query params**:
- `file_id`: File hiện tại
- `top_k`: Số câu trả về (default 5)
- `subject`: Lọc theo môn (optional)

**Response**:
```json
{
  "question": { ... câu hỏi gốc ... },
  "similar_questions": [
    {
      "question": "...",
      "answer": "B",
      "explanation": "...",
      "similarity": 0.93,
      "source_file": "de_toan_10",
      "subject": "toán"
    }
  ],
  "total_found": 3
}
```

---

### 4. POST `/ai/answer-quiz`

Tự động trả lời toàn bộ quiz session (đang thi).

**Request**:
```json
{
  "session_id": "s123456"
}
```

**Response**:
```json
{
  "session_id": "s123456",
  "ai_answers": {
    "0": "B",
    "1": "A",
    "2": "D"
  },
  "explanations": {
    "0": {
      "explanation": "...",
      "confidence": 0.89,
      "source": "llm"
    }
  },
  "total": 10
}
```

---

### 5. GET `/ai/stats`

Thống kê AI usage.

**Response**:
```json
{
  "user_id": "u_xxx",
  "vector_db": {
    "total": 1543,
    "by_subject": {"toán": 800, "lý": 400, ...},
    "by_file": {"de_1": 50, "de_2": 40, ...}
  },
  "user_cache_count": 120,
  "llm_calls_24h": 45,
  "tokens_24h": 18000,
  "cost_24h_usd": 0.0054,
  "ai_available": true,
  "mrc_model": "gemini-1.5-flash"
}
```

---

### 6. POST `/ai/cache/clear`

Xóa cache AI.

**Request**:
```json
{
  "file_id": "de_toan_10",   // Xóa cache của 1 file
  // HOẶC
  "subject": "toán"          // Xóa cache của 1 môn
  // HOẶC để trống → xóa tất cả cache của user
}
```

---

## 🚀 Workflow sử dụng

### **Scenario 1: Upload đề + AI chấm tự động**

```python
# 1. Upload file đề (không đáp án)
POST /upload
→ File được parse → lưu questions (chưa có answer)

# 2. Gọi AI để trả lời toàn bộ
POST /ai/answer-file
{
  "file_id": "abc123",
  "use_rag": true,
  "force_llm": false
}
→ Nhận kết quả: tất cả câu có đáp án + giải thích

# 3. Lưu đáp án vào DB (nếu muốn)
# Hiện tại endpoint trả về kết quả, frontend có thể:
# - Hiển thị ngay cho user
# - Gọi PUT /files/{file_id}/questions/{q_id} để lưu answer
```

---

### **Scenario 2: Thi thử + Xem đáp án**

```python
# 1. Start quiz (không cần AI)
GET /quiz/start?file_id=abc123&num=20

# 2. User làm bài → submit
POST /quiz/submit

# 3. Sau khi submit, gọi AI giải thích câu sai
POST /ai/answer-file
→ Lấy explanations cho từng câu

# 4. Hiển thị "Đáp án: B (AI confidence: 92%)"
#     + "Giải thích: ..."
```

---

### **Scenario 3: RAG - Tìm đề tương tự**

```python
# User xem câu 5 trong file A
GET /ai/similar-questions/5?file_id=fileA&top_k=3

→ Tìm 3 câu giống nhất trong toàn hệ thống
→ User có thể tham khảo đáp án từ đề khác
```

---

## 💾 Database Schema (Mới)

### Bảng `ai_cache`

Lưu cache kết quả AI prediction:

```sql
CREATE TABLE ai_cache (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  user_id VARCHAR(191) NOT NULL,
  question_hash CHAR(64) NOT NULL,  -- SHA256 của question+choices
  question_text LONGTEXT NOT NULL,
  answer CHAR(1) DEFAULT '',
  explanation TEXT,
  confidence DECIMAL(5,4) DEFAULT 0.0,
  source VARCHAR(32) DEFAULT 'llm',
  subject VARCHAR(100) DEFAULT '',
  file_id VARCHAR(255) DEFAULT '',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uq_user_question (user_id, question_hash(32))
);
```

**Ý nghĩa**:
- Khi user gọi `/ai/answer-file`, kết quả được lưu vào đây
- Lần sau gọi cùng câu hỏi → lấy từ cache (nhanh, không tốn tiền)
- Hash được tạo từ `question + choices_text`

---

### Bảng `ai_llm_logs`

Log tất cả các lần gọi LLM (audit + cost tracking):

```sql
CREATE TABLE ai_llm_logs (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  user_id VARCHAR(191) NOT NULL,
  question_id INT DEFAULT NULL,
  file_id VARCHAR(255) DEFAULT '',
  model VARCHAR(100) DEFAULT 'gemini-1.5-flash',
  prompt_text LONGTEXT,
  response_text LONGTEXT,
  prompt_tokens INT DEFAULT 0,
  response_tokens INT DEFAULT 0,
  total_tokens INT DEFAULT 0,
  cost_estimate FLOAT DEFAULT 0.0,
  success TINYINT(1) DEFAULT 1,
  error_message TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## ⚙️ Cách hoạt động chi tiết

### Pipeline `AIPipeline.process_question()`

```python
def process_question(question_data, subject, use_rag, force_llm):
    # 1. Validate input
    if not question or len(choices) < 2:
        return error

    # 2. Check existing answer (nếu user đã nhập)
    if question_data.get("answer") and not force_llm:
        return {answer: existing, source: "existing", confidence: 1.0}

    # 3. RAG retrieval (nếu use_rag=True)
    if use_rag and not force_llm:
        similar = rag.retrieve_similar(question, choices, subject)

        # 3a. Nếu tìm thấy match tốt (similarity >= 0.9)
        if similar[0]["similarity"] >= 0.9:
            return {
                answer: similar[0]["answer"],
                confidence: similar[0]["similarity"],
                source: "vector_db",
                similar_questions: similar
            }

    # 4. Gọi LLM (MRC)
    context = rag.build_context_string(similar)  # Context từ các câu tương tự
    llm_result = mrc.predict(question, choices, subject, context)

    # 5. Cache result vào vector DB
    if cache_enabled and llm_result["answer"]:
        vector_store.add_question(...)

    return llm_result
```

---

## 🎯 Use Cases chính

### **Use Case 1: Teacher upload đề → AI trả lời → Làm đề thi thử**

```
Upload đề PDF (không đáp án)
   ↓
Parse → Lấy 50 câu hỏi
   ↓
POST /ai/answer-file (use_rag=true)
   ↓
RAG: Tìm 5 câu tương tự trong DB → match 2 câu
   ↓
LLM: Gọi Gemini cho 48 câu còn lại
   ↓
Cache: Lưu 48 kết quả mới vào vector DB
   ↓
Frontend hiển thị: Đáp án + Giải thích + Confidence
   ↓
Student làm quiz → So sánh answer của AI với đáp án thực (nếu có)
```

**Lợi ích**:
- Lần 2 upload đề tương tự → 100% từ cache (không tốn tiền)
- Giảm số lần gọi LLM → tiết kiệm cost

---

### **Use Case 2: Student làm quiz → Xem giải thích**

```
GET /quiz/start?file_id=de_toan_10
   ↓
Trả về 20 câu (random)
   ↓
User trả lời → POST /quiz/submit
   ↓
Score = 15/20
   ↓
Gọi AI giải thích 5 câu sai:
   POST /ai/answer-file (file_id=de_toan_10)
   → Chỉ lấy `explanation` của 5 câu đó
   ↓
Hiển thị: "Bạn đã trả lời sai câu 3, 7, 12, 15, 18"
          + "Giải thích chi tiết cho từng câu"
```

---

### **Use Case 3: Tìm đề tương tự (RAG retrieval)**

```
User đang xem câu hỏi #5 trong file "de_toan_10"
   ↓
Click "Xem câu tương tự"
   ↓
GET /ai/similar-questions/5?file_id=de_toan_10&top_k=5
   ↓
RAG: Embed câu #5 → tìm top 5 trong vector DB
   ↓
Return: [
   {question: "...", answer: "B", similarity: 0.94, ...},
   ...
]
   ↓
User tham khảo đáp án từ các đề khác
```

---

## ⚠️ Error Handling & Edge Cases

### **1. No valid API key**

```python
_init_ai_services()  # Sẽ không khởi tạo nếu thiếu key
→ Endpoint trả về 503: "AI Pipeline chưa sẵn sàng"
```

**Fix**: Set `GEMINI_API_KEY` trong `.env`

---

### **2. Empty/invalid question**

```python
if not question or len(choices) < 2:
    return {
        "answer": "",
        "confidence": 0.0,
        "explanation": "Câu hỏi hoặc phương án không hợp lệ",
        "source": "error"
    }
```

---

### **3. LLM returns invalid JSON**

```python
def _parse_response(raw_text, choices):
    # Thử 3 method:
    # 1. Extract JSON block {...}
    # 2. Regex tìm "answer": "A"
    # 3. Regex tìm \b([A-D])\b
    # Fallback: chọn A (đề phòng)
```

---

### **4. Vector DB không có data**

Lần đầu dùng → vector DB trống → RAG không tìm được gì → Fallback sang LLM hoàn toàn.

**Không sao** – hệ thống sẽ tự động cache kết quả LLM vào DB.

---

### **5. Rate limit / API quota**

Gemini có giới hạn:
- Free tier: 60 req/phút ( Gemini 1.5 Flash)
- Nếu vượt → lỗi 429

**Giải pháp**:
- Thêm `time.sleep(0.5)` giữa các request batch
- Dùng `asyncio.Semaphore` để giới hạn concurrent
- Background worker (Celery) cho batch lớn

---

## 📊 Monitoring & Logging

### Logging

```python
import logging
logger = logging.getLogger(__name__)

# Trong các service:
logger.info(f"Embedding dimension: {self.model.get_sentence_embedding_dimension()}")
logger.debug(f"Found {len(similar)} similar questions")
logger.error(f"MRC error: {e}")
```

Xem logs:
```bash
# Nếu dùng uvicorn
uvicorn main_updated:app --reload
# Logs sẽ hiển thị trên console
```

---

### Database logs

Bảng `ai_llm_logs` lưu:
- Tất cả request/response (có thể rất lớn → cần TTL)
- Token count → tính cost
- Success/failure → alert nếu error rate > 5%

**Cleanup logs cũ** (chạy hàng ngày):
```sql
DELETE FROM ai_llm_logs WHERE created_at < DATE_SUB(NOW(), INTERVAL 30 DAY);
```

---

### Vector DB stats

```python
# Trong Python
vector_store.get_stats()
# Returns: {"total": 1500, "by_subject": {...}, "by_file": {...}}
```

---

## 💰 Cost Estimation (Gemini Flash)

**Giá (04/2026)**:
- Input: $0.000075 / 1K tokens
- Output: $0.0003 / 1K tokens

**Ước tính**:

| Loại câu | Input tokens | Output tokens | Cost/câu |
|---------|-------------|--------------|---------|
| Toán đơn giản | 200 | 150 | $0.0000375 |
| Toán phức tạp (công thức) | 500 | 300 | $0.0000975 |
| Văn học (dài) | 400 | 250 | $0.000075 |

**Ví dụ**:
- 100 câu toán trung bình: 100 × $0.00008 = **$0.008**
- 1000 câu: **$0.08**

**Cache giúp giảm cost**:
- Lần 2: cùng câu → từ vector DB (cost = $0)
- Nếu 50% câu tìm được trong DB → tiết kiệm 50%

---

## 🧪 Testing

### 1. Test embedding

```python
from services.embedding_service import EmbeddingService
e = EmbeddingService()
emb = e.embed_text("Hàm số bậc 2")
print(emb.shape)  # (384,) với model MiniLM
```

---

### 2. Test vector store

```python
from services.vector_store import VectorStore
vs = VectorStore()
vs.add_question(
    question_id="test_1",
    embedding=[0.1, 0.2, ...],
    question_text="Test question",
    answer="A",
    explanation="Because..."
)
results = vs.search_similar(query_embedding, top_k=5)
```

---

### 3. Test full pipeline

```python
from services.pipeline_service import AIPipeline
from services.embedding_service import EmbeddingService
from services.vector_store import VectorStore
from services.rag_service import RAGService
from services.mrc_service import MRCService

embedder = EmbeddingService()
vs = VectorStore()
rag = RAGService(vs, embedder)
mrc = MRCService(api_key="your_key")
pipeline = AIPipeline(embedder, vs, rag, mrc)

result = pipeline.process_question(
    question_data={
        "question": "Giải phương trình x² - 5x + 6 = 0",
        "choices": [
            {"label": "A", "text": "x = 2"},
            {"label": "B", "text": "x = 3"},
            {"label": "C", "text": "x = 2 hoặc 3"},
            {"label": "D", "text": "x = -2 hoặc -3"}
        ]
    },
    subject="toán"
)

print(result)
# {'answer': 'C', 'confidence': 0.95, 'source': 'llm', ...}
```

---

### 4. Test endpoint (curl)

```bash
# 1. Get token
TOKEN=$(curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"password"}' \
  | jq -r .access_token)

# 2. Call AI
curl -X POST http://localhost:8000/ai/answer-file \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"file_id":"de_toan_10","use_rag":true}'
```

---

## 🔄 Migration & Setup

### 1. Tạo bảng mới (AI cache + logs)

**Nếu dùng MySQL**:
```bash
mysql -u root -p cobraq_db < schema.sql
```

**Nếu dùng SQLite** (auto-migrate):
```python
# Khi chạy app, db.py sẽ tự động thêm bảng
from db import init_schema_from_file
init_schema_from_file()
```

---

### 2. Cài đặt dependencies

```bash
# Tạo virtual env (khuyến nghị)
python -m venv venv
source venv/bin/activate  # Linux/Mac
# hoặc
venv\Scripts\activate     # Windows

# Cài đặt
pip install -r requirements.txt
```

**Lưu ý**:
- `sentence-transformers` cần `torch` (có thể nặng)
- Nếu muốn nhẹ hơn, dùng `tensorflow`-based model (không khuyến nghị)
- Có thể mất 5-10 phút tải model lần đầu

---

### 3. Run app

```bash
# .env cần có:
# GEMINI_API_KEY=xxx
# DB_ENGINE=sqlite (hoặc mysql)

uvicorn main_updated:app --reload --host 0.0.0.0 --port 8000
```

Truy cập:
- API docs: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

---

## 🐛 Debugging

### Issue: `ImportError: cannot import name 'EmbeddingService'`

**Causes**:
1. Chưa cài `sentence-transformers`
2. File `services/embedding_service.py` không tồn tại

**Fix**:
```bash
pip install sentence-transformers
# Kiểm tra file tồn tại
ls services/embedding_service.py
```

---

### Issue: `RuntimeError: The current Python interpreter is not supported...`

**Cause**: `sentence-transformers` không hỗ trợ Python phiên bản này.

**Fix**: Nâng cấp Python lên 3.9+ (khuyến nghị 3.10/3.11)

---

### Issue: `CUDA out of memory`

**Cause**: Model quá lớn, GPU không đủ RAM.

**Fix**:
```python
# Trong embedding_service.py, force CPU:
self.model = SentenceTransformer(model_name, device="cpu")
```

---

### Issue: `ChromaDB collection already exists`

**Fix**: Xóa thư mục `chroma_db` và chạy lại:
```bash
rm -rf chroma_db
# hoặc
rmdir /s chroma_db  # Windows
```

---

### Issue: `Gemini API rate limit exceeded`

**Fix**:
- Giảm `batch_size` trong `process_batch`
- Thêm `time.sleep(1)` giữa các request
- Dùng `asyncio.Semaphore` để giới hạn concurrent

---

## 📈 Performance Tips

### 1. Batch embedding

```python
# Tốt hơn nhiều so với embed từng cái
embeddings = embedder.embed_batch(texts, batch_size=32)
```

---

### 2. Pre-index sau khi upload

Trong `main_updated.py`, sau khi `/upload`:

```python
# Tự động index câu hỏi mới vào vector DB
if _AI_SERVICES_AVAILABLE:
    _rag_service.index_questions_batch(
        questions=normalized_questions,
        file_id=file_id,
        subject=subject
    )
```

---

### 3. Tuning similarity threshold

```python
# Giảm threshold = nhiều câu match hơn (nhưng có thể sai)
rag = RAGService(threshold=0.80)  # default: 0.85

# Tăng threshold = ít câu match hơn (chính xác hơn)
rag = RAGService(threshold=0.90)
```

---

### 4. Cost monitoring

Query cost trong 24h:
```sql
SELECT
    COUNT(*) as calls,
    SUM(total_tokens) as tokens,
    SUM(cost_estimate) as cost_usd
FROM ai_llm_logs
WHERE created_at >= NOW() - INTERVAL 1 DAY;
```

---

## 🔮 Future Improvements

### Short-term (1-2 tuần)

- [ ] **Async processing**: Dùng Celery + Redis cho batch lớn
- [ ] **Rate limiting**: Thêm `slowapi` để giới hạn user
- [ ] **Progress bar**: WebSocket real-time progress khi xử lý file lớn
- [ ] **Cost dashboard**: UI hiển thị chi phí AI theo user/day

---

### Mid-term (1 tháng)

- [ ] **Fine-tune embedding**: Dùng data của user để fine-tune model (có vấn đề privacy)
- [ ] **Multiple LLM**: Hỗ trợ OpenAI GPT-4, Claude, local Llama
- [ ] **Answer validation**: Cross-check giữa LLM khác nhau
- [ ] **Auto-subject detection**: Dùng LLM phát hiện môn học từ câu hỏi

---

### Long-term (3 tháng+)

- [ ] **Knowledge graph**: Xây dựng graph kiến thức môn học → RAG chính xác hơn
- [ ] **Multimodal**: Hỗ trợ đề có hình ảnh (hình vẽ, đồ thị)
- [ ] **Personalization**: Dựa trên lịch sử làm bài của user để đưa ra gợi ý cá nhân hóa
- [ ] **Offline mode**: Chạy local LLM (Llama 3) khi không có internet

---

## 🆘 Support

Nếu gặp vấn đề:

1. Check logs: `tail -f logs/cobraq.log` (nếu có)
2. Verify dependencies: `pip list | grep -E "sentence|chroma|gemini"`
3. Test embedding: `python -c "from services.embedding_service import EmbeddingService; EmbeddingService()"`
4. Open issue trên GitHub repository

---

**Last updated**: April 2026
**Version**: 1.0-RAG-MRC
