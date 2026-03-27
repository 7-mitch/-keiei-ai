"""
AIGIS 336監査項目 → KEIEI-AI ChromaDB投入スクリプト v2
英日併記対応版 - 検索精度向上
使用方法: python ingest_aigis_to_chromadb_v2.py
"""
import re
import json
import chromadb
from chromadb.utils import embedding_functions

# ===== 設定 =====
HTML_PATH   = "AIGIS_Portal_v4_最有力.html"
CHROMA_PATH = "./vector_store/aigis"
COLLECTION  = "aigis_audit_items"

# ===== カテゴリ英訳マッピング =====
CATEGORY_EN = {
    "AI技術・モデルセキュリティ":        "AI Technology & Model Security",
    "AIエージェント・自律システム":       "AI Agent & Autonomous Systems",
    "AI倫理・社会・法的リスク":           "AI Ethics, Social & Legal Risk",
    "CFE・不正検知・法執行準備":          "CFE / Fraud Detection & Law Enforcement",
    "J-SOX・内部統制・ガバナンス":        "J-SOX / Internal Control & Governance",
    "MLOps・開発プロセスセキュリティ":    "MLOps & Development Process Security",
    "インフラ・ネットワークセキュリティ": "Infrastructure & Network Security",
    "サプライチェーン・ベンダーマネジメント": "Supply Chain & Vendor Management",
    "データライフサイクル・プライバシー": "Data Lifecycle & Privacy",
    "量子・PQC移行管理":                  "Quantum & PQC Migration Management",
}

# ===== 項目名英訳マッピング（主要項目） =====
ITEM_EN = {
    "直接的プロンプトインジェクション":       "Direct Prompt Injection",
    "間接的プロンプトインジェクション":       "Indirect Prompt Injection",
    "ジェイルブレイク（脱獄）試行の検知":    "Jailbreak Attempt Detection",
    "システムプロンプトの漏洩防止":           "System Prompt Leakage Prevention",
    "トークンスマグリング（難読化回避）":     "Token Smuggling / Obfuscation Bypass",
    "モデルインバージョン（学習データ復元）": "Model Inversion Attack",
    "メンバーシップ推論（学習データ特定）":   "Membership Inference Attack",
    "モデル抽出・蒸留攻撃":                  "Model Extraction / Distillation Attack",
    "敵対的サンプル（Adversarial Examples）": "Adversarial Examples",
    "リワードハッキング（報酬関数の悪用）":   "Reward Hacking",
    "過学習による機密情報出力":               "Overfitting / Confidential Data Leakage",
    "出力フィルタリングのバイパス":           "Output Filter Bypass",
    "プロンプト注入によるRAG汚染":            "RAG Poisoning via Prompt Injection",
    "難読化プロンプトの検知（Base64等）":     "Obfuscated Prompt Detection",
    "マルチモーダル入力（画像/音声）による攻撃": "Multimodal Input Attack",
    "プラグイン/ツール呼び出しの権限昇格":   "Plugin / Tool Permission Escalation",
    "データポイズニング攻撃":                 "Data Poisoning Attack",
    "サプライチェーン攻撃（モデル・ライブラリ汚染）": "Supply Chain Attack",
    "ランサムウェア対策":                     "Ransomware Countermeasures",
    "内部不正の検知":                         "Insider Threat Detection",
    "不正のトライアングル分析":               "Fraud Triangle Analysis",
    "ゼロトラストアーキテクチャ":             "Zero Trust Architecture",
    "GDPR・個人情報保護法対応":               "GDPR / Personal Information Protection",
    "EU AI Act準拠":                          "EU AI Act Compliance",
    "差分プライバシー実装":                   "Differential Privacy Implementation",
    "連合学習のセキュリティ":                 "Federated Learning Security",
    "量子コンピュータによる暗号解読リスク":   "Quantum Computing Cryptographic Risk",
    "PQC（耐量子暗号）移行計画":              "Post-Quantum Cryptography Migration",
}

# ===== 1. HTMLからデータ抽出 =====
def extract_audit_items(html_path: str) -> list[dict]:
    with open(html_path, "r", encoding="utf-8") as f:
        content = f.read()
    match = re.search(r"const AUDIT=(\[[\s\S]*?\]);", content)
    if not match:
        raise ValueError("AUDIT配列が見つかりません")
    items = json.loads(match.group(1))
    print(f"抽出完了: {len(items)}件")
    return items

