"""Kintai アプリ エントリーポイント"""

import os
from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from jinja2 import Environment

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
