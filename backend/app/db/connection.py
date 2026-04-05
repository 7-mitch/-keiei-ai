import asyncpg
from contextlib import asynccontextmanager
from app.core.config import settings

_pool: asyncpg.Pool | None = None

async def init_db() -> None:
    global _pool
    ssl = None
    _pool = await asyncpg.create_pool(
        dsn=settings.database_url,
        min_size=2,
        max_size=20,
        ssl=ssl,
        command_timeout=30,
        statement_cache_size=0,
    )
    print(f" DB接続完了（{settings.environment}）")

async def close_db() -> None:
    if _pool:
        await _pool.close()

@asynccontextmanager
async def get_conn():
    if not _pool:
        raise RuntimeError("DB未初期化")
    async with _pool.acquire() as conn:
        yield conn
