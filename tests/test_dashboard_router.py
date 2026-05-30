"""src/routers/dashboard.py のユニットテスト"""

import importlib
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

DUMMY_USER = {"user_id": "test_user", "name": "テストユーザー", "yen_per_hour": 1500}


def _make_app(dash_module) -> TestClient:
    """dependency_overrides で認証を置き換えた TestClient を返す"""
    app = FastAPI()
    app.include_router(dash_module.router)
    app.dependency_overrides[dash_module.get_current_user] = lambda: DUMMY_USER
    return TestClient(app, raise_server_exceptions=True)


# ─── ヘルパー関数のテスト ────────────────────────────────────────────

class TestCountWeekdays:
    def test_may_2026(self):
        """2026年5月の平日数（月-金）"""
        import src.routers.dashboard as dash
        importlib.reload(dash)
        # 2026-05: 土日が 2(土)・3(日)・9(土)・10(日)・16(土)・17(日)・23(土)・24(日)・30(土)・31(日) = 10日
        # 全日数31日 - 10日 = 21日
        assert dash._count_weekdays(2026, 5) == 21


class TestBuildDailyBars:
    def _make_record(self, day: int, work_minutes: int) -> dict:
        return {
            "SK":           f"WORK#202605{day:02d}",
            "work_minutes": work_minutes,
            "status":       "退勤済",
        }

    def test_bar_count_matches_days_in_month(self):
        """棒の本数が月の日数と一致すること"""
        import src.routers.dashboard as dash
        importlib.reload(dash)
        bars = dash._build_daily_bars([], 2026, 5)
        assert len(bars) == 31  # 5月は31日

    def test_no_record_day_has_min_height(self):
        """レコードがない日は最小高さ（4px）になること"""
        import src.routers.dashboard as dash
        importlib.reload(dash)
        bars = dash._build_daily_bars([], 2026, 5)
        assert bars[0]["height_px"] == 4

    def test_work_day_has_positive_height(self):
        """勤務レコードがある日は高さが 4px 超になること"""
        import src.routers.dashboard as dash
        importlib.reload(dash)
        records = [self._make_record(1, 480)]  # 8h
        bars = dash._build_daily_bars(records, 2026, 5)
        assert bars[0]["height_px"] > 4

    def test_overtime_day_has_accent(self):
        """8.5h 超の日は accent=True になること"""
        import src.routers.dashboard as dash
        importlib.reload(dash)
        records = [self._make_record(1, 540)]  # 9h
        bars = dash._build_daily_bars(records, 2026, 5)
        assert bars[0]["accent"] is True

    def test_no_overtime_no_accent(self):
        """8h の日は accent=False になること"""
        import src.routers.dashboard as dash
        importlib.reload(dash)
        records = [self._make_record(1, 480)]
        bars = dash._build_daily_bars(records, 2026, 5)
        assert bars[0]["accent"] is False

    def test_decimal_type_from_dynamodb(self):
        """DynamoDB が返す Decimal 型も正しく処理されること"""
        import src.routers.dashboard as dash
        importlib.reload(dash)
        records = [{"SK": "WORK#20260501", "work_minutes": Decimal("480"), "status": "退勤済"}]
        bars = dash._build_daily_bars(records, 2026, 5)
        assert bars[0]["height_px"] > 4


# ─── dashboard エンドポイントのテスト ────────────────────────────────

class TestDashboardEndpoint:
    def test_calls_get_record_and_get_monthly_records(self, monkeypatch):
        """WORK_TABLE_NAME が設定されているとき両リポジトリ関数が呼ばれること"""
        monkeypatch.setenv("WORK_TABLE_NAME", "kintai-works")

        import src.routers.dashboard as dash
        importlib.reload(dash)

        mock_get_record   = MagicMock(return_value={})
        mock_get_monthly  = MagicMock(return_value=[])

        with (
            patch.object(dash.work_repository, "get_record",         mock_get_record),
            patch.object(dash.work_repository, "get_monthly_records", mock_get_monthly),
        ):
            client = _make_app(dash)
            resp = client.get("/dashboard")

        assert resp.status_code == 200
        mock_get_record.assert_called_once()
        mock_get_monthly.assert_called_once()

    def test_skips_dynamodb_when_no_table_name(self, monkeypatch):
        """WORK_TABLE_NAME 未設定のとき DB 呼び出しがスキップされること"""
        monkeypatch.delenv("WORK_TABLE_NAME", raising=False)

        import src.routers.dashboard as dash
        importlib.reload(dash)

        mock_get_record  = MagicMock()
        mock_get_monthly = MagicMock()

        with (
            patch.object(dash.work_repository, "get_record",         mock_get_record),
            patch.object(dash.work_repository, "get_monthly_records", mock_get_monthly),
        ):
            client = _make_app(dash)
            resp = client.get("/dashboard")

        assert resp.status_code == 200
        mock_get_record.assert_not_called()
        mock_get_monthly.assert_not_called()

    def test_today_status_is_active_when_clocked_in(self, monkeypatch):
        """clock_in があり clock_out がない場合、出勤中ステータスが返ること"""
        monkeypatch.setenv("WORK_TABLE_NAME", "kintai-works")

        import src.routers.dashboard as dash
        importlib.reload(dash)

        today_record = {"clock_in": "09:00", "clock_out": None, "status": "出勤中"}

        with (
            patch.object(dash.work_repository, "get_record",         return_value=today_record),
            patch.object(dash.work_repository, "get_monthly_records", return_value=[]),
        ):
            client = _make_app(dash)
            resp = client.get("/dashboard")

        assert resp.status_code == 200
        assert "出勤中" in resp.text

    def test_monthly_aggregate_uses_actual_records(self, monkeypatch):
        """月次集計が実レコードから算出されること（ダミー値を使わない）"""
        monkeypatch.setenv("WORK_TABLE_NAME", "kintai-works")

        import src.routers.dashboard as dash
        importlib.reload(dash)

        monthly_records = [
            {
                "PK":               "USER#test_user",
                "SK":               "WORK#20260501",
                "clock_in":         "09:00",
                "clock_out":        "18:00",
                "work_minutes":     540,
                "overtime_minutes": 60,
                "status":           "退勤済",
            }
        ]

        with (
            patch.object(dash.work_repository, "get_record",         return_value={}),
            patch.object(dash.work_repository, "get_monthly_records", return_value=monthly_records),
        ):
            client = _make_app(dash)
            resp = client.get("/dashboard")

        assert resp.status_code == 200
        # 540分 = 9h → 1500円/h × 9h = 13,500円
        assert "13,500" in resp.text
