"""
Create the PostgreSQL database if it does not already exist.
Reads connection info from app.core.config (DATABASE_URL).
"""

import asyncio
import sys

import asyncpg
from sqlalchemy.engine import make_url

sys.path.insert(0, ".")
from app.core.config import get_settings


async def create_database_if_not_exists() -> None:
    # make_url decodes the URL-encoded credentials (urlparse would not)
    url = make_url(get_settings().DATABASE_URL)
    db_name = url.database

    # Connect to the default 'postgres' maintenance database
    conn = await asyncpg.connect(
        host=url.host,
        port=url.port or 5432,
        user=url.username,
        password=url.password,
        database="postgres",
    )

    try:
        exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", db_name)
        if exists:
            print(f"Database '{db_name}' already exists — skipping creation.")
        else:
            # CREATE DATABASE cannot run inside a transaction block
            await conn.execute(f'CREATE DATABASE "{db_name}"')
            print(f"Database '{db_name}' created.")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(create_database_if_not_exists())
