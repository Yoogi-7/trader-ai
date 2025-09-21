# Trader AI — monorepo (demo/prod-ready skeleton)

## Wymagania
- Docker + Docker Compose
- Porty wolne: 3000 (web), 8000 (api), 5432 (db), 6379 (redis), 9092 (redpanda)

## Szybki start (tryb demo/mock)
```bash
git clone <this_repo>
cd trader_ai_full
cp .env.example .env  # opcjonalnie
docker compose up -d --build
make migrate
make seed
# Panel użytkownika: http://localhost:3000/user
# Panel admina:     http://localhost:3000/admin
```

## Seedy i dane
- `make seed` generuje syntetyczne OHLCV (1m) oraz domyślnego usera.
- `make backfill` uruchamia zadanie backfill z checkpointami (symulacja).

## Trening i backtest
- `make train` zapisuje metryki OOS (demo: 57% TP1).
- `make backtest` generuje transakcje z rozliczeniem fee+funding.

## Kryteria akceptacji
- **Hit-rate ≥55% TP1 (OOS)**: widoczne w `GET /train/status` oraz w panelu admina (demo: 0.57).
- **Filtr ≥2% netto**: zaimplementowany w API/ML (publikujemy tylko sygnały z `expected_net_pct >= 2.0`), test: `apps/api/tests/test_rules.py`.
- **Resume backfill**: tabela `backfill_progress` + test `test_backfill_resume.py`.
- **Symulacja od 100$**: panel użytkownika (`/user`) i backtester z parametrami startowego kapitału.

## Endpointy
Patrz `openapi.yaml` lub dokumentacja FastAPI (po uruchomieniu).

## Jak zdekodować Base64 i rozpakować
```bash
base64 -d trader_ai_full.zip.b64 > trader_ai_full.zip && unzip trader_ai_full.zip
```

> Uwaga: repo działa w trybie **demo** bez kluczy API, z syntetycznymi danymi i lekkim silnikiem ML.