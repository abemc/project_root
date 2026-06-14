概要:
- テスト実行で検出された複数の不具合を修正し、全テストがローカルで通ることを確認しました（1088 passed, 914 warnings）。
- 目的はテスト安定化と実行環境の再現性向上です。

主な変更点:
- security_hardening.py — テスト互換のトップレベル facade を追加。
- src/optimization/db_optimizer.py — 汎用的な接続取得ヘルパー `acquire_conn()` を実装（async context manager / async generator / awaitable 対応）。Phase1 の最適化処理を単一接続で実行するよう変更。
- src/corpus/extract_pdf.py — `pix.save()` 呼び出し、`tobytes()` が bytes でない場合のフォールバック、`DEVICE=="cuda"` 時の `model.cuda()` 呼び出しの堅牢化。
- src/backup/backup_manager.py — project_root の親ディレクトリまで探索するフォールバック、manifest に入れる相対パス算出の改良。
- Dockerfile / docker-compose.yml — `WORKDIR`/`COPY`/`EXPOSE`/`CMD` とイメージ指定を追加し、ローカルビルドプラグインに依存しない構成に変更。

テスト:
- ローカルでフルテスト実行済み: `1088 passed, 914 warnings`
- 重点確認: `tests/test_db_optimization.py`, `tests/test_extract_pdf.py`, `tests/test_ui_external_drive.py` 等

添付 / 保存場所:
- git 形式パッチ: fixes_core_git.patch
- 変更ファイルアーカイブ: fixes_core_files.tar.gz

適用 / push 手順（推奨）:
1. リポジトリ所有権とロックを確認/修正（必要なら sudo）:
```bash
sudo chown -R "$(id -un):$(id -gn)" .git
rm -f .git/index.lock
```
2. パッチ適用:
```bash
git apply -p1 fixes_core_git.patch
```
3. Git 設定（未設定なら）:
```bash
git config user.email "devnull@example.com"
git config user.name "dev-agent"
```
4. ブランチ作成・コミット・プッシュ:
```bash
git checkout -b fix/test-stability-20260506
git add -A
git commit -m "Fix: handle async generator pool acquire; robust PDF extraction; translator .cuda(); backup path resolution (tests passing)"
# HTTPS に切り替える場合
# git remote set-url origin https://github.com/yourorg/yourrepo.git
git push --set-upstream origin fix/test-stability-20260506
```
5. PR 作成（gh CLI の例）:
```bash
# PR_body.md に上記本文が保存されています
gh pr create --title "Fix: テスト安定化 — 非同期接続取得の強化、PDF抽出の堅牢化、バックアップ経路解決、Docker 修正" \
  --body-file PR_body.md --base main --head fix/test-stability-20260506
```

重要な注意点:
- 現在の障害: `.git` が root 所有だったためコミットに失敗しました — 上の chown コマンドで修正してください。
- GitHub へのプッシュは SSH 鍵が未設定だと拒否されます。手元で SSH 鍵を追加するか、`origin` を HTTPS に切り替えてください。

次の推奨タスク:
- `requirements.txt` を確認して `torch`/`torchvision` の整合を図る（次の PR で対応推奨）。
