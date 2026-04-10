"""
supervisor_patch.py — 既存 supervisor.py への差分パッチ
このファイルは「追加・変更箇所のみ」を示します。
既存コードを丸ごと置き換えずに済みます。

適用手順：
  1. CLEAR_KEYWORDS に "compliance" キーを追加
  2. route_question() に compliance ルートを追加
  3. execute_agent() に compliance / info_leak_guard を追加
  4. SupervisorState に "user_role" が既にある → 変更不要
"""

# =====================================================
# PATCH 1: CLEAR_KEYWORDS への追加
# （既存の CLEAR_KEYWORDS 辞書の末尾に追加）
# =====================================================
COMPLIANCE_KEYWORDS_PATCH = {
    "compliance": [
        # 労務
        "残業代", "未払い", "サービス残業", "36協定", "労働時間",
        "有給", "育休", "産休", "解雇", "不当解雇", "最低賃金",
        "労基法", "労働基準法", "社会保険", "労災",
        # ハラスメント
        "パワハラ", "セクハラ", "マタハラ", "ハラスメント",
        "いじめ", "嫌がらせ", "退職強要",
        # 契約・規程
        "就業規則", "雇用契約書", "NDA", "秘密保持契約",
        "契約違反", "条項審査",
        # 情報管理
        "個人情報漏洩", "情報流出", "不正アクセス", "GDPR",
        "個人情報保護法",
    ],
}

# =====================================================
# PATCH 2: route_question() への追加
# （CLEAR_KEYWORDS の for ループが compliance も検出するため
#   追加コードは execute_agent() 側のみ）
# =====================================================

# =====================================================
# PATCH 3: execute_agent() への追加
# 既存の elif route == "web": の直前に挿入
# =====================================================
EXECUTE_AGENT_PATCH = '''
        elif route == "compliance":
            from app.agents.compliance_agent import run_compliance_agent
            result = await run_compliance_agent(question, session_id)

'''

# =====================================================
# PATCH 4: execute_agent() の return 直前に挿入
# result を返す前に出力スキャンを実行
# =====================================================
OUTPUT_GUARD_PATCH = '''
        # 情報漏洩ガード（全ルート共通）
        from app.agents.info_leak_guard import full_output_guard
        result = await full_output_guard(result, state.get("user_role", "staff"))

'''

# =====================================================
# PATCH 5: base_prompt.py の AGENT_PROMPTS への追加
# =====================================================
COMPLIANCE_PROMPT_PATCH = '''
        "compliance": """
【担当領域】労務・法令・ハラスメント・契約・情報管理

【専門思考】
- 「知らなかったでは済まされない」リスクを最優先で検出する
- 根拠となる法令・条文（労基法・ハラスメント防止法・個人情報保護法）を必ず明示する
- リスクレベルを4段階で評価: safe / caution / warning / critical
- 専門家（社労士・弁護士）への相談が必要な場合は明確に促す
- AIの判断はあくまで参考情報であり、法的判断の最終確認は専門家に委ねる

【禁止事項】
- 「これは問題ありません」という断定的な法的判断
- 専門家資格なしでの法的アドバイスの提供
""",
'''

# =====================================================
# 適用確認用サマリ
# =====================================================
print("""
=== supervisor_patch.py 適用ガイド ===

[1] backend/app/agents/supervisor.py の CLEAR_KEYWORDS に追加:
    CLEAR_KEYWORDS["compliance"] = [...] (COMPLIANCE_KEYWORDS_PATCH)

[2] backend/app/agents/supervisor.py の execute_agent() に追加:
    elif route == "web": の直前に EXECUTE_AGENT_PATCH を挿入

[3] backend/app/agents/supervisor.py の execute_agent() の
    return {"result": result} の直前に OUTPUT_GUARD_PATCH を挿入

[4] backend/app/agents/base_prompt.py の AGENT_PROMPTS に追加:
    "file_analysis" の後に COMPLIANCE_PROMPT_PATCH を追加
""")
