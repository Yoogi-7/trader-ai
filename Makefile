
    export $(shell sed -e '/^#/d' -e '/^$/d' .env 2>/dev/null | xargs)

    up:
		docker compose up -d --build

    down:
		docker compose down

    logs:
		docker compose logs -f api worker web

    migrate:
		docker compose exec api alembic upgrade head

    seed:
		docker compose exec api python -m apps.api.seed

    backfill:
		docker compose exec worker python -m apps.ml.jobs.backfill --years $${BACKFILL_YEARS:-4}

    train:
		docker compose exec worker python -m apps.ml.jobs.train

    backtest:
		docker compose exec api python -m apps.api.tools.run_backtest

    api:
		docker compose exec api uvicorn apps.api.main:app --host 0.0.0.0 --port 8000 --reload

    web:
		docker compose exec web npm run dev

    test:
		docker compose exec api pytest -q
