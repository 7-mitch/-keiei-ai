"""
#96 審査書類RAGエージェント（CRAG）
審査規程・社内文書をベクトル化して検索する
"""
import os
from langchain_community.document_loaders import TextLoader, DirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings

# ===== 設定 =====
DOCS_DIR    = "docs_data"
VECTOR_DIR  = "vector_store"
EMBED_MODEL = "intfloat/multilingual-e5-large"
CACHE_DIR   = "C:\\Users\\Owner\\.cache\\huggingface"

# ===== Embeddingモデル =====
def get_embeddings():
    return HuggingFaceEmbeddings(
        model_name  = EMBED_MODEL,
        cache_folder = CACHE_DIR,
        model_kwargs = {"device": "cpu"},
        encode_kwargs = {"normalize_embeddings": True},
    )

# ===== ドキュメントの読み込み・インデックス作成 =====
def build_vector_store() -> FAISS:
    """docs_dataフォルダのドキュメントをベクトル化する"""
    print("📚 ドキュメントを読み込み中...")

    # テキストファイルを読み込む
    loader = DirectoryLoader(
        DOCS_DIR,
        glob       = "**/*.txt",
        loader_cls = TextLoader,
        loader_kwargs = {"encoding": "utf-8"},
    )
    documents = loader.load()
    print(f"📄 {len(documents)}件のドキュメントを読み込みました")

    # チャンクに分割
    splitter = RecursiveCharacterTextSplitter(
        chunk_size    = 500,
        chunk_overlap = 50,
    )
    chunks = splitter.split_documents(documents)
    print(f"✂️ {len(chunks)}チャンクに分割しました")

    # ベクトルストアを作成
    embeddings   = get_embeddings()
    vector_store = FAISS.from_documents(chunks, embeddings)

    # 保存
    os.makedirs(VECTOR_DIR, exist_ok=True)
    vector_store.save_local(VECTOR_DIR)
    print(f"✅ ベクトルストアを保存しました: {VECTOR_DIR}")

    return vector_store


def load_vector_store() -> FAISS | None:
    """保存済みベクトルストアを読み込む"""
    if os.path.exists(VECTOR_DIR):
        embeddings = get_embeddings()
        return FAISS.load_local(
            VECTOR_DIR,
            embeddings,
            allow_dangerous_deserialization=True,
        )
    return None


def get_vector_store() -> FAISS:
    """ベクトルストアを取得（なければ作成）"""
    store = load_vector_store()
    if store is None:
        store = build_vector_store()
    return store


# ===== RAG検索 =====
def search_documents(query: str, k: int = 3) -> list[dict]:
    """質問に関連するドキュメントを検索する"""
    try:
        store   = get_vector_store()
        results = store.similarity_search_with_score(query, k=k)

        docs = []
        for doc, score in results:
            docs.append({
                "content":  doc.page_content,
                "source":   doc.metadata.get("source", "不明"),
                "score":    float(score),
            })
        return docs

    except Exception as e:
        print(f"⚠️ RAG検索エラー: {e}")
        return []


# ===== CRAG評価 =====
def evaluate_relevance(query: str, docs: list[dict]) -> str:
    """
    検索結果の品質を評価する（CRAG）
    GOOD / AMBIGUOUS / POOR
    """
    if not docs:
        return "POOR"

    best_score = docs[0]["score"]

    # FAISSのスコアは距離（低いほど類似）
    if best_score < 0.3:
        return "GOOD"
    elif best_score < 0.7:
        return "AMBIGUOUS"
    else:
        return "POOR"


# ===== Supervisorから呼び出す関数 =====
async def run_rag_agent(question: str, session_id: str) -> str:
    """Supervisorから呼び出されるエントリポイント"""
    print(f"📚 RAGエージェント起動: {question}")

    # ドキュメント検索
    docs = search_documents(question, k=3)
    quality = evaluate_relevance(question, docs)

    print(f"🔍 検索品質: {quality} / 結果: {len(docs)}件")

    if quality == "POOR" or not docs:
        return (
            "申し訳ありません。この質問に関連する審査規程が見つかりませんでした。\n"
            "「審査基準」「不正取引」「コンプライアンス」などのキーワードで質問してみてください。"
        )

    # 検索結果をまとめる
    context = "\n\n".join([
        f"【出典: {d['source']}】\n{d['content']}"
        for d in docs
    ])

    return (
        f"審査規程から以下の情報が見つかりました:\n\n"
        f"{context}\n\n"
        f"（検索品質: {quality}）"
    )

# ===== BigQuery統合検索（案件向け追加） =====
def search_bigquery_documents(query: str, limit: int = 5) -> list[dict]:
    """BigQueryからキーワード検索"""
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
                "score":    0.5,  # BQはスコアなしのため中間値
            }
            for r in results
        ]
    except Exception as e:
        print(f"⚠️ BigQuery検索エラー: {e}")
        return []


def search_all_sources(query: str, k: int = 3) -> list[dict]:
    """FAISS（既存）+ BigQuery（新規）を統合検索"""
    faiss_results = search_documents(query, k=k)   # 既存関数そのまま使用
    bq_results    = search_bigquery_documents(query, limit=k)

    # 結合してスコア順にソート
    all_results = faiss_results + bq_results
    all_results.sort(key=lambda x: x["score"])
    return all_results


async def run_rag_agent_full(question: str, session_id: str) -> str:
    """
    BigQuery対応版エントリポイント
    既存のrun_rag_agentはそのまま残す
    """
    print(f"📚 RAGエージェント起動（統合版）: {question}")

    docs    = search_all_sources(question, k=3)
    quality = evaluate_relevance(question, docs)  # 既存関数流用

    print(f"🔍 検索品質: {quality} / 結果: {len(docs)}件")

    if quality == "POOR" or not docs:
        return (
            "申し訳ありません。この質問に関連する情報が見つかりませんでした。\n"
            "キーワードを変えて質問してみてください。"
        )

    context = "\n\n".join([
        f"【出典: {d['source']}】\n{d['content']}"
        for d in docs
    ])

    return (
        f"関連情報が見つかりました:\n\n"
        f"{context}\n\n"
        f"（検索品質: {quality}）"
    )