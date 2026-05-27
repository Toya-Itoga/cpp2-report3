"""認証に関するビジネスロジックを定義するサービス

CLAUDE.md の認証ポリシー:
- 認証は PyJWT を使用すること
- トークン有効期間は 6 時間とすること
- 全 API エンドポイントでトークン検証を行うこと
- FastAPI の Depends を使用して共通の認証ミドルウェアとして実装すること
- 認証処理は src/services/auth_service.py に定義すること
"""

import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import HTTPException, Request

from src.repositories import user_repository

# ─── 環境設定 ─────────────────────────────────────────────────────────────
ENV            = os.getenv("ENV", "development")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-secret-key")
JWT_ALGORITHM  = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_H   = int(os.getenv("JWT_EXPIRE_HOURS", "6"))

COOKIE_NAME = "access_token"

# ─── ダミーユーザー（ENV=development 時） ─────────────────────────────────
DUMMY_USER: dict = {
    "user_id":      "dummy_user",
    "name":         "testuser",
    "email":        "test@kintai.app",
    "yen_per_hour": 1500,
}


# ─── パスワードハッシュ ────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    """
    PBKDF2-SHA256 でパスワードをハッシュ化する。
    返り値フォーマット: "<salt_hex>:<key_hex>"
    """
    salt = os.urandom(32)
    key  = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000)
    return f"{salt.hex()}:{key.hex()}"


def verify_password(plain: str, hashed: str) -> bool:
    """
    平文パスワードとハッシュを比較する。
    タイミング攻撃を防ぐため hmac.compare_digest を使用する。
    """
    try:
        salt_hex, key_hex = hashed.split(":", 1)
        salt = bytes.fromhex(salt_hex)
        key  = hashlib.pbkdf2_hmac("sha256", plain.encode(), salt, 100_000)
        return hmac.compare_digest(key.hex(), key_hex)
    except (ValueError, AttributeError):
        return False


# ─── JWT トークン ──────────────────────────────────────────────────────────

def create_token(user_id: str) -> str:
    """JWT アクセストークンを生成して返す"""
    expire  = datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_H)
    payload = {"sub": user_id, "exp": expire}
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def verify_token(token: str) -> str:
    """
    JWT トークンを検証して user_id を返す。
    有効期限切れ・不正トークンの場合は HTTPException(401) を送出する。
    """
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return str(payload["sub"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="トークンの有効期限が切れています")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="無効なトークンです")


# ─── ユーザー認証 ──────────────────────────────────────────────────────────

def authenticate(email: str, password: str) -> Optional[dict]:
    """
    メールアドレスとパスワードでユーザーを認証する。
    認証成功時はユーザー dict を返し、失敗時は None を返す。
    ENV=development では DynamoDB 接続を試み、接続できない場合はダミーユーザーを返す。
    """
    try:
        user = user_repository.get_user_by_email(email)
    except Exception:
        # DynamoDB に接続できない場合は開発環境のみダミーユーザーを返す
        if ENV == "development":
            return DUMMY_USER
        return None

    if not user:
        # DynamoDB にユーザーが存在しない場合も開発環境はダミーユーザーを返す
        if ENV == "development":
            return DUMMY_USER
        return None

    stored_hash = user.get("password_hash", "")
    if not verify_password(password, stored_hash):
        return None

    return user


def get_user_from_token(user_id: str) -> dict:
    """
    user_id から DynamoDB のユーザー情報を取得して返す。
    ユーザーが存在しない場合は HTTPException(401) を送出する。
    ENV=development ではダミーユーザーを返す。
    """
    if ENV == "development":
        return DUMMY_USER

    user = user_repository.get_user(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="ユーザーが見つかりません")

    return {
        "user_id":      user.get("user_id", user_id),
        "name":         user.get("name", ""),
        "email":        user.get("email", ""),
        "yen_per_hour": int(user.get("yen_per_hour", 0)),
    }


# ─── FastAPI Depends 用ミドルウェア ────────────────────────────────────────

async def get_current_user(request: Request) -> dict:
    """
    Cookie からトークンを取得・検証し、ユーザー情報を返す。
    FastAPI の Depends で全エンドポイントに適用する。
    ENV=development の場合は DynamoDB 認証をスキップしてダミーユーザーを返す。
    """
    if ENV == "development":
        return DUMMY_USER

    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="認証が必要です")

    user_id = verify_token(token)
    return get_user_from_token(user_id)
