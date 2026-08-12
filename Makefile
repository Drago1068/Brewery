.PHONY: up down migrate test test-api test-web test-e2e lint

up:
	docker compose up --build

down:
	docker compose down

migrate:
	docker compose run --rm api alembic upgrade head

test:
	docker compose run --rm api pytest
	docker compose run --rm web npm test

test-api:
	docker compose run --rm api pytest

test-web:
	docker compose run --rm web npm test

test-e2e:
	docker compose --profile test run --rm e2e

lint:
	docker compose run --rm api ruff check .
	docker compose run --rm web npm run lint

