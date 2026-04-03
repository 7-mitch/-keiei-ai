import uuid
import io
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional
from app.db.audit import record_audit
from app.core.security import get_current_user
from app.agents.supervisor import supervisor

router = APIRouter()


class ChatRequest(BaseModel):
    question: str
    thinking: bool = False


class ChatResponse(BaseModel):
    answer:     str
    route:      str
    session_id: str


# ===== テキストチャット =====
@router.post("", response_model=ChatResponse)
async def chat(
    req:     ChatRequest,
    request: Request,
    user:    dict = Depends(get_current_user),
):
    session_id = str(uuid.uuid4())
    try:
        # thinking モードの切り替え
        question = req.question if req.thinking else f"/no_think {req.question}"

        result = await supervisor.ainvoke(
            {
                "question":   question,
                "route":      "",
                "result":     "",
                "session_id": session_id,
                "user_role":  user.get("role", "operator"),
            },
            config={"configurable": {"thread_id": session_id}},
        )
        res_dict = dict(result) if result else {}

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
            print(" 監査ログの保存に失敗しましたが、回答表示を優先します")

        return ChatResponse(
            answer     = res_dict.get("result", "回答を取得できませんでした。"),
            route      = res_dict.get("route", "general"),
            session_id = session_id,
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="システム内でエラーが発生しました。")


# ===== ファイルアップロード =====
@router.post("/upload", response_model=ChatResponse)
async def chat_upload(
    request:  Request,
    file:     UploadFile = File(...),
    question: str        = Form("このファイルを分析してください"),
    thinking: bool       = Form(False),
    user:     dict       = Depends(get_current_user),
):
    session_id = str(uuid.uuid4())
    filename   = file.filename or ""
    ext        = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    try:
        contents = await file.read()
        text     = ""

        # ===== PDF =====
        if ext == "pdf":
            try:
                import pypdf
                reader = pypdf.PdfReader(io.BytesIO(contents))
                text   = "\n".join(p.extract_text() or "" for p in reader.pages)
            except Exception as e:
                text = f"PDFの読み込みに失敗しました: {e}"

        # ===== Excel =====
        elif ext in ("xlsx", "xls"):
            try:
                import pandas as pd
                df   = pd.read_excel(io.BytesIO(contents))
                text = df.to_string(index=False, max_rows=100)
            except Exception as e:
                text = f"Excelの読み込みに失敗しました: {e}"

        # ===== CSV =====
        elif ext == "csv":
            try:
                import pandas as pd
                df   = pd.read_csv(io.BytesIO(contents), encoding="utf-8-sig")
                text = df.to_string(index=False, max_rows=100)
            except Exception as e:
                text = f"CSVの読み込みに失敗しました: {e}"

        # ===== Word =====
        elif ext in ("docx", "doc"):
            try:
                import docx
                doc  = docx.Document(io.BytesIO(contents))
                text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
            except Exception as e:
                text = f"Wordファイルの読み込みに失敗しました: {e}"

        # ===== 画像 =====
        elif ext in ("png", "jpg", "jpeg"):
            try:
                import base64
                import httpx
                b64 = base64.b64encode(contents).decode()
                async with httpx.AsyncClient(timeout=60) as client:
                    res = await client.post(
                        "http://ollama:11434/api/chat",
                        json={
                            "model": "llama3.2-vision:latest",
                            "messages": [{
                                "role":    "user",
                                "content": question,
                                "images":  [b64],
                            }],
                            "stream": False,
                        },
                    )
                data = res.json()
                text = data.get("message", {}).get("content", "画像の解析に失敗しました")
            except Exception as e:
                text = f"画像の解析に失敗しました: {e}"

        else:
            text = f"未対応のファイル形式です（{ext}）"

        # ===== AIに渡す質問を生成 =====
        combined_question = f"""以下のファイル（{filename}）の内容を分析してください。

【質問】
{question}

【ファイル内容】
{text[:3000]}
"""
        # thinking モードの切り替え
        final_question = combined_question if thinking else f"/no_think {combined_question}"

        result = await supervisor.ainvoke(
            {
                "question":   final_question,
                "route":      "",
                "result":     "",
                "session_id": session_id,
                "user_role":  user.get("role", "operator"),
            },
            config={"configurable": {"thread_id": session_id}},
        )
        res_dict = dict(result) if result else {}

        return ChatResponse(
            answer     = res_dict.get("result", "回答を取得できませんでした。"),
            route      = res_dict.get("route", "general"),
            session_id = session_id,
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"ファイル処理エラー: {str(e)}")