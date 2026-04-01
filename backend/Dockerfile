FROM python:3.11-slim

# UTF-8設定（重要）
ENV PYTHONIOENCODING=utf-8
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV HF_CACHE_DIR=/tmp/huggingface  

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./app/
COPY docs_data/ ./docs_data/
COPY vector_store/ ./vector_store/
COPY docs_ingest/ ./docs_ingest/
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]