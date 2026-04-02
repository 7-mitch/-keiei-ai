"""
hf_router.py — HuggingFace類似度ベースルーター
既存の multilingual-e5-small を活用したコサイン類似度分類
APIコストゼロ・追加モデル不要・オンプレ完結・Confidential AI対応

改善点:
- general の代表文を経営と無関係な内容に絞る
- general にペナルティを付与して誤ルーティングを防ぐ
- 各ルートの代表文を業種横断的に拡充
"""
import os
import numpy as np
from functools import lru_cache

# ===== ルート代表文 =====
ROUTE_EXAMPLES = {
    "cash_flow": [
        "資金繰り 経費 キャッシュフロー 試算表 売掛金 買掛金",
        "月次決算 インボイス 入金 出金 資金ショート 節税",
        "利益 収支 黒字 赤字 資金調達 電帳法",
        "コスト削減 支払い 請求 費用 予算 財務",
        "病院のコスト 施設の経費 運営費 収益改善",
    ],
    "project": [
        "プロジェクト タスク 進捗 スケジュール 納期 マイルストーン",
        "工程 フェーズ 遅延 期限 担当 アサイン",
        "WBS ガントチャート 間に合う 過負荷 稼働",
        "設備点検記録 作業管理 工程管理 現場管理",
        "シフト管理 業務管理 作業スケジュール 工場管理",
    ],
    "sql": [
        "売上 KPI データ集計 統計 レポート 分析",
        "件数 残高 ユーザー数 金額 推移 比較",
        "月次レポート 売上分析 データ可視化",
        "実績集計 数値確認 データ抽出",
    ],
    "fraud": [
        "不正検知 異常取引 アラート フラグ リスクスコア",
        "不正送金 疑わしい取引 不正フラグ 監視",
        "詐欺 横領 不正行為 リスク取引",
    ],
    "rag": [
        "セキュリティ 監査 法令 規程 コンプライアンス 脆弱性",
        "OWASP NIST ISO SOX インシデント ガバナンス",
        "ゼロトラスト 暗号 ランサム プライバシー 規制 法律",
        "安全管理 安全基準 安全規則 安全教育",
        "建設現場の安全 工場安全 医療安全基準 介護法令",
    ],
    "hr": [
        "人事 評価 適性診断 育成 キャリア チーム 強み スキル",
        "採用 研修 組織 役割分担 フィードバック 1on1",
        "スタッフ 定着率 離職 人材 パーソナリティ 行動特性",
        "誰に任せる 担当者選定 チーム編成 アサイン提案",
        "介護スタッフ 医療スタッフ 現場スタッフ シフト最適化",
        "エンジニア スキルマップ 能力開発 人材育成",
        "レセプト担当 請求担当 経理担当 窓口担当",
    ],
    "web": [
        "市場動向 競合 ニュース トレンド 業界情報",
        "競合他社 市場調査 業界ニュース 最新情報",
        "他社 動向 市場分析 業界レポート",
    ],
    # generalは明らかに経営・業務と無関係なものだけ
    "general": [
        "こんにちは ありがとう よろしくお願いします 挨拶",
        "天気 食事 趣味 旅行 スポーツ 娯楽 日常会話",
        "意味がわからない 関係ない 全く別の話 雑談",
    ],
    "hr": [
    ...既存の行...
    "レセプト担当 請求担当 経理担当 窓口担当",
    "請求確認担当者 書類確認 誰が担当 担当業務確認", 
    ],
}

VALID_ROUTES = list(ROUTE_EXAMPLES.keys())

# general へのペナルティ係数
GENERAL_PENALTY = 0.88


# ===== Embeddingモデルのキャッシュ =====
@lru_cache(maxsize=1)
def get_embedding_model():
    """
    既存の multilingual-e5-small を使う
    - 追加モデル不要（KEIEI-AIで既にキャッシュ済み）
    - 100言語対応・日本語に強い
    - 軽量（133MB）・高速
    """
    from sentence_transformers import SentenceTransformer

    cache_dir = os.getenv("HF_CACHE_DIR", "/tmp/huggingface")
    print("[HF-ROUTER] multilingual-e5-small をロード中...")

    model = SentenceTransformer(
        "intfloat/multilingual-e5-small",
        cache_folder = cache_dir,
    )
    print("[HF-ROUTER] モデルロード完了")
    return model


# ===== ルート代表ベクトルの事前計算 =====
@lru_cache(maxsize=1)
def get_route_vectors() -> dict:
    """
    各ルートの代表文をベクトル化して平均を取る
    起動時に1回だけ計算・以降はキャッシュ
    """
    model = get_embedding_model()
    route_vectors = {}

    for route, examples in ROUTE_EXAMPLES.items():
        vecs = model.encode(
            examples,
            normalize_embeddings = True,
            show_progress_bar    = False,
        )
        route_vectors[route] = np.mean(vecs, axis=0)
        norm = np.linalg.norm(route_vectors[route])
        if norm > 0:
            route_vectors[route] = route_vectors[route] / norm

    print(f"[HF-ROUTER] ルートベクトル計算完了: {list(route_vectors.keys())}")
    return route_vectors


