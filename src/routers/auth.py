"""認証ルーター"""

import os
from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from src.utils.salary import format_currency

router = APIRouter(prefix="/auth", tags=["auth"])
templates = Jinja2Templates(directory="src/templates")
templates.env.filters["format_currency"] = format_currency

ENV            = os.getenv("ENV", "development")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-secret-key")
JWT_ALGORITHM  = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_H   = int(os.getenv("JWT_EXPIRE_HOURS", "6"))

COOKIE_NAME = "access_token"

# ─── ダミーユーザー（ENV=development 時） ────────────────────────────
DUMMY_USER = {
    "user_id":      "dummy_user",
    "name":         "testuser",
    "email":        "test@kintai.app",
    "yen_per_hour": 1500,
}


# ─── トークン生成・検証 ────────────────────────────────────────────────
def create_token(user_id: str) -> str:
    """JWTアクセストークンを生成する"""
    expire = datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_H)
    payload = {"sub": user_id, "exp": expire}
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def verify_token(token: str) -> str:
    """トークンを検証してuser_idを返す。無効な場合は HTTPException を送出する"""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        user_id: str = payload["sub"]
        return user_id
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="トークンの有効期限が切れています")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="無効なトークンです")


# ─── 認証依存関数 ──────────────────────────────────────────────────────
async def get_current_user(request: Request) -> dict:
    """
    Cookieからトークンを取得し、ユーザー情報を返す。
    ENV=development の場合はダミーユーザーを返す（DynamoDB認証スキップ）。
    """
    if ENV == "development":
        return DUMMY_USER

    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="認証が必要です")

    user_id = verify_token(token)

    # TODO: DynamoDBからユーザー情報を取得する
    return {"user_id": user_id, "name": "ユーザー", "email": "", "yen_per_hour": 0}


# ─── ログイン画面 ───────────────────────────────────────────────────────
@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html", {"error": None})


@router.post("/login")
async def login(
    request: Request,
    response: Response,
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
):
    """ログイン処理。ENV=development では認証をスキップしてダミートークンを発行する"""
    if ENV == "development":
        token = create_token(DUMMY_USER["user_id"])
        resp = RedirectResponse(url="/dashboard", status_code=303)
        resp.set_cookie(COOKIE_NAME, token, httponly=True, max_age=JWT_EXPIRE_H * 3600)
        return resp

    # TODO: DynamoDBでEmail+パスワードを検証する
    return templates.TemplateResponse(
        request, "login.html",
        {"error": "メールアドレスまたはパスワードが正しくありません"},
        status_code=401,
    )


@router.post("/logout")
async def logout():
    """ログアウト：Cookieを削除してログイン画面へリダイレクト"""
    resp = RedirectResponse(url="/auth/login", status_code=303)
    resp.delete_cookie(COOKIE_NAME)
    return resp
