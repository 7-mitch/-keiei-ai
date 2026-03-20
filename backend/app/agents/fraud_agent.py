"""
#93 多層不正検知エージェント
Layer 1: ルールベース判定
Layer 2: パターン認識（FAISS）
Layer 3: LLM判定（Claude）
Layer 4: ML判定（scikit-learn）
"""
from datetime import datetime, timezone
from typing import TypedDict, Literal
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END, START
from pydantic import BaseModel
from app.core.config import settings
from app.db.connection import get_conn
from app.db.audit import record_audit
import json

# ===== State定義 =====
class FraudDetectionState(TypedDict):
    transaction_id:   int
    account_id:       int
    amount:           float
    transaction_type: str
    description:      str
    created_at:       str

    # 各レイヤーの結果
    rule_result:      dict   # Layer1
    pattern_result:   dict   # Layer2
    llm_result:       dict   # Layer3
    ml_result:        dict   # Layer4

    # 最終判定
    is_fraud:         bool
    risk_score:       float
    severity:         str    # 'low'|'medium'|'high'|'critical'
    reasoning:        str
    session_id:       str

# ===== LLM =====
llm = ChatAnthropic(
    model       = "claude-sonnet-4-20250514",
    temperature = 0,
    api_key     = settings.anthropic_api_key,
)

# ===== Layer 1: ルールベース判定 =====
def layer1_rule_based(state: FraudDetectionState) -> dict:
    """
    ルールベースで即座に判定する
    - 高額取引（100万円以上）
    - 深夜取引（0〜5時）
    - マイナス残高リスク
    """
    amount      = state["amount"]
    description = state.get("description", "")
    flags       = []
    score       = 0.0

    # ルール1: 高額取引
    if amount >= 1_000_000:
        flags.append("高額取引（100万円以上）")
        score += 0.4
    elif amount >= 500_000:
        flags.append("中額取引（50万円以上）")
        score += 0.2

    # ルール2: 深夜取引
    try:
        dt   = datetime.fromisoformat(state["created_at"])
        hour = dt.hour
        if 0 <= hour < 5:
            flags.append(f"深夜取引（{hour}時台）")
            score += 0.3
    except Exception:
        pass

    # ルール3: 疑わしいキーワード
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
    print(f"🔍 Layer1 ルールベース: {result}")
    return {"rule_result": result}


# ===== Layer 2: パターン認識 =====
async def layer2_pattern_recognition(state: FraudDetectionState) -> dict:
    """
    過去の不正取引パターンとの類似度を検索する
    FAISSベクトル検索で類似パターンを発見
    """
    try:
        from sentence_transformers import SentenceTransformer
        import faiss
        import numpy as np

        # テキスト特徴量を作成
        tx_text = (
            f"金額:{state['amount']} "
            f"種別:{state['transaction_type']} "
            f"説明:{state.get('description', '')}"
        )

        # 過去の不正取引をDBから取得
        async with get_conn() as conn:
            past_frauds = await conn.fetch("""
                SELECT amount, transaction_type, description, flag_reason
                FROM transactions
                WHERE is_flagged = true
                LIMIT 100
            """)

        if not past_frauds:
            result = {
                "similar_patterns": [],
                "max_similarity":   0.0,
                "score":            0.0,
            }
            print(f"🔍 Layer2 パターン認識: 過去の不正データなし")
            return {"pattern_result": result}

        # Embeddingモデルでベクトル化
        model = SentenceTransformer(
            "intfloat/multilingual-e5-large",
            cache_folder="C:\\Users\\Owner\\.cache\\huggingface"
        )

        # 過去の不正取引をベクトル化
        past_texts = [
            f"金額:{r['amount']} 種別:{r['transaction_type']} 説明:{r.get('description','')}"
            for r in past_frauds
        ]
        past_vectors = model.encode(past_texts, normalize_embeddings=True)
        query_vector = model.encode([tx_text], normalize_embeddings=True)

        # FAISSで類似度検索
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

        result = {
            "similar_patterns": similar,
            "max_similarity":   max_sim,
            "score":            score,
        }
        print(f"🔍 Layer2 パターン認識: 類似度={max_sim:.3f}")
        return {"pattern_result": result}

    except Exception as e:
        print(f"⚠️ Layer2 エラー: {e}")
        return {"pattern_result": {"similar_patterns": [], "score": 0.0, "error": str(e)}}

