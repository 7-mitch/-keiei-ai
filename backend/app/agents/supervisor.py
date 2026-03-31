"""
supervisor.py — KEIEI-AI マルチエージェント統括
変更履歴:
  - project エージェント追加
  - check_prompt_security() セキュリティ検査追加（AIGIS連携）
  - 環境変数によるLLM切り替え（ローカル=Ollama / クラウド=Claude API）
"""
import os
from typing import TypedDict, Literal
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.memory import MemorySaver
from pydantic import BaseModel

# ===== LLM 環境切り替え =====
# ローカル環境 → Ollama（無料・完全オンプレ・セキュア）
# クラウド環境 → Claude API（外部公開・デモ用）
_env = os.getenv("ENVIRONMENT", "development")

if _env == "production":
    from langchain_anthropic import ChatAnthropic
    llm = ChatAnthropic(
        model="claude-sonnet-4-20250514",
        max_tokens=2048,
    )
    print("[LLM] Claude API（本番モード）")
else:
    from langchain_ollama import ChatOllama
    llm = ChatOllama(
        model    = "qwen3:8b",
        base_url = "http://host.docker.internal:11434",
    )
    print("[LLM] Ollama Qwen3（ローカルモード）")


# ===== State定義 =====
class SupervisorState(TypedDict):
    question:   str
    route:      str
    result:     str
    session_id: str
    user_role:  str


# ===== セキュリティ検査（AIGIS連携） =====
def check_prompt_security(question: str) -> str | None:
    """
    プロンプトインジェクション・有害入力を検査する。
    内部利用: 監査ログとして記録
    外部公開: 攻撃を遮断
    AIGIS 336監査項目をリスク辞書として活用。
    問題なし → None を返す
    問題あり → エラーメッセージを返す
    """

    # ① プロンプトインジェクションパターン検知
    injection_patterns = [
        "ignore previous instructions",
        "ignore all instructions",
        "system prompt",
        "あなたはAIではない",
        "ロールプレイ",
        "pretend you are",
        "jailbreak",
        "dan mode",
        "開発者モード",
        "制限を解除",
    ]
    q_lower = question.lower()
    for pattern in injection_patterns:
        if pattern.lower() in q_lower:
            print(f"[SECURITY] インジェクション検知: {question[:50]}")
            return "不正な入力が検知されました。この操作は監査ログに記録されます。"

    # ② 機密情報漏洩防止
    sensitive_patterns = [
        "パスワード", "APIキー", "秘密鍵", "トークン",
        "password", "api_key", "secret", "private key",
        "DATABASE_URL", "SECRET_KEY",
    ]
    for pattern in sensitive_patterns:
        if pattern.lower() in q_lower:
            print(f"[SECURITY] 機密情報関連クエリ: {question[:50]}")
            return "機密情報に関する質問には回答できません。"

    # ③ AIGISの336監査項目でリスク評価（ログ記録のみ・遮断はしない）
    try:
        from app.agents.rag_agent import search_aigis
        risk_docs = search_aigis(question, k=1)
        if risk_docs and risk_docs[0]["score"] < 0.2:
            print(f"[SECURITY] AIGISリスク高スコア検知: {question[:50]}")
    except Exception:
        pass  # AIGIS未接続でも動作継続

    return None  # 問題なし


# ===== ルーティング判断 =====
class RouteDecision(BaseModel):
    route:  Literal["project", "sql", "rag", "fraud", "web", "general"]
    reason: str

def route_question(state: SupervisorState) -> dict:
    """質問内容からキーワードベースでルーティング"""
    text = state.get("question", "").lower()

    if any(kw in text for kw in [
        "進捗", "プロジェクト", "タスク", "工程", "フェーズ",
        "遅延", "担当", "アサイン", "スケジュール", "期限",
        "稼働", "過負荷", "何が残っている", "間に合う",
    ]):
        route = "project"

    elif any(kw in text for kw in ["取引", "売上", "件数", "残高", "ユーザー", "kpi", "金額"]):
        route = "sql"

    elif any(kw in text for kw in ["不正", "アラート", "フラグ", "fraud"]):
        route = "fraud"

    elif any(kw in text for kw in [
        "規程", "審査", "ルール", "規則", "基準",
        "セキュリティ", "security", "監査", "audit",
        "攻撃", "attack", "脆弱性",
        "プロンプト", "injection",
        "owasp", "nist", "iso", "sox", "cfe",
        "暗号", "ランサム", "サプライチェーン",
        "ゼロトラスト", "インシデント", "ガバナンス",
        "量子", "pqc", "プライバシー", "対策",
    ]):
        route = "rag"

    elif any(kw in text for kw in [
        "人事", "評価", "コメント", "人材", "査定",
        "目標", "MBO", "1on1", "フィードバック", "育成",
    ]):
        route = "hr"

    elif any(kw in text for kw in ["ニュース", "市場", "競合", "最新"]):
        route = "web"

    else:
        route = "general"

    print(f"[ROUTE] routing: {route}")
    return {"route": route}


async def execute_agent(state: SupervisorState) -> dict:
    """選択されたエージェントを実行する"""
    route      = state["route"]
    question   = state["question"]
    session_id = state["session_id"]

    # ★ セキュリティ検査（全ルート共通・入口で必ず実行）
    security_error = check_prompt_security(question)
    if security_error:
        return {"result": security_error}

    try:
        if route == "project":
            from app.agents.project_agent import run_project_agent
            result = await run_project_agent(question, session_id)

        elif route == "sql":
            from app.agents.sql_agent import run_sql_agent
            result = await run_sql_agent(question, session_id)

        elif route == "fraud":
            from app.agents.fraud_agent import run_fraud_agent
            result = await run_fraud_agent(question, session_id)

        elif route == "rag":
            from app.agents.rag_agent import run_rag_agent
            result = await run_rag_agent(question, session_id)

        elif route == "hr":
            from app.agents.hr_agent import run_hr_agent
            result = await run_hr_agent(question, session_id)

        elif route == "web":
            result = f"[Web] {question} を調査中...（実装予定）"

        else:
            response = await llm.ainvoke([
                SystemMessage(content="あなたは経営支援AIアシスタントです。日本語で答えてください。"),
                HumanMessage(content=question),
            ])
            if isinstance(response.content, list):
                result = response.content[0].get("text", "") if response.content else ""
            else:
                result = str(response.content)

        return {"result": result}

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[ERROR] agent error: {e}")
        return {"result": f"error: {str(e)}"}


# ===== グラフ構築 =====
def build_supervisor():
    workflow = StateGraph(SupervisorState)
    workflow.add_node("route",   route_question)
    workflow.add_node("execute", execute_agent)
    workflow.add_edge(START, "route")
    workflow.add_edge("route", "execute")
    workflow.add_edge("execute", END)
    return workflow.compile(checkpointer=MemorySaver())

supervisor = build_supervisor()