# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A backend template for REST APIs. It has no business logic: FastAPI app factory, multi-environment settings, async SQLAlchemy 2.1 + Alembic on PostgreSQL (asyncpg), and OIDC access-token validation. Python 3.14, managed with **uv**. The README and config comments are in French.

## Commands

Run everything from the repo root, because `.env` is resolved relative to the working directory.

```bash
uv sync                                   # install deps (dev group included)
./launch.sh                               # = uv run fastapi dev (extra args forwarded, e.g. --port 8001)
uv run pytest                             # full test suite (no DB or network needed)
uv run pytest tests/test_auth.py::test_me_with_valid_token   # single test
uv run ruff check . && uv run ruff format --check .          # lint + format check
uv run alembic revision --autogenerate -m "..."              # new migration (or scripts/new_migration.sh "...")
uv run alembic upgrade head                                  # apply migrations (or scripts/migrate.sh)
scripts/init.sh                           # create the DB if missing, then migrate
scripts/rename.sh "My Project" --dry-run  # rename package, API title, README title, DB name
docker compose up --build                 # full stack; runs `alembic upgrade head && fastapi run`
```

`scripts/drop.sh` asks for interactive confirmation before it drops the database. The `fastapi` CLI reads its entrypoint (`app.main:app`) from `[tool.fastapi]` in `pyproject.toml`.

## Architecture

### Settings (`app/core/config.py`)
- Sources in decreasing priority: init kwargs > environment variables > `.env` > `config/<APP_ENV>.yaml`. Public, versioned values (CORS, hosts, OIDC issuer/audience) go in `config/*.yaml`. Secrets (`POSTGRES_PASSWORD`, an optional full `DATABASE_URL`) go in `.env`.
- `APP_ENV` is resolved *before* `Settings` is instantiated (env var first, then a manual parse of `.env`, defaulting to `development`), because it chooses which YAML file gets loaded.
- `settings = get_settings()` runs at import time, and `OIDC_ISSUER` and `OIDC_AUDIENCE` are required. Importing any `app.*` module therefore fails unless those values are available. `tests/conftest.py` sets test env vars **before** its `app` imports, so keep new imports below that block.
- `DATABASE_URL` is built from the `POSTGRES_*` parts (password URL-encoded). If set directly, it is normalized for asyncpg: the scheme is forced to `postgresql+asyncpg` and libpq `sslmode`/`channel_binding` become `ssl=true|false`. `alembic/env.py` escapes `%` in this URL for configparser.

### Database (`app/core/database.py`)
The engine and session factory are created at import time, but nothing connects until a query runs, so tests don't need Postgres. Inject sessions with `db: SessionDep`. The pool is disposed in the `lifespan` hook in `app/main.py`.

### Adding a domain
Create a new package `app/<domain>/` with `schemas.py`, `service.py` and `router.py`, then register the router in `create_app()` with `prefix=settings.API_V1_PREFIX`. Put its models in `app/models/<name>.py` and import them (adding them to `__all__`) in `app/models/__init__.py`. `alembic/env.py` imports `app.models`, so a model missing from that file is invisible to autogenerate.

### Auth (`app/core/auth.py`)
- The API is a resource server only: it **never issues tokens**. The front end runs the OIDC flow, and every request's Bearer token is validated here (RS256 via JWKS found through `/.well-known/openid-configuration`, plus checks on `iss`, `aud`, `exp`, `iat` and `sub`).
- All IdP-specific logic is kept in this one file on purpose. `OIDC_ROLES_CLAIM` names the roles claim. Its value can be a list or a mapping keyed by role (Zitadel). A nested claim such as Keycloak's `realm_access.roles` needs `_extract_roles` to be changed.
- `JWKSCache` refreshes keys after a TTL or when it sees an unknown `kid`, rate-limited so forged tokens can't hammer the IdP.
- Error contract: a missing or invalid token returns **401** with `WWW-Authenticate: Bearer` (`HTTPBearer(auto_error=False)` avoids FastAPI's default 403). An IdP that can't be reached or returns a malformed document gives **503**.
- Protect a route by adding the parameter `user: CurrentUser`. `GET /api/v1/me` is the reference example, and `/api/v1/health` stays public.
- The HTTP client package is `httpx2`, not `httpx`.

### Testing patterns (`tests/conftest.py`)
- `client` builds a fresh app through `create_app()`.
- For real token validation without network access, combine `mock_jwks` (monkeypatches `jwks_cache.get_signing_key` to return a generated RSA test key) with `make_token(...)` (signs RS256 tokens whose iss/aud/exp default to valid values; pass overrides or extra claims as kwargs).
- To skip validation entirely, set `app.dependency_overrides[get_current_user]`.
- pytest runs with `strict = true` (native `[tool.pytest]` config).

### Migrations and tooling
- `alembic.ini` `post_write_hooks` run `ruff format` and then `ruff check --fix` on every generated revision. Autogenerate uses `compare_type=True`.
- Ruff: line length 100, rules `E,F,I,UP,B`. `alembic` is declared `known-third-party` so the local `alembic/` folder doesn't confuse isort. `F401` is ignored in `alembic/versions/`.

### Docker
- The `Dockerfile` copies only `pyproject.toml`, `alembic.ini`, `alembic/`, `config/` and `app/` into the image. Any new top-level directory needed at runtime has to be added there.
- Compose forces `POSTGRES_HOST=db` for the api service. The `db` service reads `POSTGRES_*` from `.env` through compose interpolation, not from the YAML files, so keep the two consistent.

## Agent skills
`.claude/skills/` and `.agents/skills/` contain symlinks into `.venv` (for example the official FastAPI skill). They only resolve after `uv sync`. Refresh them with `uvx library-skills --claude`.
