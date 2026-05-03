FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 10000

CMD ["gunicorn", "main_updated:app", "--bind", "0.0.0.0:10000", "-w", "1", "-k", "uvicorn.workers.UvicornWorker", "--timeout", "120"]
