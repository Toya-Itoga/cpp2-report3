# requirements.md

## アプリ概要
- アプリ名: 勤怠管理アプリ
- 概要: 勤務時間の記録、想定月給与の確認が可能なWEBアプリ

## デザイン
- 画面構成・デザインはClaude Designのハンドオフバンドルを参照
- メニューバーは固定コンポーネントとしHTMX/Alpine.jsで動的に切り替えること

## 非機能要件
- パフォーマンス: Lambdaコールドスタート対策
- セキュリティ: JWT認証必須・HTTPS通信
- 対応デバイス: PC

## 制約条件
- 本番環境(AWS Lambda)上で動作すること
- DBはDynamoDBを使用すること
- ユーザー登録・編集はDynamoDBコンソールから直接行い、ユーザー管理画面は実装しない
- ローカル開発時はDocker上のローカルDynamoDBを使用すること
- 全APIエンドポイントはトークン認証必須とすること

## データ構造

### Userテーブル
- PK: USER#user_name
- SK: user_id
- attributes:
  - user_name: ユーザー名
  - user_id: ユーザーID
  - email: メールアドレス
  - password: ハッシュ化されたパスワード
  - yen_per_hour: 時給
  - created_at: 作成日時

### Workテーブル
**日次レコード**
- PK: USER#user_id
- SK: WORK#YYYYMMDD（例: WORK#20260520）
- attributes:
  - clock_in: 出勤時刻
  - clock_out: 退勤時刻
  - work_minutes: 勤務時間（分）
  - overtime_minutes: 残業時間（分）
  - status: 出勤中 / 退勤済 / 休日

## ビジネスロジック
- 月次集計は都度集計すること（DBには保存しない）
- 月次集計 = 対象月のWORK#YYYYMMDDレコードを全件取得して集計
- 想定月収 = 月の総勤務時間（時間換算） × yen_per_hour
- 想定月収はDBに保存せず都度算出すること
- 時給はyen/hourという変数名で管理すること
- 想定月収の算出関数はsrc/utils/に定義すること