"""
cash_flow_agent.py — 資金繰り監視・キャッシュフロー予測エージェント
機能:
  - 月次キャッシュフローの自動集計
  - 資金ショート予測（30日先）
  - インボイス・電帳法対応アラート
  - 経営者向け要約レポート生成
"""
from datetime import datetime
from typing import TypedDict
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END, START
from app.core.llm_factory import get_llm
from app.agents.base_prompt import get_agent_prompt
from app.db.connection import get_conn

# ===== LLM =====
llm = get_llm()


# ===== State定義 =====
class CashFlowState(TypedDict):
    question:        str
    session_id:      str
    account_id:      int
    monthly_summary: dict
    balance_now:     float
    forecast_30d:    dict
    alerts:          list
    report:          str


# ===== Step1: 月次収支集計 =====
async def step1_monthly_summary(state: CashFlowState) -> dict:
    try:
        async with get_conn() as conn:
            rows = await conn.fetch("""
                SELECT
                    DATE_TRUNC('month', created_at) AS month,
                    transaction_type,
                    SUM(amount) AS total
                FROM transactions
                WHERE account_id = $1
                  AND created_at >= NOW() - INTERVAL '3 months'
                GROUP BY month, transaction_type
                ORDER BY month DESC
            """, state["account_id"])

        summary = {}
        for row in rows:
            month_key = row["month"].strftime("%Y-%m")
            if month_key not in summary:
                summary[month_key] = {"income": 0.0, "expense": 0.0}
            if row["transaction_type"] == "credit":
                summary[month_key]["income"] += float(row["total"])
            else:
                summary[month_key]["expense"] += float(row["total"])

        for month in summary:
            summary[month]["net"] = (
                summary[month]["income"] - summary[month]["expense"]
            )

        print(f"[CashFlow] Step1 月次集計: {len(summary)}ヶ月分")
        return {"monthly_summary": summary}

    except Exception as e:
        print(f"[CashFlow] Step1 エラー: {e}")
        return {"monthly_summary": {}}


# ===== Step2: 現在残高取得 =====
async def step2_current_balance(state: CashFlowState) -> dict:
    try:
        async with get_conn() as conn:
            row = await conn.fetchrow("""
                SELECT
                    SUM(CASE WHEN transaction_type = 'credit'
                        THEN amount ELSE -amount END) AS balance
                FROM transactions
                WHERE account_id = $1
            """, state["account_id"])

        balance = float(row["balance"] or 0)
        print(f"[CashFlow] Step2 現在残高: {balance:,.0f}円")
        return {"balance_now": balance}

    except Exception as e:
        print(f"[CashFlow] Step2 エラー: {e}")
        return {"balance_now": 0.0}


# ===== Step3: 30日キャッシュフロー予測 =====
async def step3_forecast(state: CashFlowState) -> dict:
    summary = state["monthly_summary"]
    balance = state["balance_now"]

    if not summary:
        return {"forecast_30d": {"predicted_balance": balance, "risk": "データ不足"}}

    avg_income  = sum(v["income"]  for v in summary.values()) / len(summary)
    avg_expense = sum(v["expense"] for v in summary.values()) / len(summary)
    avg_net     = avg_income - avg_expense
    predicted   = balance + avg_net

    if predicted < 0:
        risk = "critical"
    elif predicted < avg_expense * 0.5:
        risk = "high"
    elif predicted < avg_expense:
        risk = "medium"
    else:
        risk = "low"

    forecast = {
        "predicted_balance":   round(predicted, 0),
        "avg_monthly_income":  round(avg_income, 0),
        "avg_monthly_expense": round(avg_expense, 0),
        "avg_monthly_net":     round(avg_net, 0),
        "risk":                risk,
    }

    print(f"[CashFlow] Step3 予測残高: {predicted:,.0f}円 リスク: {risk}")
    return {"forecast_30d": forecast}


