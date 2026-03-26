from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from app.db.connection import get_conn
from app.core.security import (
    verify_password,
    create_access_token,
    get_current_user,
    hash_password,
)

router = APIRouter()

# ===== リクエスト・レスポンスの型定義 =====
class LoginRequest(BaseModel):
    email:    str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type:   str = "bearer"
    user_id:      int
    name:         str
    role:         str

class CreateUserRequest(BaseModel):
    name:     str
    email:    str
    password: str
    role:     str = "operator"
    # 'executive' | 'manager' | 'operator'

# ===== ログイン =====
@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest):
    async with get_conn() as conn:
        user = await conn.fetchrow(
            "SELECT * FROM users WHERE email = $1 AND is_active = true",
            req.email,
        )

    if not user or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(
            status_code=401,
            detail="メールまたはパスワードが間違っています",
        )

    token = create_access_token({
        "sub":  str(user["id"]),
        "id":   user["id"],
        "role": user["role"],
        "name": user["name"],
    })

    return LoginResponse(
        access_token = token,
        user_id      = user["id"],
        name         = user["name"],
        role         = user["role"],
    )

# ===== 自分の情報を取得 =====
@router.get("/me")
async def get_me(user: dict = Depends(get_current_user)):
    return user

# ===== ユーザー作成（管理者のみ）=====
@router.post("/register")
async def register(req: CreateUserRequest):
    async with get_conn() as conn:
        # メール重複チェック
        existing = await conn.fetchrow(
            "SELECT id FROM users WHERE email = $1", req.email
        )
        if existing:
            raise HTTPException(
                status_code=400,
                detail="このメールアドレスは既に使用されています",
            )

        # ユーザー作成
        user = await conn.fetchrow("""
            INSERT INTO users (name, email, password_hash, role)
            VALUES ($1, $2, $3, $4)
            RETURNING id, name, email, role
        """,
            req.name,
            req.email,
            hash_password(req.password),
            req.role,
        )

    return {
        "message": "ユーザーを作成しました",
        "user_id": user["id"],
        "name":    user["name"],
        "role":    user["role"],
    }
