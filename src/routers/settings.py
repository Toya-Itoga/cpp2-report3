"""設定ルーター"""

from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from src.routers.auth import get_current_user
from src.utils.salary import calc_estimated_salary, format_currency

router = APIRouter(prefix="/settings", tags=["settings"])
templates = Jinja2Templates(directory="src/templates")
templates.env.filters["format_currency"] = format_currency

# 今月の勤務サマリー（ダミー）
_MONTHLY_MINUTES = 142 * 60 + 30
_MONTHLY_HOURS_F = _MONTHLY_MINUTES / 60


@router.get("", response_class=HTMLResponse)
async def settings_page(
    request: Request,
    user: dict = Depends(get_current_user),
):
    estimated_salary = calc_estimated_salary(_MONTHLY_MINUTES, user["yen_per_hour"])

    return templates.TemplateResponse(request, "settings.html", {
        "user":                   user,
        "active":                 "settings",
        "monthly_estimated_salary": estimated_salary,
        "monthly_total_hours":    f"{_MONTHLY_HOURS_F:.1f}",
        "messages":               {},
    })


@router.post("/profile")
async def update_profile(
    request: Request,
    name:  Annotated[str, Form()],
    email: Annotated[str, Form()],
    user:  dict = Depends(get_current_user),
):
    """プロフィール（氏名・メール）を更新する"""
    # TODO: DynamoDBのユーザーレコードを更新する
    return RedirectResponse(url="/settings", status_code=303)


@router.post("/password")
async def update_password(
    request: Request,
    current_password: Annotated[str, Form()],
    new_password:     Annotated[str, Form()],
    confirm_password: Annotated[str, Form()],
    user: dict = Depends(get_current_user),
):
    """パスワードを変更する"""
    if new_password != confirm_password:
        estimated_salary = calc_estimated_salary(_MONTHLY_MINUTES, user["yen_per_hour"])
        return templates.TemplateResponse(request, "settings.html", {
            "user":                   user,
            "active":                 "settings",
            "monthly_estimated_salary": estimated_salary,
            "monthly_total_hours":    f"{_MONTHLY_HOURS_F:.1f}",
            "messages":               {"password_error": "新しいパスワードが一致しません"},
        }, status_code=400)

    # TODO: 現在のパスワードを検証し、DynamoDBを更新する
    return RedirectResponse(url="/settings", status_code=303)


@router.post("/salary")
async def update_salary(
    yen_per_hour: Annotated[int, Form()],
    user: dict = Depends(get_current_user),
):
    """時給を更新する"""
    # TODO: DynamoDBのユーザーレコードを更新する
    return RedirectResponse(url="/settings", status_code=303)
