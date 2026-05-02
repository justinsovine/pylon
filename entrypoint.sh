#!/bin/bash
set -e

if [ "${RUN_MIGRATIONS:-false}" = "true" ]; then
    echo "Running database migrations..."
    uv run alembic upgrade head
fi

echo "Starting application..."
exec "$@"
