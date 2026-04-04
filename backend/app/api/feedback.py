"""
feedback.py — チャットフィードバック・ベンチマークAPI
"""
import asyncio
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from app.core.security import get_current_user
from app.db.connection import get_conn

router = APIRouter()


class FeedbackRequest(BaseModel):
    session_id:  str
    question:    str
    answer:      str
    route:       str
    feedback:    str        # "good" or "bad"
    latency_ms:  Optional[int] = None


class FeedbackResponse(BaseModel):
    feedback_id: int
    message:     str


@router.post("", response_model=FeedbackResponse)
async def submit_feedback(
    req:  FeedbackRequest,
    user: dict = Depends(get_current_user),
):
    """👍👎 フィードバックを保存 → LLM-as-Judge自動採点"""
    async with get_conn() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO chat_feedbacks
              (session_id, question, answer, route, feedback, latency_ms)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id
            """,
            req.session_id,
            req.question,
            req.answer,
            req.route,
            req.feedback,
            req.latency_ms,
        )
        feedback_id = row["id"]

    asyncio.create_task(run_judge(feedback_id, req.question, req.answer, req.route))

    return FeedbackResponse(
        feedback_id=feedback_id,
        message="フィードバックを受け付けました。自動採点中...",
    )


async def run_judge(feedback_id: int, question: str, answer: str, route: str):
    """LLM-as-Judge バックグラウンド採点"""
    try:
        from app.agents.judge_agent import evaluate_response
        scores = await evaluate_response(question, answer, route)

        async with get_conn() as conn:
            await conn.execute(
                """
                INSERT INTO chat_benchmarks
                  (feedback_id, faithfulness, relevancy, completeness,
                   business_value, routing_correct, total_score, judge_comment)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                feedback_id,
                scores["faithfulness"],
                scores["relevancy"],
                scores["completeness"],
                scores["business_value"],
                scores["routing_correct"],
                scores["total_score"],
                scores["comment"],
            )
        print(f"[JUDGE] feedback_id={feedback_id} 採点完了: {scores['total_score']}点")
    except Exception as e:
        print(f"[JUDGE] 採点エラー: {e}")


@router.get("/stats")
async def get_feedback_stats(
    user: dict = Depends(get_current_user),
):
    """フィードバック統計を取得"""
    async with get_conn() as conn:
        stats = await conn.fetchrow(
            """
            SELECT
                COUNT(*)                                        AS total,
                COUNT(*) FILTER (WHERE feedback = 'good')      AS good_count,
                COUNT(*) FILTER (WHERE feedback = 'bad')       AS bad_count,
                AVG(latency_ms)                                 AS avg_latency_ms,
                AVG(b.total_score)                              AS avg_score
            FROM chat_feedbacks f
            LEFT JOIN chat_benchmarks b ON b.feedback_id = f.id
            """
        )
        route_stats = await conn.fetch(
            """
            SELECT
                route,
                COUNT(*)                                   AS total,
                COUNT(*) FILTER (WHERE feedback = 'good') AS good_count,
                AVG(latency_ms)                            AS avg_latency_ms
            FROM chat_feedbacks
            GROUP BY route
            ORDER BY total DESC
            """
        )

    return {
        "total":          stats["total"],
        "good_count":     stats["good_count"],
        "bad_count":      stats["bad_count"],
        "avg_latency_ms": round(stats["avg_latency_ms"] or 0, 1),
        "avg_score":      round(float(stats["avg_score"] or 0), 2),
        "by_route": [
            {
                "route":          r["route"],
                "total":          r["total"],
                "good_count":     r["good_count"],
                "avg_latency_ms": round(r["avg_latency_ms"] or 0, 1),
            }
            for r in route_stats
        ],
    }