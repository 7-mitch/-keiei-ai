"""
supervisor.py — KEIEI-AI マルチエージェント統括
変更履歴:
  - project エージェント追加
  - check_prompt_security() セキュリティ検査追加（AIGIS連携）
  - 環境変数によるLLM切り替え（ローカル=Ollama / クラウド=Claude API）
  - cash_flow_agent 追加
  - hr バグ修正
  - Layer B セキュリティ検査（LLM）統合
  - hr_agent 適性診断・汎用キーワード対応
  - ハイブリッドルーティング（KI+HuggingFace VI）実装
  - llm_factory に統一（vLLM・QLoRA対応）
"""
from typing import TypedDict, Literal
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.memory import MemorySaver
from pydantic import BaseModel
from app.core.llm_factory import get_llm

llm = get_llm()  # ← これだけでOK・古いif/elseブロックは削除

# ===== State定義 =====
class SupervisorState(TypedDict):
    question:   str
    route:      str
    result:     str
    session_id: str
    user_role:  str


# ===== セキュリティ検査 Gate1（キーワード） =====
def check_prompt_security(question: str) -> str | None:
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

    sensitive_patterns = [
        "パスワード", "APIキー", "秘密鍵", "トークン",
        "password", "api_key", "secret", "private key",
        "DATABASE_URL", "SECRET_KEY",
    ]
    for pattern in sensitive_patterns:
        if pattern.lower() in q_lower:
            print(f"[SECURITY] 機密情報関連クエリ: {question[:50]}")
            return "機密情報に関する質問には回答できません。"

    # AIGIS リスク評価
    try:
        from app.agents.rag_agent import search_aigis
        risk_docs = search_aigis(question, k=1)
        if risk_docs and risk_docs[0]["score"] < 0.3:
            category = risk_docs[0].get("category", "")
            print(f"[SECURITY] AIGISリスク検知: {question[:50]} / {category}")
            return f"この質問はセキュリティリスク項目（{category}）に該当します。監査ログに記録されました。"
    except Exception:
        pass

    return None


# ===== ルーティング判断 =====
class RouteDecision(BaseModel):
    route:  Literal["project", "sql", "rag", "fraud", "web", "cash_flow", "hr", "general"]
    reason: str

# ===== Step1: 明確キーワード辞書（高信頼・即決定）=====
# 業種問わず普遍的かつ明確な複合語・専門用語のみ収録
# 単語が短いほど誤マッチしやすいので複合語優先
CLEAR_KEYWORDS = {
    "cash_flow": [
        "資金繰り", "インボイス", "試算表", "キャッシュフロー",
        "入金管理", "出金管理", "売掛金", "買掛金",
        "資金ショート", "月次決算", "電帳法",
    ],
    "project": [
        "進捗管理", "プロジェクト管理", "タスク管理",
        "マイルストーン", "wbs", "ガントチャート",
        "スケジュール管理", "遅延対応",
    ],
    "sql": [
        "kpi", "売上集計", "データ分析", "データ集計",
        "売上レポート", "月次レポート", "統計分析",
    ],
    "fraud": [
        "不正検知", "fraud", "異常取引", "不正アラート",
        "不正フラグ", "リスクスコア",
    ],
    "rag": [
        "セキュリティ規程", "監査基準", "コンプライアンス規程",
        "owasp", "nist", "sox", "cfe",
        "ゼロトラスト", "サプライチェーン攻撃", "pqc",
    ],
    "hr": [
        "適性診断", "人事評価", "チームマッチング",
        "学習パス", "キャリアパス", "能力開発計画",
        "1on1", "mbo", "人材育成",
    ],
    "web": [
        "業界動向", "競合分析", "市場調査",
        "競合他社", "業界ニュース", "市場トレンド",
    ],
}

