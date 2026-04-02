"""
#96 審査書類RAGエージェント（CRAG）+ AIGIS 336監査項目統合版
審査規程・社内文書 + AIGIS セキュリティ監査項目をベクトル化して検索する
業界別docs_data対応版・日本語パス対応
"""
import os
from langchain_community.document_loaders import TextLoader, DirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
import chromadb
from chromadb.utils import embedding_functions

# ===== 設定 =====
DOCS_DIR         = "docs_data"
VECTOR_DIR       = "vector_store"
AIGIS_CHROMA_DIR = "vector_store/aigis"
AIGIS_COLLECTION = "aigis_audit_items"
EMBED_MODEL      = "intfloat/multilingual-e5-large"
EMBED_MODEL_SM   = "intfloat/multilingual-e5-small"
CACHE_DIR        = os.getenv("HF_CACHE_DIR", "/tmp/huggingface")

# ===== 業界別キーワードマップ =====
INDUSTRY_KEYWORDS = {
    "介護": [
        "介護", "ケア", "ケアプラン", "要介護", "ヒヤリハット",
        "バイタル", "排泄", "食事摂取", "デイサービス", "訪問介護",
        "ショートステイ", "介護記録", "申し送り", "看取り",
    ],
    "医療": [
        "カルテ", "診断", "投薬", "処方", "手術", "入院", "退院",
        "患者", "医師", "看護", "病院", "クリニック", "検査",
        "バイタル", "血圧", "体温", "診療",
    ],
    "建設": [
        "建設", "建築", "施工", "工事", "設計", "点検", "修繕",
        "建築基準法", "安全管理", "現場", "足場", "コンクリート",
        "構造", "耐震", "不動産",
    ],
    "製造": [
        "製造", "品質", "ISO", "不良", "検査", "ロット", "トレーサビリティ",
        "工程", "設備", "4M", "是正", "カーボンニュートラル",
        "サプライチェーン", "生産", "在庫",
    ],
    "法律": [
        "契約", "法律", "規約", "訴訟", "判例", "コンプライアンス",
        "規制", "法令", "条例", "リーガル", "弁護士", "裁判",
        "損害賠償", "知的財産", "著作権",
    ],
}

# ===== 業界名 → 英語フォルダ名マップ（日本語パス問題を回避）=====
INDUSTRY_DIR_MAP = {
    "介護":  "care",
    "医療":  "medical",
    "建設":  "construction",
    "製造":  "manufacturing",
    "法律":  "legal",
}


# ===== 業界別フォルダパス取得 =====
def _get_vector_dir(industry: str | None) -> str:
    if industry is None:
        return VECTOR_DIR
    eng = INDUSTRY_DIR_MAP.get(industry, industry)
    return os.path.join(VECTOR_DIR, eng)

def _get_docs_dir(industry: str | None) -> str:
    if industry is None:
        return DOCS_DIR
    return os.path.join(DOCS_DIR, industry)


# ===== 業界判定 =====
def detect_industry(question: str) -> str | None:
    """質問内容から業界を判定する"""
    q = question.lower()
    for industry, keywords in INDUSTRY_KEYWORDS.items():
        if any(kw.lower() in q for kw in keywords):
            print(f" 業界判定: {industry}")
            return industry
    return None


# ===== Embeddingモデル =====
def get_embeddings():
    return HuggingFaceEmbeddings(
        model_name    = EMBED_MODEL,
        cache_folder  = CACHE_DIR,
        model_kwargs  = {"device": "cpu"},
        encode_kwargs = {"normalize_embeddings": True},
    )


# ===== AIGIS ChromaDB接続 =====
def get_aigis_collection():
    """AIGISの336監査項目ChromaDBを取得"""
    try:
        ef     = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=EMBED_MODEL_SM
        )
        client = chromadb.PersistentClient(path=AIGIS_CHROMA_DIR)
        return client.get_collection(AIGIS_COLLECTION, embedding_function=ef)
    except Exception as e:
        print(f" AIGIS ChromaDB接続エラー: {e}")
        return None


