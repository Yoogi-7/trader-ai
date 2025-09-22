
.PHONY: up down logs seed backfill train backtest api web tests lint fmt

up:
	docker compose up -d --build

down:
	docker compose down -v

logs:
	docker compose logs -f --tail=200

seed:
	docker compose exec api python -m apps.api.seed

backfill:
	docker compose exec worker python -m apps.ml.jobs.backfill

train:
	docker compose exec worker python -m apps.ml.jobs.train

backtest:
	docker compose exec worker python -m apps.ml.jobs.backtest

api:
	docker compose exec api bash

web:
	docker compose exec web sh

tests:
	docker compose exec api pytest -q

lint:
	docker compose exec api ruff check .

fmt:
	docker compose exec api ruff format .
