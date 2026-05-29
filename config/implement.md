# implement.md

## タスク

### user_repository.pyのget_user関数を修正すること
- get_itemのKeyのSKのキー名を修正すること

以下のように変更すること
- Key={"PK": f"USER#{user_name}", "user_id": user_id}
- → Key={"PK": f"USER#{user_name}", "SK": user_id}

- update_item関数も同様に確認・修正すること