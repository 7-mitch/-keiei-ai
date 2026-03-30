import asyncio, asyncpg
from app.core.config import settings

async def run():
    conn = await asyncpg.connect(settings.database_url)
    rows = await conn.fetch(
        "SELECT column_name FROM information_schema.columns WHERE table_name='users'"
    )
    for r in rows:
        print(r['column_name'])
    await conn.close()

asyncio.run(run())
