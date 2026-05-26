"""src/routers/punch.py の clock_in・clock_out エンドポイントのユニットテスト"""

import importlib
import pytest
from unittest.mock import MagicMock, patch
from botocore.exceptions import ClientError
from fastapi import FastAPI
from fastapi.testclient import TestClient

# ─── テスト用ダミーユーザー ────────────────────────────────────────────────

DUMMY_USER = {"user_id": "test_user", "name": "テストユーザー", "yen_per_hour": 1500}


def _make_client_error(code: str) -> ClientError:
    return ClientError(
        {"Error": {"Code": code, "Message": ""}},
        "PutItem",
    )


def _make_app(punch_module) -> TestClient:
    """punch_module の router を使った TestClient を返す。
    Depends(get_current_user) を DUMMY_USER を返す関数で上書きする。
    """
    app = FastAPI()
    app.include_router(punch_module.router)
    # FastAPI の dependency_overrides で認証依存を置き換える
    app.dependency_overrides[punch_module.get_current_user] = lambda: DUMMY_USER
    return TestClient(app, raise_server_exceptions=True)


# ─── clock_in のテスト ────────────────────────────────────────────────────

class TestClockIn:
    def test_calls_repository_clock_in(self, monkeypatch):
        """WORK_TABLE_NAME が設定されているとき work_repository.clock_in が呼ばれること"""
        monkeypatch.setenv("WORK_TABLE_NAME", "kintai-works")

        import src.routers.punch as punch_module
        importlib.reload(punch_module)

        mock_clock_in = MagicMock()

        with patch.object(punch_module.work_repository, "clock_in", mock_clock_in):
            client = _make_app(punch_module)
            resp = client.post("/punch/clock-in", follow_redirects=False)

        assert resp.status_code == 303
        mock_clock_in.assert_called_once()
        args = mock_clock_in.call_args.args
        assert args[0] == "test_user"   # user_id

    def test_skips_if_already_clocked_in(self, monkeypatch):
        """ConditionalCheckFailedException が発生しても例外を送出しないこと（二重打刻防止）"""
        monkeypatch.setenv("WORK_TABLE_NAME", "kintai-works")

        import src.routers.punch as punch_module
        importlib.reload(punch_module)

        with patch.object(
            punch_module.work_repository,
            "clock_in",
            side_effect=_make_client_error("ConditionalCheckFailedException"),
        ):
            client = _make_app(punch_module)
            resp = client.post("/punch/clock-in", follow_redirects=False)

        # 例外を送出せず 303 リダイレクトで終了すること
        assert resp.status_code == 303

    def test_reraises_unexpected_client_error(self, monkeypatch):
        """ConditionalCheckFailedException 以外の ClientError は再送出されること"""
        monkeypatch.setenv("WORK_TABLE_NAME", "kintai-works")

        import src.routers.punch as punch_module
        importlib.reload(punch_module)

        with patch.object(
            punch_module.work_repository,
            "clock_in",
            side_effect=_make_client_error("AccessDeniedException"),
        ):
            client = _make_app(punch_module)
            with pytest.raises(ClientError):
                client.post("/punch/clock-in", follow_redirects=False)

    def test_skips_dynamodb_when_no_table_name(self, monkeypatch):
        """WORK_TABLE_NAME 未設定のとき work_repository.clock_in が呼ばれないこと"""
        monkeypatch.delenv("WORK_TABLE_NAME", raising=False)

        import src.routers.punch as punch_module
        importlib.reload(punch_module)

        mock_clock_in = MagicMock()

        with patch.object(punch_module.work_repository, "clock_in", mock_clock_in):
            client = _make_app(punch_module)
            resp = client.post("/punch/clock-in", follow_redirects=False)

        assert resp.status_code == 303
        mock_clock_in.assert_not_called()


# ─── clock_out のテスト ───────────────────────────────────────────────────

