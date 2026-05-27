"""src/services/auth_service.py のユニットテスト"""

import os
import pytest
from unittest.mock import patch

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
        token  = create_token("uid-001", "alice")
        claims = verify_token(token)
        assert claims["user_id"]   == "uid-001"
        assert claims["user_name"] == "alice"

    def test_invalid_token_raises_401(self):
        """不正なトークンは 401 を送出すること"""
        with pytest.raises(HTTPException) as exc:
            verify_token("invalid.token.here")
        assert exc.value.status_code == 401

    def test_tampered_token_raises_401(self):
        """改ざんされたトークンは 401 を送出すること"""
        token = create_token("uid-002", "user_a")
        # payload部を書き換える
        parts    = token.split(".")
        tampered = parts[0] + ".dGFtcGVyZWQ." + parts[2]
        with pytest.raises(HTTPException) as exc:
            verify_token(tampered)
        assert exc.value.status_code == 401


class TestAuthenticate:
    def test_returns_none_when_dynamodb_unavailable(self):
        """DynamoDB に接続できない場合（USER_TABLE_NAME 未設定）は None を返すこと"""
        result = authenticate("any_user", "any_password")
        assert result is None

    def test_returns_none_when_user_not_found(self, monkeypatch):
        """DynamoDB にユーザーが存在しない場合は None を返すこと"""
        monkeypatch.setenv("USER_TABLE_NAME", "kintai-users")
        with patch("src.repositories.user_repository.get_user_by_name", return_value=None):
            result = authenticate("nonexistent", "any_password")
        assert result is None

    def test_returns_none_when_password_mismatch(self, monkeypatch):
        """パスワードが一致しない場合は None を返すこと"""
        import bcrypt as _bcrypt
        hashed = _bcrypt.hashpw(b"correct", _bcrypt.gensalt()).decode()
        user_data = {"user_id": "u1", "password": hashed, "name": "Alice", "yen_per_hour": 1500}

        monkeypatch.setenv("USER_TABLE_NAME", "kintai-users")
        with patch("src.repositories.user_repository.get_user_by_name", return_value=user_data):
            result = authenticate("alice", "wrong_password")
        assert result is None

    def test_returns_user_when_credentials_valid(self, monkeypatch):
        """ユーザー名とパスワードが正しい場合はユーザー情報を返すこと"""
        import bcrypt as _bcrypt
        hashed = _bcrypt.hashpw(b"correct", _bcrypt.gensalt()).decode()
        user_data = {"user_id": "u1", "password": hashed, "name": "Alice", "yen_per_hour": 1500}

        monkeypatch.setenv("USER_TABLE_NAME", "kintai-users")
        with patch("src.repositories.user_repository.get_user_by_name", return_value=user_data):
            result = authenticate("alice", "correct")
        assert result is not None
        assert result["user_id"] == "u1"
