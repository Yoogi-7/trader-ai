SHELL := /bin/bash

# ==== Konfiguracja ====
COMPOSE := docker compose
DB_USER := trader
DB_NAME := trader_ai
DB_HOST := db
DB_PORT := 5432

.PHONY: up down rebuild logs api web ml db dbwait migrate seed psql reset-schema help

help:
	@echo "Użycie:"
	@echo "  make up              - build & uruchom wszystkie serwisy"
	@echo "  make down            - zatrzymaj i usuń serwisy"
	@echo "  make migrate         - poczekaj na DB i wykonaj alembic upgrade head"
	@echo "  make seed            - odpal seedy"
	@echo "  make dbwait          - poczekaj aż DB przyjmuje połączenia"
	@echo "  make reset-schema    - DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
	@echo "  make psql            - wejdź do psql"
	@echo "  make api|web|ml      - zbuduj i uruchom wybrane"
	@echo "  make logs            - tail logów"
	@echo "  make rebuild         - przebuduj obrazy wszystkich serwisów"

up:
	$(COMPOSE) up -d --build

down:
	$(COMPOSE) down

rebuild:
	$(COMPOSE) build --no-cache
	$(COMPOSE) up -d

logs:
	$(COMPOSE) logs -f

api:
	$(COMPOSE) up -d --build api

web:
	$(COMPOSE) up -d --build web

ml:
	$(COMPOSE) up -d --build ml

db:
	$(COMPOSE) up -d db
	$(COMPOSE) logs -f db

dbwait:
	./scripts/wait_for_db.sh $(DB_HOST) $(DB_PORT) $(DB_USER) $(DB_NAME) 60

migrate:
	./scripts/wait_for_db.sh $(DB_HOST) $(DB_PORT) $(DB_USER) $(DB_NAME) 60
	$(COMPOSE) run --rm api alembic upgrade head

seed:
	./scripts/wait_for_db.sh $(DB_HOST) $(DB_PORT) $(DB_USER) $(DB_NAME) 60
	$(COMPOSE) run --rm api python -m apps.api.seed

psql:
	$(COMPOSE) exec -T db psql -U $(DB_USER) -d $(DB_NAME)

reset-schema:
	$(COMPOSE) exec -T db psql -U $(DB_USER) -d $(DB_NAME) -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
