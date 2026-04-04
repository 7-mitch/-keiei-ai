"""
judge_agent.py — LLM-as-Judge 自動採点エージェント
RAGASベースの評価指標で回答品質を1〜5点で採点
"""
from langchain_core.messages import HumanMessage, SystemMessage
from app.core.llm_factory import get_llm

llm = get_llm()

JUDGE_SYSTEM_PROMPT = """あなたは経営支援AIの回答品質を評価する専門家です。
以下の4つの指標で1〜5点（整数）で採点してください。

【評価指標】
1. faithfulness（事実との一致）
   5: 完全に正確  4: ほぼ正確  3: 部分的に正確  2: 不正確な部分あり  1: 誤情報多数

2. relevancy（質問への関連性）
   5: 完全に回答  4: ほぼ回答  3: 部分的に回答  2: 的外れな部分あり  1: 全く関係ない

3. completeness（回答の完全性）
   5: 非常に詳細  4: 十分な情報  3: 基本情報あり  2: 情報不足  1: ほぼ情報なし

4. business_value（ビジネス価値）
   5: 即実行可能な提案  4: 有益な示唆  3: 参考になる  2: あまり役立たない  1: 価値なし

【出力形式】必ずJSON形式で出力してください：
{
  "faithfulness": 数値,
  "relevancy": 数値,
  "completeness": 数値,
  "business_value": 数値,
  "comment": "採点理由を50文字以内で"
}"""


ROUTE_LABELS = {
    "sql":           "DB検索・KPI分析",
    "rag":           "文書検索・コンプライアンス",
    "fraud":         "不正検知",
    "web":           "Web情報収集",
    "general":       "一般的な経営相談",
    "hr":            "人事・適性診断",
    "cash_flow":     "資金繰り管理",
    "project":       "工程管理",
    "file_analysis": "ファイル解析",
}


async def evaluate_response(question: str, answer: str, route: str) -> dict:
    """LLMで回答品質を採点する"""
    import json
    import re

    route_label = ROUTE_LABELS.get(route, route)

    prompt = f"""【ルート】{route_label}

【質問】
{question[:500]}

【AIの回答】
{answer[:1000]}

上記の回答を評価してください。"""

    try:
        response = await llm.ainvoke([
            SystemMessage(content=JUDGE_SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ])

        content = str(response.content)

        # <think>タグを除去（Qwen3の推論モード対応）
        content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()

        # JSONを抽出
        json_match = re.search(r"\{.*\}", content, re.DOTALL)
        if not json_match:
            raise ValueError("JSONが見つかりません")

        scores = json.loads(json_match.group())

        # スコアを1〜5に正規化
        for key in ["faithfulness", "relevancy", "completeness", "business_value"]:
            scores[key] = max(1, min(5, int(scores.get(key, 3))))

        # 総合スコア計算（加重平均）
        scores["total_score"] = round(
            scores["faithfulness"]   * 0.25 +
            scores["relevancy"]      * 0.30 +
            scores["completeness"]   * 0.25 +
            scores["business_value"] * 0.20,
            1
        )

        # ルーティング正誤（暫定: goodフィードバックならTrue）
        scores["routing_correct"] = True
        scores["comment"] = scores.get("comment", "")[:200]

        return scores

    except Exception as e:
        print(f"[JUDGE] 採点失敗: {e}")
        return {
            "faithfulness":    3,
            "relevancy":       3,
            "completeness":    3,
            "business_value":  3,
            "routing_correct": True,
            "total_score":     3.0,
            "comment":         f"採点エラー: {str(e)[:50]}",
        }