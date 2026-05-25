"""WorkテーブルのDynamoDB操作を定義するリポジトリ"""

import os
from datetime import date
from typing import Optional

import boto3
from boto3.dynamodb.conditions import Key


def _get_table():
    """環境変数からDynamoDBテーブルリソースを生成して返す"""
    table_name = os.getenv("WORK_TABLE_NAME")
    if not table_name:
        raise RuntimeError("WORK_TABLE_NAME が設定されていません")

    dynamodb = boto3.resource(
        "dynamodb",
        region_name=os.getenv("DYNAMODB_REGION", "ap-northeast-1"),
        endpoint_url=os.getenv("DYNAMODB_ENDPOINT"),  # ローカル: http://localhost:5434
    )
    return dynamodb.Table(table_name)


def _to_sk(target_date: date) -> str:
    """date を WORK#YYYYMMDD 形式のSKに変換する"""
    return f"WORK#{target_date:%Y%m%d}"


def _to_pk(user_id: str) -> str:
    return f"USER#{user_id}"


# ─── 読み取り ────────────────────────────────────────────────────────────

def get_record(user_id: str, target_date: date) -> Optional[dict]:
    """指定日の勤務レコードを取得する。存在しない場合は None を返す"""
    table = _get_table()
    response = table.get_item(
        Key={
            "PK": _to_pk(user_id),
            "SK": _to_sk(target_date),
        }
    )
    return response.get("Item")


def get_monthly_records(user_id: str, year: int, month: int) -> list[dict]:
    """
    指定月の全勤務レコードを取得する。
    SK の前方一致（WORK#YYYYMM）でクエリする。
    """
    table = _get_table()
    sk_prefix = f"WORK#{year:04d}{month:02d}"
    response = table.query(
        KeyConditionExpression=(
            Key("PK").eq(_to_pk(user_id)) &
            Key("SK").begins_with(sk_prefix)
        )
    )
    return response.get("Items", [])


# ─── 書き込み ────────────────────────────────────────────────────────────

def clock_in(user_id: str, target_date: date, time_str: str) -> None:
    """
    出勤打刻レコードを新規作成する。
    既に当日レコードがある場合は clock_in のみ上書きする。
    """
    table = _get_table()
    table.put_item(
        Item={
            "PK":               _to_pk(user_id),
            "SK":               _to_sk(target_date),
            "clock_in":         time_str,
            "clock_out":        None,
            "work_minutes":     0,
            "overtime_minutes": 0,
            "status":           "出勤中",
        },
        # 既存レコードがあれば clock_in だけ更新する
        ConditionExpression="attribute_not_exists(PK)",
    )


def clock_out(
    user_id: str,
    target_date: date,
    time_str: str,
    work_minutes: int,
    overtime_minutes: int,
) -> None:
    """退勤打刻を記録し、勤務時間・残業時間・ステータスを更新する"""
    table = _get_table()
    table.update_item(
        Key={
            "PK": _to_pk(user_id),
            "SK": _to_sk(target_date),
        },
        UpdateExpression=(
            "SET clock_out = :co, work_minutes = :wm, "
            "overtime_minutes = :om, #status = :st"
        ),
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={
            ":co": time_str,
            ":wm": work_minutes,
            ":om": overtime_minutes,
            ":st": "退勤済",
        },
    )


def update_record(
    user_id: str,
    target_date: date,
    clock_in: Optional[str] = None,
    clock_out: Optional[str] = None,
    work_minutes: Optional[int] = None,
    overtime_minutes: Optional[int] = None,
    note: Optional[str] = None,
) -> None:
    """勤務履歴の手動編集で任意フィールドを更新する"""
    table = _get_table()

    expressions: list[str] = []
    attr_values: dict = {}
    # status は DynamoDB 予約語
    attr_names: dict = {"#status": "status"}

    if clock_in is not None:
        expressions.append("clock_in = :ci")
        attr_values[":ci"] = clock_in

    if clock_out is not None:
        expressions.append("clock_out = :co, #status = :st")
        attr_values[":co"] = clock_out
        attr_values[":st"] = "退勤済"

    if work_minutes is not None:
        expressions.append("work_minutes = :wm")
        attr_values[":wm"] = work_minutes

    if overtime_minutes is not None:
        expressions.append("overtime_minutes = :om")
        attr_values[":om"] = overtime_minutes

    if note is not None:
        expressions.append("note = :note")
        attr_values[":note"] = note

    if not expressions:
        return

    table.update_item(
        Key={
            "PK": _to_pk(user_id),
            "SK": _to_sk(target_date),
        },
        UpdateExpression="SET " + ", ".join(expressions),
        ExpressionAttributeNames=attr_names,
        ExpressionAttributeValues=attr_values,
    )
