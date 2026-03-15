import uuid
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from app.db.audit import record_audit
from app.core.security import get_current_user

router = APIRouter()

# ===== リクエスト・レスポンスの型定義 =====
class ChatRequest(BaseModel):
    question: str

class ChatResponse(BaseModel):
    answer:     str
    route:      str
    session_id: str

# ===== チャットAPI =====
@router.post("", response_model=ChatResponse)
async def chat(
    req:     ChatRequest,
    request: Request,
    user:    dict = Depends(get_current_user),
):
    session_id = str(uuid.uuid4())

    try:
        # supervisorエージェントを呼ぶ（#93で実装）
        # 現時点ではダミーレスポンスを返す
        from app.agents.supervisor import supervisor
        result = await supervisor.ainvoke(
            {
                "question":   req.question,
                "route":      "",
                "result":     "",
                "session_id": session_id,
                "user_role":  user.get("role", "operator"),
            },
            config={"configurable": {"thread_id": session_id}},
        )

        # 監査ログを記録
        await record_audit(
            operator_id   = user.get("id"),
            operator_type = "human",
            target_type   = "chat",
            target_id     = user.get("id", 0),
            action        = f"chat:{result.get('route', 'general')}",
            after_value   = {
                "question": req.question,
                "route":    result.get("route", "general"),
            },
            session_id = session_id,
            ip_address = request.client.host if request.client else None,
        )

        return ChatResponse(
            answer     = result.get("result", ""),
            route      = result.get("route", "general"),
            session_id = session_id,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))