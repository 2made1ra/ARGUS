FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice \
    tesseract-ocr \
    tesseract-ocr-rus \
    tesseract-ocr-eng \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml ./
COPY backend/pyproject.toml backend/
COPY backend/app/ backend/app/
COPY packages/sage/pyproject.toml packages/sage/
COPY packages/sage/sage/ packages/sage/sage/

RUN uv pip install --system --no-cache -e backend

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
