# 本番環境デプロイメント手順書

**作成日**: 2026-05-18  
**対象**: RAG Agent with Phase 5 Learning Systems  
**バージョン**: 1.0.0  
**ステータス**: 本番環境対応

---

## 📋 事前準備

### 1. デプロイ環境確認

```bash
# OS 確認
uname -a

# Docker インストール確認
docker --version
docker-compose --version

# Python インストール確認
python --version

# 権限確認
groups | grep docker
```

**必須**:
- Docker 20.10+
- Docker Compose 2.0+
- Python 3.10+
- Linux ユーザーが docker グループに属している

### 2. リポジトリのクローン

```bash
# リポジトリをクローン
git clone https://github.com/your-org/rag-agent.git
cd rag-agent

# main ブランチに切り替え
git checkout main

# 最新版を取得
git pull origin main

# バージョン確認
git describe --tags
```

### 3. 本番環境設定ファイルの準備

```bash
# 設定ファイルをコピー
cp .env.production.example .env.production

# 必須項目を編集
vim .env.production

# 確認項目 (チェックリスト参照)
```

**編集が必要な項目**:
```
- APP_ENV: production に設定
- DEBUG: false に設定
- OLLAMA_HOST: 本番環境ホストに変更
- GRAFANA_ADMIN_PASSWORD: 強力なパスワードに変更
- REDIS_PASSWORD: 設定 (Redis 有効時)
- DB_PASSWORD: 設定 (DB 有効時)
```

---

## 🚀 デプロイメント実行

### フェーズ 1: ビルド & テスト

```bash
# 1. イメージビルド
docker build -t rag-agent:phase5-latest -f Dockerfile.production .

# 2. イメージ確認
docker images | grep rag-agent

# 3. セキュリティスキャン (オプション)
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
  aquasec/trivy image rag-agent:phase5-latest

# 4. ローカルテスト (オプション)
docker run --rm -it \
  -p 8501:8501 \
  --env-file .env.production \
  rag-agent:phase5-latest
```

### フェーズ 2: コンテナ起動

```bash
# 1. 前のコンテナを停止 (既に実行中の場合)
docker-compose -f docker-compose.production.yml down

# 2. イメージをプル/ビルド
docker-compose -f docker-compose.production.yml build

# 3. バックグラウンドで起動
docker-compose -f docker-compose.production.yml up -d

# 4. サービス状態確認
docker-compose -f docker-compose.production.yml ps

# 出力例:
# NAME                COMMAND             SERVICE     STATUS
# rag-agent-app       streamlit run...    app         Up (healthy)
# rag-ollama          ollama serve        ollama      Up (healthy)
# rag-prometheus      prometheus          prometheus  Up
# rag-grafana         /run.sh             grafana     Up
# rag-redis           redis-server        redis       Up
```

### フェーズ 3: ヘルスチェック

```bash
# 1. Streamlit ヘルスチェック
curl -f http://localhost:8501/healthz
echo "Status: OK" 

# 2. Ollama ヘルスチェック
curl -f http://localhost:11434/api/tags
echo "Status: OK"

# 3. Prometheus ヘルスチェック
curl -f http://localhost:9090/-/healthy
echo "Status: OK"

# 4. Grafana ヘルスチェック
curl -f http://localhost:3000/api/health
echo "Status: OK"

# 5. Redis ヘルスチェック
docker exec rag-redis redis-cli ping
# Expected: PONG
```

### フェーズ 4: ログ確認

```bash
# 1. アプリケーションログ確認
docker-compose -f docker-compose.production.yml logs -f app

# 2. エラーログ確認
docker-compose -f docker-compose.production.yml logs app | grep ERROR

# 3. 全サービスログ確認
docker-compose -f docker-compose.production.yml logs

# 4. ログをファイルに保存
docker-compose -f docker-compose.production.yml logs > deployment.log
```

### フェーズ 5: パフォーマンステスト

```bash
# 1. 基本レスポンステスト
for i in {1..10}; do
  echo "Test $i:"
  time curl -s http://localhost:8501/healthz > /dev/null
done

# 2. 負荷テスト (Apache Bench)
ab -n 100 -c 10 http://localhost:8501/

# 3. メトリクス確認
curl -s http://localhost:9090/api/v1/query?query=up | jq
```

