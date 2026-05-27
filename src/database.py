"""DynamoDB接続とテーブル定義を集約するモジュール

使い方:
    from src.database import get_dynamodb, create_tables

    # テーブルリソースを取得する
    dynamodb = get_dynamodb()
    table = dynamodb.Table(os.getenv("USER_TABLE_NAME"))

    # ローカル環境でテーブルを作成する
    create_tables()
"""

import os
import logging

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

ENV = os.getenv("ENV", "development")

from dotenv import load_dotenv
load_dotenv()

def get_dynamodb():
    """
    DynamoDB リソースを返す。
    ENV=development の場合はローカルエンドポイントを使用する。
    ENV=production の場合は AWS 標準のエンドポイントを使用する。
    """
    region   = os.getenv("DYNAMODB_REGION", "ap-northeast-1")
    endpoint = os.getenv("DYNAMODB_ENDPOINT") if ENV == "development" else None

    return boto3.resource(
        "dynamodb",
        region_name=region,
        endpoint_url=endpoint,
    )


# ─── テーブル定義 ──────────────────────────────────────────────────────────

def _user_table_definition(table_name: str) -> dict:
    """
    Userテーブルの定義を返す。

    キー設計（implement.md より）:
        PK: USER#user_name (HASH)  ← ユーザー名でのログインに使用
        SK: user_id        (RANGE)
    """
    return {
        "TableName": table_name,
        "AttributeDefinitions": [
            {"AttributeName": "PK",      "AttributeType": "S"},
            {"AttributeName": "user_id", "AttributeType": "S"},
        ],
        "KeySchema": [
            {"AttributeName": "PK",      "KeyType": "HASH"},
            {"AttributeName": "user_id", "KeyType": "RANGE"},
        ],
        "BillingMode": "PAY_PER_REQUEST",
    }


def _work_table_definition(table_name: str) -> dict:
    """
    Workテーブルの定義を返す。

    キー設計（requirements.md より）:
        PK: USER#user_id       (HASH)
        SK: WORK#YYYYMMDD      (RANGE)  例: WORK#20260520
    """
    return {
        "TableName": table_name,
        "AttributeDefinitions": [
            {"AttributeName": "PK", "AttributeType": "S"},
            {"AttributeName": "SK", "AttributeType": "S"},
        ],
        "KeySchema": [
            {"AttributeName": "PK", "KeyType": "HASH"},
            {"AttributeName": "SK", "KeyType": "RANGE"},
        ],
        "BillingMode": "PAY_PER_REQUEST",
    }


# ─── テーブル作成 ──────────────────────────────────────────────────────────

def _create_table_if_not_exists(dynamodb, definition: dict) -> None:
    """
    テーブルが存在しない場合のみ作成する。
    既に存在する場合（ResourceInUseException）はスキップする。
    """
    table_name = definition["TableName"]
    try:
        dynamodb.create_table(**definition)
        # テーブルがACTIVEになるまで待機する
        table = dynamodb.Table(table_name)
        table.wait_until_exists()
        logger.info("テーブルを作成しました: %s", table_name)
    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceInUseException":
            logger.info("テーブルはすでに存在します（スキップ）: %s", table_name)
        else:
            raise


def create_tables() -> None:
    """
    UserテーブルとWorkテーブルを作成する。
    テーブルが既に存在する場合はスキップする。
    環境変数 USER_TABLE_NAME・WORK_TABLE_NAME が未設定の場合は RuntimeError を送出する。
    """
    user_table_name = os.getenv("USER_TABLE_NAME")
    work_table_name = os.getenv("WORK_TABLE_NAME")

    if not user_table_name:
        raise RuntimeError("USER_TABLE_NAME が設定されていません")
    if not work_table_name:
        raise RuntimeError("WORK_TABLE_NAME が設定されていません")

    dynamodb = get_dynamodb()

    _create_table_if_not_exists(dynamodb, _user_table_definition(user_table_name))
    _create_table_if_not_exists(dynamodb, _work_table_definition(work_table_name))
