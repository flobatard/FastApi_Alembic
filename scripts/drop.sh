#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

read -r -p "Are you sure you want to drop the database? [y/N] " confirm
if [[ "${confirm,,}" != "y" ]]; then
    echo "Aborted."
    exit 1
fi

echo "==> Dropping database..."
uv run python scripts/drop_db.py

echo "==> Done."
