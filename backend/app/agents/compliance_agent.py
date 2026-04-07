"""
compliance_agent.py — KEIEI-AI 守り：労務・法令・ハラスメント・契約審査
既存のsupervisor.py / security.py / base_prompt.py と統合して動作

対応領域：
  - 労務違反の未然防止（労基法・安衛法・育介法）
  - ハラスメント早期検知（パワハラ・セクハラ・マタハラ）
  - 契約書・就業規則のリアルタイム審査
  - is_certified フラグ（士業レビュー連携）
"""
from __future__ import annotations
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
class ComplianceResult:
    """コンプライアンス審査の結果"""
    category: Literal["labor", "harassment", "contract", "info_leak", "general"]
    risk_level: Literal["safe", "caution", "warning", "critical"]
    summary: str
    details: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    is_certified: bool = False          # 士業レビュー完了フラグ
    certified_by: str | None = None     # 確認した士業の登録番号
    certified_at: datetime | None = None
    requires_expert: bool = False       # 専門家への相談が必要か
    law_references: list[str] = field(default_factory=list)

    def to_markdown(self) -> str:
        LEVEL_LABEL = {
            "safe":     "✅ 問題なし",
            "caution":  "🟡 注意",
            "warning":  "🟠 警告",
            "critical": "🔴 緊急対応が必要",
        }
        lines = [
            f"## コンプライアンス審査結果",
            f"**リスクレベル**: {LEVEL_LABEL[self.risk_level]}",
            f"**概要**: {self.summary}",
        ]
        if self.details:
            lines.append("\n### 検出された問題点")
            for d in self.details:
                lines.append(f"- {d}")
        if self.law_references:
            lines.append("\n### 関連法令・規程")
            for r in self.law_references:
                lines.append(f"- {r}")
        if self.recommendations:
            lines.append("\n### 推奨アクション")
            for i, r in enumerate(self.recommendations, 1):
                lines.append(f"{i}. {r}")
        if self.requires_expert:
            lines.append("\n> ⚠️ **本件は社会保険労務士・弁護士への相談を推奨します。**")
        if self.is_certified:
            lines.append(
                f"\n> ✅ 士業レビュー済み（{self.certified_by} / "
                f"{self.certified_at.strftime('%Y-%m-%d') if self.certified_at else '日時不明'}）"
            )
        return "\n".join(lines)


# =====================================================
# 2. キーワード辞書（Gate1：高速検知）
# =====================================================

LABOR_KEYWORDS = [
    "残業代", "未払い", "サービス残業", "36協定", "労働時間",
    "有給", "育休", "産休", "解雇", "不当解雇", "雇用契約",
    "最低賃金", "社会保険", "労災", "安全衛生", "ハローワーク",
    "就業規則", "賃金", "休日出勤", "深夜労働", "変形労働",
    "労基法", "労働基準法", "育介法", "パートタイム",
]

HARASSMENT_KEYWORDS = [
    "パワハラ", "セクハラ", "マタハラ", "ケアハラ", "モラハラ",
    "いじめ", "嫌がらせ", "脅し", "怒鳴る", "暴言",
    "差別", "プレッシャー", "強要", "無視", "孤立",
    "精神的苦痛", "退職強要", "降格", "不当評価",
    "相談窓口", "ハラスメント", "人権",
]

CONTRACT_KEYWORDS = [
    "契約書", "雇用契約書", "業務委託", "NDA", "秘密保持",
    "就業規則", "規程", "覚書", "合意書", "同意書",
    "条項", "違反", "無効", "解約", "更新", "期間",
    "賠償", "損害", "罰則", "ペナルティ",
]

INFO_LEAK_KEYWORDS = [
    "個人情報", "マイナンバー", "顧客情報", "機密情報",
    "漏洩", "流出", "紛失", "不正アクセス", "情報管理",
    "GDPR", "個人情報保護法", "プライバシー",
    "パスワード", "アカウント", "権限", "アクセス制御",
]


def _detect_category(text: str) -> str | None:
    """キーワードからカテゴリを高速判定"""
    t = text.lower()
    scores = {
        "labor":      sum(1 for k in LABOR_KEYWORDS      if k in t),
        "harassment": sum(1 for k in HARASSMENT_KEYWORDS if k in t),
        "contract":   sum(1 for k in CONTRACT_KEYWORDS   if k in t),
        "info_leak":  sum(1 for k in INFO_LEAK_KEYWORDS  if k in t),
    }
    best = max(scores, key=lambda k: scores[k])
    return best if scores[best] >= 1 else None


# =====================================================
# 3. LLM審査プロンプト
# =====================================================

