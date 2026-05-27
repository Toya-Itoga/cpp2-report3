"""src/services/auth_service.py のユニットテスト"""

import os
import pytest

os.environ["ENV"] = "development"

from src.services.auth_service import (
    hash_password,
    verify_password,
    create_token,
    verify_token,
    authenticate,
    DUMMY_USER,
)
from fastapi import HTTPException


class TestPasswordHash:
    def test_hash_and_verify(self):
        """ハッシュ化→検証のラウンドトリップが成功すること"""
        hashed = hash_password("mysecret")
        assert verify_password("mysecret", hashed) is True

    def test_wrong_password_fails(self):
        """誤ったパスワードは検証に失敗すること"""
        hashed = hash_password("correct")
        assert verify_password("wrong", hashed) is False

    def test_same_password_different_hash(self):
        """同じパスワードでも毎回異なるハッシュが生成されること（salt）"""
        h1 = hash_password("same")
        h2 = hash_password("same")
        assert h1 != h2

    def test_both_hashes_verify_correctly(self):
        """異なるハッシュでも元のパスワードで検証できること"""
        h1 = hash_password("same")
        h2 = hash_password("same")
        assert verify_password("same", h1) is True
        assert verify_password("same", h2) is True

    def test_invalid_hash_format_returns_false(self):
        """不正なハッシュフォーマットは False を返すこと"""
        assert verify_password("password", "invalid-hash") is False

    def test_empty_password(self):
        """空パスワードもハッシュ・検証できること"""
        hashed = hash_password("")
        assert verify_password("", hashed) is True
        assert verify_password("not-empty", hashed) is False


class TestJWT:
    def test_create_and_verify_token(self):
        """トークン生成→検証ラウンドトリップが成功すること"""
        token   = create_token("user123")
        user_id = verify_token(token)
        assert user_id == "user123"

    def test_invalid_token_raises_401(self):
        """不正なトークンは 401 を送出すること"""
        with pytest.raises(HTTPException) as exc:
            verify_token("invalid.token.here")
        assert exc.value.status_code == 401

    def test_tampered_token_raises_401(self):
        """改ざんされたトークンは 401 を送出すること"""
        token = create_token("user_a")
        # payload部を書き換える
        parts    = token.split(".")
        tampered = parts[0] + ".dGFtcGVyZWQ." + parts[2]
        with pytest.raises(HTTPException) as exc:
            verify_token(tampered)
        assert exc.value.status_code == 401


class TestAuthenticate:
    def test_development_falls_back_to_dummy_when_dynamodb_unavailable(self):
        """ENV=development で DynamoDB に接続できない場合はダミーユーザーを返すこと
        （USER_TABLE_NAME 未設定 → RuntimeError → DUMMY_USER フォールバック）"""
        user = authenticate("any@example.com", "any")
        assert user == DUMMY_USER

    def test_dummy_user_has_required_fields(self):
        """ダミーユーザーが必要なフィールドを持っていること"""
        user = authenticate("", "")
        assert "user_id"      in user
        assert "name"         in user
        assert "email"        in user
        assert "yen_per_hour" in user
