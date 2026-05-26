"""src/repositories/user_repository.py のユニットテスト"""

import pytest
from unittest.mock import MagicMock, patch
from src.repositories import user_repository


def _make_mock_table():
    mock_table = MagicMock()
    mock_dynamodb = MagicMock()
    mock_dynamodb.Table.return_value = mock_table
    return mock_table, mock_dynamodb


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
