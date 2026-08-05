# 🐍 CobraQ — Hệ thống ôn tập thông minh

Hệ thống ôn tập trắc nghiệm AI-powered (FastAPI + Claude) cho học sinh Việt Nam. Tự động sinh câu hỏi, fill đáp án, tạo bài kiểm tra và đánh giá năng lực với bản đồ tương tác.

## 🌐 Live Demo

Sau khi deploy, mở URL được cấp bởi Render.com (vd `https://cobraq.onrender.com`).

## 📦 Cấu trúc dự án

```
CobraQ/
├── CobraQ_v3.html              # Frontend (single-file, không cần build)
├── cobraq_v4_map_test.html     # Bản đồ lịch sử tương tác
├── favicon.svg
├── backend/                    # FastAPI + AI services
│   ├── app/
│   │   ├── main.py             # FastAPI entry, serve frontend
│   │   ├── api/                # auth, files, quiz, map, groups, ...
│   │   ├── core/               # config, security, audit
│   │   ├── db/                 # JSON-based storage
│   │   ├── models/             # Pydantic models
│   │   └── services/           # AI quiz, seeding, ...
│   └── requirements.txt
├── Dockerfile                  # Multi-platform (Render + HF Spaces)
├── render.yaml                 # Render.com Blueprint
├── requirements.txt            # (root - mirror từ backend/)
├── DEPLOY_RENDER.md            # Hướng dẫn deploy Render
└── README.md                   # File này
```

## 🚀 Deploy

**Xem chi tiết**: [DEPLOY_RENDER.md](./DEPLOY_RENDER.md)

Nhanh:
1. Push code lên GitHub
2. Vào [Render Dashboard](https://dashboard.render.com/) → New Blueprint → Connect repo
3. Set env vars: `ANTHROPIC_API_KEY`, `SECRET_KEY`
4. Đợi build ~5-10 phút → live!

## 💻 Chạy local để dev

```bash
# Backend
cd backend
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend: mở CobraQ_v3.html trong browser, hoặc truy cập http://localhost:8000
```

## 🛠 Tech stack

| Layer | Tech |
|---|---|
| Backend | FastAPI + Uvicorn (Python 3.11+) |
| AI | Anthropic Claude (Sonnet) |
| Auth | JWT (HS256) + bcrypt |
| Storage | JSON files + ChromaDB vector store |
| Frontend | Single-file HTML + Tailwind CDN (no build step) |
| PDF parsing | PyMuPDF + pdf2image (Tesseract OCR cho scan) |
| DOCX | python-docx |
| Deployment | Docker → Render.com (free tier) / HF Spaces |

## 🔑 API chính

| Method | Path | Mô tả |
|---|---|---|
| POST | `/api/auth/register` | Đăng ký tài khoản |
| POST | `/api/auth/login` | Đăng nhập → JWT |
| GET | `/api/stats` | Thống kê user + list file |
| GET | `/api/files/{id}/questions` | List câu hỏi của file |
| PUT | `/api/files/{id}/questions/{qid}` | Update câu (text/choices/answer) |
| POST | `/api/files/upload` | Upload PDF/DOCX/ảnh |
| POST | `/api/files/ai/fill-answer` | AI Fill đáp án + giải thích |
| POST | `/api/quiz/save` | Lưu kết quả làm bài |
| GET | `/api/map/events` | Lấy danh sách sự kiện lịch sử |
| GET | `/docs` | Swagger UI đầy đủ |

## 🔒 Bảo mật

- **JWT auth** với HS256 + secret key trong env var
- **bcrypt** hash password (cost=12)
- **Rate limiting** (slowapi) — chống brute force & spam AI Fill
- **Input sanitization** (bleach) — chống XSS khi upload HTML
- **Referrer-Policy** header — fix YouTube embed error 153
- **CORS** allow `*` (public API); production nên giới hạn origin

## ⚠️ Giới hạn

- Free tier không có persistent disk → **mất data khi redeploy**
- Anthropic API tốn tiền (cần plan trả phí hoặc giới hạn rate)
- 512 MB RAM ở Render free → AI Fill chậm khi concurrent

## 📜 License

MIT — dùng tự do cho mục đích cá nhân / giáo dục.
