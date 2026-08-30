SHELL := /bin/bash
COMPOSE := docker compose

.DEFAULT_GOAL := help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	 awk 'BEGIN {FS=":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

env: ## Create .env from the template if it does not exist
	@test -f .env || (cp .env.example .env && echo ">> Created .env — edit it and replace every CHANGE_ME value.")

up: env ## Build and start the full stack
	$(COMPOSE) up -d --build

down: ## Stop the stack (data volumes preserved)
	$(COMPOSE) down

reset: ## Stop the stack and DELETE all data volumes
	$(COMPOSE) down -v

logs: ## Tail logs from all services
	$(COMPOSE) logs -f

ps: ## Show service status
	$(COMPOSE) ps

migrate: ## Apply database migrations
	$(COMPOSE) exec backend alembic upgrade head

migration: ## Autogenerate a migration:  make migration m="add x"
	$(COMPOSE) exec backend alembic revision --autogenerate -m "$(m)"

downgrade: ## Roll back one migration
	$(COMPOSE) exec backend alembic downgrade -1

seed: ## Seed roles, departments and the bootstrap admin
	$(COMPOSE) exec backend python -m app.seed

test: ## Run the backend test suite inside the container
	$(COMPOSE) exec backend pytest -q

test-local: ## Run the backend test suite on the host (no docker required)
	cd backend && python -m pytest -q

shell-api: ## Open a shell in the backend container
	$(COMPOSE) exec backend bash

shell-db: ## Open psql against the database
	$(COMPOSE) exec db psql -U $${POSTGRES_USER} -d $${POSTGRES_DB}

.PHONY: help env up down reset logs ps migrate migration downgrade seed test test-local shell-api shell-db
