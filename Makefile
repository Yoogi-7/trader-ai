SHELL := /bin/bash

.PHONY: up down logs migrate seed backfill train backtest api web

up:
\tdocker compose up -d --build

down:
\tdocker compose down -v

logs:
\tdocker compose logs -f

migrate:
\tdocker compose exec api alembic upgrade head

seed:
\t# przykładowy seed użytkownika
\tdocker compose exec db psql -U $${DB_USER:-trader} -d $${DB_NAME:-traderai} -c "INSERT INTO users(id,risk_profile,capital) VALUES (1,'LOW',100) ON CONFLICT DO NOTHING;"

backfill:
\t# symulacyjne wywołanie jobów (realnie: Celery/Kafka)
\tdocker compose exec ml python -c "from trader_ml.scheduler.tasks import run_backfill; print(run_backfill.delay('BTC/USDT'))"

train:
\t# placeholder — w realu task celery na trening+walk-forward
\techo "trigger train via API /train/run"

backtest:
\tcurl -s -X POST http://localhost:8000/backtest/run -H 'Content-Type: application/json' -d '{\"capital\":100, \"risk_profile\":\"LOW\",\"pairs\":[\"BTC/USDT\"],\"fee_maker_bps\":7,\"fee_taker_bps\":10,\"slippage_bps\":5,\"funding_on\":true}' | jq .

api:
\tdocker compose exec api bash

web:
\tdocker compose exec web sh
