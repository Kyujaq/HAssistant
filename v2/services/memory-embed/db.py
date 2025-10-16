import os
from contextlib import asynccontextmanager

import psycopg

DSN = os.getenv("DATABASE_URL")


@asynccontextmanager
async def get_conn():
    async with await psycopg.AsyncConnection.connect(DSN) as conn:
        yield conn
