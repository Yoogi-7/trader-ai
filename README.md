
# Trader AI — monorepo (prod-ready)

**Stos:** FastAPI (API), Celery (ML/worker), Next.js (FE), TimescaleDB (PG15), Redis, Redpanda (Kafka),
Alembic, GitHub Actions, testy (pytest).

## Uruchomienie (Docker Compose)

1. Skopiuj `.env.example` -> `.env` i dostosuj parametry.
2. `make up` — podniesie: db, redis, redpanda, api, worker, web.
3. Migracje: `docker compose exec api alembic upgrade head` (zrobione w CI, lokalnie uruchom ręcznie).
4. Seed (opcjonalnie): `make seed`.
5. Panel użytkownika: http://localhost:3000, API: http://localhost:8000.

### Weryfikacja kryteriów
- **Filtr ≥2% netto** — test: `tests/test_filter_net2pct.py`. W API/ML sygnały muszą spełnić `expected_net_pct>=0.02` (z kosztami: fee+slippage).
- **Hit‑rate ≥55% (TP1, OOS)** — metryki raportowane w `apps/ml/jobs/train.py` (stub losowy dla demo) i prezentowane w panelu admina. W realu: dodać walk‑forward + Optuna, zapisać metryki w `training_runs`.
- **Resume backfill** — tabela `backfill_progress` i zadanie `run_backfill` (demonstracyjnie wpisuje postęp). Test: `tests/test_backfill_resume.py`.
- **Symulacja od 100$** — FE ma sekcję symulatora, API dostarczy endpointy; można rozszerzyć backtester w `apps/ml/jobs/backtest.py`.

### Endpoints (skrót)
- `POST /backfill/start`, `GET /backfill/status`
- `POST /train/run`, `GET /train/status`
- `POST /backtest/run`, `GET /backtest/results`
- `POST /signals/generate`, `GET /signals/live`, `GET /signals/history`
- `POST /settings/profile`, `POST /capital`
- WebSocket: `/ws/live`

## Architektura folderów
- `apps/api` — FastAPI, modele SQLAlchemy, routery.
- `apps/ml` — Celery worker, zadania: backfill/train/backtest.
- `apps/web` — Next.js (User/Admin).
- `migrations` — Alembic (schemat SQL).
- `ops/github` — CI.
- `tests` — testy krytycznych logik.
- Dockerfiles + compose na poziomie repo.

## Maker-first, cooldown, korelacje, kill-switch (noty)
- Maker-first: w realnej integracji z giełdą — post-only, fallback taker z capem poślizgu (logika do dodania w module egzekucji).
- Cooldown/kill-switch: można dodać licznik strat i globalny przełącznik (feature flag) — hook w generatorze sygnałów.
- Korelacyjny cap: w module sizingu, sprawdzaj łączną ekspozycję BTC/ETH względem `CORRELATION_CAP_BTC_ETH_PCT`.

## Development (lokalnie)
- `poetry install`
- `alembic upgrade head`
- `uvicorn apps.api.main:app --reload`

## Licencja
MIT
