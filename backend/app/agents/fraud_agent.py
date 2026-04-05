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

# ===== LLM =====
llm = get_llm()


# ===== State定義 =====
class FraudDetectionState(TypedDict):
    transaction_id:   int
    account_id:       int
    amount:           float
    transaction_type: str
    description:      str
    created_at:       str
    rule_result:      dict
    pattern_result:   dict
    llm_result:       dict
    ml_result:        dict
    is_fraud:         bool
    risk_score:       float
    severity:         str
    reasoning:        str
    session_id:       str


# ===== Layer 1: ルールベース判定 =====
def layer1_rule_based(state: FraudDetectionState) -> dict:
    amount      = state["amount"]
    description = state.get("description", "")
    flags       = []
    score       = 0.0

    if amount >= 1_000_000:
        flags.append("高額取引（100万円以上）")
        score += 0.4
    elif amount >= 500_000:
        flags.append("中額取引（50万円以上）")
        score += 0.2

    try:
        dt   = datetime.fromisoformat(state["created_at"])
        hour = dt.hour
        if 0 <= hour < 5:
            flags.append(f"深夜取引（{hour}時台）")
            score += 0.3
    except Exception:
        pass

    suspicious_keywords = ["緊急", "至急", "テスト", "test", "urgent"]
    for kw in suspicious_keywords:
        if kw.lower() in description.lower():
            flags.append(f"疑わしいキーワード: {kw}")
            score += 0.2
            break

    result = {
        "triggered": len(flags) > 0,
        "flags":     flags,
        "score":     min(score, 1.0),
    }
    print(f" Layer1 ルールベース: {result}")
    return {"rule_result": result}


# ===== Layer 2: パターン認識 =====
async def layer2_pattern_recognition(state: FraudDetectionState) -> dict:
    try:
        from sentence_transformers import SentenceTransformer
        import faiss
        import numpy as np

        tx_text = (
            f"金額:{state['amount']} "
            f"種別:{state['transaction_type']} "
            f"説明:{state.get('description', '')}"
        )

        async with get_conn() as conn:
            past_frauds = await conn.fetch("""
                SELECT amount, transaction_type, description, flag_reason
                FROM transactions
                WHERE is_flagged = true
                LIMIT 100
            """)

        if not past_frauds:
            print(" Layer2 パターン認識: 過去の不正データなし")
            return {"pattern_result": {
                "similar_patterns": [],
                "max_similarity":   0.0,
                "score":            0.0,
            }}

        model = SentenceTransformer(
            "intfloat/multilingual-e5-large",
            cache_folder = os.getenv("HF_CACHE_DIR", "/tmp/huggingface"),
        )

        past_texts = [
            f"金額:{r['amount']} 種別:{r['transaction_type']} 説明:{r.get('description','')}"
            for r in past_frauds
        ]
        past_vectors = model.encode(past_texts, normalize_embeddings=True)
        query_vector = model.encode([tx_text], normalize_embeddings=True)

        dim   = past_vectors.shape[1]
        index = faiss.IndexFlatIP(dim)
        index.add(past_vectors.astype("float32"))
        distances, indices = index.search(query_vector.astype("float32"), k=3)

        similar = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx >= 0 and dist > 0.7:
                similar.append({
                    "similarity":  float(dist),
                    "flag_reason": past_frauds[idx].get("flag_reason", ""),
                })

        max_sim = float(distances[0][0]) if len(distances[0]) > 0 else 0.0
        score   = max_sim if max_sim > 0.7 else 0.0

        print(f" Layer2 パターン認識: 類似度={max_sim:.3f}")
        return {"pattern_result": {
            "similar_patterns": similar,
            "max_similarity":   max_sim,
            "score":            score,
        }}

    except Exception as e:
        print(f" Layer2 エラー: {e}")
        return {"pattern_result": {
            "similar_patterns": [],
            "score":            0.0,
            "error":            str(e),
        }}


# ===== Layer 3: LLM判定 =====
async def layer3_llm_judgment(state: FraudDetectionState) -> dict:
    try:
        rule_result    = state["rule_result"]
        pattern_result = state["pattern_result"]

        system_prompt = get_agent_prompt("fraud", extra="""
【出力形式】必ず以下のJSON形式のみで回答してください：
{"risk_score": 0.0-1.0, "is_fraud": true/false, "reason": "理由", "recommendation": "推奨アクション"}
""")

        user_message = f"""取引情報：
- 金額: {state['amount']:,}円
- 種別: {state['transaction_type']}
- 説明: {state.get('description', 'なし')}
- 日時: {state['created_at']}

Layer1（ルールベース）：
- フラグ: {rule_result.get('flags', [])}
- スコア: {rule_result.get('score', 0):.2f}

Layer2（パターン認識）：
- 類似不正パターン数: {len(pattern_result.get('similar_patterns', []))}件
- 最大類似度: {pattern_result.get('max_similarity', 0):.3f}

上記を踏まえて不正リスクを判定してください。"""

        response = await llm.ainvoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message),
        ])

        import re
        content    = response.content
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
        else:
            raise ValueError("JSON形式で返答がありませんでした")

        print(f" Layer3 LLM判定: is_fraud={result['is_fraud']} score={result['risk_score']:.2f}")
        return {"llm_result": result}

    except Exception as e:
        print(f" Layer3 エラー: {e} → フォールバック")
        rule_score    = state["rule_result"].get("score", 0)
        pattern_score = state["pattern_result"].get("score", 0)
        combined      = (rule_score + pattern_score) / 2
        return {"llm_result": {
            "is_fraud":   combined >= 0.4,
            "risk_score": combined,
            "severity":   "medium" if combined >= 0.4 else "low",
            "reasoning":  f"LLMエラーのためフォールバック: {str(e)[:50]}",
        }}


