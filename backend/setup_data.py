import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

# 設定（ここはそのままで大丈夫です）
DATABASE_URL = "postgresql+asyncpg://keiei_user:keiei_pass@localhost:5432/keiei_ai"

async def setup():
    engine = create_async_engine(DATABASE_URL)
    print("🚀 データベースに単位も含めて数字を書き込んでいます...")

    try:
        async with engine.begin() as conn:
            # いったん古いデータをきれいに消します
            await conn.execute(text("DELETE FROM kpi_metrics;"))

            # 1. 売上のデータをいれる（単位：円）
            await conn.execute(text("""
                INSERT INTO kpi_metrics (metric_name, metric_value, unit, period) 
                VALUES ('total_sales', 1500000, '円', '2026-03');
            """))

            # 2. ユーザー数のデータをいれる（単位：人）
            await conn.execute(text("""
                INSERT INTO kpi_metrics (metric_name, metric_value, unit, period) 
                VALUES ('user_count', 120, '人', '2026-03');
            """))

            # 3. 不正アラートの件数をいれる（単位：件）
            await conn.execute(text("""
                INSERT INTO kpi_metrics (metric_name, metric_value, unit, period) 
                VALUES ('fraud_alerts', 5, '件', '2026-03');
            """))

        print("✅ ついに成功しました！バケツに水と、ラベル（単位）が入りました。")
        print("ブラウザでダッシュボードを更新（F5）してみてください！")

    except Exception as e:
        print(f"❌ エラーが起きました: {e}")
    finally:
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(setup())