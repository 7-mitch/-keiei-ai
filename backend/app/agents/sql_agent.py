"""
#93 SQLエージェント
自然言語でDBに質問できるエージェント
例: 「先月の売上合計は？」「不正フラグが立った取引は何件？」
"""
from langchain_anthropic import ChatAnthropic
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langgraph.prebuilt import create_react_agent
from app.core.config import settings

# ===== LLM =====
llm = ChatAnthropic(
    model       = "claude-sonnet-4-20250514",
    temperature = 0,
    api_key     = settings.anthropic_api_key,
)

# ===== SQLエージェントを構築 =====
def build_sql_agent():
    """SQLエージェントを初期化する"""
    try:
        db      = SQLDatabase.from_uri(settings.database_url)
        toolkit = SQLDatabaseToolkit(db=db, llm=llm)
        tools   = toolkit.get_tools()

        agent = create_react_agent(
            model = llm,
            tools = tools,
            prompt = """
あなたは経営者を支援するデータアナリストAIです。
PostgreSQLデータベースに対してSQLクエリを実行して質問に答えてください。

データベースの主なテーブル:
- users:        ユーザー情報（id, name, email, role）
- accounts:     口座情報（id, user_id, balance, account_type）
- transactions: 取引履歴（id, account_id, amount, transaction_type, is_flagged, risk_score）
- fraud_alerts: 不正アラート（id, severity, status, description）
- kpi_metrics:  KPIメトリクス（metric_name, metric_value, period）
- audit_logs:   監査ログ（operator_type, action, created_at）

注意事項:
- 必ず日本語で回答する
- 金額は円単位で表示する
- SELECTクエリのみ実行する（INSERT/UPDATE/DELETEは禁止）
- 結果は経営者が理解しやすい形で説明する
            """,
        )
        return agent

    except Exception as e:
        print(f"⚠️ SQLエージェント初期化エラー: {e}")
        return None

# シングルトンとして保持
_sql_agent = None

def get_sql_agent():
    global _sql_agent
    if _sql_agent is None:
        _sql_agent = build_sql_agent()
    return _sql_agent


async def run_sql_agent(question: str, session_id: str) -> str:
    """Supervisorから呼び出されるエントリポイント"""
    agent = get_sql_agent()

    if agent is None:
        return "SQLエージェントの初期化に失敗しました。DB接続を確認してください。"

    try:
        result = await agent.ainvoke({
            "messages": [{"role": "user", "content": question}]
        })

        # 最後のメッセージを取得
        messages = result.get("messages", [])
        if messages:
            last_message = messages[-1]
            if hasattr(last_message, "content"):
                return last_message.content

        return "クエリの実行に失敗しました。"

    except Exception as e:
        return f"エラーが発生しました: {str(e)}"