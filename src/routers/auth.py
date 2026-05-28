import os
"""認証ルーター

トークン生成・検証・ユーザー認証の実装は src/services/auth_service.py に委譲する。
このファイルはHTTPエンドポイントの定義のみを担当する。
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from services import auth_service
from utils.salary import format_currency

router = APIRouter(prefix="/auth", tags=["auth"])
_TMPL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "templates")
templates = Jinja2Templates(directory=_TMPL)
templates.env.filters["format_currency"] = format_currency

# 他ルーターから Depends(get_current_user) として参照できるようエクスポートする
get_current_user = auth_service.get_current_user
COOKIE_NAME      = auth_service.COOKIE_NAME
JWT_EXPIRE_H     = auth_service.JWT_EXPIRE_H


# ─── ログイン画面 ──────────────────────────────────────────────────────────
@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html", {"error": None})


@router.post("/login")
async def login(
    request:   Request,
    response:  Response,
    user_name: Annotated[str, Form()],
    password:  Annotated[str, Form()],
):
    """ユーザー名 + パスワードで認証し、成功時は JWT Cookie を発行する"""
    user = auth_service.authenticate(user_name, password)

    if user is None:
        return templates.TemplateResponse(
            request, "login.html",
            {"error": "ユーザー名またはパスワードが正しくありません"},
            status_code=401,
        )

    token = auth_service.create_token(user["user_id"], user_name)
    resp  = RedirectResponse(url="/dashboard", status_code=303)
    resp.set_cookie(
        COOKIE_NAME,
        token,
        httponly=True,
        max_age=JWT_EXPIRE_H * 3600,
    )
    return resp


@router.post("/logout")
async def logout():
    """Cookie を削除してログイン画面へリダイレクトする"""
    resp = RedirectResponse(url="/auth/login", status_code=303)
    resp.delete_cookie(COOKIE_NAME)
    return resp
