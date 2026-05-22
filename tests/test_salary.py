"""src/utils/salary.py のユニットテスト"""

import pytest
from src.utils.salary import calc_estimated_salary, format_currency


class TestCalcEstimatedSalary:
    def test_basic(self):
        """8時間 × ¥1,000 = ¥8,000"""
        assert calc_estimated_salary(480, 1000) == 8000

    def test_with_minutes(self):
        """90分 × ¥1,200 = ¥1,800"""
        assert calc_estimated_salary(90, 1200) == 1800

    def test_rounds_half_up(self):
        """小数点以下は四捨五入される"""
        # 1分 × ¥1000 = 16.666... → 17
        assert calc_estimated_salary(1, 1000) == 17

    def test_zero_minutes(self):
        """勤務時間が0分の場合は0円"""
        assert calc_estimated_salary(0, 1500) == 0

    def test_zero_salary(self):
        """時給が0円の場合は0円"""
        assert calc_estimated_salary(480, 0) == 0

    def test_monthly_scenario(self):
        """142.5h × ¥1,500 = ¥213,750"""
        minutes = int(142.5 * 60)
        assert calc_estimated_salary(minutes, 1500) == 213750


class TestFormatCurrency:
    def test_thousands(self):
        assert format_currency(1000) == "1,000"

    def test_millions(self):
        assert format_currency(1000000) == "1,000,000"

    def test_small(self):
        assert format_currency(500) == "500"

    def test_zero(self):
        assert format_currency(0) == "0"
