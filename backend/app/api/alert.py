from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.db.connection import get_conn
from app.db.audit import record_audit
from app.core.security import get_current_user, require_role

router = APIRouter()

# ===== リクエストの型定義 =====
class AlertUpdateRequest(BaseModel):
    status:  str        # 'investigating' | 'resolved' | 'false_positive'
    comment: str = ""

# ===== アラート一覧取得 =====
@router.get("")
async def get_alerts(
    severity: str | None = None,
    status:   str | None = None,
    limit:    int        = 50,
    user:     dict       = Depends(get_current_user),
):
    """不正アラート一覧を取得する"""
    async with get_conn() as conn:
        conditions = []
        params     = []

        if severity:
            params.append(severity)
            conditions.append(f"fa.severity = ${len(params)}")
        if status:
            params.append(status)
            conditions.append(f"fa.status = ${len(params)}")

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params.append(limit)

        rows = await conn.fetch(f"""
            SELECT
                fa.id,
                fa.alert_type,
                fa.severity,
                fa.description,
                fa.status,
                fa.created_at,
                fa.resolved_at,
                t.amount,
                t.transaction_type,
                u.name AS user_name
            FROM fraud_alerts fa
            LEFT JOIN transactions t ON fa.transaction_id = t.id
            LEFT JOIN accounts     a ON t.account_id = a.id
            LEFT JOIN users        u ON a.user_id = u.id
            {where}
            ORDER BY fa.created_at DESC
            LIMIT ${len(params)}
        """, *params)

        return [dict(r) for r in rows]


# ===== アラート詳細取得 =====
@router.get("/{alert_id}")
async def get_alert(
    alert_id: int,
    user:     dict = Depends(get_current_user),
):
    """特定のアラート詳細を取得する"""
    async with get_conn() as conn:
        row = await conn.fetchrow("""
            SELECT
                fa.*,
                t.amount,
                t.description AS tx_description,
                u.name        AS user_name,
                u.email       AS user_email
            FROM fraud_alerts fa
            LEFT JOIN transactions t ON fa.transaction_id = t.id
            LEFT JOIN accounts     a ON t.account_id = a.id
            LEFT JOIN users        u ON a.user_id = u.id
            WHERE fa.id = $1
        """, alert_id)

    if not row:
        raise HTTPException(status_code=404, detail="アラートが見つかりません")

    return dict(row)


# ===== アラートステータス更新 =====
@router.patch("/{alert_id}")
async def update_alert(
    alert_id: int,
    req:      AlertUpdateRequest,
    user:     dict = Depends(require_role("manager", "executive")),
):
    """アラートのステータスを更新する（manager・executive のみ）"""
    valid_statuses = {"investigating", "resolved", "false_positive"}
    if req.status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"status は {valid_statuses} のいずれかを指定してください",
        )

    async with get_conn() as conn:
        # 変更前の値を取得
        before = await conn.fetchrow(
            "SELECT * FROM fraud_alerts WHERE id = $1", alert_id
        )
        if not before:
            raise HTTPException(status_code=404, detail="アラートが見つかりません")

        # ステータス更新
        await conn.execute("""
            UPDATE fraud_alerts
            SET
                status      = $1,
                resolved_at = CASE
                    WHEN $1::varchar IN ('resolved', 'false_positive') THEN NOW()
                    ELSE resolved_at
                END
            WHERE id = $2
        """, req.status, alert_id)

    # 監査証跡を記録
    await record_audit(
        operator_id   = user.get("id"),
        operator_type = "human",
        target_type   = "fraud_alert",
        target_id     = alert_id,
        action        = f"alert_status_update:{req.status}",
        before_value  = {"status": before["status"]},
        after_value   = {
            "status":  req.status,
            "comment": req.comment,
        },
    )

    return {
        "message":  "更新しました",
        "alert_id": alert_id,
        "status":   req.status,
    }
