"""
dpo_pipeline.py — DPO学習データ自動生成パイプライン

機能:
  ① chosen/rejected ペア自動生成
     good(👍) → chosen / bad(👎) → rejected
     スコア差が大きいペアを優先抽出

  ② プロンプト自動改善（全モデル共通）
     good回答のパターンをbase_prompt.pyに反映候補として提示

  ③ HuggingFace形式でエクスポート
     Ollama QLoRA / HuggingFace Trainer対応
"""
import json
from datetime import datetime
from app.db.connection import get_conn


# ===== ① chosen/rejected ペア生成 =====
async def generate_dpo_pairs(min_score_diff: float = 0.0) -> int:
    """
    chat_feedbacksとchat_benchmarksから
    DPO学習ペアを自動生成してdpo_datasetsに保存

    min_score_diff: chosenとrejectedのスコア差の最小値
    """
    async with get_conn() as conn:
        # good回答（chosen候補）を取得
        good_rows = await conn.fetch("""
            SELECT
                f.question, f.answer, f.route,
                b.total_score, f.session_id
            FROM chat_feedbacks f
            JOIN chat_benchmarks b ON b.feedback_id = f.id
            WHERE f.feedback = 'good'
              AND b.total_score >= 3.5
              AND f.answer NOT LIKE '%Googleによってトレーニング%'
              AND f.answer NOT LIKE '%大規模言語モデルです%'
            ORDER BY b.total_score DESC
            LIMIT 500
        """)

        # bad回答（rejected候補）を取得
        bad_rows = await conn.fetch("""
            SELECT
                f.question, f.answer, f.route,
                b.total_score, f.session_id
            FROM chat_feedbacks f
            JOIN chat_benchmarks b ON b.feedback_id = f.id
            WHERE f.feedback = 'bad'
              AND b.total_score <= 3.0
              AND f.answer NOT LIKE '%セキュリティ検査%'
              AND f.answer NOT LIKE '%不正な入力%'
            ORDER BY b.total_score ASC
            LIMIT 500
        """)

        if not good_rows or not bad_rows:
            print("[DPO] データ不足: good/badペアが作れません")
            return 0

        # ルートごとにペアを作成
        good_by_route: dict = {}
        for row in good_rows:
            good_by_route.setdefault(row["route"], []).append(row)

        bad_by_route: dict = {}
        for row in bad_rows:
            bad_by_route.setdefault(row["route"], []).append(row)

        count = 0
        for route in good_by_route:
            if route not in bad_by_route:
                continue

            goods = good_by_route[route]
            bads  = bad_by_route[route]

            for good in goods:
                for bad in bads:
                    # 同じ質問に対するペアを優先
                    if good["question"] != bad["question"]:
                        continue

                    score_diff = (good["total_score"] or 0) - (bad["total_score"] or 0)
                    if score_diff < min_score_diff:
                        continue

                    # 既存チェック
                    exists = await conn.fetchval("""
                        SELECT COUNT(*) FROM dpo_datasets
                        WHERE prompt = $1 AND chosen = $2 AND rejected = $3
                    """, good["question"], good["answer"], bad["answer"])

                    if exists:
                        continue

                    await conn.execute("""
                        INSERT INTO dpo_datasets
                          (prompt, chosen, rejected, route,
                           chosen_score, rejected_score)
                        VALUES ($1, $2, $3, $4, $5, $6)
                    """,
                        good["question"],
                        good["answer"],
                        bad["answer"],
                        route,
                        good["total_score"],
                        bad["total_score"],
                    )
                    count += 1

        print(f"[DPO] {count}件のペアを生成しました")
        return count


