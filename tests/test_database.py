"""src/database.py のユニットテスト"""

import os
import pytest
from unittest.mock import MagicMock, patch, call
from botocore.exceptions import ClientError


# ─── get_dynamodb のテスト ─────────────────────────────────────────────────

class TestGetDynamodb:
    def test_development_uses_local_endpoint(self, monkeypatch):
        """ENV=development のときローカルエンドポイントを使用すること"""
        monkeypatch.setenv("ENV",               "development")
        monkeypatch.setenv("DYNAMODB_ENDPOINT", "http://localhost:5434")
        monkeypatch.setenv("DYNAMODB_REGION",   "ap-northeast-1")

        with patch("boto3.resource") as mock_resource:
            # モジュールを再ロードして環境変数を反映する
            import importlib, src.database as db_module
            importlib.reload(db_module)

            db_module.get_dynamodb()

            mock_resource.assert_called_once_with(
                "dynamodb",
                region_name="ap-northeast-1",
                endpoint_url="http://localhost:5434",
            )

    def test_production_uses_no_endpoint(self, monkeypatch):
        """ENV=production のときエンドポイントを指定しないこと"""
        monkeypatch.setenv("ENV",             "production")
        monkeypatch.setenv("DYNAMODB_REGION", "ap-northeast-1")
        monkeypatch.delenv("DYNAMODB_ENDPOINT", raising=False)

        with patch("boto3.resource") as mock_resource:
            import importlib, src.database as db_module
            importlib.reload(db_module)

            db_module.get_dynamodb()

            mock_resource.assert_called_once_with(
                "dynamodb",
                region_name="ap-northeast-1",
                endpoint_url=None,
            )


# ─── create_tables のテスト ────────────────────────────────────────────────

