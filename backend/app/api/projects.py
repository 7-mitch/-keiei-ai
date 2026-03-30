"""
app/api/projects.py
工程管理モジュールのREST APIエンドポイント
main.py に: app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
を1行追加するだけで有効になる
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import date

from app.db.connection import get_conn
from app.core.security import get_current_user

router = APIRouter()


# ── スキーマ ──
class TaskCreate(BaseModel):
    phase:      int = 1
    name:       str
    assign:     Optional[str] = None
    status:     str = "todo"
    progress:   int = 0
    start_date: Optional[date] = None
    end_date:   Optional[date] = None
    color:      str = "blue"
    note:       Optional[str] = None

class TaskUpdate(BaseModel):
    phase:      Optional[int]  = None
    name:       Optional[str]  = None
    assign:     Optional[str]  = None
    status:     Optional[str]  = None
    progress:   Optional[int]  = None
    start_date: Optional[date] = None
    end_date:   Optional[date] = None
    color:      Optional[str]  = None
    note:       Optional[str]  = None


# ── タスク一覧取得 ──
@router.get("/{project_id}/tasks")
async def get_tasks(
    project_id: int,
    user: dict = Depends(get_current_user),
):
    async with get_conn() as conn:
        rows = await conn.fetch(
            """
            SELECT id, phase, name, assign, status, progress,
                   start_date, end_date, color, note
            FROM tasks
            WHERE project_id = $1
            ORDER BY phase, id
            """,
            project_id,
        )
    return [dict(r) for r in rows]


# ── タスク追加 ──
@router.post("/{project_id}/tasks", status_code=201)
async def create_task(
    project_id: int,
    body: TaskCreate,
    user: dict = Depends(get_current_user),
):
    async with get_conn() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO tasks
                (project_id, phase, name, assign, status, progress,
                 start_date, end_date, color, note)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
            RETURNING id
            """,
            project_id, body.phase, body.name, body.assign,
            body.status, body.progress, body.start_date,
            body.end_date, body.color, body.note,
        )
    return {"id": row["id"], "message": "タスクを追加しました"}


# ── タスク更新 ──
@router.put("/{project_id}/tasks/{task_id}")
async def update_task(
    project_id: int,
    task_id:    int,
    body: TaskUpdate,
    user: dict = Depends(get_current_user),
):
    # 変更があるフィールドだけ動的にUPDATE
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="更新フィールドがありません")

    set_clause = ", ".join(
        f"{col} = ${i+3}" for i, col in enumerate(updates.keys())
    )
    values = [project_id, task_id] + list(updates.values())

    async with get_conn() as conn:
        result = await conn.execute(
            f"""
            UPDATE tasks SET {set_clause}, updated_at = NOW()
            WHERE project_id = $1 AND id = $2
            """,
            *values,
        )
    if result == "UPDATE 0":
        raise HTTPException(status_code=404, detail="タスクが見つかりません")
    return {"message": "タスクを更新しました"}


# ── タスク削除 ──
@router.delete("/{project_id}/tasks/{task_id}")
async def delete_task(
    project_id: int,
    task_id:    int,
    user: dict = Depends(get_current_user),
):
    async with get_conn() as conn:
        result = await conn.execute(
            "DELETE FROM tasks WHERE project_id = $1 AND id = $2",
            project_id, task_id,
        )
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="タスクが見つかりません")
    return {"message": "タスクを削除しました"}


# ── メンバー一覧取得 ──
@router.get("/{project_id}/members")
async def get_members(
    project_id: int,
    user: dict = Depends(get_current_user),
):
    async with get_conn() as conn:
        rows = await conn.fetch(
            """
            SELECT id, name, role, skills, workload
            FROM project_members
            WHERE project_id = $1
            ORDER BY workload DESC
            """,
            project_id,
        )
    return [dict(r) for r in rows]


# ── 進捗サマリー（チャットボット連携用） ──
@router.get("/{project_id}/summary")
async def get_summary(
    project_id: int,
    user: dict = Depends(get_current_user),
):
    """チャットボットやダッシュボードから進捗を取得するエンドポイント"""
    async with get_conn() as conn:
        tasks = await conn.fetch(
            "SELECT status, count(*) as cnt FROM tasks WHERE project_id=$1 GROUP BY status",
            project_id,
        )
        overload = await conn.fetch(
            "SELECT name, workload FROM project_members WHERE project_id=$1 AND workload > 100",
            project_id,
        )
    return {
        "task_counts":       {r["status"]: r["cnt"] for r in tasks},
        "overload_members":  [dict(r) for r in overload],
    }