# ===== ② プロンプト改善候補抽出 =====
async def extract_prompt_improvements(limit: int = 10) -> list[dict]:
    """
    スコアの高いgood回答からプロンプト改善パターンを抽出
    base_prompt.pyの改善に活用
    """
    async with get_conn() as conn:
        rows = await conn.fetch("""
            SELECT
                f.route,
                f.question,
                f.answer,
                b.total_score,
                b.judge_comment
            FROM chat_feedbacks f
            JOIN chat_benchmarks b ON b.feedback_id = f.id
            WHERE f.feedback = 'good'
              AND b.total_score >= 4.5
            ORDER BY b.total_score DESC, f.created_at DESC
            LIMIT $1
        """, limit)

        improvements = []
        for row in rows:
            improvements.append({
                "route":         row["route"],
                "question":      row["question"][:200],
                "answer":        row["answer"][:500],
                "score":         float(row["total_score"] or 0),
                "comment":       row["judge_comment"] or "",
            })

        return improvements


# ===== ③ HuggingFace形式エクスポート =====
async def export_dpo_dataset(output_path: str = "dpo_export.jsonl") -> int:
    """
    dpo_datasetsをHuggingFace Trainer / Ollama QLoRA形式でエクスポート

    出力形式（JSONL）:
    {"prompt": "...", "chosen": "...", "rejected": "..."}
    """
    async with get_conn() as conn:
        rows = await conn.fetch("""
            SELECT prompt, chosen, rejected, route,
                   chosen_score, rejected_score
            FROM dpo_datasets
            WHERE exported = FALSE
            ORDER BY chosen_score DESC
        """)

        if not rows:
            print("[DPO] エクスポート対象なし")
            return 0

        count = 0
        with open(output_path, "w", encoding="utf-8") as f:
            for row in rows:
                record = {
                    "prompt":          row["prompt"],
                    "chosen":          row["chosen"],
                    "rejected":        row["rejected"],
                    "route":           row["route"],
                    "chosen_score":    float(row["chosen_score"] or 0),
                    "rejected_score":  float(row["rejected_score"] or 0),
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
                count += 1

        # エクスポート済みフラグを更新
        await conn.execute("""
            UPDATE dpo_datasets SET exported = TRUE
            WHERE exported = FALSE
        """)

        print(f"[DPO] {count}件を {output_path} にエクスポートしました")
        return count


# ===== ④ 統計レポート =====
async def get_dpo_stats() -> dict:
    """DPOデータセットの統計情報を取得"""
    async with get_conn() as conn:
        stats = await conn.fetchrow("""
            SELECT
                COUNT(*)                           AS total_pairs,
                COUNT(*) FILTER (WHERE exported)   AS exported_pairs,
                AVG(chosen_score)                  AS avg_chosen_score,
                AVG(rejected_score)                AS avg_rejected_score,
                AVG(chosen_score - rejected_score) AS avg_score_diff
            FROM dpo_datasets
        """)

        route_stats = await conn.fetch("""
            SELECT route, COUNT(*) AS count,
                   AVG(chosen_score) AS avg_chosen
            FROM dpo_datasets
            GROUP BY route
            ORDER BY count DESC
        """)

        feedback_stats = await conn.fetchrow("""
            SELECT
                COUNT(*)                                    AS total,
                COUNT(*) FILTER (WHERE feedback = 'good')  AS good_count,
                COUNT(*) FILTER (WHERE feedback = 'bad')   AS bad_count
            FROM chat_feedbacks
        """)

        return {
            "dpo_pairs": {
                "total":            stats["total_pairs"] or 0,
                "exported":         stats["exported_pairs"] or 0,
                "avg_chosen_score": round(float(stats["avg_chosen_score"] or 0), 2),
                "avg_score_diff":   round(float(stats["avg_score_diff"] or 0), 2),
            },
            "feedbacks": {
                "total":      feedback_stats["total"] or 0,
                "good_count": feedback_stats["good_count"] or 0,
                "bad_count":  feedback_stats["bad_count"] or 0,
            },
            "by_route": [
                {
                    "route":       r["route"],
                    "count":       r["count"],
                    "avg_chosen":  round(float(r["avg_chosen"] or 0), 2),
                }
                for r in route_stats
            ],
        }



