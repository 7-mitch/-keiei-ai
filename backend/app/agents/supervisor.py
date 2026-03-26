from typing import TypedDict, Literal
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.memory import MemorySaver
from pydantic import BaseModel
from app.core.config import settings

# ===== State定義 =====
class SupervisorState(TypedDict):
    question:   str
    route:      str
    result:     str
    session_id: str
    user_role:  str

# ===== LLM =====
llm = ChatAnthropic(
    model       = "claude-3-5-sonnet-20240620", # モデル名を最新の有効なものに修正
    temperature = 0,
    api_key     = settings.anthropic_api_key,
)

# ===== ルーティング判断 =====
class RouteDecision(BaseModel):
    route:  Literal["sql", "rag", "fraud", "web", "general"]
    reason: str

# APIクレジット復旧後に使用する場合はこちらを有効化
# router_llm = llm.with_structured_output(RouteDecision)

def route_question(state: SupervisorState) -> dict:
    """質問内容からキーワードベースでルーティング"""
    # stateからquestionを取得し、小文字化
    text = state.get("question", "").lower()
    
    if any(kw in text for kw in ["取引", "売上", "件数", "残高", "ユーザー", "kpi", "金額"]):
        route = "sql"
    elif any(kw in text for kw in ["不正", "アラート", "リスク", "フラグ", "fraud"]):
        route = "fraud"
    elif any(kw in text for kw in ["規程", "審査", "ルール", "規則", "基準"]):
        route = "rag"
    elif any(kw in text for kw in ["ニュース", "市場", "競合", "最新"]):
        route = "web"
    else:
        route = "general"

    print(f"🧭 ルーティング判定: {route}")
    return {"route": route}

async def execute_agent(state: SupervisorState) -> dict:
    """選択されたエージェントを実行する"""
    route      = state["route"]
    question   = state["question"]
    session_id = state["session_id"]

    try:
        if route == "sql":
            # インポートエラーを防ぐため正しいモジュール名を確認してください
            from app.agents.sql_agent import run_sql_agent
            result = await run_sql_agent(question, session_id)

        elif route == "fraud":
            from app.agents.fraud_agent import run_fraud_agent
            result = await run_fraud_agent(question, session_id)

        elif route == "rag":
            result = f"[RAGエージェント] 「{question}」を検索中...（実装予定）"

        elif route == "web":
            result = f"[Web収集エージェント] 「{question}」を調査中...（実装予定）"

        else:
            response = await llm.ainvoke([
                SystemMessage(content="あなたは経営支援AIアシスタント「Project AIGIS」です。"),
                HumanMessage(content=question),
            ])
            result = response.content
            
    except Exception as e:
        result = f"エラーが発生しました: {str(e)}"
        print(f"[ERROR] エージェント実行エラー: {e}".encode('utf-8').decode('utf-8'))

    return {"result": result}

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