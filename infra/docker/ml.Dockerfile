FROM python:3.12-slim
WORKDIR /app
COPY apps/ml/pyproject.toml /app/
RUN pip install --no-cache-dir -U pip && pip install --no-cache-dir -e .
COPY apps/ml/trader_ml /app/trader_ml
ENV PYTHONUNBUFFERED=1
CMD ["python","-c","import time; print('ML container ready'); time.sleep(3600)"]
