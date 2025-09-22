FROM python:3.12-slim
WORKDIR /app
COPY apps/api/pyproject.toml /app/
RUN pip install --no-cache-dir -U pip && pip install --no-cache-dir -e .
COPY apps/api/trader_api /app/trader_api
ENV PYTHONUNBUFFERED=1
CMD ["uvicorn","trader_api.main:app","--host","0.0.0.0","--port","8000"]
