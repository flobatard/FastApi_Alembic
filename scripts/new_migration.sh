#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ $# -ne 1 ]]; then
    echo "Usage: $0 \"description de la migration\"" >&2
    exit 1
fi

uv run alembic revision --autogenerate -m "$1"