class TestClockOut:
    def test_calls_repository_clock_out_with_computed_minutes(self, monkeypatch):
        """clock_in 取得後に work_minutes・overtime_minutes を算出して clock_out が呼ばれること"""
        monkeypatch.setenv("WORK_TABLE_NAME", "kintai-works")

        existing_record = {
            "PK":       "USER#test_user",
            "SK":       "WORK#20260526",
            "clock_in": "09:00",
            "status":   "出勤中",
        }
        mock_get_record = MagicMock(return_value=existing_record)
        mock_clock_out  = MagicMock()

        import src.routers.punch as punch_module
        importlib.reload(punch_module)

        with (
            patch.object(punch_module.work_repository, "get_record",  mock_get_record),
            patch.object(punch_module.work_repository, "clock_out",   mock_clock_out),
            # datetime.now() を 18:00 に固定する
            patch("src.routers.punch.datetime") as mock_dt,
        ):
            from datetime import datetime as real_datetime
            mock_dt.now.return_value = real_datetime(2026, 5, 26, 18, 0, 0)

            client = _make_app(punch_module)
            resp = client.post("/punch/clock-out", follow_redirects=False)

        assert resp.status_code == 303
        mock_clock_out.assert_called_once()
        args = mock_clock_out.call_args.args
        assert args[0] == "test_user"   # user_id
        assert args[2] == "18:00"       # time_str
        assert args[3] == 540           # work_minutes: 09:00-18:00 = 540分
        assert args[4] == 60            # overtime_minutes: 540-480 = 60分

    def test_skips_if_no_record(self, monkeypatch):
        """当日レコードが存在しない場合は clock_out が呼ばれないこと"""
        monkeypatch.setenv("WORK_TABLE_NAME", "kintai-works")

        import src.routers.punch as punch_module
        importlib.reload(punch_module)

        mock_get_record = MagicMock(return_value=None)
        mock_clock_out  = MagicMock()

        with (
            patch.object(punch_module.work_repository, "get_record",  mock_get_record),
            patch.object(punch_module.work_repository, "clock_out",   mock_clock_out),
        ):
            client = _make_app(punch_module)
            resp = client.post("/punch/clock-out", follow_redirects=False)

        assert resp.status_code == 303
        mock_clock_out.assert_not_called()

    def test_skips_if_no_clock_in_in_record(self, monkeypatch):
        """レコードはあるが clock_in が空の場合は clock_out が呼ばれないこと"""
        monkeypatch.setenv("WORK_TABLE_NAME", "kintai-works")

        import src.routers.punch as punch_module
        importlib.reload(punch_module)

        existing_record = {"PK": "USER#test_user", "SK": "WORK#20260526"}
        mock_get_record = MagicMock(return_value=existing_record)
        mock_clock_out  = MagicMock()

        with (
            patch.object(punch_module.work_repository, "get_record",  mock_get_record),
            patch.object(punch_module.work_repository, "clock_out",   mock_clock_out),
        ):
            client = _make_app(punch_module)
            resp = client.post("/punch/clock-out", follow_redirects=False)

        assert resp.status_code == 303
        mock_clock_out.assert_not_called()

    def test_skips_dynamodb_when_no_table_name(self, monkeypatch):
        """WORK_TABLE_NAME 未設定のとき get_record・clock_out が呼ばれないこと"""
        monkeypatch.delenv("WORK_TABLE_NAME", raising=False)

        import src.routers.punch as punch_module
        importlib.reload(punch_module)

        mock_get_record = MagicMock()
        mock_clock_out  = MagicMock()

        with (
            patch.object(punch_module.work_repository, "get_record",  mock_get_record),
            patch.object(punch_module.work_repository, "clock_out",   mock_clock_out),
        ):
            client = _make_app(punch_module)
            resp = client.post("/punch/clock-out", follow_redirects=False)

        assert resp.status_code == 303
        mock_get_record.assert_not_called()
        mock_clock_out.assert_not_called()
