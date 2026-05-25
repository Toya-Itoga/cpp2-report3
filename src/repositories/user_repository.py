"""Userテーブルの DynamoDB 操作を定義するリポジトリ"""

import os
from typing import Optional

import boto3
from boto3.dynamodb.conditions import Key


def _get_table():
    """環境変数からDynamoDBテーブルリソースを生成して返す"""
    table_name = os.getenv("USER_TABLE_NAME")
    if not table_name:
        raise RuntimeError("USER_TABLE_NAME が設定されていません")

    dynamodb = boto3.resource(
        "dynamodb",
        region_name=os.getenv("DYNAMODB_REGION", "ap-northeast-1"),
        endpoint_url=os.getenv("DYNAMODB_ENDPOINT"),  # ローカル: http://localhost:5434
    )
    return dynamodb.Table(table_name)


def get_user(user_id: str) -> Optional[dict]:
    """user_id でユーザーを取得する。存在しない場合は None を返す"""
    table = _get_table()
    response = table.get_item(Key={"PK": f"USER#{user_id}"})
    return response.get("Item")


def get_user_by_email(email: str) -> Optional[dict]:
    """メールアドレスでユーザーを検索する（GSI: email-index が必要）"""
    table = _get_table()
    response = table.query(
        IndexName="email-index",
        KeyConditionExpression=Key("email").eq(email),
        Limit=1,
    )
    items = response.get("Items", [])
    return items[0] if items else None


def update_user(
    user_id: str,
    name: Optional[str] = None,
    email: Optional[str] = None,
    yen_per_hour: Optional[int] = None,
    password_hash: Optional[str] = None,
) -> None:
    """ユーザーの任意フィールドを更新する"""
    table = _get_table()

    # 更新対象フィールドを動的に組み立てる
    expressions: list[str] = []
    attr_values: dict = {}
    attr_names: dict = {"#name": "name"}  # name は予約語なのでエイリアスが必要

    if name is not None:
        expressions.append("#name = :name")
        attr_values[":name"] = name

    if email is not None:
        expressions.append("email = :email")
        attr_values[":email"] = email

    if yen_per_hour is not None:
        expressions.append("yen_per_hour = :yph")
        attr_values[":yph"] = yen_per_hour

    if password_hash is not None:
        expressions.append("password_hash = :ph")
        attr_values[":ph"] = password_hash

    if not expressions:
        return

    table.update_item(
        Key={"PK": f"USER#{user_id}"},
        UpdateExpression="SET " + ", ".join(expressions),
        ExpressionAttributeNames=attr_names,
        ExpressionAttributeValues=attr_values,
    )