---

## 📊 監視ダッシュボードセットアップ

### Grafana ダッシュボード設定

```bash
# 1. Grafana にアクセス
# URL: http://localhost:3000
# ユーザー: admin
# パスワード: (.env.production の GRAFANA_ADMIN_PASSWORD)

# 2. Prometheus をデータソースとして追加
# Settings > Data Sources > Add new > Prometheus
# URL: http://prometheus:9090
# Save & Test

# 3. ダッシュボード作成
# Create > Dashboard > Add Panel
# Metrics: phase5_cache_hit_rate, phase5_success_rate など

# 4. アラート設定
# Alert Rules > Create > 
# Query: success_rate < 70
# Condition: Alert when below
```

### Prometheus アラート設定

```bash
# 1. アラートルール確認
curl http://localhost:9090/api/v1/rules

# 2. カスタムアラートを追加
# config/prometheus_alerts.yml を編集

cat > config/prometheus_alerts.yml << 'EOF'
groups:
  - name: rag_agent_alerts
    interval: 30s
    rules:
      - alert: HighErrorRate
        expr: error_rate > 0.05
        for: 5m
        annotations:
          summary: "High error rate detected"
      
      - alert: LowCacheHitRate
        expr: phase5_cache_hit_rate < 0.4
        for: 10m
        annotations:
          summary: "Cache hit rate is low"
      
      - alert: HighMemoryUsage
        expr: memory_usage_mb > 800
        for: 5m
        annotations:
          summary: "Memory usage is high"
EOF

# 3. Prometheus を再起動してアラートを反映
docker-compose -f docker-compose.production.yml restart prometheus
```

---

## 🔐 セキュリティ確認

### SSL/TLS 設定 (本番環境推奨)

```bash
# 1. 自己署名証明書生成 (テスト用)
mkdir -p certs
openssl req -x509 -newkey rsa:4096 -keyout certs/key.pem -out certs/cert.pem -days 365 -nodes

# 2. Let's Encrypt 証明書取得 (推奨)
# certbot コマンドを使用
certbot certonly --standalone -d your-domain.com

# 3. Docker コンテナに証明書をマウント
# docker-compose.production.yml の volumes に追加:
# - ./certs:/app/certs:ro
```

### ファイアウォール設定

```bash
# 1. 必要なポートのみを公開
sudo ufw allow 8501/tcp   # Streamlit
sudo ufw allow 3000/tcp   # Grafana
sudo ufw allow 9090/tcp   # Prometheus (内部ネットワークのみ)
sudo ufw allow 11434/tcp  # Ollama (内部ネットワークのみ)

# 2. 不要なポートをブロック
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw enable
```

### シークレット管理

```bash
# 1. Docker Secrets を使用 (Swarm モード時)
echo "your_secret_password" | docker secret create db_password -

# 2. Vault を使用 (推奨・将来対応)
vault kv put secret/rag-agent \
  db_password="secure_password" \
  api_key="secret_key"
```

---

## 📈 デプロイ後の確認

### 1 時間チェック

```bash
# メトリクス確認
curl -s http://localhost:9090/api/v1/query?query=up | jq
curl -s http://localhost:9090/api/v1/query?query=phase5_success_rate | jq

# ログエラー確認
docker-compose -f docker-compose.production.yml logs app | grep ERROR | wc -l

# リソース使用状況
docker stats rag-agent-app --no-stream
```

### 24 時間チェック

```bash
# アップタイム確認
docker-compose -f docker-compose.production.yml ps

# キャッシュ効率確認
curl -s "http://localhost:9090/api/v1/query?query=phase5_cache_hit_rate" | jq

# 成功率確認
curl -s "http://localhost:9090/api/v1/query?query=phase5_success_rate" | jq

# メモリ使用量トレンド
curl -s "http://localhost:9090/api/v1/query_range?query=memory_usage_mb&start=1&end=2&step=60" | jq
```

### 1 週間レビュー

