FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Copy frontend HTML as index.html in dist/
RUN mkdir -p /app/dist && cp /app/CobraQ_v3.html /app/dist/index.html

EXPOSE 10000

CMD ["gunicorn", "main_updated:app", "--bind", "0.0.0.0:10000", "-w", "1", "-k", "uvicorn.workers.UvicornWorker", "--timeout", "120"]
