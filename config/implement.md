# implement.md

## タスク
- src/routers/dashboard.pyのTODOとダミーデータを実際のDynamoDBデータに置き換えること

## 取得が必要なデータ
- 当日の勤務レコード（clock_in・clock_out・status）
  PK: USER#user_id / SK: WORK#YYYYMMDD

- 月次集計データ（当月のWORK#YYYYMMDDレコードを全件取得して集計）
  - total_minutes: 月の総勤務時間（分）
  - work_days: 出勤日数
  - overtime_minutes: 残業時間合計

- 直近5件の勤務レコード
  - 当月のWORK#YYYYMMDDレコードから直近5件を取得

## 集計ロジック
- 月次集計はsrc/repositories/work_repository.pyに定義すること
- requirements.mdのビジネスロジックを参照すること