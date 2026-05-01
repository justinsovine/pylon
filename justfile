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

# Pre-investigation (zero-token static analysis)
pre-investigate repo_path notes_path *keywords:
    python -m src.pylon.harness.cli pre-investigate {{repo_path}} {{notes_path}} {{keywords}}

check-tools:
    python -m src.pylon.harness.cli check-tools

# Setup
install:
    uv sync --all-extras

install-system-tools:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "Installing system tools..."
    if command -v apt-get &>/dev/null; then
        sudo apt-get update && sudo apt-get install -y ripgrep universal-ctags php-cli php-xml php-mbstring
    elif command -v brew &>/dev/null; then
        brew install ripgrep universal-ctags php
    else
        echo "Unsupported package manager. Install manually: ripgrep, universal-ctags, php-cli"
        exit 1
    fi
    echo "Installing phpstan..."
    if command -v composer &>/dev/null; then
        composer global require phpstan/phpstan --no-interaction
    else
        echo "Composer not found. Install composer first, then: composer global require phpstan/phpstan"
    fi
    echo "Done. Run 'just check-tools' to verify."

db-create:
    createdb pylon
    createdb pylon_test

seed:
    python -m src.pylon.seed
