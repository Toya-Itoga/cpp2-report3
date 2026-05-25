# implement.md

## タスク
- src/database.pyを作成してテーブル定義とDB接続処理を定義すること

## database.pyに含める内容
- get_dynamodb(): DB接続処理（ENV=developmentの場合はローカルエンドポイントを使用）
- create_tables(): UserテーブルとWorkテーブルの作成処理
- UserテーブルとWorkテーブルのキー定義はrequirements.mdを参照すること

## 注意事項
- テーブルが既に存在する場合はスキップすること
- scripts/setup_local_db.pyからcreate_tables()を呼び出せるようにすること