# ===== 2. 英日併記ドキュメント生成 =====
def build_document(item: dict) -> str:
    category_ja = item.get("大分類", "")
    category_en = CATEGORY_EN.get(category_ja, "")
    name_ja     = item.get("項目名", "")
    name_en     = ITEM_EN.get(name_ja, "")

    # 英訳がある場合は併記、ない場合は日本語のみ
    category_str = f"{category_ja} / {category_en}" if category_en else category_ja
    name_str     = f"{name_ja} ({name_en})" if name_en else name_ja

    return f"""
カテゴリ / Category: {category_str}
項目名 / Item: {name_str}
チェック内容: {item.get('チェック内容', '')}
準拠規格 / Standard: {item.get('準拠規格', '')}
監査手段 / Audit Method: {item.get('監査手段・統計手法', '')}
エビデンス例 / Evidence: {item.get('エビデンス例', '')}
区分 / Classification: {item.get('J-SOX/CFE区分', '')}
優先度 / Priority: {item.get('優先度', '').replace('🔴 ', 'Critical-').replace('🟡 ', 'High-')}
初期リスク / Initial Risk: {item.get('初期リスク(AxB)', '')}
残存リスク / Residual Risk: {item.get('残存リスク(CxB)', '')}
""".strip()

# ===== 3. ChromaDBへの投入 =====
def ingest_to_chromadb(items: list[dict]):
    ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="intfloat/multilingual-e5-small"
    )
    client = chromadb.PersistentClient(path=CHROMA_PATH)

    try:
        client.delete_collection(COLLECTION)
        print(f"既存コレクション削除: {COLLECTION}")
    except Exception:
        pass

    collection = client.create_collection(
        name=COLLECTION,
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"},
    )

    batch_size = 50
    for i in range(0, len(items), batch_size):
        batch = items[i:i + batch_size]
        collection.add(
            ids       = [f"aigis_{i + j}" for j, _ in enumerate(batch)],
            documents = [build_document(item) for item in batch],
            metadatas = [
                {
                    "category_ja":  item.get("大分類", ""),
                    "category_en":  CATEGORY_EN.get(item.get("大分類", ""), ""),
                    "name_ja":      item.get("項目名", ""),
                    "name_en":      ITEM_EN.get(item.get("項目名", ""), ""),
                    "priority":     item.get("優先度", "").replace("🔴 ", "Critical-").replace("🟡 ", "High-"),
                    "risk_score":   str(item.get("初期リスク(AxB)", 0)),
                    "standard":     item.get("準拠規格", ""),
                    "classification": item.get("J-SOX/CFE区分", ""),
                }
                for item in batch
            ],
        )
        print(f"投入済み: {min(i + batch_size, len(items))}/{len(items)}件")

    print(f"\n完了: {collection.count()}件をChromaDBに投入しました")
    return collection

# ===== 4. 検索テスト（英日両方） =====
def test_search():
    ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="intfloat/multilingual-e5-small"
    )
    client     = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = client.get_collection(COLLECTION, embedding_function=ef)

    print("\n=== 検索テスト ===")
    queries = [
        "プロンプトインジェクション対策",       # 日本語
        "prompt injection countermeasures",       # 英語
        "model inversion attack prevention",      # 英語
        "サプライチェーンセキュリティ評価",       # 日本語
        "fraud detection AI risk",                # 英語
    ]

    for query in queries:
        results = collection.query(query_texts=[query], n_results=2)
        print(f"\nクエリ: {query}")
        for meta in results["metadatas"][0]:
            name = meta["name_en"] if meta.get("name_en") else meta["name_ja"]
            print(f"  → {meta['name_ja']} / {name} [{meta['priority']}]")

# ===== メイン =====
if __name__ == "__main__":
    items = extract_audit_items(HTML_PATH)

    # サンプル確認
    print("\n=== サンプル（英日併記）===")
    print(build_document(items[0]))
    print(f"\n文字数: {len(build_document(items[0]))}文字")

    # 投入
    ingest_to_chromadb(items)

    # 検索テスト
    test_search()
