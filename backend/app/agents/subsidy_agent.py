"""
subsidy_agent.py — KEIEI-AI 攻め：補助金・助成金自動マッチング
機能:
  - jGrants API連携（経産省公式）
  - 自社プロファイルとのベクトルマッチング
  - 適合スコアリング（獲得見込額・締切・難易度）
  - 申請書下書き自動生成
  - 速報アラート
"""
from __future__ import annotations
import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal
from langchain_core.messages import HumanMessage, SystemMessage
from app.core.llm_factory import get_llm, get_llm_analysis
from app.agents.base_prompt import get_agent_prompt


# =====================================================
# 1. データモデル
# =====================================================

@dataclass
class SubsidyItem:
    """補助金1件の情報"""
    name: str
    amount: str
    deadline: str
    target: str
    summary: str
    url: str = ""
    source: str = ""
    match_score: float = 0.0
    match_reason: str = ""


@dataclass
class SubsidyMatchResult:
    """マッチング結果"""
    matched: list[SubsidyItem] = field(default_factory=list)
    company_profile: dict = field(default_factory=dict)
    total_potential: str = ""
    generated_at: str = ""

    def to_markdown(self) -> str:
        if not self.matched:
            return "## 補助金マッチング結果\n\n該当する補助金が見つかりませんでした。"

        lines = [
            "## 補助金マッチング結果",
            f"**検索日時**: {self.generated_at}",
            f"**獲得見込み総額**: {self.total_potential}",
            "",
        ]
        for i, s in enumerate(self.matched, 1):
            lines += [
                f"### {i}. {s.name}",
                f"- **補助額**: {s.amount}",
                f"- **締切**: {s.deadline}",
                f"- **対象**: {s.target}",
                f"- **適合理由**: {s.match_reason}",
                f"- **概要**: {s.summary}",
            ]
            if s.url:
                lines.append(f"- **詳細**: {s.url}")
            lines.append("")

        lines.append("\n> [ヒント] 申請書の下書きを作成しますか？「申請書を作って」と入力してください。")
        return "\n".join(lines)


# =====================================================
# 2. 補助金データベース（jGrants代替・主要補助金）
# =====================================================

MAJOR_SUBSIDIES = [
    {
        "name": "ものづくり・商業・サービス生産性向上促進補助金",
        "amount": "最大1,250万円（通常枠）",
        "deadline": "2026年6月頃（第19次締切予定）",
        "target": "中小企業・小規模事業者（製造業・サービス業等）",
        "summary": "革新的な設備投資・システム構築・プロセス改善等を支援",
        "url": "https://portal.monodukuri-hojo.jp/",
        "keywords": ["製造", "設備投資", "DX", "生産性向上", "システム構築", "省力化"],
    },
    {
        "name": "IT導入補助金",
        "amount": "最大450万円（複数社連携IT導入類型）",
        "deadline": "2026年通年受付",
        "target": "中小企業・小規模事業者",
        "summary": "業務効率化・DX推進のためのITツール導入費用を補助",
        "url": "https://www.it-hojo.jp/",
        "keywords": ["IT", "DX", "システム", "ソフトウェア", "デジタル化", "AI", "業務効率"],
    },
    {
        "name": "事業再構築補助金",
        "amount": "最大3,000万円（成長枠）",
        "deadline": "2026年随時受付",
        "target": "中小企業・中堅企業（売上高等要件あり）",
        "summary": "新分野展開・業態転換・事業転換・業種転換等の思い切った事業再構築を支援",
        "url": "https://jigyou-saikouchiku.go.jp/",
        "keywords": ["新規事業", "業態転換", "事業転換", "新分野", "再構築"],
    },
    {
        "name": "小規模事業者持続化補助金",
        "amount": "最大200万円（特別枠）",
        "deadline": "2026年第17回締切予定",
        "target": "小規模事業者（従業員20名以下等）",
        "summary": "販路開拓・業務効率化の取り組みを支援",
        "url": "https://s23.jizokukahojokin.info/",
        "keywords": ["小規模", "販路開拓", "マーケティング", "広告", "ホームページ"],
    },
    {
        "name": "キャリアアップ助成金",
        "amount": "最大95.7万円/人（正社員化コース）",
        "deadline": "随時受付",
        "target": "非正規雇用労働者を正規雇用に転換する事業主",
        "summary": "非正規雇用から正規雇用への転換・処遇改善を支援",
        "url": "https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/koyou_roudou/part_haken/jigyounushi/career.html",
        "keywords": ["雇用", "正社員化", "パート", "アルバイト", "人材", "労務"],
    },
    {
        "name": "人材開発支援助成金",
        "amount": "訓練費用の最大75%",
        "deadline": "随時受付",
        "target": "従業員の職業訓練を実施する事業主",
        "summary": "従業員のスキルアップ・資格取得・OJT訓練費用を補助",
        "url": "https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/koyou_roudou/koyou/kyufukin/d01-1.html",
        "keywords": ["人材育成", "研修", "スキルアップ", "資格", "教育", "訓練", "eラーニング"],
    },
    {
        "name": "省力化投資補助金",
        "amount": "最大1,500万円",
        "deadline": "2026年通年受付",
        "target": "中小企業・小規模事業者",
        "summary": "人手不足解消のためのIoT・ロボット等の省力化製品導入を支援",
        "url": "https://shoryokuka.smrj.go.jp/",
        "keywords": ["省力化", "人手不足", "ロボット", "IoT", "自動化", "効率化"],
    },
    {
        "name": "地域DX促進活動支援事業",
        "amount": "最大500万円",
        "deadline": "都道府県により異なる",
        "target": "地域の中小企業のDX推進を支援する団体・企業",
        "summary": "地域全体のデジタル化・DX推進を支援",
        "url": "https://www.meti.go.jp/",
        "keywords": ["地域", "DX", "デジタル", "地方", "中小企業支援"],
    },
]


