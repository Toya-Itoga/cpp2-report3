"""打刻ルーター"""

from datetime import date, datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from src.routers.auth import get_current_user
from src.utils.salary import format_currency

router = APIRouter(prefix="/punch", tags=["punch"])
templates = Jinja2Templates(directory="src/templates")
templates.env.filters["format_currency"] = format_currency


@router.get("", response_class=HTMLResponse)
async def punch_page(request: Request, user: dict = Depends(get_current_user)):
    today = date.today()
    weekday_ja = ["月", "火", "水", "木", "金", "土", "日"]
    date_label = f"{today.year}年 {today.month}月 {today.day}日 ({weekday_ja[today.weekday()]})"

    # TODO: DynamoDBから当日の打刻レコードを取得する
    clock_in     = "09:02"   # ダミー
    clock_out    = None       # ダミー
    today_status = "出勤中"

    elapsed = None
    if clock_in and not clock_out:
        now = datetime.now()
        h, m = map(int, clock_in.split(":"))
        start = now.replace(hour=h, minute=m, second=0, microsecond=0)
        diff = max(0, int((now - start).total_seconds()))
        dh, dm = divmod(diff // 60, 60)
        elapsed = f"{dh}h {dm:02d}m"

    return templates.TemplateResponse(request, "punch.html", {
        "user":         user,
        "active":       "punch",
        "date_label":   date_label,
        "today_status": today_status,
        "clock_in":     clock_in,
        "clock_out":    clock_out,
        "elapsed":      elapsed,
    })


@router.post("/clock-in")
async def clock_in(request: Request, user: dict = Depends(get_current_user)):
    """出勤打刻処理"""
    # TODO: DynamoDBに出勤レコードを書き込む
    return RedirectResponse(url="/punch", status_code=303)


@router.post("/clock-out")
async def clock_out(request: Request, user: dict = Depends(get_current_user)):
    """退勤打刻処理"""
    # TODO: DynamoDBの退勤時刻を更新する
    return RedirectResponse(url="/dashboard", status_code=303)
