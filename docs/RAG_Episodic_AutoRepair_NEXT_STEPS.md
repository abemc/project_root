次アクション提案（短期優先）

1) 影響の少ないパッチをコミットして PR を作成
   - 新規ファイル: `src/rag/embed_store.py`, `src/memory/episodic_memory.py`
   - 新規テスト: `tests/test_embed_store.py`, `tests/test_episodic_memory.py`
   - 目的: MVP を main branch に統合し CI で回す

2) `MemoryManager` と `FeedbackManager` の統合作業
   - `MemoryManager.summarize_and_store()` が `retriever.add_texts()` を使う代わりに、`EpisodicMemory` へも保存できるように拡張
   - `FeedbackManager.record_feedback()` に `episode_id` オプションを追加

3) AutoRepair のデザイン & プロトタイプ
   - `src/self_improvement/auto_repair.py` のスケルトンを作成
   - LLM を使ったパッチ提案はオプション (最初はルールベースでカバー)
   - サンドボックス検証フレームワーク（既存の `Sandbox` を活用）を使う

4) CI と監査
   - 新規テストを CI に追加
   - 自動修正のログと承認フローの設計

推奨: まずコミットして PR を作り、CI 実行で問題がないか確認した後に `MemoryManager` 側の統合を進めます。
