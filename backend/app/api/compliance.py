"""
api/compliance.py — コンプライアンスAPIエンドポイント
既存の backend/app/api/ に追加するファイル

エンドポイント一覧:
  POST /compliance/check      — コンプライアンス審査
  POST /compliance/certify    — 士業レビュー認証
  GET  /compliance/audit-log  — 監査ログ取得（admin専用）
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Literal
from app.core.security import get_current_user, require_role
from app.agents.compliance_agent import (
    run_compliance_agent,
    certify_compliance_result,
)

router = APIRouter(prefix="/compliance", tags=["compliance"])


# =====================================================
# リクエスト / レスポンスモデル
# =====================================================

class ComplianceCheckRequest(BaseModel):
    question: str
    session_id: str = "default"


class ComplianceCheckResponse(BaseModel):
    result: str              # Markdown形式の審査結果
    risk_level: str
    requires_expert: bool


class CertifyRequest(BaseModel):
    result_id: str
    license_number: str
    specialist_type: Literal["sr", "lawyer", "cpa", "smc"]


# =====================================================
# エンドポイント
# =====================================================

@router.post("/check", response_model=ComplianceCheckResponse)
async def check_compliance(
    req: ComplianceCheckRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    コンプライアンス審査エンドポイント
    全ロールでアクセス可能（ログイン必須）
    """
    result_md = await run_compliance_agent(req.question, req.session_id)

    # risk_level と requires_expert を結果から抽出
    risk_level = "caution"
    requires_expert = False
    if "🔴" in result_md:
        risk_level = "critical"
        requires_expert = True
    elif "🟠" in result_md:
        risk_level = "warning"
        requires_expert = True
    elif "🟡" in result_md:
        risk_level = "caution"
    elif "✅" in result_md:
        risk_level = "safe"

    return ComplianceCheckResponse(
        result=result_md,
        risk_level=risk_level,
        requires_expert=requires_expert,
    )


@router.post("/certify")
async def certify_result(
    req: CertifyRequest,
    current_user: dict = Depends(require_role("admin", "specialist")),
):
    """
    士業によるレビュー認証エンドポイント
    admin / specialist ロールのみアクセス可能
    """
    certified = await certify_compliance_result(
        result_id=req.result_id,
        specialist_license_number=req.license_number,
        specialist_type=req.specialist_type,
    )
    return {
        "message": "士業レビュー認証が完了しました",
        "certified_by": certified.certified_by,
        "certified_at": certified.certified_at.isoformat() if certified.certified_at else None,
    }


@router.get("/audit-log")
async def get_audit_log(
    date: str | None = None,
    current_user: dict = Depends(require_role("admin")),
):
    """
    監査ログ取得エンドポイント（adminのみ）
    date: YYYYMMDD 形式（省略時は当日）
    """
    import json, os
    from datetime import datetime, timezone

    target_date = date or datetime.now(timezone.utc).strftime("%Y%m%d")
    log_path = f"logs/compliance/audit_{target_date}.jsonl"

    if not os.path.exists(log_path):
        return {"date": target_date, "entries": [], "count": 0}

    entries = []
    with open(log_path, encoding="utf-8") as f:
        for line in f:
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    return {"date": target_date, "entries": entries, "count": len(entries)}
