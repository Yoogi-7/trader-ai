# Trader AI — Production-Ready Monorepo

Trader AI is a full-stack cryptocurrency trading research and execution platform. The repository bundles a FastAPI service, an ML/Celery worker, and a Next.js dashboard together with infrastructure tooling (TimescaleDB, Redis) so the system can be demonstrated end-to-end: fetch market data, engineer features, train and backtest models, and surface live trading signals.

## Highlights
- **Event-driven architecture:** Lightweight HTTP webhook fan-out keeps API, worker jobs, and dashboards in sync without external brokers.
- **Autonomous research loop:** The `ml-backfill` worker continuously backfills, resamples, computes features, retrains, and mints fresh signals without manual intervention (zapasowy generator danych syntetycznych pozwala wystartować także bez dostępu do giełd).
- **TimescaleDB-backed history:** Backfill and resumable jobs populate TimescaleDB with candle data and progress metadata.
- **Feature + labeling pipeline:** Modular feature builders, triple-barrier labeling, and walk-forward training automation (Optuna-ready).
- **Signal governance:** Net profit filters, confidence thresholds, exposure caps, cooldowns, and funding adjustments baked into the signal engine.
- **Accuracy scoring:** Każdy sygnał otrzymuje rating potencjalnej trafności wyliczony z historycznych wyników PnL, dominującego reżimu rynku i oczekiwanego zysku netto.
- **Next.js dashboard:** Separate user/admin views for monitoring backfills, model runs, and portfolio simulations.
- **Production ergonomics:** Docker images, health checks, Alembic migrations, CI hooks, and pytest coverage for critical logic (net profit filter, backfill resume, basic feature sanity).

## Repository Layout
- `apps/api` — FastAPI service (routers, CRUD, WebSocket manager, Alembic-powered DB boot).
- `apps/ml` — Celery/ML code: backfill, backtest, training, risk management, signal engine, feature pipelines.
- `apps/web` — Next.js front-end (React + Tailwind) built into a standalone Node server.
- `apps/common` — Shared building blocks (Celery instance, cache helpers, event bus integration).
- `infra/dockerfiles` & `infra/entrypoints` — Container build definitions and boot scripts.
- `migrations` — Alembic migrations for the TimescaleDB schema.
- `tests` — Pytest suite covering backfill resume, feature basics, sizing/liquidation checks, and profitability constraints.
- `openapi.yaml`, `postman_collection.json` — Snapshot of the HTTP API contract for reference/testing.

## Service Topology (Docker Compose)
The stack runs the following containers via `docker-compose.yml`:
- `db` — TimescaleDB (PostgreSQL 15) with persistence; readiness probed before API boot.
- `redis` — Cache and task queue broker for Celery.
- `api` — FastAPI app served by Uvicorn; runs Alembic migrations on startup and exposes `/docs`, `/redoc`, and `/ws/live`.
- `web` — Next.js dashboard served from the production build.
- `ml-backfill` — Python worker performing continuous CCXT backfills and feature generation.

## Prerequisites
- Docker 24+
- Docker Compose plugin (v2)
- GNU Make

## Quick Start (Docker Compose)
1. Duplicate environment defaults: `cp .env.example .env` and review secrets/URLs.
2. Launch the full stack: `make up` (builds images and starts all services in the background).
3. Confirm the health checks:
   - API docs: http://localhost:8000/docs
   - Web dashboard: http://localhost:3000
4. (Optional) Apply the latest migrations manually if you run the API outside of Docker: `docker compose exec api alembic upgrade head`.
5. (Optional) Seed demo data: `make seed`.

Useful maintenance commands:
- Tail logs: `make logs`
- Stop and clean volumes: `make down`
- Drop into an API shell: `make api`
- Run the pytest suite: `make tests`
- Lint/format with Ruff: `make lint`, `make fmt`

## Local Development Without Docker
```bash
poetry install
poetry run alembic upgrade head
poetry run uvicorn apps.api.main:app --reload
```

Run background workers locally as needed:
```bash
# Celery worker (re-uses apps.common.celery_app)
poetry run celery -A apps.common.celery_app worker -l info

# Continuous backfill loop
poetry run python -m apps.ml.backfill

# Fire a training or backtest job manually
poetry run python -m apps.ml.jobs.train
poetry run python -m apps.ml.jobs.backtest
```

Frontend development mode:
```bash
cd apps/web
npm install
npm run dev
```
Point `NEXT_PUBLIC_API_URL` in `.env.local` (or `.env`) at your API instance.

### Lightweight test environment
```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-test.txt
python -m pytest
```

## Configuration
All runtime configuration is sourced from `.env`. Key sections in `.env.example` include:
- **Core services:** `DATABASE_URL`, `REDIS_URL`, `API_PREFIX`.
- **Backfill controls:** Exchange, symbol list, chunk sizing, and retry/backoff knobs.
- **Feature & labeling:** `FEATURES_VERSION`, triple-barrier parameters, walk-forward purge/embargo.
- **Signal engine:** Net profit thresholds, fee/slippage, exposure caps, cooldown switches.
- **User defaults:** Risk profiles and base capital for simulations.
- **Frontend:** `NEXT_PUBLIC_API_URL` for the Next.js app.

## API Surface
FastAPI automatically publishes the OpenAPI schema at `/openapi.json`. Notable routes:
- Backfill orchestration: `POST /backfill/start`, `GET /backfill/status`
- Model lifecycle: `POST /train/run`, `GET /train/status`, `POST /backtest/run`, `GET /backtest/results`
- Signal endpoints: `POST /signals/generate`, `GET /signals/live`, `GET /signals/history` (odpowiedzi zawierają metrykę `potential_accuracy` z oceną i składowymi).
- Portfolio controls: `POST /settings/profile`, `POST /capital`
- Live updates: WebSocket at `/ws/live`

See `openapi.yaml` or import `postman_collection.json` into Postman for a ready-made collection.

## Testing & Quality Gates
- **Unit tests:** `make tests` (or `docker compose exec api pytest -q`).
- **Static analysis:** `make lint` / `ruff check .`.
- **Formatting:** `make fmt` / `ruff format .`.
- **CI/CD:** GitHub Actions workflows in `ops/github` run lint + tests and can be extended with build/publish jobs.

## Operational Notes
- API entrypoint waits for PostgreSQL, runs `alembic upgrade head`, then starts Uvicorn (`infra/entrypoints/api.sh`).
- ML images default to executing the backfill loop; override the command to launch Celery workers or ad-hoc jobs.
- TimescaleDB volumes (`dbdata`) persist across restarts. Use `make down` to remove them locally.

## License
Released under the MIT License.
