# api.Dockerfile
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev git curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY infra/requirements-api.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Skopiuj cały monorepo (API używa apps/, migrations/, etc.)
COPY . /app

EXPOSE 8000
# Komenda właściwa jest podawana w docker-compose.yml (uvicorn ...)
