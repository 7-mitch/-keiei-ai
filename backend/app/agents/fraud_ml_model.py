"""
#93 不正検知MLモデル
scikit-learnでPrecision/Recallを最適化した分類モデル
実際の取引データで学習・改善できる
"""
import numpy as np
import joblib
import os
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import (
    precision_score, recall_score, f1_score,
    classification_report, confusion_matrix
)
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline

MODEL_PATH = "app/agents/fraud_model.pkl"
SCALER_PATH = "app/agents/fraud_scaler.pkl"

# ===== 特徴量エンジニアリング =====
def extract_features(transactions: list[dict]) -> np.ndarray:
    """
    取引データから特徴量を抽出する

    特徴量:
    - amount:           取引金額
    - is_debit:         出金フラグ
    - hour:             取引時刻（深夜リスク）
    - rule_score:       ルールベーススコア
    - pattern_score:    パターン認識スコア
    - amount_log:       金額の対数（外れ値対策）
    - is_night:         深夜（0〜5時）フラグ
    - is_large_amount:  高額（100万円以上）フラグ
    """
    features = []

    for tx in transactions:
        from datetime import datetime
        try:
            dt   = datetime.fromisoformat(str(tx.get("created_at", "")))
            hour = dt.hour
        except Exception:
            hour = 12

        amount = float(tx.get("amount", 0))

        feature_vector = [
            amount,
            1 if tx.get("transaction_type") == "debit" else 0,
            hour,
            float(tx.get("rule_score", 0)),
            float(tx.get("pattern_score", 0)),
            np.log1p(amount),           # 対数変換
            1 if 0 <= hour < 5 else 0,  # 深夜フラグ
            1 if amount >= 1_000_000 else 0,  # 高額フラグ
        ]
        features.append(feature_vector)

    return np.array(features)


# ===== モデル学習 =====
def train_model(transactions: list[dict], labels: list[int]) -> dict:
    """
    不正検知モデルを学習する

    Args:
        transactions: 取引データのリスト
        labels:       正解ラベル（1=不正, 0=正常）

    Returns:
        学習結果（Precision/Recall/F1スコア）
    """
    X = extract_features(transactions)
    y = np.array(labels)

    if len(X) < 10:
        return {"error": "学習データが不足しています（最低10件必要）"}

    # 学習・テストデータに分割
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    # モデル候補
    models = {
        "random_forest": RandomForestClassifier(
            n_estimators   = 100,
            max_depth      = 5,
            class_weight   = "balanced",  # 不均衡データ対策
            random_state   = 42,
        ),
        "gradient_boosting": GradientBoostingClassifier(
            n_estimators   = 100,
            max_depth      = 3,
            random_state   = 42,
        ),
        "logistic_regression": Pipeline([
            ("scaler", StandardScaler()),
            ("clf", LogisticRegression(
                class_weight = "balanced",
                random_state = 42,
                max_iter     = 1000,
            )),
        ]),
    }

    # 最良モデルを選択（F1スコアで比較）
    best_model      = None
    best_f1         = 0
    best_model_name = ""

    for name, model in models.items():
        scores = cross_val_score(model, X_train, y_train, cv=3, scoring="f1")
        mean_f1 = scores.mean()
        print(f"  {name}: F1={mean_f1:.3f}")

        if mean_f1 > best_f1:
            best_f1         = mean_f1
            best_model      = model
            best_model_name = name

    # 最良モデルで学習
    best_model.fit(X_train, y_train)
    y_pred = best_model.predict(X_test)

    # Precision/Recall評価
    precision = precision_score(y_test, y_pred, zero_division=0)
    recall    = recall_score(y_test, y_pred, zero_division=0)
    f1        = f1_score(y_test, y_pred, zero_division=0)

    print(f"\n📊 最良モデル: {best_model_name}")
    print(f"  Precision: {precision:.3f}")
    print(f"  Recall:    {recall:.3f}")
    print(f"  F1 Score:  {f1:.3f}")
    print(classification_report(y_test, y_pred))

    # モデルを保存
    joblib.dump(best_model, MODEL_PATH)
    print(f"✅ モデルを保存: {MODEL_PATH}")

    return {
        "model_name": best_model_name,
        "precision":  precision,
        "recall":     recall,
        "f1_score":   f1,
        "train_size": len(X_train),
        "test_size":  len(X_test),
        "confusion_matrix": confusion_matrix(y_test, y_pred).tolist(),
    }


# ===== DBからデータを取得して学習 =====
async def train_from_db() -> dict:
    """
    PostgreSQLの実際の取引データでモデルを学習する
    """
    from app.db.connection import get_conn

    async with get_conn() as conn:
        rows = await conn.fetch("""
            SELECT
                amount,
                transaction_type,
                created_at,
                is_flagged,
                COALESCE(risk_score, 0) AS rule_score
            FROM transactions
            ORDER BY created_at DESC
            LIMIT 10000
        """)

    if len(rows) < 10:
        return {"error": "学習データが不足しています"}

    transactions = [dict(r) for r in rows]
    labels       = [1 if r["is_flagged"] else 0 for r in rows]

    fraud_count  = sum(labels)
    normal_count = len(labels) - fraud_count
    print(f"📊 学習データ: 正常={normal_count}件, 不正={fraud_count}件")

    return train_model(transactions, labels)


# ===== モデル評価 =====
def evaluate_model() -> dict:
    """
    保存済みモデルの情報を返す
    """
    if not os.path.exists(MODEL_PATH):
        return {"status": "未学習", "model_path": MODEL_PATH}

    model = joblib.load(MODEL_PATH)
    return {
        "status":     "学習済み",
        "model_path": MODEL_PATH,
        "model_type": type(model).__name__,
    }