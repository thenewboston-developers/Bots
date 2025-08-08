# Variables
SHELL := /bin/bash
.DEFAULT_GOAL := help
PYTHON := poetry run python
MANAGE := $(PYTHON) manage.py
DOCKER_COMPOSE := docker-compose
CELERY := poetry run celery

# Help
.PHONY: help
help:
	@echo "Available commands:"
	@echo ""
	@echo "  Development:"
	@echo "    make init                Initialize project"
	@echo "    make install             Install dependencies"
	@echo "    make migrate             Run database migrations"
	@echo "    make runserver           Start Django server"
	@echo ""
	@echo "  Docker:"
	@echo "    make docker-up           Start all services"
	@echo "    make docker-down         Stop all services"
	@echo "    make docker-logs         View logs"
	@echo "    make docker-init         First time setup"
	@echo ""
	@echo "  Testing:"
	@echo "    make test                Run tests"
	@echo "    make lint                Run linters"

# Development Setup
.PHONY: install
install:
	poetry install

.PHONY: install-pre-commit
install-pre-commit:
	poetry run pre-commit uninstall; poetry run pre-commit install

.PHONY: init
init:
	test -f .env || cp .env.example .env
	poetry install
	$(MANAGE) migrate || echo "Migration failed or already applied"
	$(MANAGE) collectstatic --noinput || true
	@echo "Initialization complete"

.PHONY: update
update: install install-pre-commit

# Database
.PHONY: migrate
migrate:
	$(MANAGE) migrate

.PHONY: makemigrations
makemigrations:
	$(MANAGE) makemigrations

.PHONY: createsuperuser
createsuperuser:
	$(MANAGE) createsuperuser

.PHONY: dbshell
dbshell:
	$(MANAGE) dbshell

# Local Development
.PHONY: runserver
runserver:
	$(MANAGE) runserver

.PHONY: redis
redis:
	redis-server

.PHONY: celery
celery:
	$(CELERY) -A tnb_exchange worker --loglevel=info

.PHONY: celery-beat
celery-beat:
	$(CELERY) -A tnb_exchange beat --loglevel=info

.PHONY: celery-flower
celery-flower:
	$(CELERY) -A tnb_exchange flower

# Bot Commands
.PHONY: run-bot
run-bot:
	@echo "Usage: make run-bot BOT=<bot_name>"
	@echo "Example: make run-bot BOT=my-trading-bot"
	@echo ""
	$(MANAGE) run_bot $(BOT) $(ARGS)

.PHONY: setup-bot
setup-bot:
	@echo "Usage: make setup-bot NAME=<name> USER=<username> PASS=<password>"
	@echo "Example: make setup-bot NAME=my-bot USER=myuser PASS=mypass"
	@echo ""
	$(MANAGE) setup_bot $(NAME) $(USER) $(PASS) $(ARGS)

.PHONY: list-bots
list-bots:
	$(MANAGE) shell -c "from trading.models import BotConfig; bots = BotConfig.objects.all(); [print(f'{b.name} ({b.bot_type}) - {b.status}') for b in bots] if bots else print('No bots configured. Use make setup-bot to create one.')"

.PHONY: create-sample-bot
create-sample-bot:
	$(MANAGE) shell -c "from trading.models import BotConfig; BotConfig.objects.get_or_create(name='sample-bot', defaults={'api_username': 'test_user', 'api_password': 'test_pass', 'bot_type': 'randy', 'status': 'stopped'}); print('Sample bot created: sample-bot')"

# Testing
.PHONY: test
test:
	$(MANAGE) test

.PHONY: lint
lint:
	poetry run pre-commit run --all-files

.PHONY: shell
shell:
	$(MANAGE) shell

# Docker Commands
.PHONY: docker-init
docker-init:
	$(DOCKER_COMPOSE) build && $(DOCKER_COMPOSE) up -d && sleep 5 && $(DOCKER_COMPOSE) exec -T web python manage.py migrate
	@echo "Docker environment ready"

.PHONY: docker-build
docker-build:
	$(DOCKER_COMPOSE) build

.PHONY: docker-up
docker-up:
	$(DOCKER_COMPOSE) up -d
	@echo "Services: Web (localhost:8000), Flower (localhost:5555)"

.PHONY: docker-down
docker-down:
	$(DOCKER_COMPOSE) down

.PHONY: docker-restart
docker-restart: docker-down docker-up

.PHONY: docker-logs
docker-logs:
	$(DOCKER_COMPOSE) logs -f

.PHONY: docker-ps
docker-ps:
	$(DOCKER_COMPOSE) ps

.PHONY: docker-shell
docker-shell:
	$(DOCKER_COMPOSE) exec web python manage.py shell

.PHONY: docker-bash
docker-bash:
	$(DOCKER_COMPOSE) exec web bash

.PHONY: docker-migrate
docker-migrate:
	$(DOCKER_COMPOSE) exec web python manage.py migrate

.PHONY: docker-makemigrations
docker-makemigrations:
	$(DOCKER_COMPOSE) exec web python manage.py makemigrations

.PHONY: docker-createsuperuser
docker-createsuperuser:
	$(DOCKER_COMPOSE) exec web python manage.py createsuperuser

.PHONY: docker-test
docker-test:
	$(DOCKER_COMPOSE) exec web python manage.py test

.PHONY: docker-clean
docker-clean:
	$(DOCKER_COMPOSE) down -v

# Cleanup
.PHONY: clean
clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true

# Development
.PHONY: dev
dev:
	@echo "Docker: make docker-init && make docker-up"
	@echo "Local: Run in separate terminals: make redis, make celery, make celery-beat, make runserver"