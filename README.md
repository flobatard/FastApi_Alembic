# FastAPI + Alembic Template

Template de backend pour démarrer un projet **API REST**. Il fournit un socle
prêt à l'emploi : app factory, configuration multi-environnements, base de
données async et validation de tokens OIDC — sans aucune logique métier. À
cloner puis à adapter (renommer `PROJECT_NAME`, ajouter vos domaines).

Stack : **Python 3.14** + **FastAPI** + **SQLAlchemy 2.1 (async)** + **Alembic** +
**PostgreSQL 18 (asyncpg)** + **OIDC** (validation JWT côté resource-server).
Dépendances et environnement gérés par **[uv](https://docs.astral.sh/uv/)**,
lint/format par **Ruff**, tests par **pytest**.

## Architecture

```
app/
├── main.py            # FastAPI app factory + lifespan + CORS
├── core/              # cross-cutting concerns
│   ├── config.py      # settings (env > .env > config/<APP_ENV>.yaml)
│   ├── database.py    # async engine, session (SessionDep), declarative Base
│   └── auth.py        # validation JWT OIDC (JWKS) + CurrentUser
├── models/            # un module par modèle, tous ré-exportés dans __init__.py
├── health/            # healthcheck (public)
└── auth/              # route de démo protégée GET /me
config/                # config publique par environnement (development.yaml, production.yaml)
alembic/               # migrations (env.py async)
scripts/               # création / suppression de la base, raccourcis Alembic
tests/                 # pytest (sans réseau ni fournisseur OIDC réel)
pyproject.toml         # dépendances, entrypoint FastAPI, config Ruff et pytest
uv.lock                # versions exactes résolues (à committer)
```

Chaque nouveau domaine est un nouveau package sous `app/` avec ses `schemas.py`,
`service.py` et `router.py` ; ses modèles vont dans `app/models/<name>.py` et
sont importés (et listés dans `__all__`) dans `app/models/__init__.py` pour que
l'autogenerate d'Alembic les voie. Les dépendances s'injectent via des alias
`Annotated` : `db: SessionDep` pour une session, `user: CurrentUser` pour une
route protégée.

## Configuration

Les settings sont résolus par priorité décroissante : variables
d'environnement > `.env` > `config/<APP_ENV>.yaml` (`APP_ENV` vaut
`development` par défaut). Les valeurs publiques et versionnées (CORS, hôtes,
issuer/audience OIDC) vivent dans `config/` ; les secrets et overrides locaux
(`POSTGRES_PASSWORD`, éventuellement un `DATABASE_URL` complet) vivent dans
`.env`. L'URL de base de données est assemblée à partir des composants
`POSTGRES_*` avec encodage du mot de passe ; une URL de Postgres managé (avec
`sslmode=...`) peut être collée telle quelle dans `DATABASE_URL`, elle est
normalisée pour asyncpg.

## Authentification

Le flow de login OIDC (Authorization Code + PKCE) est censé être géré par le
client front. **Cette API n'émet jamais de tokens** : elle valide le token
d'accès à chaque requête — signature RS256 via le JWKS (découvert depuis
l'issuer), plus les vérifications `issuer`, `audience` et expiration. Deux
réglages suffisent : `OIDC_ISSUER` et `OIDC_AUDIENCE`.

Tout ce qui est spécifique au fournisseur d'identité est isolé dans
[app/core/auth.py](app/core/auth.py), pour qu'un changement de fournisseur ne
touche que ce fichier. Le claim portant les rôles applicatifs dépend du
fournisseur : il se configure via `OIDC_ROLES_CLAIM` (ex. `roles`, ou
`urn:zitadel:iam:org:project:roles` pour Zitadel).

Les routes protégées déclarent un paramètre `user: CurrentUser` (alias de
`Depends(get_current_user)`) ; `GET /api/v1/me` sert d'exemple de référence.
`/api/v1/health` reste publique.

## Setup (dev local)

Prérequis : [uv](https://docs.astral.sh/uv/getting-started/installation/) (il
installe lui-même Python 3.14 si besoin, cf. `.python-version`).

```bash
uv sync                       # crée .venv et installe les dépendances (dev incluses)
cp .env.example .env          # secrets ; mettez vos URLs OIDC dans config/development.yaml
```

Ajouter une dépendance : `uv add <paquet>` (ou `uv add --dev <paquet>`) ; mettre
à jour le lockfile : `uv lock --upgrade`.

## Run

### Docker (nominal)

```bash
cp .env.example .env          # définir POSTGRES_PASSWORD (et APP_ENV=production en prod)
docker compose up --build
```

Les migrations s'appliquent automatiquement au démarrage (`alembic upgrade
head`), puis l'API est servie par `fastapi run` sur le port 8000. L'image est
construite avec uv à partir de `uv.lock` (sans les dépendances de dev). Un éventuel reverse proxy devant
l'API est hors périmètre de ce repo.

### Bare (dev)

```bash
uv run fastapi dev            # entrypoint lu dans [tool.fastapi] (pyproject.toml)
```

Docs sur http://localhost:8000/docs · health sur http://localhost:8000/api/v1/health

## Migrations de base de données

```bash
uv run alembic revision --autogenerate -m "..."   # créer une migration depuis les modèles
uv run alembic upgrade head                        # appliquer les migrations
uv run alembic downgrade -1                        # revenir une révision en arrière
```

Les migrations générées sont automatiquement passées à `ruff check --fix` puis
`ruff format` (hooks `post_write_hooks` dans `alembic.ini`). Raccourcis
équivalents : `scripts/new_migration.sh "..."`, `scripts/migrate.sh`, et
`scripts/init.sh` / `scripts/drop.sh` pour créer / supprimer la base.

Exécution manuelle dans Docker : `docker compose run --rm api alembic upgrade head`.

## Tests

```bash
uv run pytest
uv run ruff check . && uv run ruff format --check .
```

Les tests d'auth signent des tokens avec une clé RSA générée et stubbent le
cache JWKS — aucun réseau ni fournisseur OIDC réel requis.

## Skills pour agents IA

`.agents/skills/` et `.claude/skills/` contiennent des liens vers les skills
fournies par les dépendances installées (ex. la skill officielle FastAPI) ; ils
se résolvent après `uv sync`. Pour les rafraîchir après une mise à jour :
`uvx library-skills --claude`.
