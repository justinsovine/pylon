# Pylon task runner

default:
    @just --list

# Development
dev:
    uvicorn src.pylon.main:app --reload --host 0.0.0.0 --port 8000

worker:
    celery -A src.pylon.tasks.celery_app worker --loglevel=info --concurrency=3

beat:
    celery -A src.pylon.tasks.celery_app beat --loglevel=info

flower:
    celery -A src.pylon.tasks.celery_app flower --port=5555

# Run all services locally (API + worker + beat)
up:
    docker compose up -d

down:
    docker compose down

logs:
    docker compose logs -f

# Database
migrate:
    alembic upgrade head

migration message:
    alembic revision --autogenerate -m "{{message}}"

rollback:
    alembic downgrade -1

# Testing
test *args:
    pytest {{args}}

test-cov:
    pytest --cov=src/pylon --cov-report=term-missing

# Code quality
lint:
    ruff check src/ tests/
    pyright src/

fmt:
    ruff format src/ tests/
    ruff check --fix src/ tests/

# Setup
install:
    uv sync --all-extras

db-create:
    createdb pylon
    createdb pylon_test

seed:
    python -m src.pylon.seed
