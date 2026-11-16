FROM python:3.14-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.13.8 /uv /bin/uv
# Bytecode précompilé (démarrage plus rapide), copie depuis le cache monté,
# et utilisation du Python de l'image (pas de téléchargement par uv).
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0
WORKDIR /srv/app
# Dépendances seules (sans le groupe dev), dans une couche mise en cache tant
# que pyproject.toml / uv.lock ne changent pas.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-dev

FROM python:3.14-slim
ENV PATH="/srv/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1
RUN useradd --create-home appuser
WORKDIR /srv/app
COPY --from=builder /srv/app/.venv ./.venv
# pyproject.toml porte l'entrypoint lu par `fastapi run` ([tool.fastapi])
COPY pyproject.toml alembic.ini ./
COPY alembic/ ./alembic/
COPY config/ ./config/
COPY app/ ./app/
USER appuser
EXPOSE 8000
CMD ["fastapi", "run"]
