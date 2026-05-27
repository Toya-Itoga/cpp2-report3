"""Kintai アプリ エントリーポイント"""

import os
from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from mangum import Mangum

from src.routers import auth, dashboard, punch, history, settings
from src.utils.salary import format_currency

# ─── アプリ初期化 ───────────────────────────────────────────────────
app = FastAPI(title="Kintai")

# 静的ファイル
app.mount("/static", StaticFiles(directory="src/static"), name="static")

# Jinja2テンプレート設定
templates = Jinja2Templates(directory="src/templates")
templates.env.filters["format_currency"] = format_currency

# ─── ルーター登録 ────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(punch.router)
app.include_router(history.router)
app.include_router(settings.router)


# ─── 例外ハンドラー ─────────────────────────────────────────────────
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """未認証（401）のリクエストはログイン画面へリダイレクトする"""
    if exc.status_code == 401:
        return RedirectResponse(url="/auth/login", status_code=303)
    # その他の HTTP 例外はデフォルト処理に委譲する
    from fastapi.exception_handlers import http_exception_handler as _default
    return await _default(request, exc)


# ─── AWS Lambda ハンドラー ───────────────────────────────────────────
handler = Mangum(app)
