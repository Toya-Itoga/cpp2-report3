"""src/services/work_service.py のユニットテスト"""

import pytest
from src.services.work_service import (
    calc_work_minutes,
    calc_overtime_minutes,
    aggregate_monthly,
    STANDARD_WORK_MINUTES,
)


class TestCalcWorkMinutes:
    def test_basic(self):
        """09:00 - 18:00 = 540分"""
        assert calc_work_minutes("09:00", "18:00") == 540

    def test_with_odd_minutes(self):
        """08:55 - 19:00 = 605分 (10h 5m)"""
        assert calc_work_minutes("08:55", "19:00") == 605

    def test_exact_8h(self):
        """ぴったり8時間 = 480分"""
        assert calc_work_minutes("09:00", "17:00") == 480

    def test_short_work(self):
        """1時間だけ = 60分"""
        assert calc_work_minutes("10:00", "11:00") == 60

    def test_same_time_returns_zero(self):
        """同じ時刻 = 0分"""
        assert calc_work_minutes("09:00", "09:00") == 0


class TestCalcOvertimeMinutes:
    def test_no_overtime(self):
        """所定内 (480分) = 残業なし"""
        assert calc_overtime_minutes(480) == 0

    def test_overtime(self):
        """540分 - 480分 = 60分の残業"""
        assert calc_overtime_minutes(540) == 60

    def test_short_day_no_negative(self):
        """早退 (360分) = 残業なし（マイナスは 0 に丸める）"""
        assert calc_overtime_minutes(360) == 0

    def test_custom_standard(self):
        """所定 360分の場合に 420分 → 60分残業"""
        assert calc_overtime_minutes(420, standard_minutes=360) == 60


class TestAggregateMonthly:
    def _make_record(self, work_minutes: int, overtime_minutes: int) -> dict:
        return {
            "work_minutes":     work_minutes,
            "overtime_minutes": overtime_minutes,
            "status":           "退勤済",
        }

    def test_empty_records(self):
        """レコードなし = ゼロ集計"""
        result = aggregate_monthly([], yen_per_hour=1000)
        assert result["total_minutes"]    == 0
        assert result["work_days"]        == 0
        assert result["overtime_minutes"] == 0
        assert result["estimated_salary"] == 0

    def test_basic_aggregation(self):
        """2日 × 480分 = 960分, 出勤日数2, 想定月収は calc_estimated_salary に準拠"""
        records = [self._make_record(480, 0), self._make_record(480, 0)]
        result  = aggregate_monthly(records, yen_per_hour=1000)
        assert result["total_minutes"] == 960
        assert result["work_days"]     == 2
        # 960分 = 16時間 → 1000 × 16 = 16000円
        assert result["estimated_salary"] == 16000

    def test_overtime_included(self):
        """残業時間も正しく集計される"""
        records = [
            self._make_record(540, 60),  # 9h, 1h残業
            self._make_record(600, 120), # 10h, 2h残業
        ]
        result = aggregate_monthly(records, yen_per_hour=1500)
        assert result["total_minutes"]    == 1140
        assert result["overtime_minutes"] == 180

    def test_holiday_records_excluded(self):
        """休日レコードは集計から除外される"""
        records = [
            self._make_record(480, 0),
            {"work_minutes": 0, "overtime_minutes": 0, "status": "休日"},
        ]
        result = aggregate_monthly(records, yen_per_hour=1000)
        assert result["work_days"]     == 1
        assert result["total_minutes"] == 480

    def test_hours_str_format(self):
        """合計時間の文字列フォーマットが正しいこと"""
        records = [self._make_record(90, 0)]  # 1h 30m
        result  = aggregate_monthly(records, yen_per_hour=1000)
        assert result["total_hours_str"] == "1h 30m"

    def test_zero_work_minutes_excluded(self):
        """work_minutes が 0 のレコードは出勤日数に含めない"""
        records = [
            self._make_record(480, 0),
            self._make_record(0, 0),  # 出勤のみで退勤なし = work_minutes未設定扱い
        ]
        result = aggregate_monthly(records, yen_per_hour=1000)
        assert result["work_days"] == 1

    def test_decimal_type_from_dynamodb(self):
        """DynamoDB から返る Decimal 型も正しく処理される"""
        from decimal import Decimal
        records = [
            {
                "work_minutes":     Decimal("480"),
                "overtime_minutes": Decimal("60"),
                "status":           "退勤済",
            }
        ]
        result = aggregate_monthly(records, yen_per_hour=1000)
        assert result["total_minutes"]    == 480
        assert result["overtime_minutes"] == 60