```bash
# パフォーマンスレポート生成
cat > performance_report.sh << 'EOF'
#!/bin/bash
echo "=== 1 Week Performance Report ==="
echo "Uptime:"
docker-compose -f docker-compose.production.yml ps

echo "Metrics:"
curl -s "http://localhost:9090/api/v1/query?query=up" | jq

echo "Success Rate (average):"
curl -s "http://localhost:9090/api/v1/query?query=avg(phase5_success_rate)" | jq

echo "Cache Hit Rate (average):"
curl -s "http://localhost:9090/api/v1/query?query=avg(phase5_cache_hit_rate)" | jq

echo "Max Memory Usage:"
curl -s "http://localhost:9090/api/v1/query?query=max(memory_usage_mb)" | jq
EOF

chmod +x performance_report.sh
./performance_report.sh
```

---

## 🔄 デプロイ後の運用

### 日次チェック

```bash
# システムヘルスチェック
./scripts/health_check.sh

# ログローテーション確認
ls -la logs/

# バックアップ確認
ls -la backups/ | tail -5
```

### 週次メンテナンス

```bash
# イメージの更新確認
docker images | grep rag-agent

# 古いイメージをクリーンアップ
docker image prune -a --force

# ボリュームの確認
docker volume ls | grep rag

# ディスク使用量確認
df -h
```

### 月次メンテナンス

```bash
# パフォーマンス分析
# Grafana ダッシュボードからレポート生成

# セキュリティアップデート確認
docker pull mcr.microsoft.com/devcontainers/python:3.10

# ドキュメント更新
# パフォーマンス改善案をまとめる
```

---

## ⏮️ ロールバック手順

### 緊急ロールバック

```bash
# 1. 前のイメージバージョンを確認
docker images | grep rag-agent

# 2. コンテナを停止
docker-compose -f docker-compose.production.yml down

# 3. 前のイメージを使用して再起動
docker tag rag-agent:phase5-previous rag-agent:phase5-current
docker-compose -f docker-compose.production.yml up -d

# 4. ヘルスチェック実行
curl -f http://localhost:8501/healthz
echo "Status: OK"
```

### グレースフルロールバック

```bash
# 1. 新しいトラフィックを古いバージョンへ
# ロードバランサー設定を変更

# 2. 既存接続の終了を待つ
sleep 60

# 3. 新しいコンテナを停止
docker-compose -f docker-compose.production.yml stop

# 4. ダウンタイムゼロデプロイ完了
```

---

## 🆘 トラブルシューティング

### コンテナが起動しない

```bash
# ログを確認
docker-compose -f docker-compose.production.yml logs app

# 一般的な問題:
# 1. ポート競合: 既存プロセスをチェック
lsof -i :8501

# 2. メモリ不足: リソース制限を確認
free -h

# 3. イメージエラー: ビルドをやり直す
docker-compose -f docker-compose.production.yml build --no-cache
```

### 高い CPU 使用率

```bash
# CPU 使用率確認
docker stats rag-agent-app

# プロセスの詳細確認
docker exec rag-agent-app ps aux

# ロギングレベルを低下
docker exec rag-agent-app streamlit config set logger.level warning
```

### メモリリーク疑い

```bash
# メモリ使用量トレンド確認
docker stats rag-agent-app --no-stream --interval 5 | head -20

# コンテナ再起動
docker-compose -f docker-compose.production.yml restart app

# メモリダンプ採取
docker exec rag-agent-app python -m pympler.asizeof
```

---

## 📞 サポート連絡先

**デプロイメント中の問題**:
- **担当者**: abemc
- **Slack**: #rag-agent-deployment
- **緊急時**: +81-90-xxxx-xxxx

**営業時間**: 09:00-18:00 (日本時間)

---

## ✅ デプロイメント完了チェック

デプロイメント完了後に確認:

```bash
[ ] ポート 8501 でアクセス可能
[ ] ヘルスチェック成功
[ ] ログにエラーなし
[ ] メトリクス取得可能
[ ] Grafana ダッシュボード表示
[ ] パフォーマンステスト合格
[ ] 全ユーザーからのアクセス確認
[ ] 24 時間安定実行確認
```

---

**デプロイメント準備完了**: 🟢 **いつでも実行可能**

