.PHONY: help build up down logs test migrate shell

help:
	@echo "TraderAI - Makefile Commands"
	@echo ""
	@echo "  make build    - Build Docker images"
	@echo "  make up       - Start all services"
	@echo "  make down     - Stop all services"
	@echo "  make logs     - View logs (all services)"
	@echo "  make test     - Run test suite"
	@echo "  make migrate  - Run database migrations"
	@echo "  make shell    - Open API container shell"

build:
	docker-compose build

up:
	docker-compose up -d

down:
	docker-compose down

logs:
	docker-compose logs -f

test:
	docker-compose exec api pytest tests/ -v

migrate:
	docker-compose exec api alembic upgrade head

shell:
	docker-compose exec api /bin/bash
