#!/usr/bin/env bash
# Lance l'API en mode dev (rechargement auto) : http://localhost:8000/docs
# Les arguments sont transmis à `fastapi dev` (ex. ./launch.sh --port 8001).
set -euo pipefail
cd "$(dirname "$0")"

if ! command -v uv >/dev/null 2>&1; then
    echo "uv est requis : https://docs.astral.sh/uv/getting-started/installation/" >&2
    exit 1
fi

if [[ ! -f .env ]]; then
    echo "Note : pas de .env (cp .env.example .env pour définir POSTGRES_PASSWORD)." >&2
fi

exec uv run fastapi dev "$@"
