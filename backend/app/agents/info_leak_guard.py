"""
info_leak_guard.py — KEIEI-AI 守り：情報漏洩ガード
RAGアクセス制御・機密スキャン・出力フィルタリング

既存の security.py の full_security_check() に統合して使用
"""
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Literal


# =====================================================
# 1. 機密情報パターン定義
# =====================================================

# 正規表現で検出するパターン
SENSITIVE_PATTERNS: list[tuple[str, str]] = [
    (r"(?<!\d)\d{4}-\d{4}-\d{4}-\d{4}(?!\d)",  "クレジットカード番号"),
    (r"\b\d{3}-\d{4}-\d{4}\b",                  "電話番号"),
    (r"\b[A-Z0-9]{12}\b",                        "マイナンバー候補"),
    (r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z]{2,}", "メールアドレス"),
    (r"\b\d{3}-\d{4}\b",                         "郵便番号"),
    (r"(?i)(password|passwd|secret|api.?key)\s*[=:]\s*\S+", "認証情報"),
    (r"(?i)bearer\s+[a-zA-Z0-9\-._~+/]+=*",     "BearerToken"),
    (r"(?i)sk-[a-zA-Z0-9]{16,}",                "APIキー候補"),
]

# キーワードで検出するパターン
SENSITIVE_KEYWORDS = [
    "個人情報", "マイナンバー", "健康保険証", "パスポート",
    "銀行口座", "口座番号", "暗証番号", "パスワード",
    "顧客名簿", "社員番号", "給与明細", "源泉徴収",
    "DATABASE_URL", "SECRET_KEY", "PRIVATE_KEY",
]

# RAGアクセス権限マップ（ロール → アクセス可能カテゴリ）
ROLE_ACCESS_MAP: dict[str, list[str]] = {
    "admin":    ["all"],
    "manager":  ["company_assets", "hr", "financial", "compliance", "general"],
    "staff":    ["company_assets", "general"],
    "guest":    ["general"],
}


# =====================================================
# 2. 出力スキャン
# =====================================================

@dataclass
class LeakScanResult:
    has_risk: bool
    findings: list[str]
    masked_text: str  # マスク処理済みテキスト


def scan_output(text: str) -> LeakScanResult:
    """
    LLM出力テキストをスキャンして機密情報を検出・マスクする
    supervisor.py の execute_agent() の result 返却前に呼ぶ
    """
    findings: list[str] = []
    masked = text

    # 正規表現パターンスキャン
    for pattern, label in SENSITIVE_PATTERNS:
        matches = re.findall(pattern, masked)
        if matches:
            findings.append(f"{label}を検出 ({len(matches)}件)")
            masked = re.sub(pattern, f"[{label}:マスク済み]", masked)

    # キーワードスキャン
    for keyword in SENSITIVE_KEYWORDS:
        if keyword in masked:
            findings.append(f"機密キーワード「{keyword}」を検出")

    return LeakScanResult(
        has_risk=len(findings) > 0,
        findings=findings,
        masked_text=masked,
    )


# =====================================================
# 3. RAGアクセス制御
# =====================================================

def check_rag_access(user_role: str, collection_name: str) -> bool:
    """
    ユーザーのロールに基づいてRAGコレクションへのアクセスを制御
    rag_agent.py の run_rag_agent() 冒頭で呼ぶ
    """
    allowed = ROLE_ACCESS_MAP.get(user_role, ["general"])
    if "all" in allowed:
        return True
    # コレクション名がアクセス可能カテゴリに含まれるか確認
    for category in allowed:
        if category in collection_name:
            return True
    print(f"[INFO-LEAK] アクセス拒否: role={user_role}, collection={collection_name}")
    return False


def get_allowed_collections(user_role: str) -> list[str]:
    """ロールが参照できるコレクション一覧を返す"""
    allowed = ROLE_ACCESS_MAP.get(user_role, ["general"])
    if "all" in allowed:
        return ["all"]
    return allowed


# =====================================================
# 4. security.py への統合ヘルパー
# =====================================================

async def full_output_guard(result: str, user_role: str) -> str:
    """
    既存の full_security_check() に続いて、
    LLM出力をスキャンしてマスク処理を施す

    supervisor.py の execute_agent() の return 直前に挿入：
        from app.agents.info_leak_guard import full_output_guard
        result = await full_output_guard(result, state.get("user_role", "staff"))
        return {"result": result}
    """
    scan = scan_output(result)
    if scan.has_risk:
        print(f"[INFO-LEAK] 出力スキャン警告: {scan.findings}")
        # adminには詳細を通知、それ以外はマスク済みテキストのみ返す
        if user_role == "admin":
            warning = (
                "\n\n---\n"
                "⚠️ **情報漏洩ガード発動**\n"
                f"検出内容: {', '.join(scan.findings)}\n"
                "一部の情報をマスクしました。"
            )
            return scan.masked_text + warning
        return scan.masked_text
    return result
