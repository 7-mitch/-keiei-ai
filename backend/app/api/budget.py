"""
budget.py — 予実管理API
予算登録・実績更新・差異分析
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from app.core.security import get_current_user
from app.db.connection import get_conn

router = APIRouter()


class BudgetRequest(BaseModel):
    account_id: int
    year:       int
    month:      int
    category:   str
    budget_amt: float
    actual_amt: float = 0
    note:       Optional[str] = None


@router.get("/{account_id}/{year}/{month}")
async def get_budget(
    account_id: int,
    year:       int,
    month:      int,
    user: dict = Depends(get_current_user),
):
    """指定月の予実データを取得"""
    async with get_conn() as conn:
        rows = await conn.fetch("""
            SELECT id, category, budget_amt, actual_amt, note
            FROM budgets
            WHERE account_id = $1 AND year = $2 AND month = $3
            ORDER BY category
        """, account_id, year, month)

    items = [dict(row) for row in rows]

    # 合計計算
    total_budget = sum(r["budget_amt"] for r in items)
    total_actual = sum(r["actual_amt"] for r in items)
    variance     = total_actual - total_budget
    rate         = round(total_actual / total_budget * 100, 1) if total_budget > 0 else 0

    return {
        "items":        items,
        "total_budget": total_budget,
        "total_actual": total_actual,
        "variance":     variance,
        "rate":         rate,
    }


@router.post("/")
async def upsert_budget(
    req:  BudgetRequest,
    user: dict = Depends(get_current_user),
):
    """予算・実績を登録/更新"""
    async with get_conn() as conn:
        row = await conn.fetchrow("""
            INSERT INTO budgets
                (account_id, year, month, category, budget_amt, actual_amt, note)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            ON CONFLICT (account_id, year, month, category)
            DO UPDATE SET
                budget_amt = $5,
                actual_amt = $6,
                note       = $7,
                updated_at = NOW()
            RETURNING id, category, budget_amt, actual_amt
        """,
            req.account_id, req.year, req.month,
            req.category, req.budget_amt, req.actual_amt, req.note,
        )
    return dict(row)


@router.get("/summary/{account_id}/{year}")
async def get_annual_summary(
    account_id: int,
    year:       int,
    user: dict = Depends(get_current_user),
):
    """年間予実サマリーを取得"""
    async with get_conn() as conn:
        rows = await conn.fetch("""
            SELECT
                month,
                SUM(budget_amt) AS budget,
                SUM(actual_amt) AS actual
            FROM budgets
            WHERE account_id = $1 AND year = $2
            GROUP BY month
            ORDER BY month
        """, account_id, year)

    return [dict(row) for row in rows]