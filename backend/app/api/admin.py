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
    mode:     str
    password: str


@router.get("/llm-mode")
async def get_llm_mode(user: dict = Depends(get_current_user)):
    """現在のLLMモードを取得"""
    if user.get("role") != "executive":
        raise HTTPException(status_code=403, detail="権限がありません")

    import os
    mode = os.getenv("ENVIRONMENT", "development")
    return {
        "mode": mode,
        "options": [
            {"value": "development", "label": "Ollama（ローカル・無料）"},
            {"value": "production",  "label": "Claude API（クラウド）"},
            {"value": "vllm",        "label": "vLLM（オンプレGPU）"},
            {"value": "qlora",       "label": "DPOファインチューニング済みモデル"},
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

    valid_modes = ["development", "production", "vllm", "qlora"]
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

    # llm_factoryのキャッシュをクリア
    from app.core.llm_factory import get_llm
    get_llm.cache_clear()

    return {
        "message": f"LLMモードを {req.mode} に変更しました",
        "mode":    req.mode,
    }