# ===== Step4: アラート生成 =====
async def step4_alerts(state: CashFlowState) -> dict:
    alerts   = []
    forecast = state["forecast_30d"]

    risk = forecast.get("risk", "low")
    if risk == "critical":
        alerts.append({
            "type":     "cash_flow",
            "severity": "critical",
            "message":  "30日以内に資金ショートの可能性があります。即座に対応が必要です。",
        })
    elif risk == "high":
        alerts.append({
            "type":     "cash_flow",
            "severity": "high",
            "message":  "資金残高が月次経費の50%を下回る見込みです。資金調達を検討してください。",
        })

    try:
        async with get_conn() as conn:
            row = await conn.fetchrow("""
                SELECT MAX(created_at) AS last_tx
                FROM transactions
                WHERE account_id = $1
            """, state["account_id"])

        if row["last_tx"]:
            days_since = (datetime.now(row["last_tx"].tzinfo) - row["last_tx"]).days
            if days_since > 30:
                alerts.append({
                    "type":     "accounting",
                    "severity": "medium",
                    "message":  f"最終取引から{days_since}日経過しています。試算表の更新を確認してください。",
                })
    except Exception as e:
        print(f"[CashFlow] アラート取得エラー: {e}")

    alerts.append({
        "type":     "invoice",
        "severity": "info",
        "message":  "2026年インボイス制度：経過措置の控除割合が縮小されています。仕入税額控除の確認を推奨します。",
    })

    print(f"[CashFlow] Step4 アラート: {len(alerts)}件")
    return {"alerts": alerts}


# ===== Step5: LLMレポート生成 =====
async def step5_report(state: CashFlowState) -> dict:
    summary  = state["monthly_summary"]
    balance  = state["balance_now"]
    forecast = state["forecast_30d"]
    alerts   = state["alerts"]
    question = state["question"]

    alert_text = "\n".join([
        f"[{a['severity'].upper()}] {a['message']}"
        for a in alerts
    ]) or "特になし"

    monthly_text = "\n".join([
        f"{month}: 収入{v['income']:,.0f}円 / 支出{v['expense']:,.0f}円 / 純利益{v['net']:,.0f}円"
        for month, v in sorted(summary.items(), reverse=True)
    ]) or "データなし"

    system_prompt = get_agent_prompt("cash_flow")

    user_message = f"""質問：{question}

【現在残高】{balance:,.0f}円
【30日後予測残高】{forecast.get('predicted_balance', 0):,.0f}円
【リスク】{forecast.get('risk', '不明')}

【月次収支（直近3ヶ月）】
{monthly_text}

【アラート】
{alert_text}

上記をもとに経営者向けの資金繰りレポートを作成してください。"""

    try:
        response = await llm.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message),
        ])

        if isinstance(response.content, list):
            report = response.content[0].get("text", "") if response.content else ""
        else:
            report = str(response.content)

    except Exception as e:
        print(f"[CashFlow] LLMエラー: {e}")
        report = f"""【資金繰りサマリー】
現在残高：{balance:,.0f}円
30日後予測：{forecast.get('predicted_balance', 0):,.0f}円
リスク：{forecast.get('risk', '不明')}

{alert_text}"""

    print(f"[CashFlow] Step5 レポート生成完了")
    return {"report": report}


# ===== グラフ構築 =====
def build_cash_flow_agent():
    g = StateGraph(CashFlowState)
    g.add_node("step1", step1_monthly_summary)
    g.add_node("step2", step2_current_balance)
    g.add_node("step3", step3_forecast)
    g.add_node("step4", step4_alerts)
    g.add_node("step5", step5_report)
    g.add_edge(START,   "step1")
    g.add_edge("step1", "step2")
    g.add_edge("step2", "step3")
    g.add_edge("step3", "step4")
    g.add_edge("step4", "step5")
    g.add_edge("step5", END)
    return g.compile()

cash_flow_agent = build_cash_flow_agent()


# ===== 外部から呼び出す関数 =====
async def run_cash_flow_agent(question: str, session_id: str) -> str:
    """Supervisorから呼び出されるエントリポイント"""
    state = await cash_flow_agent.ainvoke({
        "question":        question,
        "session_id":      session_id,
        "account_id":      1,
        "monthly_summary": {},
        "balance_now":     0.0,
        "forecast_30d":    {},
        "alerts":          [],
        "report":          "",
    })
    return state["report"]