class TestCreateTables:
    def _make_client_error(self, code: str) -> ClientError:
        return ClientError(
            {"Error": {"Code": code, "Message": ""}},
            "CreateTable",
        )

    def test_raises_if_user_table_name_missing(self, monkeypatch):
        """USER_TABLE_NAME 未設定で RuntimeError が出ること"""
        monkeypatch.delenv("USER_TABLE_NAME", raising=False)
        monkeypatch.setenv("WORK_TABLE_NAME", "kintai-works")

        # load_dotenv が .env を再読み込みして monkeypatch を上書きするのを防ぐ
        with patch("dotenv.load_dotenv"):
            import importlib, src.database as db_module
            importlib.reload(db_module)

            with pytest.raises(RuntimeError, match="USER_TABLE_NAME"):
                db_module.create_tables()

    def test_raises_if_work_table_name_missing(self, monkeypatch):
        """WORK_TABLE_NAME 未設定で RuntimeError が出ること"""
        monkeypatch.setenv("USER_TABLE_NAME", "kintai-users")
        monkeypatch.delenv("WORK_TABLE_NAME", raising=False)

        # load_dotenv が .env を再読み込みして monkeypatch を上書きするのを防ぐ
        with patch("dotenv.load_dotenv"):
            import importlib, src.database as db_module
            importlib.reload(db_module)

            with pytest.raises(RuntimeError, match="WORK_TABLE_NAME"):
                db_module.create_tables()

    def test_creates_both_tables(self, monkeypatch):
        """両テーブルが create_table を呼び出すこと"""
        monkeypatch.setenv("USER_TABLE_NAME", "kintai-users")
        monkeypatch.setenv("WORK_TABLE_NAME", "kintai-works")
        monkeypatch.setenv("ENV",             "development")

        mock_table = MagicMock()
        mock_dynamodb = MagicMock()
        mock_dynamodb.create_table.return_value = mock_table
        mock_dynamodb.Table.return_value = mock_table

        import importlib, src.database as db_module
        importlib.reload(db_module)

        with patch.object(db_module, "get_dynamodb", return_value=mock_dynamodb):
            db_module.create_tables()

        assert mock_dynamodb.create_table.call_count == 2
        table_names = [
            c.kwargs["TableName"]
            for c in mock_dynamodb.create_table.call_args_list
        ]
        assert "kintai-users" in table_names
        assert "kintai-works" in table_names

    def test_skips_existing_table(self, monkeypatch):
        """テーブルが既に存在する場合（ResourceInUseException）はスキップすること"""
        monkeypatch.setenv("USER_TABLE_NAME", "kintai-users")
        monkeypatch.setenv("WORK_TABLE_NAME", "kintai-works")
        monkeypatch.setenv("ENV",             "development")

        mock_dynamodb = MagicMock()
        mock_dynamodb.create_table.side_effect = self._make_client_error(
            "ResourceInUseException"
        )

        import importlib, src.database as db_module
        importlib.reload(db_module)

        with patch.object(db_module, "get_dynamodb", return_value=mock_dynamodb):
            # 例外を送出せずに完了すること
            db_module.create_tables()

    def test_reraises_unexpected_client_error(self, monkeypatch):
        """想定外の ClientError は再送出されること"""
        monkeypatch.setenv("USER_TABLE_NAME", "kintai-users")
        monkeypatch.setenv("WORK_TABLE_NAME", "kintai-works")
        monkeypatch.setenv("ENV",             "development")

        mock_dynamodb = MagicMock()
        mock_dynamodb.create_table.side_effect = self._make_client_error(
            "AccessDeniedException"
        )

        import importlib, src.database as db_module
        importlib.reload(db_module)

        with patch.object(db_module, "get_dynamodb", return_value=mock_dynamodb):
            with pytest.raises(ClientError):
                db_module.create_tables()

    def test_user_table_has_pk_and_user_id_key_schema(self, monkeypatch):
        """Userテーブルの KeySchema に PK(HASH) と user_id(RANGE) が含まれること"""
        monkeypatch.setenv("USER_TABLE_NAME", "kintai-users")
        monkeypatch.setenv("WORK_TABLE_NAME", "kintai-works")
        monkeypatch.setenv("ENV",             "development")

        mock_table    = MagicMock()
        mock_dynamodb = MagicMock()
        mock_dynamodb.create_table.return_value = mock_table
        mock_dynamodb.Table.return_value = mock_table

        import importlib, src.database as db_module
        importlib.reload(db_module)

        with patch.object(db_module, "get_dynamodb", return_value=mock_dynamodb):
            db_module.create_tables()

        # 最初の呼び出しが User テーブル
        user_call  = mock_dynamodb.create_table.call_args_list[0]
        key_schema = user_call.kwargs["KeySchema"]
        assert {"AttributeName": "PK",      "KeyType": "HASH"}  in key_schema
        assert {"AttributeName": "user_id", "KeyType": "RANGE"} in key_schema

    def test_user_table_has_no_gsi(self, monkeypatch):
        """Userテーブルに GSI が定義されていないこと（email-index 削除済み）"""
        monkeypatch.setenv("USER_TABLE_NAME", "kintai-users")
        monkeypatch.setenv("WORK_TABLE_NAME", "kintai-works")
        monkeypatch.setenv("ENV",             "development")

        mock_table    = MagicMock()
        mock_dynamodb = MagicMock()
        mock_dynamodb.create_table.return_value = mock_table
        mock_dynamodb.Table.return_value = mock_table

        import importlib, src.database as db_module
        importlib.reload(db_module)

        with patch.object(db_module, "get_dynamodb", return_value=mock_dynamodb):
            db_module.create_tables()

        user_call = mock_dynamodb.create_table.call_args_list[0]
        gsi = user_call.kwargs.get("GlobalSecondaryIndexes", [])
        assert gsi == []

    def test_work_table_has_pk_and_sk_key_schema(self, monkeypatch):
        """Workテーブルの KeySchema に PK(HASH) と SK(RANGE) が含まれること"""
        monkeypatch.setenv("USER_TABLE_NAME", "kintai-users")
        monkeypatch.setenv("WORK_TABLE_NAME", "kintai-works")
        monkeypatch.setenv("ENV",             "development")

        mock_table    = MagicMock()
        mock_dynamodb = MagicMock()
        mock_dynamodb.create_table.return_value = mock_table
        mock_dynamodb.Table.return_value = mock_table

        import importlib, src.database as db_module
        importlib.reload(db_module)

        with patch.object(db_module, "get_dynamodb", return_value=mock_dynamodb):
            db_module.create_tables()

        # 2番目の呼び出しが Work テーブル
        work_call  = mock_dynamodb.create_table.call_args_list[1]
        key_schema = work_call.kwargs["KeySchema"]
        assert {"AttributeName": "PK", "KeyType": "HASH"}  in key_schema
        assert {"AttributeName": "SK", "KeyType": "RANGE"} in key_schema

    def test_work_table_has_pk_attribute_definition(self, monkeypatch):
        """Workテーブルの AttributeDefinitions に PK が含まれること"""
        monkeypatch.setenv("USER_TABLE_NAME", "kintai-users")
        monkeypatch.setenv("WORK_TABLE_NAME", "kintai-works")
        monkeypatch.setenv("ENV",             "development")

        mock_table    = MagicMock()
        mock_dynamodb = MagicMock()
        mock_dynamodb.create_table.return_value = mock_table
        mock_dynamodb.Table.return_value = mock_table

        import importlib, src.database as db_module
        importlib.reload(db_module)

        with patch.object(db_module, "get_dynamodb", return_value=mock_dynamodb):
            db_module.create_tables()

        work_call = mock_dynamodb.create_table.call_args_list[1]
        attr_names = [a["AttributeName"] for a in work_call.kwargs["AttributeDefinitions"]]
        assert "PK" in attr_names
        assert "SK" in attr_names
