# Makefile (root)

SHELL := /bin/bash

.PHONY: up down logs sh-api sh-worker ps web api backfill

up:
\tdocker compose -f infra/docker-compose.yml up -d --build

down:
\tdocker compose -f infra/docker-compose.yml down -v

logs:
\tdocker compose -f infra/docker-compose.yml logs -f --tail=200

ps:
\tdocker compose -f infra/docker-compose.yml ps

sh-api:
\tdocker compose -f infra/docker-compose.yml exec api /bin/sh

sh-worker:
\tdocker compose -f infra/docker-compose.yml exec ml-backfill /bin/sh

api:
\tuvicorn apps.api.main:app --host 0.0.0.0 --port 8000 --reload

web:
\tcd apps/web && npm run dev

backfill:
\tBACKFILL_MODE=loop python -m apps.ml.backfill
