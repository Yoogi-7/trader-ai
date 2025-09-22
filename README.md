# Trader AI — monorepo (prod)

System generujący sygnały na krypto futures z minimalną ingerencją użytkownika.  
Stack: **FastAPI + TimescaleDB + Redis + Redpanda/Kafka + Celery + Next.js**.

## Szybki start

```bash
git clone https://github.com/Yoogi-7/trader-ai.git
cd trader-ai
cp .env.example .env
make up
make migrate
make seed
