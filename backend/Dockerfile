FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# libpq is needed by psycopg2; curl is used by container healthchecks.
RUN apt-get update \
 && apt-get install -y --no-install-recommends libpq5 curl poppler-utils tesseract-ocr tesseract-ocr-eng gcc python3-dev libpq-dev \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run as a non-root user.
RUN useradd --create-home --uid 10001 nyaya && chown -R nyaya:nyaya /app
USER nyaya

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
