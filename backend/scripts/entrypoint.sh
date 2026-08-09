#!/bin/sh
set -e

echo "BrewingOS backend: running migrations..."
alembic upgrade head

echo "BrewingOS backend: starting API..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
