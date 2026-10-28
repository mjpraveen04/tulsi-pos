#!/bin/sh
set -e

echo "[entrypoint] applying Alembic migrations..."
alembic upgrade head

if [ "${SEED_ON_START:-false}" = "true" ]; then
  echo "[entrypoint] seeding demo data (idempotent)..."
  python -m app.seed
fi

echo "[entrypoint] starting uvicorn..."
# Render injects PORT; Compose and local runs fall back to 8000.
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers --forwarded-allow-ips="*"
