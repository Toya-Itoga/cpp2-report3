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
    # DynamoDB に保存された最新の時給で user を上書きする
    if USER_TABLE_NAME:
        db_user = user_repository.get_user(user["user_id"])
        if db_user and "yen_per_hour" in db_user:
            user = {**user, "yen_per_hour": int(db_user["yen_per_hour"])}
    return templates.TemplateResponse(request, "settings.html", {
        "user":     user,
        "active":   "settings",
        "messages": {},
        **_monthly_context(user),
    })


# ─── プロフィール更新 ─────────────────────────────────────────────────

@router.post("/profile")
async def update_profile(
    name:  Annotated[str, Form()],
    email: Annotated[str, Form()],
    user:  dict = Depends(get_current_user),
):
    """プロフィール（氏名・メール）を更新する"""
    if USER_TABLE_NAME:
        user_repository.update_user(user["user_id"], name=name, email=email)
    return RedirectResponse(url="/settings", status_code=303)


# ─── パスワード変更 ───────────────────────────────────────────────────

@router.post("/password")
async def update_password(
    request: Request,
    current_password: Annotated[str, Form()],
    new_password:     Annotated[str, Form()],
    confirm_password: Annotated[str, Form()],
    user: dict = Depends(get_current_user),
):
    """パスワードを変更する"""
    def _error_response(msg: str):
        return templates.TemplateResponse(request, "settings.html", {
            "user":     user,
            "active":   "settings",
            "messages": {"password_error": msg},
            **_monthly_context(user),
        }, status_code=400)

    if new_password != confirm_password:
        return _error_response("新しいパスワードが一致しません")

    if USER_TABLE_NAME:
        # DynamoDB からユーザーを取得して現在のパスワードを検証する
        db_user = user_repository.get_user(user["user_id"])
        if db_user and db_user.get("password_hash"):
            if not auth_service.verify_password(current_password, db_user["password_hash"]):
                return _error_response("現在のパスワードが正しくありません")
        new_hash = auth_service.hash_password(new_password)
        user_repository.update_user(user["user_id"], password_hash=new_hash)

    return RedirectResponse(url="/settings", status_code=303)


# ─── 時給更新 ─────────────────────────────────────────────────────────

@router.post("/salary")
async def update_salary(
    yen_per_hour: Annotated[int, Form()],
    user: dict = Depends(get_current_user),
):
    """時給を更新する"""
    if USER_TABLE_NAME:
        user_repository.update_user(user["user_id"], yen_per_hour=yen_per_hour)
    return RedirectResponse(url="/settings", status_code=303)
