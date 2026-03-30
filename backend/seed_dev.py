import asyncio, asyncpg
from app.core.config import settings

async def run():
    conn = await asyncpg.connect(settings.database_url)
    await conn.execute("INSERT INTO projects (name, description, status) VALUES ($1, $2, $3) ON CONFLICT DO NOTHING", "KEIEI-AI工程管理", "工程管理モジュール開発", "active")
    pid = await conn.fetchval("SELECT id FROM projects WHERE name = $1", "KEIEI-AI工程管理")
    tasks = [
        (pid,1,"要件定義","田中 健","done",100),
        (pid,1,"基本設計","佐藤 花子","doing",65),
        (pid,2,"API実装","山田 太郎","risk",40),
        (pid,2,"UI実装","鈴木 誠","todo",0),
        (pid,3,"テスト","田中 健","todo",0),
    ]
    for t in tasks:
        await conn.execute("INSERT INTO tasks (project_id,phase,name,assign,status,progress) VALUES ($1,$2,$3,$4,$5,$6)", *t)
    print("サンプルデータ投入完了")
    await conn.close()

asyncio.run(run())
