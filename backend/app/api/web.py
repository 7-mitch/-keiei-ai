"""
#95 Web収集API
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.agents.web_agent import collect_news, collect_url
from app.core.security import get_current_user

router = APIRouter()

class CollectUrlRequest(BaseModel):
    url: str

@router.post("/collect")
async def collect(
    user: dict = Depends(get_current_user),
):
    """金融ニュースを一括収集する"""
    results = await collect_news()
    return {
        "message": f"{len(results)}件収集しました",
        "results": results[:10],
    }

@router.post("/collect/url")
async def collect_custom_url(
    req:  CollectUrlRequest,
    user: dict = Depends(get_current_user),
):
    """指定URLのコンテンツを収集する"""
    result = await collect_url(req.url)
    return result

@router.get("/logs")
async def get_logs(
    limit: int  = 20,
    user:  dict = Depends(get_current_user),
):
    """収集ログを取得する"""
    from app.db.connection import get_conn
    async with get_conn() as conn:
        rows = await conn.fetch("""
            SELECT id, url, status, data_type, processed_at
            FROM web_collection_logs
            ORDER BY processed_at DESC
            LIMIT $1
        """, limit)
    return [dict(r) for r in rows]
