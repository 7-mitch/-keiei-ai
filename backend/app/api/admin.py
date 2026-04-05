"""
admin.py — 管理者設定API
LLM環境の切り替え・システム設定管理
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from app.core.security import get_current_user, verify_password
from app.db.connection import get_conn

router = APIRouter()

class LlmModeRequest(BaseModel):
    mode:      str
    model_key: str = ""
    password:  str

@router.get("/llm-mode")
async def get_llm_mode(user: dict = Depends(get_current_user)):
    """現在のLLMモードを取得"""
    if user.get("role") != "executive":
        raise HTTPException(status_code=403, detail="権限がありません")
    import os
    mode = os.getenv("ENVIRONMENT", "development")
    return {
        "mode": mode,
        "providers": [
            {
                "value": "development",
                "label": "🖥️ Ollama（ローカル・無料）",
                "models": [
                    {"key": "fast", "label": "gemma3:4b（標準・高速）"},
                    {"key": "deep", "label": "qwen3:8b（推論・高精度）"},
                ]
            },
            {
                "value": "production",
                "label": "⚡ Claude API",
                "models": [
                    {"key": "haiku",  "label": "Haiku（高速・低コスト）"},
                    {"key": "sonnet", "label": "Sonnet（バランス）"},
                    {"key": "opus",   "label": "Opus（最高精度）"},
                ]
            },
            {
                "value": "openai",
                "label": "🤖 OpenAI",
                "models": [
                    {"key": "mini",  "label": "GPT-4o mini（高速・低コスト）"},
                    {"key": "gpt4o", "label": "GPT-4o（バランス）"},
                    {"key": "o1",    "label": "o1（推論特化）"},
                ]
            },
            {
                "value": "gemini",
                "label": "💎 Gemini",
                "models": [
                    {"key": "flash", "label": "Gemini Flash（高速・低コスト）"},
                    {"key": "pro",   "label": "Gemini Pro（バランス）"},
                    {"key": "ultra", "label": "Gemini Ultra（最高精度）"},
                ]
            },
        ]
    }

@router.post("/llm-mode")
async def set_llm_mode(
    req:  LlmModeRequest,
    user: dict = Depends(get_current_user),
):
    """LLMモードを変更（パスワード認証必須）"""
    if user.get("role") != "executive":
        raise HTTPException(status_code=403, detail="権限がありません")

    valid_modes = ["development", "production", "openai", "gemini", "vllm", "qlora"]
    if req.mode not in valid_modes:
        raise HTTPException(status_code=400, detail="無効なモードです")

    # パスワード確認
    async with get_conn() as conn:
        db_user = await conn.fetchrow(
            "SELECT password_hash FROM users WHERE id = $1",
            user["id"],
        )
    if not db_user or not verify_password(req.password, db_user["password_hash"]):
        raise HTTPException(status_code=401, detail="パスワードが間違っています")

    # 環境変数を更新
    import os
    os.environ["ENVIRONMENT"] = req.mode
    if req.model_key:
        os.environ["LLM_MODEL_KEY"] = req.model_key

    # llm_factoryのキャッシュをクリア
    from app.core.llm_factory import get_llm
    get_llm.cache_clear()

    return {
        "message":   f"LLMを {req.mode} / {req.model_key or 'default'} に変更しました",
        "mode":      req.mode,
        "model_key": req.model_key,
    }
