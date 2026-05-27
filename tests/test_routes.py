"""全画面のルーティングと基本レスポンスのテスト"""

import os
import pytest

from fastapi.testclient import TestClient
from src.main import app
from src.services import auth_service

# テスト用ダミーユーザーで認証をバイパスする（全ルートテスト共通）
_TEST_USER = {
    "user_id":      "test_user",
    "user_name":    "test_user",
    "name":         "テストユーザー",
    "email":        "test@kintai.app",
    "yen_per_hour": 1500,
}
app.dependency_overrides[auth_service.get_current_user] = lambda: _TEST_USER

client = TestClient(app, follow_redirects=True)


def test_root_redirects_to_dashboard():
    """/ は /dashboard にリダイレクトされること"""
    r = client.get("/")
    assert r.status_code == 200
    assert "ダッシュボード" in r.text or "Kintai" in r.text


def test_dashboard_page():
    """ダッシュボード画面が200を返し、主要要素を含むこと"""
    r = client.get("/dashboard")
    assert r.status_code == 200
    assert "こんにちは" in r.text
    assert "今日のステータス" in r.text
    assert "想定給与" in r.text


def test_punch_page():
    """打刻画面が200を返し、時刻表示要素を含むこと"""
    r = client.get("/punch")
    assert r.status_code == 200
    assert "出勤時刻" in r.text
    assert "退勤時刻" in r.text


def test_history_page():
    """勤務履歴画面が200を返し、カレンダー要素を含むこと"""
    r = client.get("/history")
    assert r.status_code == 200
    assert "cal-grid" in r.text
    assert "月の合計" in r.text


def test_history_month_navigation():
    """月パラメータ付きで履歴画面が正しくレンダリングされること"""
    r = client.get("/history?year=2026&month=4")
    assert r.status_code == 200
    assert "4月" in r.text


def test_settings_page():
    """設定画面が200を返し、全セクションを含むこと"""
    r = client.get("/settings")
    assert r.status_code == 200
    assert "プロフィール" in r.text
    assert "パスワード" in r.text
    assert "給与" in r.text


def test_login_page():
    """ログイン画面が200を返すこと（認証不要）"""
    r = client.get("/auth/login")
    assert r.status_code == 200
    assert "ログイン" in r.text


def test_clock_in_redirects():
    """出勤打刻がPOST後に打刻画面へリダイレクトされること"""
    r = client.post("/punch/clock-in")
    assert r.status_code == 200
    # follow_redirects=True なので最終レスポンスが /punch の内容
    assert "出勤時刻" in r.text


def test_clock_out_redirects():
    """退勤打刻がPOST後にダッシュボードへリダイレクトされること"""
    r = client.post("/punch/clock-out")
    assert r.status_code == 200
    assert "こんにちは" in r.text or "Kintai" in r.text


def test_unauthenticated_redirects_to_login():
    """Cookie なしのリクエストは /auth/login にリダイレクトされること"""
    # dependency_overrides を一時的に解除して本来の認証フローをテストする
    saved = app.dependency_overrides.copy()
    app.dependency_overrides.clear()
    try:
        unauthed = TestClient(app, follow_redirects=False)
        r = unauthed.get("/dashboard")
        assert r.status_code == 303
        assert "/auth/login" in r.headers["location"]
    finally:
        app.dependency_overrides.update(saved)
