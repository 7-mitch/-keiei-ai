from contextlib import asynccontextmanager
import os
import sys
import io
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.db.connection import init_db, close_db
from app.api import chat, alert, report, auth, fraud, web, rag, collect

# Windows UTF-8対応
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

@asynccontextmanager
async def lifespan(app: FastAPI):
    # LangSmith設定
    os.environ["LANGCHAIN_TRACING_V2"] = settings.langchain_tracing_v2
    os.environ["LANGCHAIN_API_KEY"]    = settings.langchain_api_key
    os.environ["LANGCHAIN_PROJECT"]    = settings.langchain_project
    # ===== 起動時 =====
    print("🚀 KEIEI-AI 起動中...")
    await init_db()
    print("✅ 起動完了")
    yield
    # ===== 終了時 =====
    print("🛑 KEIEI-AI 終了中...")
    await close_db()
    print("✅ 終了完了")

app = FastAPI(
    title       = "KEIEI-AI",
    description = "経営者支援AIシステム（LangGraph + FastAPI）",
    version     = "1.0.0",
    lifespan    = lifespan,
    docs_url    = "/docs"  if settings.environment == "development" else None,
    redoc_url   = "/redoc" if settings.environment == "development" else None,
)

# ===== CORS設定 =====
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "https://keiei-ai-frontend.vercel.app",
        "https://*.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# ===== ルーター登録 =====
app.include_router(auth.router,   prefix="/api/auth",   tags=["認証"])
app.include_router(chat.router,   prefix="/api/chat",   tags=["チャット"])
app.include_router(alert.router,  prefix="/api/alert",  tags=["アラート"])
app.include_router(report.router, prefix="/api/report", tags=["レポート"])
app.include_router(fraud.router,  prefix="/api/fraud",  tags=["不正検知"])
app.include_router(web.router,    prefix="/api/web",    tags=["web収集"])
app.include_router(rag.router,    prefix="/api/rag",    tags=["RAG検索"])
app.include_router(collect.router, prefix="/api/collect", tags=["データ収集"])

# ===== ヘルスチェック =====
@app.get("/health", tags=["システム"])
async def health():
    return {
        "status":  "ok",
        "env":     settings.environment,
        "version": "1.0.0",
    }