# ===== Layer 3: LLM判定 =====
async def layer3_llm_judgment(state: FraudDetectionState) -> dict:
    """Layer3: LLM判定（クレジット復旧後に本実装）"""
    rule_score    = state["rule_result"].get("score", 0)
    pattern_score = state["pattern_result"].get("score", 0)
    combined      = (rule_score + pattern_score) / 2

    is_fraud   = combined >= 0.4
    risk_score = combined
    severity   = "critical" if combined >= 0.8 else \
                 "high"     if combined >= 0.6 else \
                 "medium"   if combined >= 0.4 else "low"

    result = {
        "is_fraud":   is_fraud,
        "risk_score": risk_score,
        "severity":   severity,
        "reasoning":  f"ルールスコア:{rule_score:.2f} パターンスコア:{pattern_score:.2f}（LLM判定は一時スキップ）",
    }
    print(f"🤖 Layer3 スキップ: score={risk_score:.2f}")
    return {"llm_result": result}

# ===== Layer 4: ML判定 =====
def layer4_ml_judgment(state: FraudDetectionState) -> dict:
    """
    scikit-learnの学習済みモデルで判定する
    モデルがない場合はルールベーススコアで代替
    """
    try:
        import joblib
        import numpy as np
        import os

        model_path = "app/agents/fraud_model.pkl"

        if os.path.exists(model_path):
            model    = joblib.load(model_path)
            features = np.array([[
                state["amount"],
                1 if state["transaction_type"] == "debit" else 0,
                state["rule_result"].get("score", 0),
                state["pattern_result"].get("max_similarity", 0),
            ]])
            proba  = model.predict_proba(features)[0][1]
            result = {
                "score":      float(proba),
                "model_used": True,
            }
        else:
            # モデルがない場合はルール+パターンスコアの平均
            rule_score    = state["rule_result"].get("score", 0)
            pattern_score = state["pattern_result"].get("score", 0)
            score         = (rule_score + pattern_score) / 2
            result        = {
                "score":      score,
                "model_used": False,
                "note":       "学習済みモデルなし・ルールスコアで代替",
            }

        print(f"🧠 Layer4 ML判定: score={result['score']:.3f}")
        return {"ml_result": result}

    except Exception as e:
        print(f"⚠️ Layer4 エラー: {e}")
        return {"ml_result": {"score": 0.0, "error": str(e)}}


# ===== 最終判定・DB保存 =====
async def finalize_judgment(state: FraudDetectionState) -> dict:
    """
    4つのレイヤーの結果を統合して最終判定を下す
    DBに保存・監査ログを記録する
    """
    rule_score    = state["rule_result"].get("score", 0)
    pattern_score = state["pattern_result"].get("score", 0)
    llm_result    = state["llm_result"]
    ml_score      = state["ml_result"].get("score", 0)

    # 重み付き平均でリスクスコアを計算
    # LLM判定を最も重視（金融機関の実務に合わせた重み）
    final_score = (
        rule_score    * 0.20 +
        pattern_score * 0.20 +
        llm_result.get("risk_score", 0) * 0.40 +
        ml_score      * 0.20
    )

    is_fraud = final_score >= 0.5 or llm_result.get("is_fraud", False)
    severity = llm_result.get("severity", "low")

    # severityをfinal_scoreで補正
    if final_score >= 0.8:
        severity = "critical"
    elif final_score >= 0.6:
        severity = "high"
    elif final_score >= 0.4:
        severity = "medium"

    # DBに不正フラグを記録
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

    # 監査ログ（手動テスト時はスキップ）
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
        print(f"📝 監査ログスキップ（手動テスト）: is_fraud={is_fraud} score={final_score:.2f}")

    print(f"✅ 最終判定: is_fraud={is_fraud} score={final_score:.2f} severity={severity}")

    return {
        "is_fraud":   is_fraud,
        "risk_score": final_score,
        "severity":   severity,
        "reasoning":  llm_result.get("reasoning", ""),
    }


# ===== グラフ構築 =====
def build_fraud_detector():
    g = StateGraph(FraudDetectionState)

    g.add_node("layer1", layer1_rule_based)
    g.add_node("layer2", layer2_pattern_recognition)
    g.add_node("layer3", layer3_llm_judgment)
    g.add_node("layer4", layer4_ml_judgment)
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