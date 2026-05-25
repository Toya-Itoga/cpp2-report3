"""勤務関連のビジネスロジックを定義するサービス"""

from datetime import datetime
from decimal import Decimal

from src.utils.salary import calc_estimated_salary

# 所定労働時間（分）: 8時間
STANDARD_WORK_MINUTES = 8 * 60


def calc_work_minutes(clock_in: str, clock_out: str) -> int:
    """
    出退勤時刻文字列（HH:MM）から勤務時間（分）を計算する。
    退勤が翌日の場合も考慮しない（同日内の差分）。
    """
    fmt = "%H:%M"
    start = datetime.strptime(clock_in, fmt)
    end   = datetime.strptime(clock_out, fmt)
    diff  = end - start
    return max(0, int(diff.total_seconds() // 60))


def calc_overtime_minutes(
    work_minutes: int,
    standard_minutes: int = STANDARD_WORK_MINUTES,
) -> int:
    """所定労働時間を超えた残業時間（分）を返す。マイナスは 0 とする"""
    return max(0, work_minutes - standard_minutes)


def _to_int(value) -> int:
    """DynamoDBのDecimal型を含む数値をintに変換する"""
    if isinstance(value, Decimal):
        return int(value)
    return int(value) if value is not None else 0


def aggregate_monthly(records: list[dict], yen_per_hour: int) -> dict:
    """
    対象月の勤務レコード一覧から月次サマリーを集計する。
    月次集計は都度計算し、DBには保存しない。

    Args:
        records:      get_monthly_records() が返す勤務レコードのリスト
        yen_per_hour: ユーザーの時給（円）

    Returns:
        dict:
            total_minutes    - 月の総勤務時間（分）
            total_hours_str  - "142h 30m" 形式の文字列
            work_days        - 出勤日数
            overtime_minutes - 月の総残業時間（分）
            overtime_str     - "12h 15m" 形式の文字列
            estimated_salary - 想定月収（円）
    """
    total_minutes    = 0
    overtime_minutes = 0
    work_days        = 0

    for r in records:
        # 休日レコードは集計対象外
        if r.get("status") == "休日":
            continue

        wm = _to_int(r.get("work_minutes", 0))
        om = _to_int(r.get("overtime_minutes", 0))

        if wm > 0:
            work_days        += 1
            total_minutes    += wm
            overtime_minutes += om

    th, tm = divmod(total_minutes, 60)
    oh, om = divmod(overtime_minutes, 60)

    # 想定月収 = 月の総勤務時間（時間換算） × yen_per_hour
    estimated_salary = calc_estimated_salary(total_minutes, yen_per_hour)

    return {
        "total_minutes":    total_minutes,
        "total_hours_str":  f"{th}h {tm:02d}m",
        "work_days":        work_days,
        "overtime_minutes": overtime_minutes,
        "overtime_str":     f"{oh}h {om:02d}m",
        "estimated_salary": estimated_salary,
    }


def format_elapsed(clock_in: str) -> str:
    """
    出勤時刻（HH:MM）から現在までの経過時間を "Xh YYm" 形式で返す。
    出勤していない場合は空文字を返す。
    """
    if not clock_in:
        return ""
    now = datetime.now()
    h, m = map(int, clock_in.split(":"))
    start = now.replace(hour=h, minute=m, second=0, microsecond=0)
    diff = max(0, int((now - start).total_seconds()))
    dh, dm = divmod(diff // 60, 60)
    return f"{dh}h {dm:02d}m"
