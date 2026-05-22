"""勤務履歴ルーター"""

import calendar
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from src.routers.auth import get_current_user
from src.utils.salary import calc_estimated_salary, format_currency

router = APIRouter(prefix="/history", tags=["history"])
templates = Jinja2Templates(directory="src/templates")
templates.env.filters["format_currency"] = format_currency

# ダミー勤務データ（日: 勤務時間[h]）
_DUMMY_DATA: dict[int, float] = {
    1: 8.25, 2: 9.33, 5: 8.0, 6: 10.75, 7: 8.0, 8: 7.83, 9: 8.5,
    12: 8.25, 13: 10.67, 14: 8.0, 15: 9.08, 16: 8.0, 19: 8.5, 20: 5.4,
}


def _build_calendar_cells(year: int, month: int, data: dict[int, float]) -> list[dict]:
    """カレンダー表示用のセルリストを生成する"""
    first_weekday, days_in_month = calendar.monthrange(year, month)
    # Pythonのmonthrange: 0=月曜 → 日曜始まりに変換
    start_col = (first_weekday + 1) % 7  # 0=日曜

    cells = []
    for i in range(6 * 7):
        day = i - start_col + 1
        if day < 1 or day > days_in_month:
            cells.append({"day": None, "col": i % 7})
            continue

        col      = i % 7
        is_today = (date.today() == date(year, month, day))
        hours    = data.get(day)

        record = None
        if hours is not None:
            work_minutes  = int(hours * 60)
            h, m          = divmod(work_minutes, 60)
            bar_pct       = min(100, int((hours / 10) * 100))
            record = {
                "work_hours_label": f"{hours:.1f}h",
                "bar_pct":          bar_pct,
                "clock_in":         "09:02",
                "clock_out":        None if (is_today and hours < 8) else "18:30",
                "clock_in_raw":     "09:02",
                "clock_out_raw":    None,
                "duration_label":   f"{h}h {m:02d}m",
                "overtime_label":   "0h 00m",
                "status":           "出勤中" if is_today else None,
                "note":             "",
            }

        cells.append({
            "day":        day,
            "col":        col,
            "is_today":   is_today,
            "is_weekend": col == 0 or col == 6,
            "record":     record,
        })

    return cells


def _monthly_summary(data: dict[int, float], yen_per_hour: int) -> dict:
    """月次サマリーを集計する"""
    total_minutes  = int(sum(v * 60 for v in data.values()))
    work_days      = len(data)
    h, m           = divmod(total_minutes, 60)
    overtime_min   = max(0, total_minutes - work_days * 8 * 60)
    oh, om         = divmod(overtime_min, 60)
    salary         = calc_estimated_salary(total_minutes, yen_per_hour)
    total_hours_f  = total_minutes / 60

    return {
        "total_hours":       f"{h}h {m:02d}m",
        "work_days":         work_days,
        "overtime_hours":    f"{oh}h {om:02d}m",
        "estimated_salary":  salary,
        "total_hours_float": total_hours_f,
    }


# ─── 勤務履歴一覧 ────────────────────────────────────────────────────
@router.get("", response_class=HTMLResponse)
async def history_page(
    request: Request,
    user: dict = Depends(get_current_user),
    year:  int = 0,
    month: int = 0,
):
    today = date.today()
    if year == 0:
        year = today.year
    if month == 0:
        month = today.month

    # 前後月の計算
    prev_month = month - 1 or 12
    prev_year  = year - (1 if month == 1 else 0)
    next_month = month % 12 + 1
    next_year  = year + (1 if month == 12 else 0)

    # TODO: DynamoDBから実データを取得する
    data    = _DUMMY_DATA
    cells   = _build_calendar_cells(year, month, data)
    monthly = _monthly_summary(data, user["yen_per_hour"])

    return templates.TemplateResponse(request, "history.html", {
        "user":           user,
        "active":         "history",
        "year":           year,
        "month":          month,
        "prev_year":      prev_year,
        "prev_month":     prev_month,
        "next_year":      next_year,
        "next_month":     next_month,
        "calendar_cells": cells,
        "monthly":        monthly,
    })


# ─── 勤務記録の編集 ───────────────────────────────────────────────────
@router.post("/edit/{year}/{month}/{day}")
async def edit_record(
    year:  int,
    month: int,
    day:   int,
    clock_in:  Annotated[str | None, Form()] = None,
    clock_out: Annotated[str | None, Form()] = None,
    note:      Annotated[str | None, Form()] = None,
    user: dict = Depends(get_current_user),
):
    """勤務記録を更新してDynamoDBに保存する"""
    # TODO: DynamoDBの該当日レコードを更新する
    return RedirectResponse(url=f"/history?year={year}&month={month}", status_code=303)
