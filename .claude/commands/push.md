# /push

GitHubにpushする。

## コンテキスト
- CLAUDE.md

## 手順
1. git diffで変更内容を確認する
2. 変更の種類ごとにコミットを分割する
3. 各コミットにConventional Commitsに沿ったメッセージをつける
4. git pushする

## コミットメッセージのプレフィックス
- feat: 新機能追加
- fix: バグ修正
- docs: ドキュメント更新
- chore: 保守作業
- ci: CI/CD関連
- refactor: リファクタリング
- test: テスト関連
- style: コードスタイル修正