# ===== Step2: 曖昧キーワード辞書（中信頼・HF前の補助）=====
# 単語が短く誤マッチしやすいが、複数一致なら信頼できるもの
SOFT_KEYWORDS = {
    "cash_flow": [
        "資金", "経費", "収支", "利益", "予測",
        "入金", "出金", "節税", "黒字", "赤字",
    ],
    "project": [
        "進捗", "タスク", "工程", "フェーズ",
        "遅延", "期限", "納期", "間に合う",
    ],
    "sql": [
        "売上", "件数", "残高", "ユーザー数",
        "金額", "推移", "比較",
    ],
    "fraud": [
        "不正", "アラート", "フラグ", "疑わしい",
    ],
    "rag": [
        "セキュリティ", "監査", "規程", "脆弱性",
        "暗号", "ランサム", "インシデント", "ガバナンス",
        "プライバシー", "法令", "規制",
    ],
    "hr": [
        "人事", "評価", "人材", "査定", "採用",
        "育成", "研修", "強み", "弱み", "特性",
        "キャリア", "成長", "スキル", "組織",
        "チーム", "役割", "リーダー", "コミュニケーション",
        "行動力", "創造性", "論理性", "柔軟性", "主体性",
        "協調性", "分析力", "共感力", "計画性",
        "独創性", "俊敏性", "継続力", "自己信頼", "現実思考",
    ],
    "web": [
        "ニュース", "市場", "競合", "最新",
        "トレンド", "他社",
    ],
}


def route_question(state: SupervisorState) -> dict:
    """
    ハイブリッドルーティング（3段階）

    設計方針：
    Step1: 明確キーワード（複合語・専門用語）→ 即決定（0ms・最高信頼）
    Step2: 曖昧キーワード（単語）→ 複数一致で決定（高信頼）
    Step3: どちらも一致しない → HuggingFaceで意図分類（APIコストゼロ）

    業種非依存：IT・介護・製造・建設・医療・法律どの業種でも機能する
    """
    text     = state.get("question", "").lower()
    question = state.get("question", "")

    # ===== Step1: 明確キーワードで即決定 =====
    for route, keywords in CLEAR_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            print(f"[ROUTE-KI1] 即決定: {route}")
            return {"route": route}

    # ===== Step2: 曖昧キーワードのスコアリング =====
    scores: dict[str, int] = {r: 0 for r in SOFT_KEYWORDS}
    for route, keywords in SOFT_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                scores[route] += 1

    best_route = max(scores, key=lambda r: scores[r])
    best_score = scores[best_route]

    # 2件以上マッチしたルートは信頼度が高い
    if best_score >= 2:
        print(f"[ROUTE-KI2] スコア決定: {best_route} (score={best_score})")
        return {"route": best_route}

    # 1件マッチでも他ルートと差があれば採用
    second_scores = sorted(scores.values(), reverse=True)
    if best_score == 1 and (len(second_scores) < 2 or second_scores[1] == 0):
        print(f"[ROUTE-KI2] 単独マッチ決定: {best_route}")
        return {"route": best_route}

    # ===== Step3: HuggingFaceで意図分類 =====
    print(f"[ROUTE-HF] HuggingFaceで意図分類中: {question[:30]}")
    try:
        from app.agents.hf_router import route_with_hf
        route = route_with_hf(question)
        print(f"[ROUTE-HF] 分類結果: {route}")
        return {"route": route}
    except Exception as e:
        print(f"[ROUTE-HF] エラー: {e} → general")
        return {"route": "general"}


# ===== エージェント実行 =====
async def execute_agent(state: SupervisorState) -> dict:
    """選択されたエージェントを実行する"""
    route      = state["route"]
    question   = state["question"]
    session_id = state["session_id"]

    # ★ Gate1 + Gate2 統合セキュリティ検査
    from app.core.security import full_security_check
    security_error = await full_security_check(question)
    if security_error:
        return {"result": security_error}

    try:
        if route == "cash_flow":
            from app.agents.cash_flow_agent import run_cash_flow_agent
            result = await run_cash_flow_agent(question, session_id)

        elif route == "project":
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