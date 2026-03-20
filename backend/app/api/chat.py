import uuid
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from app.db.audit import record_audit
from app.core.security import get_current_user

router = APIRouter()

class ChatRequest(BaseModel):
    question: str

class ChatResponse(BaseModel):
    answer:     str
    route:      str
    session_id: str

@router.post("", response_model=ChatResponse)
async def chat(
    req:     ChatRequest,
    request: Request,
    user:    dict = Depends(get_current_user),
):
    session_id = str(uuid.uuid4())

    try:
        # 1. AIエージェントを呼ぶ
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

        res_dict = dict(result) if result else {}

        # 2. 監査ログを記録（ここを独立した try-except にします）
        try:
            await record_audit(
                operator_id   = user.get("id"),
                operator_type = "human",
                target_type   = "chat",
                target_id     = None, 
                action        = f"chat:{res_dict.get('route', 'general')}",
                after_value   = {
                    "question": req.question,
                    "route":    res_dict.get("route", "general"),
                },
                session_id = session_id,
                ip_address = request.client.host if request.client else None,
            )
        except Exception:
            # ログ保存でエラー（0番さんがいない等）が出ても無視して進む
            print("⚠️ 監査ログの保存に失敗しましたが、回答表示を優先します")
            pass

        # 3. 正常な回答を返す
        return ChatResponse(
            answer     = res_dict.get("result", "回答を取得できませんでした。"),
            route      = res_dict.get("route", "general"),
            session_id = session_id,
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="システム内でエラーが発生しました。")