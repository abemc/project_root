**Knowledge Schema (推奨メタデータ設計)**

目的: ナレッジコーパスを一貫したスキーマで保持し、検索/更新/ガベージコレクション/継続学習で利用しやすくする。

必須フィールド
- `doc_id`: 一意識別子（例: sha1 または UUID）
- `source`: 元ファイルパスまたはシステム（例: onenote、pdf、web）
- `title`: 表題（存在すれば）
- `text`: 正規化済み本文（チャンク化済みならチャンクテキスト）
- `chunk_id`: 文書内チャンク番号（チャンク化する場合）
- `created_at`: ISO8601 日時
- `language`: 言語コード（例: ja）

推奨フィールド
- `url`: 元の URL（あれば）
- `tags`: タグ配列
- `checksum`: 元文書のハッシュ（変更検出用）
- `offset_start`, `offset_end`: 元文書内の文字オフセット（チャンク化時）
- `embedding_path`: 埋め込みが保存されているファイルパス（オプション）
- `version`: 文書のバージョン（更新でインクリメント）
- `deleted`: ブール（削除マーク）
- `provenance`: 取り込み元や処理履歴の簡易ログ

運用上の注意
- `doc_id` は安定に生成すること（例: source+path+offset のハッシュ）。
- 変更のたびに `version` を上げ、古いバージョンはメタデータDBで追跡する。
- `deleted` フラグを用いたソフトデリートを採用し、定期的に FAISS コンパクション（再構築）を実行する。

推奨インデックス
- SQLite/PG に `docs(doc_id primary key, title, source, checksum, deleted integer, created_at, version)` を持たせる
- 検索評価・モニタリング用に `ingest_events` テーブルを用意する（timestamp, docs_added, duration_ms, host）

例 JSONL 行
{
  "doc_id": "sha1:abcd...",
  "source": "uploads/report.pdf",
  "title": "報告書",
  "text": "正規化済みテキスト...",
  "chunk_id": 0,
  "created_at": "2026-05-15T12:00:00Z",
  "language": "ja"
}
