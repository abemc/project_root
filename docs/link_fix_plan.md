# Docs Link Fix Plan

## 概要
生成した `docs/link_check_report.txt` をもとに、最も発生頻度の高い欠損リンクについて自動修正候補を提示します。多くはバックアップフォルダ `docs.backup_local/` に同名ファイルが存在するため、欠損先ファイルを復元（コピー）することでリンクを復旧できます。

## 上位問題（抜粋）
- `docs/07_学習資料/ニューラルネットワーク完全ガイド.md` (14件) — 候補: `docs.backup_local/07_学習資料/ニューラルネットワーク完全ガイド.md`
- `src/multimodal/MULTIMODAL_GUIDE.md` (12件) — 候補: `docs.backup_local/.../MULTIMODAL_GUIDE.md` (バックアップ内)
- `docs/00_ドキュメント索引.md` (10件) — 候補: `docs.backup_local/.../00_ドキュメント索引.md`
- `docs/07_学習資料/プロジェクトに必要な数学基礎.md` (10件) — 候補: `docs.backup_local/.../プロジェクトに必要な数学基礎.md`
- `docs/DOCUMENTATION_DASHBOARD.md` (9件) — 候補: `docs.backup_local/09_システム管理/DOCUMENTATION_DASHBOARD.md`

(完全一覧は `docs/link_fix_suggestions.json` を参照)

## 修正方針（提案）
1. まず、**ドキュメント本体（docs/配下）に存在すべきファイル**はバックアップから復元（コピー）する。復元対象は `link_fix_suggestions.json` で候補が1つしかないもの。\
2. `src/` や `app.py` などリポジトリルートを参照するリンクは、ドキュメント側からの相対パスが正しくない場合が多い。これらは自動で修正せず、リンク先を `../src/...` とするか、ドキュメント内での正しい相対階層を確認して手動修正する。\
3. 候補が複数ある場合は人手で確認して最適な場所へコピー／リンク書換を行う。

## 自動適用スクリプト
- `scripts/apply_link_fixes.py` を用意しました。動作条件:
  - `docs/link_fix_suggestions.json` が存在すること
  - 候補が1つで、リンク先パスが `docs/...` の形式のときに自動コピーを行います。\
- 実行前に差分とコピー先を確認してください。

## 実行例
```bash
# 変更を確認してから実行（dry-run 推奨）
.venv/bin/python scripts/apply_link_fixes.py --dry-run
# 実行する場合
.venv/bin/python scripts/apply_link_fixes.py
```

## 次の推奨アクション
- 私が `--dry-run` を実行して復元候補のサマリを出力しますか？（推奨）
- その後、問題ない候補のみ実際に復元（コピー）してよいですか？

