"""ダッシュボードルーター"""

import os
import calendar
from decimal import Decimal
from datetime import date, datetime, timezone, timedelta

# Lambda実行環境はUTCのため、日本時間（JST）に変換する
JST = timezone(timedelta(hours=9))

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from repositories import work_repository
from routers.auth import get_current_user
from services import work_service
from utils.salary import format_currency

router = APIRouter(tags=["dashboard"])
_TMPL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "templates")
templates = Jinja2Templates(directory=_TMPL)
templates.env.filters["format_currency"] = format_currency

WORK_TABLE_NAME = os.getenv("WORK_TABLE_NAME")

# 曜日ラベル（月=0 … 日=6）
WEEKDAY_JA = ["月", "火", "水", "木", "金", "土", "日"]


# ─── ヘルパー ─────────────────────────────────────────────────────────

def _elapsed_label(clock_in_str: str | None) -> str | None:
    """出勤時刻（HH:MM）から現在までの経過時間ラベルを返す（JST基準）"""
    if not clock_in_str:
        return None
    now = datetime.now(JST)
    h, m = map(int, clock_in_str.split(":"))
    start = now.replace(hour=h, minute=m, second=0, microsecond=0)
    diff = max(0, int((now - start).total_seconds()))
    dh, dm = divmod(diff // 60, 60)
    return f"{dh}h {dm:02d}m"


def _count_weekdays(year: int, month: int) -> int:
    """指定月の平日数（月-金）を返す"""
    _, days = calendar.monthrange(year, month)
    return sum(
        1 for d in range(1, days + 1)
        if date(year, month, d).weekday() < 5
    )


def _build_daily_bars(
    records: list[dict],
    year: int,
    month: int,
    max_h: int = 10,
    bar_max_px: int = 140,
) -> list[dict]:
    """月次レコードから日別棒グラフデータを生成する。
    SK が WORK#YYYYMMDD 形式なので末尾2桁を日付として使用する。
    """
    _, total_days = calendar.monthrange(year, month)

    # 日付 → 勤務時間（h）のマップを作成する
    day_hours: dict[int, float] = {}
    for r in records:
        sk = r.get("SK", "")
        if not sk.startswith("WORK#"):
            continue
        day = int(sk[-2:])
        wm = int(Decimal(str(r.get("work_minutes") or 0)))
        day_hours[day] = wm / 60

    bars = []
    for d in range(1, total_days + 1):
        v = day_hours.get(d, 0.0)
        pct = min(1.0, v / max_h) if v > 0 else 0
        bars.append({
            "label":     str(d),
            "height_px": max(4, int(pct * bar_max_px)) if v > 0 else 4,
            "accent":    v > 8.5,
        })
    return bars


# ─── ルート ───────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def root():
    return RedirectResponse(url="/dashboard")


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, user: dict = Depends(get_current_user)):
    today = datetime.now(JST).date()
    today_label = f"{today.year}年{today.month}月{today.day}日（{WEEKDAY_JA[today.weekday()]}）"

    # ─── DynamoDB からデータを取得する ────────────────────────────────
    today_record    = {}
    monthly_records = []
    if WORK_TABLE_NAME:
        today_record    = work_repository.get_record(user["user_id"], today) or {}
        monthly_records = work_repository.get_monthly_records(
            user["user_id"], today.year, today.month
        )

    # ─── 当日のステータスを決定する ────────────────────────────────────
    clock_in  = today_record.get("clock_in")
    clock_out = today_record.get("clock_out")
    today_status = today_record.get("status") or (
        "出勤中" if clock_in and not clock_out else
        "退勤済" if clock_out else
        "未出勤"
    )
    elapsed = _elapsed_label(clock_in) if clock_in and not clock_out else None

    # ─── 月次集計する ─────────────────────────────────────────────────
    agg = work_service.aggregate_monthly(monthly_records, user["yen_per_hour"])
    monthly = {
        "total_hours":      agg["total_hours_str"],
        "work_days":        agg["work_days"],
        "total_work_days":  _count_weekdays(today.year, today.month),
        "overtime_hours":   agg["overtime_str"],
        "estimated_salary": agg["estimated_salary"],
        "total_minutes":    agg["total_minutes"],
    }

    return templates.TemplateResponse(request, "dashboard.html", {
        "user":         user,
        "active":       "dashboard",
        "today_label":  today_label,
        "today_status": today_status,
        "clock_in":     clock_in,
        "clock_out":    clock_out,
        "elapsed":      elapsed,
        "monthly":      monthly,
        "daily_bars":   _build_daily_bars(monthly_records, today.year, today.month),
    })
