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


# DynamoDB にレコードが存在しない場合のフォールバック値（ダミーデータは含めない）
_FALLBACK_USER_FIELDS: dict = {
    "name":         "",
    "email":        "",
    "yen_per_hour": 0,
}


def get_user(user_name: str, user_id: str) -> dict:
    """PK(USER#user_name) + SK(user_id) で get_item してユーザーを取得する。存在しない場合はフォールバックを返す"""
    table = _get_table()
    response = table.get_item(Key={"PK": f"USER#{user_name}", "SK": user_id})
    item = response.get("Item")
    if item:
        return item
    # DynamoDB にレコードが存在しない場合はフォールバックを返す
    return {"user_id": user_id, **_FALLBACK_USER_FIELDS}


def get_user_by_name(user_name: str) -> Optional[dict]:
    """user_name でユーザーを検索する。存在しない場合は None を返す"""
    table = _get_table()
    response = table.query(
        KeyConditionExpression=Key("PK").eq(f"USER#{user_name}"),
        Limit=1,
    )
    items = response.get("Items", [])
    return items[0] if items else None


def update_user(
    user_id: str,
    user_name: str,
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
    # name は DynamoDB 予約語のため、更新するときのみエイリアスを追加する
    attr_names: dict = {}

    if name is not None:
        expressions.append("#name = :name")
        attr_values[":name"] = name
        attr_names["#name"] = "name"

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

    update_kwargs: dict = {
        "Key":                       {"PK": f"USER#{user_name}", "SK": user_id},
        "UpdateExpression":          "SET " + ", ".join(expressions),
        "ExpressionAttributeValues": attr_values,
    }
    # 未使用の ExpressionAttributeNames を渡すと DynamoDB が ValidationException を返すため
    # name を更新するときのみ追加する
    if attr_names:
        update_kwargs["ExpressionAttributeNames"] = attr_names

    table.update_item(**update_kwargs)
