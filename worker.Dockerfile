# worker.Dockerfile
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev git curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY infra/requirements-ml.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app

# Komenda startowa jest w docker-compose.yml:
# command: ["python", "-m", "apps.ml.worker"]
