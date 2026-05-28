"""勤務履歴ルーター"""

import os
import calendar
from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from fastapi.templating import Jinja2Templates

from repositories import work_repository
from routers.auth import get_current_user
from services import work_service
from utils.salary import format_currency

router = APIRouter(prefix="/history", tags=["history"])
_TMPL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "templates")
templates = Jinja2Templates(directory=_TMPL)
templates.env.filters["format_currency"] = format_currency

WORK_TABLE_NAME = os.getenv("WORK_TABLE_NAME")


def _build_calendar_cells(year: int, month: int, records: list[dict]) -> list[dict]:
    """DynamoDB の月次レコードからカレンダー表示用のセルリストを生成する"""
    first_weekday, days_in_month = calendar.monthrange(year, month)
    # Pythonのmonthrange: 0=月曜 → 日曜始まりに変換
    start_col = (first_weekday + 1) % 7  # 0=日曜

    # SK (WORK#YYYYMMDD) から日付 → レコードのマップを作成する
    day_records: dict[int, dict] = {}
    for r in records:
        sk = r.get("SK", "")
        if sk.startswith("WORK#"):
            day = int(sk[-2:])
            day_records[day] = r

    cells = []
    for i in range(6 * 7):
        day = i - start_col + 1
        if day < 1 or day > days_in_month:
            cells.append({"day": None, "col": i % 7})
            continue

        col      = i % 7
        is_today = (date.today() == date(year, month, day))
        r        = day_records.get(day)

        record = None
        if r is not None and r.get("status") != "休日":
            wm = int(Decimal(str(r.get("work_minutes") or 0)))
            om = int(Decimal(str(r.get("overtime_minutes") or 0)))
            hours   = wm / 60
            h, m    = divmod(wm, 60)
            oh, oom = divmod(om, 60)

            record = {
                "work_hours_label": f"{hours:.1f}h",
                "bar_pct":          min(100, int((hours / 10) * 100)),
                "clock_in":         r.get("clock_in"),
                "clock_out":        r.get("clock_out"),
                "clock_in_raw":     r.get("clock_in"),
                "clock_out_raw":    r.get("clock_out"),
                "duration_label":   f"{h}h {m:02d}m",
                "overtime_label":   f"{oh}h {oom:02d}m",
                "status":           r.get("status"),
                "note":             r.get("note", ""),
            }

        cells.append({
            "day":        day,
            "col":        col,
            "is_today":   is_today,
            "is_weekend": col == 0 or col == 6,
            "record":     record,
        })

    return cells


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

    # 対象月の勤務レコードを全件取得する
    records = []
    if WORK_TABLE_NAME:
        records = work_repository.get_monthly_records(user["user_id"], year, month)

    cells   = _build_calendar_cells(year, month, records)
    agg     = work_service.aggregate_monthly(records, user["yen_per_hour"])
    monthly = {
        "total_hours":       agg["total_hours_str"],
        "work_days":         agg["work_days"],
        "overtime_hours":    agg["overtime_str"],
        "estimated_salary":  agg["estimated_salary"],
        "total_hours_float": agg["total_minutes"] / 60,
    }

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
    request: Request,
    year:  int,
    month: int,
    day:   int,
    clock_in:  Annotated[str | None, Form()] = None,
    clock_out: Annotated[str | None, Form()] = None,
    note:      Annotated[str | None, Form()] = None,
    user: dict = Depends(get_current_user),
):
    """勤務記録を更新してDynamoDBに保存する"""
    if WORK_TABLE_NAME:
        target_date = date(year, month, day)

        # clock_in・clock_out が揃っている場合は勤務時間を再計算する
        work_minutes: int | None     = None
        overtime_minutes: int | None = None
        ci = clock_in  or None
        co = clock_out or None
        if ci and co:
            work_minutes     = work_service.calc_work_minutes(ci, co)
            overtime_minutes = work_service.calc_overtime_minutes(work_minutes)

        work_repository.update_record(
            user["user_id"],
            target_date,
            clock_in=ci,
            clock_out=co,
            work_minutes=work_minutes,
            overtime_minutes=overtime_minutes,
            note=note or None,
        )

    # HTMX リクエストのときはカレンダーセルを再レンダリングして返す
    if request.headers.get("HX-Request"):
        updated_records = []
        if WORK_TABLE_NAME:
            updated_records = work_repository.get_monthly_records(user["user_id"], year, month)
        cells = _build_calendar_cells(year, month, updated_records)
        # カレンダーセルの HTML を Jinja2 でレンダリングする
        cells_html = templates.env.get_template("_history_calendar_cells.html").render(
            calendar_cells=cells,
        )
        # OOB スワップで保存結果メッセージを panel-feedback に反映する
        feedback_oob = '<div id="panel-feedback" hx-swap-oob="true"><span style="color: #2e7d32;">✓ 保存しました</span></div>'
        return HTMLResponse(cells_html + feedback_oob)
    return RedirectResponse(url=f"/history?year={year}&month={month}", status_code=303)
