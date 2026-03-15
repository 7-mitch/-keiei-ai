from datetime import datetime, timedelta, timezone
from typing import Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.config import settings

pwd_context   = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer()

def hash_password(password: str) -> str:
    """パスワードをハッシュ化する"""
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    """パスワードを検証する"""
    return pwd_context.verify(plain, hashed)

def create_access_token(data: dict[str, Any]) -> str:
    """JWTトークンを発行する"""
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire
    )
    return jwt.encode(
        {**data, "exp": expire},
        settings.secret_key,
        algorithm=settings.algorithm,
    )

def decode_token(token: str) -> dict[str, Any]:
    """JWTトークンを検証・デコードする"""
    try:
        return jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="トークンが無効です",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict[str, Any]:
    """現在のログインユーザーを取得する（依存性注入）"""
    return decode_token(credentials.credentials)

def require_role(*roles: str):
    """
    ロールベースアクセス制御（依存性注入）

    使い方:
        @router.get("/kpi", dependencies=[Depends(require_role("executive"))])
        @router.get("/data", dependencies=[Depends(require_role("executive", "manager"))])
    """
    async def check_role(
        current_user: dict = Depends(get_current_user)
    ) -> dict:
        if current_user.get("role") not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"このAPIには {list(roles)} のいずれかの権限が必要です",
            )
        return current_user
    return check_role