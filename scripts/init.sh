#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> Creating database if not exists..."
uv run python scripts/init_db.py

echo "==> Running Alembic migrations..."
uv run alembic upgrade head

echo "==> Done."