# ===== Layer 4: ML判定 =====
def layer4_ml_judgment(state: FraudDetectionState) -> dict:
    try:
        import joblib
        import numpy as np

        model_path = "app/agents/fraud_model.pkl"

        if os.path.exists(model_path):
            model  = joblib.load(model_path)
            amount = state["amount"]
            try:
                dt   = datetime.fromisoformat(state["created_at"])
                hour = dt.hour
            except Exception:
                hour = 12

            features = np.array([[
                amount,
                1 if state["transaction_type"] == "debit" else 0,
                hour,
                state["rule_result"].get("score", 0),
                state["pattern_result"].get("score", 0),
                np.log1p(amount),
                1 if 0 <= hour < 5 else 0,
                1 if amount >= 1_000_000 else 0,
            ]])

            proba  = model.predict_proba(features)[0][1]
            result = {"score": float(proba), "model_used": True}
        else:
            rule_score    = state["rule_result"].get("score", 0)
            pattern_score = state["pattern_result"].get("score", 0)
            result = {
                "score":      (rule_score + pattern_score) / 2,
                "model_used": False,
            }

        print(f" Layer4 ML判定: score={result['score']:.3f}")
        return {"ml_result": result}

    except Exception as e:
        print(f" Layer4 エラー: {e}")
        return {"ml_result": {"score": 0.0, "error": str(e)}}


# ===== 最終判定・DB保存 =====
async def finalize_judgment(state: FraudDetectionState) -> dict:
    rule_score    = state["rule_result"].get("score", 0)
    pattern_score = state["pattern_result"].get("score", 0)
    llm_result    = state["llm_result"]
    ml_score      = state["ml_result"].get("score", 0)

    final_score = (
        rule_score    * 0.20 +
        pattern_score * 0.20 +
        llm_result.get("risk_score", 0) * 0.40 +
        ml_score      * 0.20
    )

    is_fraud = final_score >= 0.5 or llm_result.get("is_fraud", False)
    severity = llm_result.get("severity", "low")

    if final_score >= 0.8:
        severity = "critical"
    elif final_score >= 0.6:
        severity = "high"
    elif final_score >= 0.4:
        severity = "medium"

    if is_fraud and state["transaction_id"] > 0:
        async with get_conn() as conn:
            await conn.execute("""
                UPDATE transactions
                SET is_flagged  = true,
                    flag_reason = $1,
                    risk_score  = $2
                WHERE id = $3
            """,
                llm_result.get("reasoning", "")[:500],
                final_score,
                state["transaction_id"],
            )
            await conn.execute("""
                INSERT INTO fraud_alerts (
                    transaction_id, account_id,
                    alert_type, severity, description,
                    ai_reasoning, status
                ) VALUES ($1, $2, $3, $4, $5, $6, 'open')
            """,
                state["transaction_id"],
                state["account_id"],
                "multi_layer_detection",
                severity,
                f"多層検知: スコア={final_score:.2f}",
                json.dumps({
                    "layer1": state["rule_result"],
                    "layer2": {"score": pattern_score},
                    "layer3": llm_result,
                    "layer4": state["ml_result"],
                }, ensure_ascii=False),
            )

    if state["transaction_id"] > 0:
        await record_audit(
            operator_id   = None,
            operator_type = "ai_agent",
            target_type   = "fraud_check",
            target_id     = state["transaction_id"],
            action        = f"fraud_detected:{severity}",
            after_value   = {
                "risk_score": final_score,
                "is_fraud":   is_fraud,
                "severity":   severity,
            },
            ai_confidence = final_score,
            session_id    = state.get("session_id"),
        )
    else:
        print(f" 監査ログスキップ（手動テスト）: is_fraud={is_fraud} score={final_score:.2f}")

    print(f" 最終判定: is_fraud={is_fraud} score={final_score:.2f} severity={severity}")
    return {
        "is_fraud":   is_fraud,
        "risk_score": final_score,
        "severity":   severity,
        "reasoning":  llm_result.get("reasoning", ""),
    }


# ===== グラフ構築 =====
def build_fraud_detector():
    g = StateGraph(FraudDetectionState)
    g.add_node("layer1",   layer1_rule_based)
    g.add_node("layer2",   layer2_pattern_recognition)
    g.add_node("layer3",   layer3_llm_judgment)
    g.add_node("layer4",   layer4_ml_judgment)
    g.add_node("finalize", finalize_judgment)
    g.add_edge(START,      "layer1")
    g.add_edge("layer1",   "layer2")
    g.add_edge("layer2",   "layer3")
    g.add_edge("layer3",   "layer4")
    g.add_edge("layer4",   "finalize")
    g.add_edge("finalize", END)
    return g.compile()

fraud_detector = build_fraud_detector()


# ===== 外部から呼び出す関数 =====
async def run_fraud_agent(question: str, session_id: str) -> str:
    """Supervisorから呼び出されるエントリポイント"""
    return f"[不正検知エージェント] 「{question}」を分析します。取引IDを指定してAPIから呼び出してください。"