# ===== AIGIS監査項目検索 =====
def search_aigis(query: str, k: int = 3) -> list[dict]:
    """AIGISの336監査項目から検索"""
    try:
        collection = get_aigis_collection()
        if collection is None:
            return []

        results = collection.query(query_texts=[query], n_results=k)
        docs = []
        for doc, meta, distance in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            name    = meta.get("name_ja", "")
            name_en = meta.get("name_en", "")
            label   = f"{name} / {name_en}" if name_en else name

            docs.append({
                "content":  doc,
                "source":   f"AIGIS監査項目: {label}",
                "score":    float(distance),
                "category": meta.get("category_ja", ""),
                "priority": meta.get("priority", ""),
                "standard": meta.get("standard", ""),
            })
        return docs

    except Exception as e:
        print(f" AIGIS検索エラー: {e}")
        return []


# ===== 業界別ベクトルストア構築 =====
def build_vector_store(industry: str | None = None) -> FAISS:
    """
    業界指定あり → その業界フォルダのみ読み込む
    業界指定なし → docs_data全体を読み込む
    """
    target_dir = _get_docs_dir(industry)
    vector_dir = _get_vector_dir(industry)

    if industry and not os.path.exists(target_dir):
        print(f" 業界フォルダなし: {target_dir} → 全体検索にフォールバック")
        return build_vector_store(None)

    print(f" ドキュメントを読み込み中: {target_dir}")
    loader = DirectoryLoader(
        target_dir,
        glob          = "**/*.txt",
        loader_cls    = TextLoader,
        loader_kwargs = {"encoding": "utf-8"},
    )
    documents = loader.load()
    print(f" {len(documents)}件のドキュメントを読み込みました")

    if not documents:
        print(f" ドキュメントなし: {target_dir}")
        raise ValueError(f"ドキュメントが見つかりません: {target_dir}")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size    = 500,
        chunk_overlap = 50,
    )
    chunks = splitter.split_documents(documents)
    print(f" {len(chunks)}チャンクに分割しました")

    embeddings   = get_embeddings()
    vector_store = FAISS.from_documents(chunks, embeddings)

    os.makedirs(vector_dir, exist_ok=True)
    vector_store.save_local(vector_dir)
    print(f" ベクトルストアを保存しました: {vector_dir}")
    return vector_store


def load_vector_store(industry: str | None = None) -> FAISS | None:
    vector_dir = _get_vector_dir(industry)
    if os.path.exists(vector_dir):
        embeddings = get_embeddings()
        return FAISS.load_local(
            vector_dir,
            embeddings,
            allow_dangerous_deserialization=True,
        )
    return None


def get_vector_store(industry: str | None = None) -> FAISS:
    store = load_vector_store(industry)
    if store is None:
        store = build_vector_store(industry)
    return store


# ===== FAISS検索（業界対応） =====
def search_documents(query: str, k: int = 3, industry: str | None = None) -> list[dict]:
    try:
        store   = get_vector_store(industry)
        results = store.similarity_search_with_score(query, k=k)
        docs = []
        for doc, score in results:
            source = doc.metadata.get("source", "不明")
            if industry:
                source = f"[{industry}] {source}"
            docs.append({
                "content":  doc.page_content,
                "source":   source,
                "score":    float(score),
                "category": industry or "",
                "priority": "",
                "standard": "",
            })
        return docs
    except Exception as e:
        print(f" RAG検索エラー: {e}")
        return []


# ===== CRAG評価 =====
def evaluate_relevance(query: str, docs: list[dict]) -> str:
    if not docs:
        return "POOR"
    best_score = docs[0]["score"]
    if best_score < 0.3:
        return "GOOD"
    elif best_score < 0.7:
        return "AMBIGUOUS"
    else:
        return "POOR"


# ===== クエリ判定：AIGISが必要か =====
def is_security_query(question: str) -> bool:
    keywords = [
        "セキュリティ", "security", "監査", "audit",
        "攻撃", "attack", "リスク", "risk", "脆弱性", "vulnerability",
        "不正", "fraud", "プロンプト", "prompt", "injection",
        "OWASP", "NIST", "ISO", "SOX", "CFE",
        "暗号", "crypto", "ランサム", "ransomware",
        "サプライチェーン", "supply chain", "ゼロトラスト", "zero trust",
        "インシデント", "incident", "ガバナンス", "governance",
        "量子", "quantum", "PQC", "プライバシー", "privacy",
    ]
    q = question.lower()
    return any(kw.lower() in q for kw in keywords)


