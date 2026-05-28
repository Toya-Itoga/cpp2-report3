"""打刻ルーター"""

import os
from datetime import date, datetime  # datetime は clock_in/clock_out エンドポイントで使用

import boto3
from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from repositories import work_repository
from routers.auth import get_current_user
from services import work_service
from utils.salary import format_currency

router = APIRouter(prefix="/punch", tags=["punch"])
_TMPL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "templates")
templates = Jinja2Templates(directory=_TMPL)
templates.env.filters["format_currency"] = format_currency

WORK_TABLE_NAME = os.getenv("WORK_TABLE_NAME")
_work_table = None
if WORK_TABLE_NAME:
    _work_table = boto3.resource(
        "dynamodb",
        region_name=os.getenv("DYNAMODB_REGION", "ap-northeast-1"),
        endpoint_url=os.getenv("DYNAMODB_ENDPOINT"),
    ).Table(WORK_TABLE_NAME)


@router.get("", response_class=HTMLResponse)
async def punch_page(request: Request, user: dict = Depends(get_current_user)):
    today = date.today()
    weekday_ja = ["月", "火", "水", "木", "金", "土", "日"]
    date_label = f"{today.year}年 {today.month}月 {today.day}日 ({weekday_ja[today.weekday()]})"

    record = {}
    if _work_table is not None:
        response = _work_table.get_item(
            Key={
                "PK": f"USER#{user['user_id']}",
                "SK": f"WORK#{today:%Y%m%d}",
            },
            ProjectionExpression="clock_in, clock_out, #status",
            ExpressionAttributeNames={"#status": "status"},
        )
        record = response.get("Item", {})

    clock_in     = record.get("clock_in")
    clock_out    = record.get("clock_out")
    today_status = record.get("status") or ("出勤中" if clock_in and not clock_out else "退勤済" if clock_out else "未出勤")

    return templates.TemplateResponse(request, "punch.html", {
        "user":         user,
        "active":       "punch",
        "date_label":   date_label,
        "today_status": today_status,
        "clock_in":     clock_in,
        "clock_out":    clock_out,
    })


@router.post("/clock-in")
async def clock_in(request: Request, user: dict = Depends(get_current_user)):
    """出勤打刻処理: 現在時刻を WORK#YYYYMMDD レコードに書き込む"""
    time_str = datetime.now().strftime("%H:%M")
    today    = date.today()

    if WORK_TABLE_NAME:
        try:
            work_repository.clock_in(user["user_id"], today, time_str)
        except ClientError as e:
            # 既に当日レコードが存在する場合はスキップ（二重打刻防止）
            if e.response["Error"]["Code"] != "ConditionalCheckFailedException":
                raise

    return RedirectResponse(url="/punch", status_code=303)


@router.post("/clock-out")
async def clock_out(request: Request, user: dict = Depends(get_current_user)):
    """退勤打刻処理: clock_in との差分から work_minutes・overtime_minutes を算出して更新する"""
    time_str = datetime.now().strftime("%H:%M")
    today    = date.today()

    if WORK_TABLE_NAME:
        record = work_repository.get_record(user["user_id"], today)
        # 出勤打刻済みのレコードがある場合のみ更新する
        if record and record.get("clock_in"):
            wm = work_service.calc_work_minutes(record["clock_in"], time_str)
            om = work_service.calc_overtime_minutes(wm)
            work_repository.clock_out(user["user_id"], today, time_str, wm, om)

    return RedirectResponse(url="/dashboard", status_code=303)
