"""
dpo.py — DPOパイプライン管理API
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.core.security import get_current_user

router = APIRouter()


class ExportRequest(BaseModel):
    output_path: str = "dpo_export.jsonl"


@router.post("/generate")
async def generate_pairs(
    user: dict = Depends(get_current_user),
):
    """chosen/rejectedペアを自動生成"""
    if user.get("role") != "executive":
        raise HTTPException(status_code=403, detail="権限がありません")
    from app.agents.dpo_pipeline import generate_dpo_pairs
    count = await generate_dpo_pairs()
    return {"message": f"{count}件のDPOペアを生成しました", "count": count}


@router.post("/export")
async def export_dataset(
    req:  ExportRequest,
    user: dict = Depends(get_current_user),
):
    """HuggingFace形式でエクスポート"""
    if user.get("role") != "executive":
        raise HTTPException(status_code=403, detail="権限がありません")
    from app.agents.dpo_pipeline import export_dpo_dataset
    count = await export_dpo_dataset(req.output_path)
    return {"message": f"{count}件をエクスポートしました", "path": req.output_path}


@router.get("/stats")
async def get_stats(
    user: dict = Depends(get_current_user),
):
    """DPO統計情報を取得"""
    if user.get("role") != "executive":
        raise HTTPException(status_code=403, detail="権限がありません")
    from app.agents.dpo_pipeline import get_dpo_stats
    stats = await get_dpo_stats()
    return stats


@router.get("/improvements")
async def get_improvements(
    user: dict = Depends(get_current_user),
):
    """プロンプト改善候補を取得"""
    if user.get("role") != "executive":
        raise HTTPException(status_code=403, detail="権限がありません")
    from app.agents.dpo_pipeline import extract_prompt_improvements
    improvements = await extract_prompt_improvements()
    return {"improvements": improvements}