# HuggingFace Spaces / Render.com — CobraQ
# HF dùng port 7860; Render.com dùng port 10000 (đọc từ env PORT)
FROM python:3.11-slim

# System deps cho PDF/image processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-vie \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Cài deps trước để cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY backend/ ./backend/
COPY CobraQ_v3.html ./CobraQ_v3.html
COPY cobraq_v4_map_test.html ./cobraq_v4_map_test.html
COPY favicon.svg ./favicon.svg

# Data dir (persistent nếu dùng HF Spaces paid tier; với free thì ephemeral)
RUN mkdir -p /app/data/users /app/data/uploads /app/data/chroma_db

# Env
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DATA_DIR=/app/data

EXPOSE 7860 10000

# Healthcheck (Render và HF đều check /health)
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD curl -fsS http://127.0.0.1:${PORT:-7860}/health || exit 1

# Run — tự động đọc PORT từ env (Render=10000, HF=7860), fallback 7860
CMD cd /app/backend && uvicorn app.main:app \
    --host 0.0.0.0 \
    --port ${PORT:-7860} \
    --workers 1 \
    --timeout-keep-alive 75 \
    --log-level info