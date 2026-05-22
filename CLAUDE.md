# CLAUDE.md

## アーキテクチャ
- レイヤードアーキテクチャ

## レンダリング方式
- SSR

## ディレクトリ・ファイル構成
- `.venv/`                - 仮想環境
- `src/main.py`           - アプリ本体
- `src/routers/`          - ルータ層
- `src/services/`         - サービス層
- `src/repositories/`     - リポジトリ層
- `src/utils/`            - ユーティリティ関数定義
- `src/template/`         - HTMLファイル
- `src/static/css/`       - CSSファイル
- `src/static/js/`        - JavaScriptファイル
- `config/`               - 設定・ドキュメント
- `scripts/`              - 開発補助スクリプト
- `tests/`                - テストコード
- `.claude/commands/`     - コマンド
- `.claude/agents/`       - サブエージェント定義

## コーディング規約
- コメントを書くこと
- コードを機能単位のブロックで分割すること
- 生成するコードはsrc/に配置すること
- config/のファイルは読み取り専用とすること
- 機能を実装する際は必ずtests/にテストを作成すること
- HTMLのクラス名はBEM記法を遵守すること
- REST原則を遵守すること

## データベース
- 環境ごとにDBを分けること
- 本番環境とテスト環境のDBを分けること

## 禁止事項
- .envファイルの参照
- any型の乱用禁止

## 更新ポリシー
- 機能追加時はREADME.mdを更新すること
- AIが間違った動作をしたらここに反映すること

## 認証
- 認証はPyJWTを使用すること
- トークン有効期間は6時間とすること
- 全てのAPIエンドポイントでトークン検証を行うこと
- FastAPIのDependsを使用して共通の認証ミドルウェアとして実装すること
- 認証処理はsrc/services/auth_service.pyに定義すること

## 環境設定
- ローカル開発時はダミーユーザーを返すこと
- ENV=developmentの場合はDynamoDBへの認証をスキップしてダミーユーザーを使用すること

## ダミーユーザー
- user_id: dummy_user
- name: testuser
- yen_per_hour: 1500

## 技術スタック
- Python3.12
- FastAPI
- uvicorn
- boto3
- HTMX
- PyJWT
- Alpine.js