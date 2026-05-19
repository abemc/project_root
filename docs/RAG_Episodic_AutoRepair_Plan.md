**目的**
RAG の検索精度と即応性を高め、エピソード記憶（成功/失敗体験）を蓄積して再利用し、エラー発生時に自己修正する AutoRepair ワークフローを安全に導入する。

**現状の観察**
- RAG 実装: [src/rag/multi_domain_retriever.py](../src/rag/multi_domain_retriever.py) と [src/rag/retriever.py](../src/rag/retriever.py) に FAISS ベースのインデックス管理がある。
- メモリ: [src/rag/memory.py](../src/rag/memory.py) の `MemoryManager` は `retriever.add_texts()` を用いて会話要約をコーパスに追加・検索している。
- フィードバック: [src/self_improvement/feedback_manager.py](../src/self_improvement/feedback_manager.py) は JSONL でフィードバックを永続化し、`export_for_training()` がある。
- 自己改善: `src/self_improvement` に多くのモジュール存在。ただし「自動修正（AutoRepair）」のエンドツーエンド実装は存在しない。

**要件（高レベル）**
1. ベクタストア抽象レイヤ（`embed_store`）を作成し、FAISS/Chroma/Pinecone などの切替を容易にする。メタデータに `source`, `doc_id`, `chunk_id`, `embedding_version`, `origin_commit`, `episode_id` を含める。 
2. エピソード記憶モジュール（`episodic_memory`）を作成。スキーマ: `{episode_id, timestamp, trigger, query, action, result, resolution, feedback, tags, vector?}`。保存: JSONL + オプションでベクトル索引（FAISS）。検索 API を提供。 
3. `MemoryManager`/`FeedbackManager` をエピソードと結合して、フィードバックや成功体験を `episode_id` で紐づける。 `FeedbackManager.record_feedback()` に `episode_id` 引数を追加（オプション）。
4. AutoRepair プロトコル: エラー検知 → ログ/スタックトレース解析 → 過去エピソード検索（類似エラー） → 修正案生成（Patch suggestion via heuristic or LLM）→ サンドボックスで検証 → 人による承認 or 自動適用（autonomy level に依存）。
5. 安全ガード: 自動適用はデフォルト無効。自動パッチはサンドボックスでのテスト結果と監査ログがなければ適用しない。すべて Audit する。

**設計（コンポーネント & API）**
- `src/rag/embed_store.py` (新規)
  - class `EmbedStore` (抽象)
    - `upsert(documents: List[dict]) -> List[str]`  # returns ids
    - `delete(ids: List[str])`
    - `search(query_vector: np.ndarray, top_k:int, filters: dict) -> List[dict]`
  - plugin: `FaissStore(EmbedStore)`, `ChromaStore(EmbedStore)`
  - metadata expected: {"id","text","meta":{...},"embedding_version"}

- `src/memory/episodic_memory.py` (新規)
  - class `EpisodicMemory`:
    - `store_episode(episode: dict) -> episode_id`
    - `query_episodes(query: str|vector, top_k=10, filters=None)`
    - persistent file: `logs/episodes.jsonl`, optional index: `corpus/episodes.index`

- `src/self_improvement/auto_repair.py` (新規)
  - class `AutoRepairEngine`:
    - `ingest_error(log_payload)`
    - `find_similar_episodes(error_signature)`
    - `propose_fix(error_context) -> [patch_candidates]` (LLM-assisted)
    - `test_patch(patch, sandbox) -> test_result`
    - `apply_patch(patch) / create_pr(patch)`
  - Safety: requires `autonomy_level == AUTONOMOUS` and passes sandbox tests to auto-apply; otherwise create PR and notify.

**実装ステップ（短期MVP）**
1. 軽量 `EmbedStore` 抽象 + `FaissStore` 実装（wrap 現行 `Retriever` の add/search を移植） — 2 日
2. `EpisodicMemory` スケルトン（JSONL 永続、簡易検索） — 1-2 日
3. `MemoryManager` を `EpisodicMemory` に対応させ、`episode_id` を付与する — 0.5 日
4. `FeedbackManager.record_feedback()` に `episode_id` optional 引数を追加 — 0.5 日
5. 単体テスト: `tests/test_episodic_memory.py`, `tests/test_embed_store.py` — 1-2 日

**中期（堅牢化）**
- `AutoRepairEngine` プロトタイプ（LLM による候補生成 + サンドボックス検証） — 3-5 日
- 埋め込みバージョン管理とマイグレーションツール（embedding_version フィールド） — 2 日
- プラグイン化: Chroma/Pinecone 実装（環境別） — 追加 3-5 日

**テスト & CI**
- 重点: データ永続化の回帰、検索の再現性、AutoRepair のサンドボックス検証。CI に新規テストを追加し、PR 作成時にステージング実行を必須化。

**安全と運用**
- 自動修正はデフォルト無効、管理者承認を要件にする。
- エピソードには機微情報を含めない（PII マスキング）。
- 保持ポリシー（TTL）を設定し、古いエピソードはアーカイブ/削除する。

**推奨次アクション（私が行う）**
- 1) 実装前の詳細インタフェース定義ファイルを作成（`src/rag/embed_store.py` のインタフェース草案 + `src/memory/episodic_memory.py` のスケーマ例）。
- 2) MVP のパッチを作成（小さな変更で既存コードに影響しない形で追加）。

もしこの計画で良ければ、まず `embed_store` と `episodic_memory` のスケルトン実装パッチを作成してユニットテストを追加します。
