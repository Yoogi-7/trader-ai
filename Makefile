SHELL:=/bin/bash

up:
	docker compose up -d --build

down:
	docker compose down -v

logs:
	docker compose logs -f --tail=100

migrate:
	docker compose run --rm api alembic upgrade head

seed:
	docker compose run --rm api python -m apps.api.seed

backfill:
	docker compose run --rm ml python -m apps.ml.jobs.backfill_ccxt

train:
	docker compose run --rm ml python -m apps.ml.train

backtest:
	docker compose run --rm ml python -m apps.ml.backtest

api:
	docker compose logs -f api

web:
	docker compose logs -f web

test:
	docker compose run --rm api pytest -q
