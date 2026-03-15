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
    model      = "claude-sonnet-4-20250514",
    temperature = 0,
    api_key    = settings.anthropic_api_key,
)

# ===== ルーティング判断 =====
class RouteDecision(BaseModel):
    route:  Literal["sql", "rag", "fraud", "web", "general"]
    reason: str

router_llm = llm.with_structured_output(RouteDecision)

def route_question(state: SupervisorState) -> dict:
    """質問内容から最適なエージェントを選択する"""
    decision = router_llm.invoke([
        SystemMessage(content="""
質問を分析して最適なエージェントを選んでください:

- sql:     DB内のデータ集計・検索
           例: 売上・取引件数・ユーザー数・残高

- rag:     審査規程・社内文書・ルールの検索
           例: 審査基準・コンプライアンス・規則

- fraud:   不正検知・リスク分析・アラート確認
           例: 不正フラグ・異常取引・リスクスコア

- web:     最新の市場情報・競合・ニュース収集
           例: 金利動向・競合他社・市場データ

- general: 上記に当てはまらない一般的な質問
        """),
        HumanMessage(content=f"質問: {state['question']}"),
    ])
    print(f"🧭 ルーティング: {decision.route} / 理由: {decision.reason}")
    return {"route": decision.route}


async def execute_agent(state: SupervisorState) -> dict:
    """選択されたエージェントを実行する"""
    route      = state["route"]
    question   = state["question"]
    session_id = state["session_id"]

    # #93以降で各エージェントを実装
    # 現時点はダミーレスポンス
    if route == "sql":
        result = f"[SQLエージェント] 「{question}」を調査します。（#93で実装）"
    elif route == "rag":
        result = f"[RAGエージェント] 「{question}」を審査規程から検索します。（#96で実装）"
    elif route == "fraud":
        result = f"[不正検知エージェント] 「{question}」のリスクを分析します。（#93で実装）"
    elif route == "web":
        result = f"[Web収集エージェント] 「{question}」の最新情報を収集します。（#95で実装）"
    else:
        # 一般的な質問はLLMが直接回答
        response = await llm.ainvoke([
            SystemMessage(content="あなたは経営者を支援するAIアシスタントです。日本語で丁寧に回答してください。"),
            HumanMessage(content=question),
        ])
        result = response.content

    return {"result": result}


# ===== グラフ構築 =====
def build_supervisor():
    g = StateGraph(SupervisorState)
    g.add_node("route",   route_question)
    g.add_node("execute", execute_agent)
    g.add_edge(START,     "route")
    g.add_edge("route",   "execute")
    g.add_edge("execute", END)
    return g.compile(checkpointer=MemorySaver())

supervisor = build_supervisor()