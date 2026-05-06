# 本番デプロイメントガイド：自律型RAGエージェント

**最終更新**: 2026-05-02  
**対象フェーズ**: Phase 20 (Production Readiness)

---

## 1. 概要
本ドキュメントは、開発された自律型RAGエージェントをエンタープライズ本番環境にデプロイするための手順とベストプラクティスをまとめたものです。

## 2. 構成要素
- **Web UI**: Streamlit (ポート 8501)
- **Agent Core**: Python 3.10+
- **Database/Cache**: Redis 7.2 (ポート 6379)
- **Search Engine**: FAISS (ローカルファイル) + Web Search (SearXNG等)

## 3. デプロイ手順

### 3.1 Docker Compose による起動
推奨されるデプロイ方法は Docker です。

```bash
# Redis サーバーの起動
docker-compose -f docker-compose-redis.yml up -d

# アプリケーションの起動
streamlit run app.py --server.port 8501
```

### 3.2 環境変数の設定 (`.env`)
本番環境では以下の項目を必ず設定してください。

```ini
# セキュリティ
ENCRYPTION_KEY=your_secure_key_here
AUDIT_LOG_ENABLED=true

# パフォーマンス
RAG_CACHE_ENABLED=true
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=your_redis_password

# SLA
RAG_INDEX_REBUILD_THRESHOLD=1000
```

## 4. 運用・監視

### 4.1 SLA ダッシュボード
UI上の「🛡️ エンタープライズ統合」ページから、リアルタイムの可用性とレイテンシを確認できます。

### 4.2 バックアップ戦略
- **コーパス**: `corpus/` ディレクトリを定期的にスナップショット取得。
- **監査ログ**: `logs/audit.jsonl` を外部ストレージ（S3等）へログ転送。

## 5. スケーリング
- **垂直スケーリング**: FAISSインデックスのロードと埋め込みモデルの実行のため、十分なRAM (16GB+) と GPU (推奨) を確保してください。
- **水平スケーリング**: Redisを共有することで、複数のUIノード間でキャッシュを同期可能です。

---

**お問い合わせ**: システム管理者まで。
