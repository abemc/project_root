# クリーンアップ記録

日付: 2026-05-11

実施内容:

- アーカイブ作成: `backups/cleanup_20260511_113434.tar.gz`（約566M）および `backups/cleanup_20260511_113434.tar.gz`（2.2G）など、クリーンアップ用アーカイブを作成しました。アーカイブは `backups/` 配下に保存されています。
- 削除対象と処理:
  - `.deleted_by_agent_20260507_210709` — root 所有の `hf_cache` が含まれていたため一旦アーカイブし、最終的に所有権を変更して削除しました（`sudo chown -R $(id -u):$(id -g) .deleted_by_agent_20260507_210709` → `rm -rf .deleted_by_agent_20260507_210709`）。
  - `changes.patch`, `myenv` — アーカイブ後に削除しました。

結果（実行後のトップレベルサイズ抜粋）:

- `.venv`: 8.1G
- `backups`: 7.4G（アーカイブ含む）
- `checkpoints`: 4.4G
- `models`: 1.2G
- `corpus`: 178M
- その他は数MB以下

注意事項:

- `.git`（34G）は履歴サイズが大きいため別途整理（git gc / filter-repo）を検討してください。操作にはリスクがあるため事前にリポジトリのバックアップを推奨します。
- `.venv` は再作成可能です。ディスクをさらに削減したい場合は `pip freeze > requirements.lock` を保存した上で `.venv` を削除し再構築してください。

再現コマンド（参考）:

```bash
# アーカイブ（例）
TS=$(date +%Y%m%d_%H%M%S)
tar -czf backups/cleanup_${TS}.tar.gz .deleted_by_agent_20260507_210709 changes.patch myenv

# root 所有ファイルの削除（要 sudo）
sudo chown -R $(id -u):$(id -g) .deleted_by_agent_20260507_210709
rm -rf .deleted_by_agent_20260507_210709
```
