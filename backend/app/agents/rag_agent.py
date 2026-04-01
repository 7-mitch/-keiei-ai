"""
#96 審査書類RAGエージェント（CRAG）+ AIGIS 336監査項目統合版
審査規程・社内文書 + AIGIS セキュリティ監査項目をベクトル化して検索する
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
CACHE_DIR        = os.getenv("HF_CACHE_DIR", "/tmp/huggingface")  # ← 修正済み

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

# ===== ドキュメントの読み込み・インデックス作成 =====
def build_vector_store() -> FAISS:
    print(" ドキュメントを読み込み中...")
    loader = DirectoryLoader(
        DOCS_DIR,
        glob          = "**/*.txt",
        loader_cls    = TextLoader,
        loader_kwargs = {"encoding": "utf-8"},
    )
    documents = loader.load()
    print(f" {len(documents)}件のドキュメントを読み込みました")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size    = 500,
        chunk_overlap = 50,
    )
    chunks = splitter.split_documents(documents)
    print(f" {len(chunks)}チャンクに分割しました")

    embeddings   = get_embeddings()
    vector_store = FAISS.from_documents(chunks, embeddings)

    os.makedirs(VECTOR_DIR, exist_ok=True)
    vector_store.save_local(VECTOR_DIR)
    print(f" ベクトルストアを保存しました: {VECTOR_DIR}")
    return vector_store


def load_vector_store() -> FAISS | None:
    if os.path.exists(VECTOR_DIR):
        embeddings = get_embeddings()
        return FAISS.load_local(
            VECTOR_DIR,
            embeddings,
            allow_dangerous_deserialization=True,
        )
    return None


def get_vector_store() -> FAISS:
    store = load_vector_store()
    if store is None:
        store = build_vector_store()
    return store


# ===== FAISS検索 =====
def search_documents(query: str, k: int = 3) -> list[dict]:
    try:
        store   = get_vector_store()
        results = store.similarity_search_with_score(query, k=k)
        docs = []
        for doc, score in results:
            docs.append({
                "content":  doc.page_content,
                "source":   doc.metadata.get("source", "不明"),
                "score":    float(score),
                "category": "",
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
    """セキュリティ・監査関連の質問かどうかを判定"""
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


# ===== 統合RAGエージェント（メイン） =====
async def run_rag_agent(question: str, session_id: str) -> str:
    """Supervisorから呼び出されるエントリポイント"""
    print(f" RAGエージェント起動: {question}")

    all_docs = []

    # セキュリティ関連ならAIGISも検索
    if is_security_query(question):
        print(" AIGIS監査項目を検索中...")
        aigis_docs = search_aigis(question, k=3)
        all_docs.extend(aigis_docs)
        print(f" AIGIS: {len(aigis_docs)}件ヒット")

    # 通常のFAISS検索
    faiss_docs = search_documents(question, k=3)
    all_docs.extend(faiss_docs)

    quality = evaluate_relevance(question, all_docs)
    print(f" 検索品質: {quality} / 合計: {len(all_docs)}件")

    if not all_docs or quality == "POOR":
        return (
            "申し訳ありません。この質問に関連する情報が見つかりませんでした。\n"
            "「セキュリティ」「監査」「リスク」「不正検知」などのキーワードで質問してみてください。"
        )

    # 結果をフォーマット
    lines = []
    for d in all_docs[:5]:
        source   = d["source"]
        priority = f"【{d['priority']}】" if d.get("priority") else ""
        standard = f"（{d['standard']}）" if d.get("standard") else ""
        lines.append(f"■ {source} {priority}{standard}\n{d['content'][:300]}")

    context = "\n\n".join(lines)
    return (
        f"関連する監査・セキュリティ情報が見つかりました:\n\n"
        f"{context}\n\n"
        f"（検索品質: {quality} / {len(all_docs)}件）"
    )


# ===== BigQuery統合検索（案件向け追加） =====
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