# IHSA backend (FastAPI). Synthetic-data prototype.
# Build: docker build -t ihsa-backend ./backend   (see docs/phase-8/deployment-guide.md)
FROM python:3.12-slim AS runtime

# Tesseract (with English data) enables OCR for scanned pages; curl-free health check uses Python.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

# Application code only (.dockerignore keeps .env, .venv, .local, tests caches and uploads out).
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini ./
COPY scripts ./scripts
COPY data/knowledge ./data/knowledge
COPY data/samples ./data/samples

# Non-root user; writable data lives on mounted volumes only.
RUN useradd --create-home --uid 10001 ihsa \
    && mkdir -p /data/uploads /data/models \
    && chown -R ihsa:ihsa /data
USER ihsa

ENV APP_ENV=production \
    DOCUMENT_STORAGE_DIR=/data/uploads \
    EMBEDDING_CACHE_DIR=/data/models \
    OCR_ENGINE=tesseract \
    OCR_TESSERACT_PATH=/usr/bin/tesseract

EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=60s --retries=5 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=4).status == 200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