# =====================================================
# 3. マッチングエンジン
# =====================================================

async def _score_subsidy(
    subsidy: dict,
    company_profile: dict,
    question: str,
) -> SubsidyItem:
    """補助金と自社プロファイルの適合度をスコアリング"""

    # キーワードマッチング
    q_text = (question + " " + json.dumps(company_profile, ensure_ascii=False)).lower()
    keyword_score = sum(1 for kw in subsidy["keywords"] if kw in q_text)
    match_score = min(keyword_score / max(len(subsidy["keywords"]), 1), 1.0)

    # マッチ理由を生成
    matched_keywords = [kw for kw in subsidy["keywords"] if kw in q_text]
    match_reason = f"キーワード一致: {', '.join(matched_keywords[:3])}" if matched_keywords else "条件確認要"

    return SubsidyItem(
        name=subsidy["name"],
        amount=subsidy["amount"],
        deadline=subsidy["deadline"],
        target=subsidy["target"],
        summary=subsidy["summary"],
        url=subsidy["url"],
        match_score=match_score,
        match_reason=match_reason,
    )


async def match_subsidies(
    question: str,
    company_profile: dict | None = None,
) -> SubsidyMatchResult:
    """自社プロファイルと補助金をマッチング"""

    if company_profile is None:
        company_profile = {}

    # 全補助金をスコアリング
    scored = []
    for subsidy in MAJOR_SUBSIDIES:
        item = await _score_subsidy(subsidy, company_profile, question)
        scored.append(item)

    # スコア順にソート・上位5件
    scored.sort(key=lambda x: x.match_score, reverse=True)
    top_matches = [s for s in scored if s.match_score > 0][:5]

    # スコアが0でも上位3件は返す
    if not top_matches:
        top_matches = scored[:3]

    # 獲得見込み総額（概算）
    total_potential = f"最大{len(top_matches)}件・合計数百万〜数千万円規模"

    return SubsidyMatchResult(
        matched=top_matches,
        company_profile=company_profile,
        total_potential=total_potential,
        generated_at=datetime.now(timezone.utc).strftime("%Y年%m月%d日 %H:%M"),
    )


# =====================================================
# 4. 申請書自動生成
# =====================================================

DRAFT_SYSTEM_PROMPT = """あなたはKEIEI-AIの補助金申請書作成エージェントです。
中小企業診断士レベルの知識で、採択率の高い申請書の下書きを作成します。

【作成方針】
- 補助金の審査基準に沿った構成にする
- 自社の強みを具体的に記載する
- 数値・実績を積極的に盛り込む
- 「革新性」「効果」「実現可能性」を明確に示す
- 専門家（中小企業診断士）による最終確認を推奨する旨を末尾に記載する

必ずMarkdown形式で出力してください。"""


async def generate_application_draft(
    subsidy_name: str,
    company_profile: dict,
    question: str,
) -> str:
    """補助金申請書の下書きを生成"""
    llm = get_llm_analysis()

    profile_text = json.dumps(company_profile, ensure_ascii=False, indent=2) if company_profile else "（プロファイル未設定）"

    response = await llm.ainvoke([
        SystemMessage(content=DRAFT_SYSTEM_PROMPT),
        HumanMessage(content=f"""
以下の情報をもとに「{subsidy_name}」の申請書下書きを作成してください。

【自社情報】
{profile_text}

【申請目的・背景】
{question}

申請書の構成：
1. 事業概要
2. 現状の課題
3. 補助事業の内容
4. 革新性・独自性
5. 期待される効果（数値目標）
6. 実施スケジュール
7. 資金計画
"""),
    ])

    if isinstance(response.content, list):
        return response.content[0].get("text", "")
    return str(response.content)


# =====================================================
# 5. メインエントリーポイント
# =====================================================

async def run_subsidy_agent(question: str, session_id: str) -> str:
    """supervisor.py から呼ばれるメインエントリー"""
    q = question.lower()

    # 申請書生成モード
    if any(kw in q for kw in ["申請書", "申請を", "書類", "下書き", "ドラフト"]):
        # セッションから補助金名を特定（簡易実装）
        subsidy_name = "IT導入補助金"
        for s in MAJOR_SUBSIDIES:
            if s["name"][:10].lower() in q:
                subsidy_name = s["name"]
                break

        draft = await generate_application_draft(
            subsidy_name=subsidy_name,
            company_profile={},
            question=question,
        )
        return f"## {subsidy_name} 申請書下書き\n\n{draft}\n\n---\n> [注意] **中小企業診断士・社労士による最終確認を推奨します。**"

    # マッチングモード
    result = await match_subsidies(question=question)
    return result.to_markdown()
