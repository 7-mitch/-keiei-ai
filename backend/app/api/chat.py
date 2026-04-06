import uuid
import io
import logging
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from typing import Optional, Tuple, Any
import httpx

# ※各種自作モジュールのimport
from app.db.audit import record_audit
from app.core.security import get_current_user
from app.agents.supervisor import supervisor
from app.core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

# ===== 定数設定 =====
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10MB上限
MAX_EXTRACTED_TEXT_LEN = 3000           # LLMに渡すテキストの上限文字数
DF_MAX_ROWS_PREVIEW = 100               # データフレームのテキストプレビュー上限行数


class ChatRequest(BaseModel):
    question:    str
    thinking:    bool  = False
    mode:        str   = "standard"
    temperature: float = 0.7
    top_p:       float = 0.9


class ChatResponse(BaseModel):
    answer:       str
    route:        str
    session_id:   str
    graph_base64: str | None = None
    graph_json:   str | None = None


# ==========================================
# ヘルパー関数: 同期的な重いファイル解析処理 (Threadpoolで実行)
# ==========================================
def _sync_parse_file(contents: bytes, ext: str) -> Tuple[str, Any]:
    """CPUを消費するファイル解析処理（Pandas/PyPDF/Docx）"""
    text = ""
    df_for_graph = None

    if ext == "pdf":
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(contents))
        text = "\n".join(p.extract_text() or "" for p in reader.pages)

    elif ext in ("xlsx", "xls"):
        import pandas as pd
        df = pd.read_excel(io.BytesIO(contents))
        df_for_graph = df
        text = df.to_string(index=False, max_rows=DF_MAX_ROWS_PREVIEW)

    elif ext == "csv":
        import pandas as pd
        for enc in ("utf-8-sig", "shift_jis", "cp932", "utf-8"):
            try:
                df = pd.read_csv(io.BytesIO(contents), encoding=enc)
                df_for_graph = df
                text = df.to_string(index=False, max_rows=DF_MAX_ROWS_PREVIEW)
                break
            except Exception:
                continue
        else:
            raise ValueError("CSVのエンコーディングが特定できませんでした")

    elif ext in ("docx", "doc"):
        import docx
        doc = docx.Document(io.BytesIO(contents))
        text = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        
    return text, df_for_graph


# ==========================================
# ヘルパー関数: ファイル内容の抽出 (非同期統合インターフェース)
# ==========================================
async def extract_file_content(contents: bytes, filename: str, question: str) -> Tuple[str, Any]:
    """ファイルの内容をテキスト化し、グラフ用のDataFrameがあれば返す"""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    text = ""
    df_for_graph = None

    # LLMを利用する非同期処理（画像解析）
    if ext in ("png", "jpg", "jpeg"):
        try:
            import base64
            b64 = base64.b64encode(contents).decode()
            ollama_url = getattr(settings, "OLLAMA_API_URL", "http://ollama:11434")
            
            async with httpx.AsyncClient(timeout=60) as client:
                res = await client.post(
                    f"{ollama_url}/api/chat",
                    json={
                        "model": "llava-phi3",
                        "messages": [{
                            "role":    "user",
                            "content": question,
                            "images":  [b64],
                        }],
                        "stream": False,
                    },
                )
                res.raise_for_status()
                data = res.json()
                text = data.get("message", {}).get("content", "画像の解析に失敗しました")
        except Exception as e:
            text = f"画像の解析に失敗しました: {e}"
            logger.error(f"Image parsing failed: {e}")

    # CPUバウンドな同期処理（別スレッドで実行）
    elif ext in ("pdf", "xlsx", "xls", "csv", "docx", "doc"):
        try:
            text, df_for_graph = await run_in_threadpool(_sync_parse_file, contents, ext)
        except Exception as e:
            text = f"ファイルの読み込みに失敗しました ({ext}): {e}"
            logger.error(f"File parsing failed for {filename}: {e}")
            
    else:
        text = f"未対応のファイル形式です（{ext}）"

    return text, df_for_graph


