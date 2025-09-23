# ====== Builder ======
FROM python:3.12-slim AS builder
ENV PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc libpq-dev curl && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY infra/requirements-api.txt /app/requirements.txt
RUN python -m pip install --upgrade pip && pip wheel --wheel-dir=/wheels -r /app/requirements.txt

# ====== Runtime ======
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UVICORN_WORKERS=2
RUN useradd -m -u 10001 appuser
WORKDIR /app
COPY --from=builder /wheels /wheels
COPY infra/requirements-api.txt /app/requirements.txt
RUN python -m pip install --no-index --find-links=/wheels -r /app/requirements.txt && rm -rf /wheels

# Copy app
COPY apps /app/apps
COPY alembic.ini /app/alembic.ini
COPY migrations /app/migrations

EXPOSE 8000
USER appuser
CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
