"""
#93 不正検知API
- 取引の不正チェック
- モデルの学習・評価
- Precision/Recall確認
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.agents.fraud_agent import fraud_detector
from app.agents.fraud_ml_model import train_from_db, evaluate_model
from app.db.connection import get_conn
from app.core.security import get_current_user, require_role
from datetime import datetime, timezone
import uuid

router = APIRouter()

# ===== リクエストの型定義 =====
class FraudCheckRequest(BaseModel):
    transaction_id: int

class ManualFraudRequest(BaseModel):
    account_id:       int
    amount:           float
    transaction_type: str = "debit"
    description:      str = ""

# ===== 取引の不正チェック =====
@router.post("/check")
async def check_fraud(
    req:  FraudCheckRequest,
    user: dict = Depends(get_current_user),
):
    """既存の取引IDに対して不正検知を実行する"""
    async with get_conn() as conn:
        tx = await conn.fetchrow("""
            SELECT
                t.*,
                a.user_id AS account_user_id
            FROM transactions t
            JOIN accounts a ON t.account_id = a.id
            WHERE t.id = $1
        """, req.transaction_id)

    if not tx:
        raise HTTPException(status_code=404, detail="取引が見つかりません")

    session_id = str(uuid.uuid4())

    result = await fraud_detector.ainvoke({
        "transaction_id":   tx["id"],
        "account_id":       tx["account_id"],
        "amount":           float(tx["amount"]),
        "transaction_type": tx["transaction_type"],
        "description":      tx.get("description", "") or "",
        "created_at":       str(tx["created_at"]),
        "rule_result":      {},
        "pattern_result":   {},
        "llm_result":       {},
        "ml_result":        {},
        "is_fraud":         False,
        "risk_score":       0.0,
        "severity":         "low",
        "reasoning":        "",
        "session_id":       session_id,
    })

    return {
        "transaction_id": req.transaction_id,
        "is_fraud":       result["is_fraud"],
        "risk_score":     round(result["risk_score"], 3),
        "severity":       result["severity"],
        "reasoning":      result["reasoning"],
        "session_id":     session_id,
    }


# ===== 手動で取引データを入力して不正チェック =====
@router.post("/check/manual")
async def check_fraud_manual(
    req:  ManualFraudRequest,
    user: dict = Depends(get_current_user),
):
    """取引データを直接入力して不正チェックを実行する（テスト用）"""
    session_id = str(uuid.uuid4())

    result = await fraud_detector.ainvoke({
        "transaction_id":   0,
        "account_id":       req.account_id,
        "amount":           req.amount,
        "transaction_type": req.transaction_type,
        "description":      req.description,
        "created_at":       datetime.now(timezone.utc).isoformat(),
        "rule_result":      {},
        "pattern_result":   {},
        "llm_result":       {},
        "ml_result":        {},
        "is_fraud":         False,
        "risk_score":       0.0,
        "severity":         "low",
        "reasoning":        "",
        "session_id":       session_id,
    })

    return {
        "is_fraud":   result["is_fraud"],
        "risk_score": round(result["risk_score"], 3),
        "severity":   result["severity"],
        "reasoning":  result["reasoning"],
        "session_id": session_id,
    }


# ===== MLモデルをDBデータで学習 =====
@router.post("/model/train")
async def train_fraud_model(
    user: dict = Depends(require_role("executive", "manager")),
):
    """DBの取引データでMLモデルを学習する"""
    try:
        result = await train_from_db()
        return {"message": "学習完了", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ===== モデル評価結果を確認 =====
@router.get("/model/evaluate")
async def get_model_evaluation(
    user: dict = Depends(get_current_user),
):
    """現在のMLモデルのPrecision/Recallを確認する"""
    return evaluate_model()