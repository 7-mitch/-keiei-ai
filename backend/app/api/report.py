from fastapi import APIRouter, Depends
from app.db.connection import get_conn
from app.core.security import get_current_user, require_role

router = APIRouter()

# ===== KPIサマリー =====
@router.get("/kpi")
async def get_kpi(
    user: dict = Depends(require_role("executive", "manager")),
):
    """経営KPIサマリーを取得する（executive・manager のみ）"""
    async with get_conn() as conn:

        # 総資産（アクティブ口座の合計残高）
        total_balance = await conn.fetchval("""
            SELECT COALESCE(SUM(balance), 0)
            FROM accounts
            WHERE status = 'active'
        """)

        # 今月の取引統計
        tx_stats = await conn.fetchrow("""
            SELECT
                COUNT(*)                                AS tx_count,
                COALESCE(SUM(amount), 0)                AS tx_amount,
                COUNT(*) FILTER (WHERE is_flagged)      AS flagged_count,
                COUNT(*) FILTER (WHERE transaction_type = 'credit') AS credit_count,
                COUNT(*) FILTER (WHERE transaction_type = 'debit')  AS debit_count
            FROM transactions
            WHERE created_at >= DATE_TRUNC('month', NOW())
        """)

        # 未解決アラート数（重要度別）
        alert_stats = await conn.fetchrow("""
            SELECT
                COUNT(*)                                        AS total,
                COUNT(*) FILTER (WHERE severity = 'critical')  AS critical,
                COUNT(*) FILTER (WHERE severity = 'high')       AS high,
                COUNT(*) FILTER (WHERE severity = 'medium')     AS medium,
                COUNT(*) FILTER (WHERE severity = 'low')        AS low
            FROM fraud_alerts
            WHERE status = 'open'
        """)

        # アクティブユーザー数
        user_count = await conn.fetchval(
            "SELECT COUNT(*) FROM users WHERE is_active = true"
        )

        # 先月比（取引金額）
        last_month_amount = await conn.fetchval("""
            SELECT COALESCE(SUM(amount), 0)
            FROM transactions
            WHERE created_at >= DATE_TRUNC('month', NOW() - INTERVAL '1 month')
              AND created_at <  DATE_TRUNC('month', NOW())
        """)

    # 先月比を計算
    current  = float(tx_stats["tx_amount"])
    previous = float(last_month_amount)
    growth   = ((current - previous) / previous * 100) if previous > 0 else 0

    return {
        "total_balance":    float(total_balance),
        "tx_count":         tx_stats["tx_count"],
        "tx_amount":        float(tx_stats["tx_amount"]),
        "flagged_count":    tx_stats["flagged_count"],
        "credit_count":     tx_stats["credit_count"],
        "debit_count":      tx_stats["debit_count"],
        "open_alerts": {
            "total":    alert_stats["total"],
            "critical": alert_stats["critical"],
            "high":     alert_stats["high"],
            "medium":   alert_stats["medium"],
            "low":      alert_stats["low"],
        },
        "user_count":       user_count,
        "growth_rate":      round(growth, 2),
    }


# ===== 監査ログ取得 =====
@router.get("/audit")
async def get_audit_logs(
    limit: int  = 100,
    user:  dict = Depends(require_role("executive", "manager")),
):
    """監査ログを取得する（executive・manager のみ）"""
    async with get_conn() as conn:
        rows = await conn.fetch("""
            SELECT
                al.id,
                al.operator_type,
                al.target_type,
                al.action,
                al.before_value,
                al.after_value,
                al.reason,
                al.session_id,
                al.created_at,
                u.name AS operator_name
            FROM audit_logs al
            LEFT JOIN users u ON al.operator_id = u.id
            ORDER BY al.created_at DESC
            LIMIT $1
        """, limit)

        return [dict(r) for r in rows]


# ===== 取引履歴レポート =====
@router.get("/transactions")
async def get_transaction_report(
    limit: int  = 200,
    user:  dict = Depends(get_current_user),
):
    """取引履歴レポートを取得する"""
    async with get_conn() as conn:
        rows = await conn.fetch("""
            SELECT
                t.id,
                t.amount,
                t.transaction_type,
                t.description,
                t.is_flagged,
                t.risk_score,
                t.created_at,
                u.name    AS user_name,
                a.account_type
            FROM transactions t
            JOIN accounts a ON t.account_id = a.id
            JOIN users    u ON a.user_id    = u.id
            ORDER BY t.created_at DESC
            LIMIT $1
        """, limit)

        return [dict(r) for r in rows]