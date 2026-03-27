from typing import TypedDict, Literal
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.memory import MemorySaver
from pydantic import BaseModel
from langchain_ollama import ChatOllama

# ===== LLM（Ollama + Qwen3）=====
llm = ChatOllama(
    model    = "qwen3:8b",
    base_url = "http://localhost:11434"
)

# ===== State定義 =====
class SupervisorState(TypedDict):
    question:   str
    route:      str
    result:     str
    session_id: str
    user_role:  str

# ===== ルーティング判断 =====
class RouteDecision(BaseModel):
    route:  Literal["sql", "rag", "fraud", "web", "general"]
    reason: str

def route_question(state: SupervisorState) -> dict:
    """質問内容からキーワードベースでルーティング"""
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

    print(f"[ROUTE] routing: {route}")
    return {"route": route}

async def execute_agent(state: SupervisorState) -> dict:
    """選択されたエージェントを実行する"""
    route      = state["route"]
    question   = state["question"]
    session_id = state["session_id"]

    try:
        if route == "sql":
            from app.agents.sql_agent import run_sql_agent
            result = await run_sql_agent(question, session_id)

        elif route == "fraud":
            from app.agents.fraud_agent import run_fraud_agent
            result = await run_fraud_agent(question, session_id)

        elif route == "rag":
            result = f"[RAG] {question} を検索中...（実装予定）"

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
        result = f"error: {str(e)}"
        print(f"[ERROR] agent error: {e}")
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