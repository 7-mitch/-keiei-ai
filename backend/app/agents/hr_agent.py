"""
#93 多層不正検知エージェント
Layer 1: ルールベース判定
Layer 2: パターン認識（FAISS）
Layer 3: LLM判定（Claude）
Layer 4: ML判定（scikit-learn）
"""
import os
import json
from datetime import datetime
from typing import TypedDict
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END, START
from app.core.llm_factory import get_llm
from app.agents.base_prompt import get_agent_prompt
from app.db.connection import get_conn
from app.db.audit import record_audit

llm = get_llm()

# ===== 適性診断スコア定義 =====
APTITUDE_TRAITS = [
    "独創性", "俊敏性", "現実思考", "自己信頼", "継続力",
    "協調性", "分析力", "リーダーシップ", "共感力", "計画性",
]


# ===== 適性診断結果をDBに保存 =====
async def save_aptitude_result(user_id: int, scores: dict) -> bool:
    try:
        from app.db.connection import get_conn
        async with get_conn() as conn:
            await conn.execute("""
                INSERT INTO aptitude_results (user_id, scores, created_at)
                VALUES ($1, $2, NOW())
                ON CONFLICT (user_id)
                DO UPDATE SET scores = $2, updated_at = NOW()
            """, user_id, json.dumps(scores, ensure_ascii=False))
        return True
    except Exception as e:
        print(f"[HR] 適性診断保存エラー: {e}")
        return False


# ===== 適性診断結果をDBから取得 =====
async def get_aptitude_result(user_id: int) -> dict | None:
    try:
        from app.db.connection import get_conn
        async with get_conn() as conn:
            row = await conn.fetchrow("""
                SELECT scores FROM aptitude_results
                WHERE user_id = $1
                ORDER BY created_at DESC
                LIMIT 1
            """, user_id)
        if row:
            return json.loads(row["scores"])
        return None
    except Exception as e:
        print(f"[HR] 適性診断取得エラー: {e}")
        return None


# ===== 強みプロファイルのテキスト生成 =====
def format_aptitude_profile(scores: dict) -> str:
    if not scores:
        return "適性診断データなし"

    sorted_traits = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top3    = sorted_traits[:3]
    bottom2 = sorted_traits[-2:]

    lines = ["【強み TOP3】"]
    for trait, score in top3:
        bar = "■" * int(score) + "□" * (5 - int(score))
        lines.append(f"  {trait}: {bar} ({score}/5)")

    lines.append("【成長余地】")
    for trait, score in bottom2:
        bar = "■" * int(score) + "□" * (5 - int(score))
        lines.append(f"  {trait}: {bar} ({score}/5)")

    return "\n".join(lines)


# ===== 人事評価コメント生成 =====
async def generate_evaluation_comment(question: str, aptitude: dict | None) -> str:
    aptitude_text = format_aptitude_profile(aptitude) if aptitude else ""

    system_prompt = get_agent_prompt("hr")
    response = await llm.ainvoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=question),
    ])

    if isinstance(response.content, list):
        return response.content[0].get("text", "") if response.content else ""
    return str(response.content)


# ===== 強みに合わせたアドバイス生成 =====
async def generate_strength_advice(aptitude: dict) -> str:
    profile = format_aptitude_profile(aptitude)

    response = await llm.ainvoke([
        SystemMessage(content="""あなたは人材育成の専門家AIです。
適性診断結果を分析し、その人が最大限活躍できる
具体的な業務アドバイスを3つ提案してください。
各アドバイスは50文字以内で簡潔に。"""),
        HumanMessage(content=f"適性診断結果:\n{profile}"),
    ])

    if isinstance(response.content, list):
        return response.content[0].get("text", "") if response.content else ""
    return str(response.content)


# ===== チームマッチング提案 =====
async def suggest_team_matching(
    members:      list[dict],
    project_type: str,
) -> str:
    members_text = ""
    for m in members:
        profile = format_aptitude_profile(m.get("scores", {}))
        members_text += f"\n■ {m['name']}\n{profile}\n"

    response = await llm.ainvoke([
        SystemMessage(content="""あなたは組織設計の専門家AIです。
メンバーの適性診断結果を分析し、
プロジェクトに最適なチーム編成と役割分担を提案してください。
特に強みの補完関係に注目してください。"""),
        HumanMessage(content=f"""
プロジェクト種別: {project_type}

メンバー適性一覧:
{members_text}
"""),
    ])

    if isinstance(response.content, list):
        return response.content[0].get("text", "") if response.content else ""
    return str(response.content)


# ===== 個人別ラーニングパス生成 =====
async def generate_learning_path(
    aptitude: dict,
    goal:     str,
) -> str:
    profile = format_aptitude_profile(aptitude)

    response = await llm.ainvoke([
        SystemMessage(content="""あなたはキャリア開発の専門家AIです。
適性診断結果と目標を踏まえ、
その人の強みを最大限活かしながら目標達成できる
3ヶ月の学習パスを提案してください。

出力形式:
【1ヶ月目】...
【2ヶ月目】...
【3ヶ月目】...
【強みの活かし方】...
"""),
        HumanMessage(content=f"""
適性診断結果:
{profile}

目標: {goal}
"""),
    ])

    if isinstance(response.content, list):
        return response.content[0].get("text", "") if response.content else ""
    return str(response.content)


# ===== ルーティング判定 =====
def detect_hr_intent(question: str) -> str:
    q = question.lower()

    if any(kw in q for kw in ["チーム", "編成", "マッチング", "誰が向いている"]):
        return "team_matching"

    if any(kw in q for kw in ["学習", "勉強", "スキル", "成長", "学びたい", "キャリア"]):
        return "learning_path"

    if any(kw in q for kw in ["アドバイス", "強み", "活かし", "適性", "向いている"]):
        return "advice"

    return "evaluation"


# ===== Supervisorから呼び出す関数 =====
async def run_hr_agent(question: str, session_id: str) -> str:
    """Supervisorから呼び出されるエントリポイント"""
    print(f"[HR] 起動: {question[:50]}")

    intent   = detect_hr_intent(question)
    print(f"[HR] 意図判定: {intent}")

    aptitude = await get_aptitude_result(user_id=1)

    if any(kw in question for kw in ["独創性", "俊敏性", "継続力", "現実思考", "自己信頼"]):
        intent = "advice"
        if not aptitude:
            aptitude = {
                "独創性": 5, "俊敏性": 5, "現実思考": 5,
                "自己信頼": 5, "継続力": 5,
            }

    try:
        if intent == "advice" and aptitude:
            return await generate_strength_advice(aptitude)

        elif intent == "learning_path" and aptitude:
            return await generate_learning_path(aptitude, goal=question)

        elif intent == "team_matching":
            return "[チームマッチング] APIから /api/hr/team-matching を呼び出してください。"

        else:
            return await generate_evaluation_comment(question, aptitude)

    except Exception as e:
        print(f"[HR] エラー: {e}")
        return f"人事エージェントでエラーが発生しました: {str(e)}"

