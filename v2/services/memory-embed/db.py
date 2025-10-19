import os
from contextlib import asynccontextmanager
from typing import Optional

from psycopg_pool import AsyncConnectionPool

DSN = os.getenv("DATABASE_URL")
POOL_MIN_SIZE = int(os.getenv("DB_POOL_MIN_SIZE", "1"))
POOL_MAX_SIZE = int(os.getenv("DB_POOL_MAX_SIZE", "10"))

_pool: Optional[AsyncConnectionPool] = None


def _get_pool() -> AsyncConnectionPool:
    global _pool
    if _pool is None:
        if not DSN:
            raise RuntimeError("DATABASE_URL is not configured")
        _pool = AsyncConnectionPool(conninfo=DSN, min_size=POOL_MIN_SIZE, max_size=POOL_MAX_SIZE)
    return _pool


@asynccontextmanager
async def get_conn():
    pool = _get_pool()
    async with pool.connection() as conn:
        yield conn