# ===== ベクトルストア再構築（業界追加時に呼ぶ） =====
def rebuild_all_vector_stores():
    """
    全業界のベクトルストアを再構築する
    docs_dataに新しいファイルを追加した後に呼ぶ
    """
    print(" 全業界のベクトルストアを再構築します...")

    # 全体インデックス
    build_vector_store(None)

    # 業界別インデックス（英語フォルダ名で保存）
    for industry in INDUSTRY_KEYWORDS.keys():
        industry_dir = _get_docs_dir(industry)
        if os.path.exists(industry_dir):
            try:
                build_vector_store(industry)
                eng = INDUSTRY_DIR_MAP.get(industry, industry)
                print(f" {industry}（{eng}/）: 完了")
            except Exception as e:
                print(f" {industry}: スキップ ({e})")

    print(" 全ベクトルストア再構築完了")


# ===== 統合RAGエージェント（メイン） =====
async def run_rag_agent(question: str, session_id: str) -> str:
    """Supervisorから呼び出されるエントリポイント"""
    print(f" RAGエージェント起動: {question}")

    all_docs = []

    # 業界判定
    industry = detect_industry(question)

    # セキュリティ関連ならAIGISも検索
    if is_security_query(question):
        print(" AIGIS監査項目を検索中...")
        aigis_docs = search_aigis(question, k=3)
        all_docs.extend(aigis_docs)
        print(f" AIGIS: {len(aigis_docs)}件ヒット")

    # 業界別FAISS検索
    if industry:
        print(f" 業界別検索: {industry}")
        industry_docs = search_documents(question, k=3, industry=industry)
        all_docs.extend(industry_docs)

    # 全体FAISS検索
    faiss_docs = search_documents(question, k=3, industry=None)
    all_docs.extend(faiss_docs)

    # 重複除去
    seen = set()
    unique_docs = []
    for d in all_docs:
        key = d["content"][:100]
        if key not in seen:
            seen.add(key)
            unique_docs.append(d)
    all_docs = unique_docs

    quality = evaluate_relevance(question, all_docs)
    print(f" 検索品質: {quality} / 合計: {len(all_docs)}件")

    if not all_docs or quality == "POOR":
        industry_hint = f"「{industry}」関連の" if industry else ""
        return (
            f"申し訳ありません。{industry_hint}情報が見つかりませんでした。\n"
            "より具体的なキーワードで質問してみてください。"
        )

    # 結果をフォーマット
    lines = []
    for d in all_docs[:5]:
        source   = d["source"]
        priority = f"【{d['priority']}】" if d.get("priority") else ""
        standard = f"（{d['standard']}）" if d.get("standard") else ""
        category = f"[{d['category']}]" if d.get("category") else ""
        lines.append(f"■ {source} {category}{priority}{standard}\n{d['content'][:300]}")

    context        = "\n\n".join(lines)
    industry_label = f"（{industry}業界特化検索）" if industry else ""
    return (
        f"関連情報が見つかりました{industry_label}:\n\n"
        f"{context}\n\n"
        f"（検索品質: {quality} / {len(all_docs)}件）"
    )


# ===== BigQuery統合検索 =====
def search_bigquery_documents(query: str, limit: int = 5) -> list[dict]:
    try:
        from app.services.bigquery_service import BigQueryService
        bq  = BigQueryService()
        sql = f"""
            SELECT id, source, content, created_at
            FROM `{bq.client.project}.{bq.dataset_id}.documents`
            WHERE LOWER(content) LIKE LOWER('%{query}%')
            LIMIT {limit}
        """
        results = bq.query(sql)
        return [
            {
                "content":  r["content"],
                "source":   f"BigQuery({r['source']})",
                "score":    0.5,
                "category": "",
                "priority": "",
                "standard": "",
            }
            for r in results
        ]
    except Exception as e:
        print(f" BigQuery検索エラー: {e}")
        return []