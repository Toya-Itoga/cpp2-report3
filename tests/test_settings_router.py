"""src/routers/settings.py のユニットテスト"""

import importlib
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

DUMMY_USER = {"user_id": "test_user", "user_name": "test_user", "name": "テストユーザー", "yen_per_hour": 1500}


def _make_app(sett_module) -> TestClient:
    app = FastAPI()
    app.include_router(sett_module.router)
    app.dependency_overrides[sett_module.get_current_user] = lambda: DUMMY_USER
    return TestClient(app, raise_server_exceptions=True)


# ─── settings_page のテスト ───────────────────────────────────────────

class TestSettingsPage:
    def test_calls_get_monthly_records_when_table_set(self, monkeypatch):
        """WORK_TABLE_NAME が設定されているとき月次データ取得が呼ばれること"""
        monkeypatch.setenv("WORK_TABLE_NAME", "kintai-works")
        monkeypatch.delenv("USER_TABLE_NAME", raising=False)

        import src.routers.settings as sett
        importlib.reload(sett)

        mock_get = MagicMock(return_value=[])
        with patch.object(sett.work_repository, "get_monthly_records", mock_get):
            resp = _make_app(sett).get("/settings")

        assert resp.status_code == 200
        mock_get.assert_called_once()

    def test_skips_dynamodb_when_no_table_name(self, monkeypatch):
        """WORK_TABLE_NAME 未設定のとき get_monthly_records が呼ばれないこと"""
        monkeypatch.delenv("WORK_TABLE_NAME", raising=False)
        monkeypatch.delenv("USER_TABLE_NAME", raising=False)

        import src.routers.settings as sett
        importlib.reload(sett)

        mock_get = MagicMock()
        with patch.object(sett.work_repository, "get_monthly_records", mock_get):
            resp = _make_app(sett).get("/settings")

        assert resp.status_code == 200
        mock_get.assert_not_called()


# ─── update_salary のテスト ──────────────────────────────────────────

class TestUpdateSalary:
    def test_calls_update_user_with_yen_per_hour(self, monkeypatch):
        """USER_TABLE_NAME が設定されているとき user_repository.update_user が呼ばれること"""
        monkeypatch.setenv("USER_TABLE_NAME", "kintai-users")

        import src.routers.settings as sett
        importlib.reload(sett)

        mock_update = MagicMock()
        with patch.object(sett.user_repository, "update_user", mock_update):
            resp = _make_app(sett).post(
                "/settings/salary",
                data={"yen_per_hour": "2000"},
                follow_redirects=False,
            )

        assert resp.status_code == 303
        mock_update.assert_called_once_with("test_user", "test_user", yen_per_hour=2000)

    def test_skips_dynamodb_when_no_table_name(self, monkeypatch):
        """USER_TABLE_NAME 未設定のとき update_user が呼ばれないこと"""
        monkeypatch.delenv("USER_TABLE_NAME", raising=False)

        import src.routers.settings as sett
        importlib.reload(sett)

        mock_update = MagicMock()
        with patch.object(sett.user_repository, "update_user", mock_update):
            resp = _make_app(sett).post(
                "/settings/salary",
                data={"yen_per_hour": "2000"},
                follow_redirects=False,
            )

        assert resp.status_code == 303
        mock_update.assert_not_called()


# ─── update_profile のテスト ─────────────────────────────────────────

class TestUpdateProfile:
    def test_calls_update_user_with_name_and_email(self, monkeypatch):
        """USER_TABLE_NAME が設定されているとき update_user が name・email で呼ばれること"""
        monkeypatch.setenv("USER_TABLE_NAME", "kintai-users")

        import src.routers.settings as sett
        importlib.reload(sett)

        mock_update = MagicMock()
        with patch.object(sett.user_repository, "update_user", mock_update):
            resp = _make_app(sett).post(
                "/settings/profile",
                data={"name": "新しい名前", "email": "new@example.com"},
                follow_redirects=False,
            )

        assert resp.status_code == 303
        mock_update.assert_called_once_with("test_user", "test_user", name="新しい名前", email="new@example.com")


# ─── update_password のテスト ────────────────────────────────────────

class TestUpdatePassword:
    def test_returns_400_when_passwords_do_not_match(self, monkeypatch):
        """new_password と confirm_password が異なる場合は 400 を返すこと"""
        monkeypatch.delenv("USER_TABLE_NAME", raising=False)
        monkeypatch.delenv("WORK_TABLE_NAME", raising=False)

        import src.routers.settings as sett
        importlib.reload(sett)

        resp = _make_app(sett).post(
            "/settings/password",
            data={
                "current_password": "old",
                "new_password":     "abc",
                "confirm_password": "xyz",
            },
        )
        assert resp.status_code == 400
        assert "一致しません" in resp.text

    def test_returns_400_when_current_password_wrong(self, monkeypatch):
        """現在のパスワードが誤っている場合は 400 を返すこと"""
        monkeypatch.setenv("USER_TABLE_NAME", "kintai-users")
        monkeypatch.delenv("WORK_TABLE_NAME", raising=False)

        import src.routers.settings as sett
        importlib.reload(sett)

        db_user = {"user_id": "test_user", "password_hash": "pbkdf2:sha256:xxx"}
        with (
            patch.object(sett.user_repository, "get_user",     return_value=db_user),
            patch.object(sett.auth_service,    "verify_password", return_value=False),
        ):
            resp = _make_app(sett).post(
                "/settings/password",
                data={
                    "current_password": "wrong",
                    "new_password":     "newpass",
                    "confirm_password": "newpass",
                },
            )
        assert resp.status_code == 400
        assert "正しくありません" in resp.text

    def test_updates_password_hash_on_success(self, monkeypatch):
        """パスワードが正しい場合は update_user が password_hash で呼ばれること"""
        monkeypatch.setenv("USER_TABLE_NAME", "kintai-users")
        monkeypatch.delenv("WORK_TABLE_NAME", raising=False)

        import src.routers.settings as sett
        importlib.reload(sett)

        db_user = {"user_id": "test_user", "password_hash": "pbkdf2:sha256:xxx"}
        mock_update = MagicMock()
        with (
            patch.object(sett.user_repository, "get_user",        return_value=db_user),
            patch.object(sett.auth_service,    "verify_password", return_value=True),
            patch.object(sett.auth_service,    "hash_password",   return_value="new_hash"),
            patch.object(sett.user_repository, "update_user",     mock_update),
        ):
            resp = _make_app(sett).post(
                "/settings/password",
                data={
                    "current_password": "correct",
                    "new_password":     "newpass",
                    "confirm_password": "newpass",
                },
                follow_redirects=False,
            )

        assert resp.status_code == 303
        mock_update.assert_called_once_with("test_user", "test_user", password_hash="new_hash")