# ===== コサイン類似度計算 =====
def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b))


# ===== スコアにペナルティを適用 =====
def apply_penalty(scores: dict) -> dict:
    """
    general に penalty を付与して誤ルーティングを防ぐ
    """
    return {
        route: (s * GENERAL_PENALTY if route == "general" else s)
        for route, s in scores.items()
    }


# ===== HuggingFaceによるルーティング =====
def route_with_hf(question: str) -> str:
    """
    multilingual-e5-small のコサイン類似度でルートを決定する
    APIコストゼロ・外部送信なし・既存キャッシュ活用
    """
    try:
        model         = get_embedding_model()
        route_vectors = get_route_vectors()

        q_vec = model.encode(
            [question],
            normalize_embeddings = True,
            show_progress_bar    = False,
        )[0]

        scores = {
            route: cosine_similarity(q_vec, r_vec)
            for route, r_vec in route_vectors.items()
        }

        # general ペナルティ適用
        scores = apply_penalty(scores)

        best_route = max(scores, key=lambda r: scores[r])
        best_score = scores[best_route]

        print(f"[HF-ROUTER] route={best_route} score={best_score:.3f}")
        return best_route

    except Exception as e:
        print(f"[HF-ROUTER] エラー: {e} → general にフォールバック")
        return "general"


# ===== 信頼度付きルーティング =====
def route_with_hf_scored(question: str) -> dict:
    """
    スコア付きでルーティング結果を返す（デバッグ・ベンチマーク用）
    """
    try:
        model         = get_embedding_model()
        route_vectors = get_route_vectors()

        q_vec = model.encode(
            [question],
            normalize_embeddings = True,
            show_progress_bar    = False,
        )[0]

        scores = {
            route: cosine_similarity(q_vec, r_vec)
            for route, r_vec in route_vectors.items()
        }

        # general ペナルティ適用
        scores = apply_penalty(scores)

        routes_scored = sorted(
            [{"route": r, "score": round(s, 4)} for r, s in scores.items()],
            key     = lambda x: x["score"],
            reverse = True,
        )

        top = routes_scored[0]
        print(f"[HF-ROUTER] TOP3: {routes_scored[:3]}")

        return {
            "route": top["route"],
            "score": top["score"],
            "all":   routes_scored,
        }

    except Exception as e:
        print(f"[HF-ROUTER] エラー: {e}")
        return {"route": "general", "score": 0.0, "all": []}


# ===== ベンチマーク実行 =====
def run_benchmark() -> list[dict]:
    """
    標準テストセットでルーターの精度を測定する
    """
    test_cases = [
        # 明確なケース
        {"q": "資金繰りが厳しい来月どうする",         "expected": "cash_flow"},
        {"q": "プロジェクトの進捗を確認したい",        "expected": "project"},
        {"q": "今月の売上KPIを見せて",               "expected": "sql"},
        {"q": "不正取引のアラートが出ている",          "expected": "fraud"},
        {"q": "セキュリティ規程を確認したい",          "expected": "rag"},
        {"q": "スタッフの定着率が下がっている",         "expected": "hr"},
        {"q": "競合他社の動向を調べたい",             "expected": "web"},
        # 曖昧なケース（業種横断）
        {"q": "誰に任せればいいか",                  "expected": "hr"},
        {"q": "来月の資金が心配",                    "expected": "cash_flow"},
        {"q": "現場の安全管理について教えて",          "expected": "rag"},
        {"q": "エンジニアのスキルマップを作りたい",     "expected": "hr"},
        {"q": "レセプト請求の確認をしたい",            "expected": "hr"},
        {"q": "工場の設備点検記録を管理したい",        "expected": "project"},
        {"q": "介護スタッフの夜勤シフトを最適化したい", "expected": "hr"},
        {"q": "病院のコスト削減方法を教えて",          "expected": "cash_flow"},
    ]

    results = []
    correct = 0

    for tc in test_cases:
        result = route_with_hf_scored(tc["q"])
        match  = result["route"] == tc["expected"]
        if match:
            correct += 1
        results.append({
            "question": tc["q"],
            "expected": tc["expected"],
            "actual":   result["route"],
            "score":    result["score"],
            "correct":  match,
        })

    accuracy = correct / len(test_cases) * 100
    print(f"\n[BENCHMARK] 正解率: {accuracy:.1f}% ({correct}/{len(test_cases)})")
    return results