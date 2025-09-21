FROM python:3.11-slim
WORKDIR /app
COPY infra/requirements-api.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PYTHONPATH=/app
EXPOSE 8000