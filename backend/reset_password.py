import asyncio, asyncpg, bcrypt
from app.core.config import settings

async def run():
    pw = "Keiei2025!"
    hashed = bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()
    conn = await asyncpg.connect(settings.database_url)
    sql = "UPDATE users SET password_hash = $1 WHERE email = $2"
    await conn.execute(sql, hashed, "ceo@keiei-ai.com")
    await conn.close()
    print("完了!")

asyncio.run(run())