COMPLIANCE_SYSTEM_PROMPT = """あなたはKEIEI-AIのコンプライアンス審査エージェントです。
日本の労働法・ハラスメント防止法・個人情報保護法・契約法に精通した法務AIです。

【審査方針】
- 「知らなかったでは済まされない」リスクを最優先で検出する
- 根拠となる法令・条文を必ず明示する
- リスクレベルは4段階：safe / caution / warning / critical
- 専門家（社労士・弁護士）が必要な案件は明確にフラグを立てる
- AIとして法的判断の最終確認は専門家に委ねることを明示する

【出力フォーマット（JSON）】
{
  "risk_level": "safe|caution|warning|critical",
  "category": "labor|harassment|contract|info_leak|general",
  "summary": "30文字以内の要約",
  "details": ["問題点1", "問題点2"],
  "law_references": ["労働基準法第XX条", "..."],
  "recommendations": ["推奨アクション1", "推奨アクション2"],
  "requires_expert": true|false
}

必ずJSONのみを返してください。前後に説明文を付けないでください。"""


async def _run_llm_compliance_check(question: str, category: str) -> dict:
    """LLMによる詳細コンプライアンス審査"""
    llm = get_llm_analysis()
    category_hints = {
        "labor":      "労働法・労基法・社会保険・雇用契約の観点で審査してください。",
        "harassment": "ハラスメント防止法・企業の防止義務・相談体制の観点で審査してください。",
        "contract":   "契約法・就業規則の法的有効性・リスク条項の観点で審査してください。",
        "info_leak":  "個人情報保護法・セキュリティガバナンス・漏洩リスクの観点で審査してください。",
        "general":    "経営法務全般の観点で審査してください。",
    }
    hint = category_hints.get(category, category_hints["general"])

    response = await llm.ainvoke([
        SystemMessage(content=COMPLIANCE_SYSTEM_PROMPT),
        HumanMessage(content=f"{hint}\n\n審査対象：\n{question[:2000]}"),
    ])

    import json, re
    content = str(response.content).strip()
    # コードブロックを除去
    content = re.sub(r"```json|```", "", content).strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        # パース失敗時のフォールバック
        return {
            "risk_level": "caution",
            "category": category,
            "summary": "審査結果の解析に失敗しました。専門家にご確認ください。",
            "details": [],
            "law_references": [],
            "recommendations": ["社会保険労務士・弁護士への相談を推奨します。"],
            "requires_expert": True,
        }


# =====================================================
# 4. メインエントリーポイント
# =====================================================

async def run_compliance_agent(question: str, session_id: str) -> str:
    """
    supervisor.py から呼ばれるメインエントリー
    既存の execute_agent() の elif ブロックに追加する形で使用
    """
    # Gate1: キーワードでカテゴリ判定
    category = _detect_category(question) or "general"
    print(f"[COMPLIANCE] カテゴリ判定: {category}")

    # Gate2: LLMで詳細審査
    raw = await _run_llm_compliance_check(question, category)

    result = ComplianceResult(
        category=raw.get("category", category),
        risk_level=raw.get("risk_level", "caution"),
        summary=raw.get("summary", ""),
        details=raw.get("details", []),
        recommendations=raw.get("recommendations", []),
        requires_expert=raw.get("requires_expert", False),
        law_references=raw.get("law_references", []),
    )

    # 監査ログ記録
    _write_audit_log(session_id, question, result)

    return result.to_markdown()


def _write_audit_log(session_id: str, question: str, result: ComplianceResult) -> None:
    """コンプライアンス審査の監査ログを記録"""
    import json, os
    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        "question_preview": question[:100],
        "risk_level": result.risk_level,
        "category": result.category,
        "requires_expert": result.requires_expert,
        "is_certified": result.is_certified,
    }
    log_dir = "logs/compliance"
    os.makedirs(log_dir, exist_ok=True)
    log_path = f"{log_dir}/audit_{datetime.now(timezone.utc).strftime('%Y%m%d')}.jsonl"
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    print(f"[COMPLIANCE] 監査ログ記録: {log_path}")


# =====================================================
# 5. 士業レビューAPI用ヘルパー
# =====================================================

async def certify_compliance_result(
    result_id: str,
    specialist_license_number: str,
    specialist_type: Literal["sr", "lawyer", "cpa", "smc"],
) -> ComplianceResult:
    """
    士業が審査結果をレビューして is_certified フラグを付与
    api/compliance.py のエンドポイントから呼ばれる

    specialist_type:
      sr     = 社会保険労務士
      lawyer = 弁護士
      cpa    = 公認会計士
      smc    = 中小企業診断士
    """
    # TODO: DBからresult_idで結果を取得して更新
    # 現時点ではプレースホルダー実装
    print(f"[COMPLIANCE] 士業認証: {specialist_type} / {specialist_license_number}")
    return ComplianceResult(
        category="general",
        risk_level="safe",
        summary="士業レビュー済み",
        is_certified=True,
        certified_by=f"{specialist_type}:{specialist_license_number}",
        certified_at=datetime.now(timezone.utc),
    )
