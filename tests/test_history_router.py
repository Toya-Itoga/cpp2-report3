"""src/routers/history.py のユニットテスト"""

import importlib
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

DUMMY_USER = {"user_id": "test_user", "name": "テストユーザー", "yen_per_hour": 1500}


def _make_app(hist_module) -> TestClient:
    app = FastAPI()
    app.include_router(hist_module.router)
    app.dependency_overrides[hist_module.get_current_user] = lambda: DUMMY_USER
    return TestClient(app, raise_server_exceptions=True)


def _make_record(day: int, ci: str, co: str, wm: int, om: int, status: str = "退勤済") -> dict:
    return {
        "PK":               "USER#test_user",
        "SK":               f"WORK#202605{day:02d}",
        "clock_in":         ci,
        "clock_out":        co,
        "work_minutes":     wm,
        "overtime_minutes": om,
        "status":           status,
    }


# ─── _build_calendar_cells のテスト ──────────────────────────────────

class TestBuildCalendarCells:
    def test_total_cell_count(self):
        """6週×7列 = 42セルが生成されること"""
        import src.routers.history as hist
        importlib.reload(hist)
        cells = hist._build_calendar_cells(2026, 5, [])
        assert len(cells) == 42

    def test_no_record_day_has_no_record(self):
        """レコードがない日の record は None であること"""
        import src.routers.history as hist
        importlib.reload(hist)
        cells = hist._build_calendar_cells(2026, 5, [])
        day1 = next(c for c in cells if c.get("day") == 1)
        assert day1["record"] is None

    def test_record_day_has_record_data(self):
        """レコードがある日は record に clock_in・duration_label が含まれること"""
        import src.routers.history as hist
        importlib.reload(hist)
        records = [_make_record(1, "09:00", "18:00", 540, 60)]
        cells = hist._build_calendar_cells(2026, 5, records)
        day1 = next(c for c in cells if c.get("day") == 1)
        assert day1["record"] is not None
        assert day1["record"]["clock_in"]       == "09:00"
        assert day1["record"]["duration_label"] == "9h 00m"
        assert day1["record"]["overtime_label"] == "1h 00m"

    def test_holiday_record_has_no_record_block(self):
        """休日レコードは record=None として扱われること"""
        import src.routers.history as hist
        importlib.reload(hist)
        records = [{"SK": "WORK#20260501", "work_minutes": 0, "overtime_minutes": 0, "status": "休日"}]
        cells = hist._build_calendar_cells(2026, 5, records)
        day1 = next(c for c in cells if c.get("day") == 1)
        assert day1["record"] is None

    def test_decimal_type_from_dynamodb(self):
        """DynamoDB が返す Decimal 型でもエラーが出ないこと"""
        import src.routers.history as hist
        importlib.reload(hist)
        records = [{
            "SK":               "WORK#20260501",
            "clock_in":         "09:00",
            "clock_out":        "18:00",
            "work_minutes":     Decimal("540"),
            "overtime_minutes": Decimal("60"),
            "status":           "退勤済",
        }]
        cells = hist._build_calendar_cells(2026, 5, records)
        day1 = next(c for c in cells if c.get("day") == 1)
        assert day1["record"]["duration_label"] == "9h 00m"

    def test_weekend_flag(self):
        """2026年5月1日（金）は is_weekend=False であること"""
        import src.routers.history as hist
        importlib.reload(hist)
        cells = hist._build_calendar_cells(2026, 5, [])
        day1 = next(c for c in cells if c.get("day") == 1)
        assert day1["is_weekend"] is False

    def test_sunday_is_weekend(self):
        """2026年5月3日（日）は is_weekend=True であること"""
        import src.routers.history as hist
        importlib.reload(hist)
        cells = hist._build_calendar_cells(2026, 5, [])
        day3 = next(c for c in cells if c.get("day") == 3)
        assert day3["is_weekend"] is True


# ─── history_page エンドポイントのテスト ─────────────────────────────

class TestHistoryPage:
    def test_calls_get_monthly_records(self, monkeypatch):
        """WORK_TABLE_NAME が設定されているとき get_monthly_records が呼ばれること"""
        monkeypatch.setenv("WORK_TABLE_NAME", "kintai-works")

        import src.routers.history as hist
        importlib.reload(hist)

        mock_get = MagicMock(return_value=[])
        with patch.object(hist.work_repository, "get_monthly_records", mock_get):
            resp = _make_app(hist).get("/history")

        assert resp.status_code == 200
        mock_get.assert_called_once()

    def test_skips_dynamodb_when_no_table_name(self, monkeypatch):
        """WORK_TABLE_NAME 未設定のとき get_monthly_records が呼ばれないこと"""
        monkeypatch.delenv("WORK_TABLE_NAME", raising=False)

        import src.routers.history as hist
        importlib.reload(hist)

        mock_get = MagicMock()
        with patch.object(hist.work_repository, "get_monthly_records", mock_get):
            resp = _make_app(hist).get("/history")

        assert resp.status_code == 200
        mock_get.assert_not_called()


