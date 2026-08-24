from uvfastapi.config.settings import (
    POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DATABASE,
    POSTGRES_USER, POSTGRES_PASSWORD,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = (
    f"postgresql+psycopg2://{POSTGRES_USER}:{POSTGRES_PASSWORD}"
    f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DATABASE}"
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


import asyncpg

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    """
    Return the shared asyncpg connection pool, creating it on first call.
    Call this once at app startup (e.g. inside FastAPI lifespan) and then
    it is re-used for every request.
    """
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            host=POSTGRES_HOST,
            port=int(POSTGRES_PORT),
            database=POSTGRES_DATABASE,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
            min_size=2,
            max_size=10,
        )
    return _pool


async def close_pool() -> None:
    """Gracefully close the connection pool. Call this on app shutdown."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None