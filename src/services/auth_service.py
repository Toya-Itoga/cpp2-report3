"""認証に関するビジネスロジックを定義するサービス

CLAUDE.md の認証ポリシー:
- 認証は PyJWT を使用すること
- トークン有効期間は 6 時間とすること
- 全 API エンドポイントでトークン検証を行うこと
- FastAPI の Depends を使用して共通の認証ミドルウェアとして実装すること
- 認証処理は src/services/auth_service.py に定義すること
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from fastapi import HTTPException, Request

from src.repositories import user_repository

# ─── 環境設定 ─────────────────────────────────────────────────────────────
ENV            = os.getenv("ENV", "development")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-secret-key")
JWT_ALGORITHM  = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_H   = int(os.getenv("JWT_EXPIRE_HOURS", "6"))

COOKIE_NAME = "access_token"

# ─── ダミーユーザー（定義のみ・使用しない） ───────────────────────────────
DUMMY_USER: dict = {
    "user_id":      "dummy_user",
    "name":         "testuser",
    "email":        "test@kintai.app",
    "yen_per_hour": 1500,
}


# ─── パスワードハッシュ ────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    """bcrypt でパスワードをハッシュ化して文字列で返す"""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """bcrypt でパスワードを検証する。不正なハッシュの場合は False を返す"""
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


# ─── JWT トークン ──────────────────────────────────────────────────────────

def create_token(user_id: str, user_name: str) -> str:
    """JWT アクセストークンを生成して返す（sub に user_id、user_name も格納する）"""
    expire  = datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_H)
    payload = {"sub": user_id, "user_name": user_name, "exp": expire}
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def verify_token(token: str) -> dict:
    """
    JWT トークンを検証して {"user_id": ..., "user_name": ...} を返す。
    有効期限切れ・不正トークンの場合は HTTPException(401) を送出する。
    """
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return {
            "user_id":   str(payload["sub"]),
            "user_name": str(payload.get("user_name", payload["sub"])),
        }
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="トークンの有効期限が切れています")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="無効なトークンです")


# ─── ユーザー認証 ──────────────────────────────────────────────────────────

def authenticate(user_name: str, password: str) -> Optional[dict]:
    """
    ユーザー名とパスワードでユーザーを認証する。
    認証成功時はユーザー dict を返し、失敗時は None を返す。
    """
    try:
        user = user_repository.get_user_by_name(user_name)
    except Exception:
        return None

    if not user:
        return None

    stored_hash = user.get("password", "")
    if not stored_hash:
        return None
    try:
        if not bcrypt.checkpw(password.encode(), stored_hash.encode()):
            return None
    except Exception:
        return None

    return user


def get_user_from_token(user_id: str, user_name: str) -> dict:
    """
    JWT の sub（user_id）と user_name から DynamoDB のユーザー情報を取得して返す。
    ユーザーが存在しない場合は HTTPException(401) を送出する。
    """
    user = user_repository.get_user(user_name, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="ユーザーが見つかりません")

    return {
        "user_id":      user.get("user_id", user_id),
        "user_name":    user_name,
        "name":         user.get("name", ""),
        "email":        user.get("email", ""),
        "yen_per_hour": int(user.get("yen_per_hour", 0)),
    }


# ─── FastAPI Depends 用ミドルウェア ────────────────────────────────────────

async def get_current_user(request: Request) -> dict:
    """
    Cookie からトークンを取得・検証し、ユーザー情報を返す。
    FastAPI の Depends で全エンドポイントに適用する。
    トークンがない場合は 401 を送出し、main.py のハンドラーが /auth/login へリダイレクトする。
    """
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="認証が必要です")

    claims = verify_token(token)
    return get_user_from_token(claims["user_id"], claims["user_name"])
