"""
PlanAI 工程管理エージェント
- 「このプロジェクトの進捗は？」→ DBからタスク取得 + RAGで回答
- supervisor.py から run_project_agent() を呼ぶだけで動く
"""
from app.db.connection import get_conn
from app.agents.rag_agent import search_documents  # 既存RAGをそのまま流用


# ===== キーワード判定（supervisor用） =====
def is_project_query(question: str) -> bool:
    """工程・プロジェクト管理に関する質問かどうか判定"""
    keywords = [
        "進捗", "プロジェクト", "タスク", "工程", "フェーズ",
        "遅延", "担当", "アサイン", "スケジュール", "期限",
        "稼働", "過負荷", "完了", "未着手", "リスク",
        "誰が", "いつまで", "何が残っている", "間に合う",
    ]
    return any(kw in question for kw in keywords)


# ===== DB: タスク一覧取得 =====
async def fetch_tasks(project_id: int) -> list[dict]:
    """指定プロジェクトのタスクをDBから取得"""
    async with get_conn() as conn:
        rows = await conn.fetch(
            """
            SELECT phase, name, assign, status, progress,
                   start_date, end_date, note
            FROM tasks
            WHERE project_id = $1
            ORDER BY phase, id
            """,
            project_id,
        )
    return [dict(r) for r in rows]


# ===== DB: メンバー一覧取得 =====
async def fetch_members(project_id: int) -> list[dict]:
    """指定プロジェクトのメンバーをDBから取得"""
    async with get_conn() as conn:
        rows = await conn.fetch(
            """
            SELECT name, role, skills, workload
            FROM project_members
            WHERE project_id = $1
            ORDER BY workload DESC
            """,
            project_id,
        )
    return [dict(r) for r in rows]


# ===== DB: プロジェクト検索（名前から） =====
async def find_project_id(question: str) -> int:
    """質問文からプロジェクトIDを推定（デフォルトは最新の1件）"""
    async with get_conn() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, name FROM projects
            WHERE status = 'active'
            ORDER BY updated_at DESC
            LIMIT 1
            """
        )
    return row["id"] if row else 1


# ===== フォーマット: タスク → テキスト =====
def format_tasks(tasks: list[dict]) -> str:
    if not tasks:
        return "タスクが登録されていません。"

    STATUS_JP = {
        "done":  "✅ 完了",
        "doing": "🔵 進行中",
        "todo":  "⬜ 未着手",
        "risk":  "⚠️  遅延リスク",
    }
    PHASE_JP = {1: "計画・設計", 2: "開発", 3: "検証・リリース"}

    lines = []
    current_phase = None
    for t in tasks:
        if t["phase"] != current_phase:
            current_phase = t["phase"]
            lines.append(f"\n【フェーズ{current_phase}: {PHASE_JP.get(current_phase, '')}】")

        status  = STATUS_JP.get(t["status"], t["status"])
        assign  = t["assign"] or "未定"
        prog    = t["progress"]
        end     = t["end_date"].strftime("%m/%d") if t["end_date"] else "—"
        lines.append(f"  {status} {t['name']}（担当: {assign} / 進捗: {prog}% / 期限: {end}）")

    return "\n".join(lines)


# ===== フォーマット: メンバー → テキスト =====
def format_members(members: list[dict]) -> str:
    if not members:
        return ""
    lines = ["\n【メンバー稼働状況】"]
    for m in members:
        load    = m["workload"]
        alert   = " ⚠️ 過負荷" if load > 100 else (" 注意" if load > 85 else "")
        skills  = "・".join(m["skills"]) if m["skills"] else "—"
        lines.append(f"  {m['name']}（{m['role']}）: {load}%{alert} ／ スキル: {skills}")
    return "\n".join(lines)


# ===== AIによる分析コメント生成 =====
def generate_analysis(tasks: list[dict], members: list[dict]) -> str:
    """ルールベースでリスク・提案を生成（LLM不要）"""
    comments = []

    # 遅延リスクタスク
    risk_tasks = [t for t in tasks if t["status"] == "risk"]
    if risk_tasks:
        names = "、".join(t["name"] for t in risk_tasks)
        comments.append(f"⚠️  遅延リスクのタスク: {names}")

    # 進捗0%で期限が近いタスク
    import datetime
    today = datetime.date.today()
    for t in tasks:
        if t["status"] == "todo" and t["end_date"]:
            days_left = (t["end_date"] - today).days
            if days_left <= 7:
                comments.append(
                    f"🔴 「{t['name']}」は未着手ですが期限まで{days_left}日です"
                )

    # 過負荷メンバー
    overload = [m for m in members if m["workload"] > 100]
    if overload:
        names = "、".join(m["name"] for m in overload)
        comments.append(f"👤 稼働過多のメンバー: {names}（タスク再配分を検討してください）")

    # 全完了チェック
    total = len(tasks)
    done  = sum(1 for t in tasks if t["status"] == "done")
    if total > 0:
        comments.append(f"📊 全体進捗: {done}/{total} タスク完了（{int(done/total*100)}%）")

    return "\n".join(comments) if comments else "現時点で特筆すべきリスクはありません。"


# ===== メインエントリポイント =====
async def run_project_agent(question: str, session_id: str) -> str:
    """supervisor.py から呼び出されるエントリポイント"""
    print(f"📋 工程管理エージェント起動: {question}")

    # プロジェクト特定
    project_id = await find_project_id(question)

    # DB からタスク・メンバー取得
    tasks   = await fetch_tasks(project_id)
    members = await fetch_members(project_id)

    # 既存RAGからも関連情報を検索（任意）
    rag_docs = search_documents(question, k=2)
    rag_context = ""
    if rag_docs:
        rag_context = "\n\n【関連ナレッジ】\n" + "\n".join(
            d["content"][:200] for d in rag_docs
        )

    # 回答を組み立て
    task_text   = format_tasks(tasks)
    member_text = format_members(members)
    analysis    = generate_analysis(tasks, members)

    return (
        f"プロジェクトの現在状況をお伝えします。\n"
        f"{task_text}"
        f"{member_text}\n\n"
        f"【AIによる分析】\n{analysis}"
        f"{rag_context}"
    )
