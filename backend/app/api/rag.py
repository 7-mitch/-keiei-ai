"""
#96 RAG API
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.agents.rag_agent import (
    build_vector_store,
    search_documents,
    evaluate_relevance,
)
from app.core.security import get_current_user

router = APIRouter()

class RagSearchRequest(BaseModel):
    query: str
    k:     int = 3

# ===== ドキュメント検索 =====
@router.post("/search")
async def search(
    req:  RagSearchRequest,
    user: dict = Depends(get_current_user),
):
    """審査規程・社内文書を検索する"""
    docs    = search_documents(req.query, k=req.k)
    quality = evaluate_relevance(req.query, docs)

    return {
        "query":   req.query,
        "quality": quality,
        "results": docs,
    }


# ===== インデックス再構築 =====
@router.post("/rebuild")
async def rebuild_index(
    user: dict = Depends(get_current_user),
):
    """ベクトルストアを再構築する"""
    try:
        store = build_vector_store()
        return {"message": "インデックスを再構築しました"}
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=str(e))