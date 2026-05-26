# implement.md

## タスク
- src/routers/punch.pyのclock_in・clock_outのTODOを実装すること

## clock_inの処理
- 現在時刻を取得する
- DynamoDBにWORK#YYYYMMDDのレコードを作成する
- clock_in・status（出勤中）を書き込む

## clock_outの処理
- DynamoDBのWORK#YYYYMMDDのレコードを更新する
- clock_out・work_minutes・status（退勤済）を書き込む
- work_minutes = clock_outの時刻 - clock_inの時刻（分換算）