# ─── edit_record エンドポイントのテスト ──────────────────────────────

class TestEditRecord:
    def test_calls_update_record_with_computed_minutes(self, monkeypatch):
        """clock_in・clock_out が揃っているとき work_minutes が計算されて update_record が呼ばれること"""
        monkeypatch.setenv("WORK_TABLE_NAME", "kintai-works")

        import src.routers.history as hist
        importlib.reload(hist)

        mock_update = MagicMock()
        with patch.object(hist.work_repository, "update_record", mock_update):
            resp = _make_app(hist).post(
                "/history/edit/2026/5/1",
                data={"clock_in": "09:00", "clock_out": "18:00"},
                follow_redirects=False,
            )

        assert resp.status_code == 303
        mock_update.assert_called_once()
        call = mock_update.call_args
        assert call.args[0] == "test_user"
        assert call.kwargs["clock_in"]       == "09:00"
        assert call.kwargs["clock_out"]      == "18:00"
        assert call.kwargs["work_minutes"]   == 540
        assert call.kwargs["overtime_minutes"] == 60

    def test_no_work_minutes_when_clock_out_missing(self, monkeypatch):
        """clock_out がない場合は work_minutes を計算しないこと"""
        monkeypatch.setenv("WORK_TABLE_NAME", "kintai-works")

        import src.routers.history as hist
        importlib.reload(hist)

        mock_update = MagicMock()
        with patch.object(hist.work_repository, "update_record", mock_update):
            resp = _make_app(hist).post(
                "/history/edit/2026/5/1",
                data={"clock_in": "09:00"},
                follow_redirects=False,
            )

        assert resp.status_code == 303
        call = mock_update.call_args
        assert call.kwargs["work_minutes"]   is None
        assert call.kwargs["overtime_minutes"] is None

    def test_skips_dynamodb_when_no_table_name(self, monkeypatch):
        """WORK_TABLE_NAME 未設定のとき update_record が呼ばれないこと"""
        monkeypatch.delenv("WORK_TABLE_NAME", raising=False)

        import src.routers.history as hist
        importlib.reload(hist)

        mock_update = MagicMock()
        with patch.object(hist.work_repository, "update_record", mock_update):
            resp = _make_app(hist).post(
                "/history/edit/2026/5/1",
                data={"clock_in": "09:00", "clock_out": "18:00"},
                follow_redirects=False,
            )

        assert resp.status_code == 303
        mock_update.assert_not_called()

    def test_returns_html_snippet_for_htmx_request(self, monkeypatch):
        """HX-Request ヘッダーがある場合は 200 でカレンダーセルと保存メッセージを返すこと"""
        monkeypatch.setenv("WORK_TABLE_NAME", "kintai-works")

        import src.routers.history as hist
        importlib.reload(hist)

        with (
            patch.object(hist.work_repository, "update_record",       MagicMock()),
            patch.object(hist.work_repository, "get_monthly_records",  MagicMock(return_value=[])),
        ):
            resp = _make_app(hist).post(
                "/history/edit/2026/5/1",
                data={"clock_in": "09:00", "clock_out": "18:00"},
                headers={"HX-Request": "true"},
                follow_redirects=False,
            )

        assert resp.status_code == 200
        assert "保存しました" in resp.text

    def test_htmx_response_contains_calendar_cells(self, monkeypatch):
        """HX-Request ヘッダーがある場合はカレンダーセルが含まれること"""
        monkeypatch.setenv("WORK_TABLE_NAME", "kintai-works")

        import src.routers.history as hist
        importlib.reload(hist)

        record = _make_record(1, "09:00", "18:00", 540, 60)
        with (
            patch.object(hist.work_repository, "update_record",       MagicMock()),
            patch.object(hist.work_repository, "get_monthly_records",  MagicMock(return_value=[record])),
        ):
            resp = _make_app(hist).post(
                "/history/edit/2026/5/1",
                data={"clock_in": "09:00", "clock_out": "18:00"},
                headers={"HX-Request": "true"},
                follow_redirects=False,
            )

        assert resp.status_code == 200
        # カレンダーセルと OOB フィードバックが両方含まれること
        assert "cal-cell" in resp.text
        assert "panel-feedback" in resp.text
