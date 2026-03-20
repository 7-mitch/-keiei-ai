"""
#93 SQLエージェント（asyncpg直接実行版）
Claude APIが使えない間もDBに直接問い合わせる
"""
from app.db.connection import get_conn

async def run_sql_agent(question: str, session_id: str) -> str:
    """自然言語の質問をSQLで答える（キーワードベース）"""
    q = question.lower()

    try:
        async with get_conn() as conn:

            # 取引件数・金額
            if any(kw in q for kw in ["取引件数", "取引数", "件数"]):
                row = await conn.fetchrow("""
                    SELECT COUNT(*) AS cnt, COALESCE(SUM(amount),0) AS total
                    FROM transactions
                    WHERE created_at >= DATE_TRUNC('month', NOW())
                """)
                return f"今月の取引件数は {row['cnt']}件、合計金額は ¥{int(row['total']):,} です。"

            # 残高・総資産
            elif any(kw in q for kw in ["残高", "総資産", "資産"]):
                row = await conn.fetchrow("""
                    SELECT COALESCE(SUM(balance),0) AS total
                    FROM accounts WHERE status = 'active'
                """)
                return f"総資産（アクティブ口座合計）は ¥{int(row['total']):,} です。"

            # 不正・アラート
            elif any(kw in q for kw in ["不正", "アラート", "フラグ"]):
                row = await conn.fetchrow("""
                    SELECT
                        COUNT(*) AS total,
                        COUNT(*) FILTER (WHERE status='open') AS open,
                        COUNT(*) FILTER (WHERE severity='critical') AS critical
                    FROM fraud_alerts
                """)
                return f"不正アラートは合計 {row['total']}件（未対応: {row['open']}件、重大: {row['critical']}件）です。"

            # ユーザー数
            elif any(kw in q for kw in ["ユーザー", "利用者", "ユーザ数"]):
                cnt = await conn.fetchval(
                    "SELECT COUNT(*) FROM users WHERE is_active = true"
                )
                return f"アクティブユーザーは {cnt}人 です。"

            # 売上
            elif any(kw in q for kw in ["売上", "収益", "入金"]):
                row = await conn.fetchrow("""
                    SELECT COALESCE(SUM(amount),0) AS total, COUNT(*) AS cnt
                    FROM transactions
                    WHERE transaction_type = 'credit'
                    AND created_at >= DATE_TRUNC('month', NOW())
                """)
                return f"今月の入金（credit）は {row['cnt']}件、合計 ¥{int(row['total']):,} です。"

            else:
                return "申し訳ありません。その質問には対応していません。「取引件数」「残高」「不正アラート」「ユーザー数」などについて質問してみてください。"

    except Exception as e:
        return f"DB問い合わせでエラーが発生しました: {str(e)}"