# ===== テキストチャット =====
@router.post("", response_model=ChatResponse)
async def chat(
    req:     ChatRequest,
    request: Request,
    user:    dict = Depends(get_current_user),
):
    session_id = str(uuid.uuid4())
    try:
        question = req.question if req.thinking else f"/no_think {req.question}"

        result = await supervisor.ainvoke(
            {
                "question":    question,
                "route":       "",
                "result":      "",
                "session_id":  session_id,
                "user_role":   user.get("role", "operator"),
                "mode":        req.mode,
                "temperature": req.temperature,
                "top_p":       req.top_p,
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
                    "mode":     req.mode,
                },
                session_id = session_id,
                ip_address = request.client.host if request.client else None,
            )
        except Exception as e:
            logger.warning(f"監査ログの保存に失敗しましたが、回答表示を優先します: {e}")

        return ChatResponse(
            answer     = res_dict.get("result", "回答を取得できませんでした。"),
            route      = res_dict.get("route", "general"),
            session_id = session_id,
        )
    except Exception as e:
        logger.exception("Chat endpoint error")
        raise HTTPException(status_code=500, detail="システム内でエラーが発生しました。")


# ===== ファイルアップロード =====
@router.post("/upload", response_model=ChatResponse)
async def chat_upload(
    request:     Request,
    file:        UploadFile = File(...),
    question:    str        = Form("このファイルを分析してください"),
    thinking:    bool       = Form(False),
    mode:        str        = Form("standard"),
    temperature: float      = Form(0.7),
    top_p:       float      = Form(0.9),
    user:        dict       = Depends(get_current_user),
):
    session_id = str(uuid.uuid4())
    filename   = file.filename or "unknown"

    try:
        contents = await file.read()
        
        # 1. セキュリティ: ファイルサイズ制限
        if len(contents) > MAX_FILE_SIZE_BYTES:
            raise HTTPException(status_code=413, detail=f"ファイルサイズが上限({MAX_FILE_SIZE_BYTES/1024/1024}MB)を超えています。")

        # 2. ファイルの抽出処理 (別スレッド処理含む)
        text, df_for_graph = await extract_file_content(contents, filename, question)

        # 3. テキストの切り出し (LLMのコンテキストウィンドウ溢れ防止)
        truncated_text = text[:MAX_EXTRACTED_TEXT_LEN]
        if len(text) > MAX_EXTRACTED_TEXT_LEN:
            truncated_text += "\n\n...（テキストが長いため以降は省略されました）"

        combined_question = f"""以下のファイル（{filename}）の内容を分析してください。

【質問】
{question}

【ファイル内容】
{truncated_text}
"""
        final_question = combined_question if thinking else f"/no_think {combined_question}"

        # 4. エージェントの実行
        result = await supervisor.ainvoke(
            {
                "question":    final_question,
                "route":       "file_analysis",
                "result":      "",
                "session_id":  session_id,
                "user_role":   user.get("role", "operator"),
                "mode":        mode,
                "temperature": temperature,
                "top_p":       top_p,
            },
            config={"configurable": {"thread_id": session_id}},
        )
        res_dict = dict(result) if result else {}

        # 5. 監査ログの記録 (追加実装)
        try:
            await record_audit(
                operator_id   = user.get("id"),
                operator_type = "human",
                target_type   = "file_upload",
                target_id     = filename,
                action        = f"upload:{res_dict.get('route', 'file_analysis')}",
                after_value   = {
                    "question":  question,
                    "filename":  filename,
                    "file_size": len(contents),
                    "route":     res_dict.get("route", "file_analysis"),
                    "mode":      mode,
                },
                session_id = session_id,
                ip_address = request.client.host if request.client else None,
            )
        except Exception as e:
            logger.warning(f"アップロード監査ログの保存に失敗: {e}")

        # 6. グラフ生成
        graph_base64 = None
        graph_json   = None
        if df_for_graph is not None:
            # グラフ生成もCPUバウンドなためスレッドプール化を推奨しますが、今回は現状のまま呼び出します
            from app.agents.graph_agent import generate_graph, generate_graph_json
            graph_json = generate_graph_json(df_for_graph, filename)
            if graph_json is None:
                graph_base64 = generate_graph(df_for_graph, filename)

        return ChatResponse(
            answer       = res_dict.get("result", "回答を取得できませんでした。"),
            route        = res_dict.get("route", "file_analysis"),
            session_id   = session_id,
            graph_base64 = graph_base64,
            graph_json   = graph_json,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"File upload processing error: {filename}")
        raise HTTPException(status_code=500, detail=f"ファイル処理中にエラーが発生しました。")