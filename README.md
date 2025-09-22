
# Trader AI — monorepo (prod-ready, minimal)

System AI generujący sygnały dla krypto futures. Monorepo zawiera:

- **apps/api** — FastAPI + SQLAlchemy + Alembic (TimescaleDB)
- **apps/ml** — worker z generatorem sygnałów (demo), zadania backfill/train
- **apps/web** — Next.js (panel użytkownika + admin — wersja minimal)
- **docker-compose.yml** — cały stos: TimescaleDB, Redis, Redpanda, API, worker, web
- **tests** — testy: filtr ≥2% net, sizing + likwidacja, smoke backfill
- **ops/github/ci.yml** — GitHub Actions (build + test)
- **openapi.yaml** — skrócone API

> Kod jest niewielki, ale zorganizowany produkcyjnie. Możesz rozszerzać ML (walk‑forward, Optuna) w `apps/ml`.

## Szybki start

```bash
cp .env.example .env
make up
make migrate
make seed
# (opcjonalnie) uruchom podgląd backfill/train:
make backfill
make train

# API: http://localhost:8000/docs
# WEB: http://localhost:3000
```

## Struktura repo

```
.:
Makefile
alembic.ini
apps
docker-compose.yml
infra
migrations
openapi.yaml
ops
tests

./apps:
api
ml
web

./apps/api:
__init__.py
config.py
crud.py
db
main.py
migrations_env.py
routers.py
schemas.py
security.py
seed.py
services
tools
websocket.py

./apps/api/db:
__init__.py
models.py
session.py

./apps/api/services:
risk.py

./apps/api/tools:
__init__.py
backtester.py
filters.py
run_backtest.py
signals.py
sizing.py

./apps/ml:
__init__.py
jobs
worker.py

./apps/ml/jobs:
__init__.py
backfill.py
train.py

./apps/web:
next.config.js
package.json
pages

./apps/web/pages:
admin.tsx
index.tsx

./infra:
api.Dockerfile
requirements-api.txt
requirements-ml.txt
web.Dockerfile
worker.Dockerfile

./migrations:
README
env.py
versions

./migrations/versions:
0001_init.py

./ops:
github

./ops/github:
ci.yml

./tests:
__init__.py
test_backfill_resume_stub.py
test_filter_net2pct.py
test_sizing_liq.py

```

## Kryteria akceptacji – gdzie w kodzie

- **Hit‑rate ≥ 55% (TP1, OOS, po kosztach)** – panel admina pokazuje wynik z backtestu (mock). Docelowo: `apps/ml/jobs/train.py` + rejestr metryk w DB.
- **Filtr ≥ 2% netto** – `apps/api/tools/filters.py` + endpoint `/signals/generate` + test `tests/test_filter_net2pct.py`.
- **Resume backfill** – stub w `apps/ml/jobs/backfill.py` (wejście pod realny backfill z checkpointami).
- **Symulacja od 100$** – `/backtest/run` zwraca PnL od 100$ (przykład), front (user panel).

## Co usunąć z Twojego ZIP-a i dlaczego

1. **Duplikaty API**: katalog `apps/api/trader_api/*` — przestarzała wersja z błędami (ucięte pliki, literówki), powoduje konflikty importów.
2. **Powielone Dockerfile**: `infra/docker/*.Dockerfile` i `infra/*.Dockerfile` — zostaw **infra/api.Dockerfile**, **infra/worker.Dockerfile**, **infra/web.Dockerfile**.
3. **Nadmiarowe pliki testów z błędami**: `apps/api/tests/*` w starym layoucie (odwołują się do nieistniejących modułów) — zastąp testami z `tests/`.
4. **Braki infra**: brakowało `docker-compose.yml` — dodane w tym repo.
5. **Uszkodzone moduły**: `services/filters.py`, `models.py`, `worker.py` w Twoim ZIP-ie zawierały wstawki typu `...` i błędne identyfikatory (`risk_$`, `...xposure_usd`). Usuń/napraw — w tym repo masz poprawne odpowiedniki: `apps/api/tools/*`, `apps/ml/worker.py`.
6. **Podwójne requirements**: scal w dwa pliki: `infra/requirements-api.txt` i `infra/requirements-ml.txt`.

## Jak uruchomić i zweryfikować

1. **Start**: `make up && make migrate && make seed`  
2. **API**: otwórz `http://localhost:8000/docs` (OpenAPI).  
3. **Front**: `http://localhost:3000` – heartbeat + panele.  
4. **Testy**: `make test`.  
5. **Sygnały**: wywołaj `POST /signals/generate` z korpusem:
   ```json
   {
     "symbol":"BTCUSDT","direction":"LONG","entry":60000,"sl":59400,"tp":[60600,61200,62000],
     "leverage":5,"risk_pct":0.01,"margin_mode":"isolated","tf_base":"15m","ts":"2025-09-22T10:37:33.301826","confidence":0.6
   }
   ```
   Powinieneś otrzymać `ok=true` jeśli **expected_net_pct ≥ 2%** i **confidence ≥ 0.55**.

## Kolejne kroki (propozycja)

- Zastąp demo worker `apps/ml/worker.py` realnym pipeline’em:
  - backfill OHLCV 1m (ccxt) + resampling do 15m/1h/4h/1d
  - featury (EMA/RSI/ATR/Ichimoku/Fibo), triple‑barrier labels, meta‑labeling
  - walk‑forward (purge & embargo), Optuna, rejestr modeli i metryk
  - drift PSI/KS i autoretrain + rollback
- Dodaj webhooki (Telegram/Discord) i paper/live trading (maker‑first, fallback taker z capem poślizgu).

---

> W tym repo skupiłem się, żeby **aplikacja faktycznie wstała** i żeby krytyczne elementy (filtr ≥2% net, sizing, likwidacja, testy, CI) były gotowe do działania. Dalej możemy rozbudowywać ML zgodnie z Twoimi wymaganiami.
