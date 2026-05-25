"""ローカル開発用 DynamoDB テーブルセットアップスクリプト

前提:
    - Docker でローカル DynamoDB が起動していること
      docker run -p 5434:8000 amazon/dynamodb-local

使い方:
    ENV=development \
    DYNAMODB_ENDPOINT=http://localhost:5434 \
    USER_TABLE_NAME=kintai-users \
    WORK_TABLE_NAME=kintai-works \
    python scripts/setup_local_db.py
"""

import logging
import os
import sys

# プロジェクトルートをパスに追加してsrcモジュールをimportできるようにする
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

from src.database import create_tables

if __name__ == "__main__":
    print("ローカル DynamoDB のテーブルをセットアップします...")
    try:
        create_tables()
        print("セットアップ完了。")
    except RuntimeError as e:
        print(f"エラー: {e}", file=sys.stderr)
        sys.exit(1)
