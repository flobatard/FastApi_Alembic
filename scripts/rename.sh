#!/usr/bin/env bash
# Renomme le projet issu du template : scripts/rename.sh "Mon Projet" [--dry-run]
# Options (--slug, --db, --description) : scripts/rename.sh --help
set -euo pipefail
cd "$(dirname "$0")/.."

exec uv run python scripts/rename_project.py "$@"
