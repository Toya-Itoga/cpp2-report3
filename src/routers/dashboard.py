"""ダッシュボードルーター"""

import calendar
from datetime import date, datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from src.routers.auth import get_current_user
from src.utils.salary import calc_estimated_salary, format_currency

router = APIRouter(tags=["dashboard"])
templates = Jinja2Templates(directory="src/templates")
templates.env.filters["format_currency"] = format_currency


def _make_dummy_monthly(yen_per_hour: int) -> dict:
    """ダッシュボード用のダミー月次データを返す"""
    total_minutes = 142 * 60 + 30
    return {
        "total_hours":       "142h 30m",
        "work_days":         17,
        "total_work_days":   20,
        "overtime_hours":    "12h 15m",
        "estimated_salary":  calc_estimated_salary(total_minutes, yen_per_hour),
        "total_minutes":     total_minutes,
    }


def _make_daily_bars(work_data: list[float], max_h: int = 10, bar_max_px: int = 140) -> list[dict]:
    """日別棒グラフ用データを生成する"""
    bars = []
    for i, v in enumerate(work_data):
        pct = min(1.0, v / max_h)
        bars.append({
            "label":     str(i + 1),
            "height_px": max(4, int(pct * bar_max_px)),
            "accent":    v > 8.5,
        })
    return bars


def _elapsed_label(clock_in_str: str | None) -> str | None:
    """出勤時刻（HH:MM）から現在までの経過時間ラベルを返す"""
    if not clock_in_str:
        return None
    now = datetime.now()
    h, m = map(int, clock_in_str.split(":"))
    start = now.replace(hour=h, minute=m, second=0, microsecond=0)
    diff = max(0, int((now - start).total_seconds()))
    dh, dm = divmod(diff // 60, 60)
    return f"{dh}h {dm:02d}m"


# ─── ルート ───────────────────────────────────────────────────────────
@router.get("/", response_class=HTMLResponse)
async def root():
    return RedirectResponse(url="/dashboard")


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, user: dict = Depends(get_current_user)):
    today = date.today()
    weekday_ja = ["月", "火", "水", "木", "金", "土", "日"]
    today_label = f"{today.year}年{today.month}月{today.day}日（{weekday_ja[today.weekday()]}）"

    # TODO: DynamoDBから当日の勤務レコードを取得する
    clock_in     = "09:02"   # ダミー
    clock_out    = None       # ダミー（出勤中）
    today_status = "出勤中"
    elapsed      = _elapsed_label(clock_in)

    monthly  = _make_dummy_monthly(user["yen_per_hour"])
    raw_data = [8, 7.5, 8, 9, 6, 0, 0, 8, 8.5, 9, 7, 8, 0, 0, 8, 9, 10, 8, 7, 8.5, 5.5, 0, 0]
    bars     = _make_daily_bars(raw_data)

    recent_records = [
        {"date_label": "5/19 (火)", "clock_in": "09:00", "clock_out": "18:30", "duration_label": "8h 30m"},
        {"date_label": "5/18 (月)", "clock_in": "09:05", "clock_out": "18:15", "duration_label": "8h 10m"},
        {"date_label": "5/17 (日)", "clock_in": None,    "clock_out": None,    "duration_label": "休"},
        {"date_label": "5/16 (土)", "clock_in": None,    "clock_out": None,    "duration_label": "休"},
        {"date_label": "5/15 (金)", "clock_in": "08:55", "clock_out": "19:00", "duration_label": "9h 05m"},
    ]

    return templates.TemplateResponse(request, "dashboard.html", {
        "user":           user,
        "active":         "dashboard",
        "today_label":    today_label,
        "today_status":   today_status,
        "clock_in":       clock_in,
        "clock_out":      clock_out,
        "elapsed":        elapsed,
        "monthly":        monthly,
        "daily_bars":     bars,
        "recent_records": recent_records,
    })
