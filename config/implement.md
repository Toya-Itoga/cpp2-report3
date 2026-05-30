# implement.md

## タスク

### ダッシュボード画面の修正
- src/templates/dashboard.htmlから「直近の勤務」セクションを削除すること
- 「今月の勤務時間」の横幅を画面幅いっぱいに広げること
- 関連するバックエンドのコード（recent_recordsなど）も削除すること

### 打刻画面のタイムゾーン修正
- 打刻時刻がUTC-9時間で記録される問題を修正すること
- Lambdaの実行環境はUTCのため日本時間（JST/UTC+9）に変換すること
- 以下のように修正すること

from datetime import datetime, timezone, timedelta
JST = timezone(timedelta(hours=9))
now = datetime.now(JST)

- clock_in・clock_outの時刻記録処理を全て上記に統一すること
- src/routers/punch.pyとsrc/services/work_service.pyを確認・修正すること

## 注意事項
- ローカル環境でも動作確認すること
- 既存の機能を壊さないこと