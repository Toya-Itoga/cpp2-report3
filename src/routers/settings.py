"""設定ルーター"""

import os
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from src.repositories import user_repository, work_repository
from src.routers.auth import get_current_user
from src.services import auth_service, work_service
from src.utils.salary import format_currency

router = APIRouter(prefix="/settings", tags=["settings"])
templates = Jinja2Templates(directory="src/templates")
templates.env.filters["format_currency"] = format_currency

USER_TABLE_NAME = os.getenv("USER_TABLE_NAME")
WORK_TABLE_NAME = os.getenv("WORK_TABLE_NAME")


def _monthly_context(user: dict) -> dict:
    """設定画面で共通使用する当月サマリーのコンテキストを返す"""
    today = date.today()
    records = []
    if WORK_TABLE_NAME:
        records = work_repository.get_monthly_records(user["user_id"], today.year, today.month)
    agg = work_service.aggregate_monthly(records, user["yen_per_hour"])
    return {
        "monthly_estimated_salary": agg["estimated_salary"],
        "monthly_total_hours":      f"{agg['total_minutes'] / 60:.1f}",
    }


# ─── ページ表示 ───────────────────────────────────────────────────────

@router.get("", response_class=HTMLResponse)
async def settings_page(
    request: Request,
    user: dict = Depends(get_current_user),
):
    # DynamoDB に保存された最新の時給で user を上書きする（DB 接続失敗時はそのまま使用）
    if USER_TABLE_NAME:
        try:
            db_user = user_repository.get_user(user["user_name"], user["user_id"])
            if db_user and "yen_per_hour" in db_user:
                user = {**user, "yen_per_hour": int(db_user["yen_per_hour"])}
        except Exception:
            pass
    return templates.TemplateResponse(request, "settings.html", {
        "user":     user,
        "active":   "settings",
        "messages": {},
        **_monthly_context(user),
    })


# ─── 時給更新 ─────────────────────────────────────────────────────────

@router.post("/salary")
async def update_salary(
    yen_per_hour: Annotated[int, Form()],
    user: dict = Depends(get_current_user),
):
    """時給を更新する"""
    if USER_TABLE_NAME:
        user_repository.update_user(user["user_id"], user["user_name"], yen_per_hour=yen_per_hour)
    return RedirectResponse(url="/settings", status_code=303)
