# api.Dockerfile
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev git curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Zależności API
COPY infra/requirements-api.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Całe monorepo (API korzysta z apps/, migrations/, itp.)
COPY . /app

EXPOSE 8000
# Komendę startową podajemy w docker-compose.yml (uvicorn apps.api.main:app ...)
