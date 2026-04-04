"""
evaluate.py - Ground Truthとの自動比較スクリプト
使い方: python benchmark/scripts/evaluate.py
"""
import asyncio
import json
import os
import httpx
from pathlib import Path
from dotenv import load_dotenv

# .envから読み込む
load_dotenv(Path(__file__).parent.parent.parent / "backend" / ".env")

API_URL  = "http://localhost:8000"
EMAIL    = os.getenv("BENCHMARK_EMAIL", "")
PASSWORD = os.getenv("BENCHMARK_PASSWORD", "")

GROUND_TRUTH_DIR = Path(__file__).parent.parent / "ground_truth"


async def get_token() -> str:
    async with httpx.AsyncClient() as client:
        res = await client.post(
            f"{API_URL}/api/auth/login",
            json={"email": EMAIL, "password": PASSWORD},
        )
        return res.json()["access_token"]


async def ask_question(token: str, question: str) -> dict:
    async with httpx.AsyncClient(timeout=60) as client:
        res = await client.post(
            f"{API_URL}/api/chat",
            json={"question": question, "thinking": False},
            headers={"Authorization": f"Bearer {token}"},
        )
        return res.json()


def evaluate_answer(result: dict, ground_truth: dict) -> dict:
    score  = 0
    issues = []

    # ルーティング確認
    if result.get("route") == ground_truth.get("expected_route"):
        score += 2
    else:
        issues.append(f"ルート誤り: {result.get('route')} (期待: {ground_truth.get('expected_route')})")

    # 必須キーワード確認
    answer = result.get("answer", "")
    for keyword in ground_truth.get("must_contain", []):
        if keyword in answer:
            score += 1
        else:
            issues.append(f"キーワード不足: {keyword}")

    # 禁止ワード確認
    for word in ground_truth.get("must_not_say", []):
        if word in answer:
            score -= 2
            issues.append(f"禁止ワード使用: {word}")

    return {
        "question": ground_truth["question"],
        "route":    result.get("route"),
        "expected": ground_truth.get("expected_route"),
        "score":    max(0, score),
        "issues":   issues,
        "pass":     len(issues) == 0,
    }


async def run_benchmark():
    print("=" * 60)
    print("KEIEI-AI ベンチマーク評価")
    print("=" * 60)

    if not EMAIL or not PASSWORD:
        print("ERROR: BENCHMARK_EMAIL と BENCHMARK_PASSWORD を backend/.env に設定してください")
        return

    token   = await get_token()
    results = []

    for jsonl_file in GROUND_TRUTH_DIR.glob("*.jsonl"):
        print(f"\n[{jsonl_file.stem}]")
        with open(jsonl_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                gt     = json.loads(line)
                result = await ask_question(token, gt["question"])
                eval_result = evaluate_answer(result, gt)
                results.append(eval_result)

                status = "OK" if eval_result["pass"] else "NG"
                print(f"  [{status}] {gt['question'][:30]}... (score: {eval_result['score']})")
                for issue in eval_result["issues"]:
                    print(f"       WARNING: {issue}")

    # サマリー
    total     = len(results)
    passed    = sum(1 for r in results if r["pass"])
    avg_score = sum(r["score"] for r in results) / total if total > 0 else 0

    print("\n" + "=" * 60)
    print("ベンチマーク結果")
    print(f"  合格率:     {passed}/{total} ({passed/total*100:.1f}%)")
    print(f"  平均スコア: {avg_score:.1f}")
    print("=" * 60)

    # JSON保存
    output = Path(__file__).parent.parent / "results.json"
    with open(output, "w", encoding="utf-8") as f:
        json.dump({
            "total":     total,
            "passed":    passed,
            "pass_rate": passed / total if total > 0 else 0,
            "avg_score": avg_score,
            "details":   results,
        }, f, ensure_ascii=False, indent=2)
    print(f"\n結果保存: {output}")


if __name__ == "__main__":
    asyncio.run(run_benchmark())