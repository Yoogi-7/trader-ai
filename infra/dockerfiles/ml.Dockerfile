# ====== Builder ======
FROM python:3.12-slim AS builder
ENV PIP_NO_CACHE_DIR=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc libpq-dev curl && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY infra/requirements-ml.txt /app/requirements.txt
RUN python -m pip install --upgrade pip && pip wheel --wheel-dir=/wheels -r /app/requirements.txt

# ====== Runtime ======
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN useradd -m -u 10002 mluser
WORKDIR /app
COPY --from=builder /wheels /wheels
COPY infra/requirements-ml.txt /app/requirements.txt
RUN python -m pip install --no-index --find-links=/wheels -r /app/requirements.txt && rm -rf /wheels

COPY apps /app/apps

USER mluser
CMD ["python", "-m", "apps.ml.backfill"]
