"""想定月収の算出ユーティリティ"""

from decimal import Decimal, ROUND_HALF_UP


def calc_estimated_salary(total_work_minutes: int, yen_per_hour: int) -> int:
    """
    月の総勤務時間（分）と時給から想定月収を算出する。
    小数点以下は四捨五入。
    """
    total_hours = Decimal(total_work_minutes) / Decimal(60)
    salary = total_hours * Decimal(yen_per_hour)
    return int(salary.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def format_currency(value: int) -> str:
    """整数を3桁カンマ区切りの文字列にフォーマットする"""
    return f"{value:,}"
