# backend/app/api/collect.py
from fastapi import APIRouter, Depends
from app.services.data_collector import collect_and_store
from app.services.dwh_schema import initialize_tables
from app.services.bigquery_service import BigQueryService
from app.core.security import get_current_user

router = APIRouter()

@router.post("/initialize")
async def initialize_dwh(
    user: dict = Depends(get_current_user)
):
    """DWHテーブルを初期化"""
    bq = BigQueryService()
    initialize_tables(bq)
    return {"message": "DWH初期化完了"}

@router.post("/sync")
async def sync_data(
    user: dict = Depends(get_current_user)
):
    """全データソースから同期"""
    await collect_and_store()
    return {"message": "データ同期完了"}