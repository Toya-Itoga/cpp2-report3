"""src/repositories/user_repository.py のユニットテスト"""

import pytest
from unittest.mock import MagicMock, patch
from src.repositories import user_repository


def _make_mock_table():
    mock_table = MagicMock()
    mock_dynamodb = MagicMock()
    mock_dynamodb.Table.return_value = mock_table
    return mock_table, mock_dynamodb


# ─── get_user のテスト ────────────────────────────────────────────────

class TestGetUser:
    def test_returns_item_when_found(self, monkeypatch):
        """DynamoDB にユーザーが存在する場合はそのアイテムを返すこと"""
        monkeypatch.setenv("USER_TABLE_NAME", "kintai-users")

        mock_table, mock_dynamodb = _make_mock_table()
        mock_table.get_item.return_value = {
            "Item": {"PK": "USER#u1", "user_id": "u1", "name": "Alice", "yen_per_hour": 2000}
        }

        with patch("boto3.resource", return_value=mock_dynamodb):
            result = user_repository.get_user("u1")

        assert result["name"] == "Alice"
        assert result["yen_per_hour"] == 2000

    def test_returns_fallback_when_not_found(self, monkeypatch):
        """DynamoDB にユーザーが存在しない場合はフォールバックを返すこと"""
        monkeypatch.setenv("USER_TABLE_NAME", "kintai-users")

        mock_table, mock_dynamodb = _make_mock_table()
        mock_table.get_item.return_value = {}  # Item キーなし

        with patch("boto3.resource", return_value=mock_dynamodb):
            result = user_repository.get_user("unknown_user")

        assert result["user_id"]      == "unknown_user"
        assert result["name"]         == "sampleuser"
        assert result["email"]        == "sample@kintai.app"
        assert result["yen_per_hour"] == 1500

    def test_fallback_does_not_contain_password_hash(self, monkeypatch):
        """フォールバックユーザーには password_hash が含まれないこと"""
        monkeypatch.setenv("USER_TABLE_NAME", "kintai-users")

        mock_table, mock_dynamodb = _make_mock_table()
        mock_table.get_item.return_value = {}

        with patch("boto3.resource", return_value=mock_dynamodb):
            result = user_repository.get_user("no_such_user")

        assert "password_hash" not in result


# ─── get_user_by_name のテスト ───────────────────────────────────────

class TestGetUserByName:
    def test_returns_item_when_found(self, monkeypatch):
        """PK=USER#user_name でヒットしたとき最初のアイテムを返すこと"""
        monkeypatch.setenv("USER_TABLE_NAME", "kintai-users")

        mock_table, mock_dynamodb = _make_mock_table()
        mock_table.query.return_value = {
            "Items": [{"PK": "USER#admin", "user_id": "u1", "name": "Admin"}]
        }

        with patch("boto3.resource", return_value=mock_dynamodb):
            result = user_repository.get_user_by_name("admin")

        assert result is not None
        assert result["name"] == "Admin"
        # PK: USER#admin でクエリされること
        call_kwargs = mock_table.query.call_args.kwargs
        assert "KeyConditionExpression" in call_kwargs

    def test_returns_none_when_not_found(self, monkeypatch):
        """該当ユーザーが存在しない場合は None を返すこと"""
        monkeypatch.setenv("USER_TABLE_NAME", "kintai-users")

        mock_table, mock_dynamodb = _make_mock_table()
        mock_table.query.return_value = {"Items": []}

        with patch("boto3.resource", return_value=mock_dynamodb):
            result = user_repository.get_user_by_name("unknown")

        assert result is None


# ─── update_user のテスト ─────────────────────────────────────────────

class TestUpdateUser:
    def _call_update_user(self, mock_dynamodb, **kwargs):
        with patch("boto3.resource", return_value=mock_dynamodb):
            user_repository.update_user("test_user", **kwargs)

    def test_update_yen_per_hour_does_not_send_attr_names(self, monkeypatch):
        """yen_per_hour のみ更新するとき ExpressionAttributeNames を送らないこと
        （送ると DynamoDB が ValidationException を返すバグの回避）"""
        monkeypatch.setenv("USER_TABLE_NAME", "kintai-users")

        mock_table, mock_dynamodb = _make_mock_table()
        self._call_update_user(mock_dynamodb, yen_per_hour=2000)

        call_kwargs = mock_table.update_item.call_args.kwargs
        assert "ExpressionAttributeNames" not in call_kwargs

    def test_update_name_sends_attr_names(self, monkeypatch):
        """name を更新するとき ExpressionAttributeNames を送ること（予約語エイリアス）"""
        monkeypatch.setenv("USER_TABLE_NAME", "kintai-users")

        mock_table, mock_dynamodb = _make_mock_table()
        self._call_update_user(mock_dynamodb, name="新しい名前")

        call_kwargs = mock_table.update_item.call_args.kwargs
        assert "ExpressionAttributeNames" in call_kwargs
        assert call_kwargs["ExpressionAttributeNames"] == {"#name": "name"}

    def test_update_email_only_does_not_send_attr_names(self, monkeypatch):
        """email のみ更新するとき ExpressionAttributeNames を送らないこと"""
        monkeypatch.setenv("USER_TABLE_NAME", "kintai-users")

        mock_table, mock_dynamodb = _make_mock_table()
        self._call_update_user(mock_dynamodb, email="new@example.com")

        call_kwargs = mock_table.update_item.call_args.kwargs
        assert "ExpressionAttributeNames" not in call_kwargs

    def test_update_name_and_yen_per_hour_sends_both(self, monkeypatch):
        """name と yen_per_hour を両方更新するとき両方が UpdateExpression に含まれること"""
        monkeypatch.setenv("USER_TABLE_NAME", "kintai-users")

        mock_table, mock_dynamodb = _make_mock_table()
        self._call_update_user(mock_dynamodb, name="テスト", yen_per_hour=1800)

        call_kwargs = mock_table.update_item.call_args.kwargs
        expr = call_kwargs["UpdateExpression"]
        assert "#name" in expr
        assert "yen_per_hour" in expr

    def test_no_fields_skips_update(self, monkeypatch):
        """更新フィールドが何もない場合は update_item を呼ばないこと"""
        monkeypatch.setenv("USER_TABLE_NAME", "kintai-users")

        mock_table, mock_dynamodb = _make_mock_table()
        self._call_update_user(mock_dynamodb)

        mock_table.update_item.assert_not_called()
