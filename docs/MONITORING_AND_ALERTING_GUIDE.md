# 本番環境 監視・アラート設定ガイド

**作成日**: 2026-05-18  
**対象**: RAG Agent with Phase 5 Learning Systems  
**バージョン**: 1.0.0

---

## 📊 監視戦略概要

本番環境での RAG Agent システムの監視は、以下の 3 層で構成されます：

1. **インフラ層**: CPU、メモリ、ディスク、ネットワーク
2. **アプリケーション層**: レスポンスタイム、スループット、エラー率
3. **ビジネス層**: 成功率、キャッシュ効率、学習効果

---

## 🎯 監視メトリクス定義

### インフラメトリクス

| メトリクス | 正常 | 警告 | クリティカル | 収集間隔 |
|---------|------|------|-----------|--------|
| CPU 使用率 | < 60% | 60-80% | > 80% | 15s |
| メモリ使用率 | < 70% | 70-85% | > 85% | 15s |
| ディスク使用率 | < 80% | 80-90% | > 90% | 60s |
| ネットワーク | 正常 | 高遅延 | パケット損失 | 30s |

### アプリケーションメトリクス

| メトリクス | 正常 | 警告 | クリティカル | 説明 |
|---------|------|------|-----------|-----|
| レスポンスタイム | < 100ms | 100-300ms | > 300ms | P95 |
| エラー率 | < 1% | 1-5% | > 5% | 400+500 errors |
| スループット | > 50 req/s | 30-50 | < 30 | requests/sec |
| アップタイム | > 99.9% | 99-99.9% | < 99% | 月間 |

### Phase 5 メトリクス

| メトリクス | 正常 | 警告 | クリティカル | 説明 |
|---------|------|------|-----------|-----|
| 成功率 | 70-90% | 50-70% | < 50% | task success % |
| キャッシュヒット率 | > 60% | 40-60% | < 40% | cache hit % |
| 記録時間 | < 1ms | 1-5ms | > 5ms | trace record ms |
| メモリ効率 | < 2KB/trace | 2-4KB | > 4KB | bytes/trace |
| インデックス検索 | < 1ms | 1-5ms | > 5ms | query latency |

---

## 🔧 Prometheus 設定

### メトリクス収集設定

```yaml
# config/prometheus.yml
global:
  scrape_interval: 15s
  scrape_timeout: 10s
  evaluation_interval: 15s
  external_labels:
    environment: 'production'
    service: 'rag-agent'

# スクレイプ設定
scrape_configs:
  # RAG Agent アプリケーション
  - job_name: 'rag-agent'
    static_configs:
      - targets: ['app:8501']
    metrics_path: '/metrics'
    scrape_interval: 15s
  
  # Node Exporter (システムメトリクス)
  - job_name: 'node'
    static_configs:
      - targets: ['localhost:9100']
    scrape_interval: 15s
  
  # Ollama LLM
  - job_name: 'ollama'
    static_configs:
      - targets: ['ollama:11434']
    metrics_path: '/metrics'
    scrape_interval: 30s
  
  # Redis キャッシング
  - job_name: 'redis'
    static_configs:
      - targets: ['redis:9121']
    scrape_interval: 15s

# アラート設定
alerting:
  alertmanagers:
    - static_configs:
        - targets: ['alertmanager:9093']

# アラートルール
rule_files:
  - '/etc/prometheus/rag_agent_alerts.yml'
```

### アラートルール定義

```yaml
# config/rag_agent_alerts.yml
groups:
  - name: rag_agent_alerts
    interval: 30s
    rules:
      # ========================================
      # インフラアラート
      # ========================================
      
      - alert: HighCpuUsage
        expr: process_cpu_percent > 80
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High CPU usage detected"
          description: "CPU usage is {{ $value }}%"
      
      - alert: CriticalCpuUsage
        expr: process_cpu_percent > 95
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Critical CPU usage"
          description: "CPU usage is {{ $value }}%"
      
      - alert: HighMemoryUsage
        expr: process_memory_mb > 800
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High memory usage detected"
          description: "Memory usage is {{ $value }} MB"
      
      - alert: CriticalMemoryUsage
        expr: process_memory_mb > 900
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Critical memory usage"
          description: "Memory usage is {{ $value }} MB"
      
      # ========================================
      # アプリケーションアラート
      # ========================================
      
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.05
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High error rate detected"
          description: "Error rate is {{ $value | humanizePercentage }}"
      
      - alert: CriticalErrorRate
        expr: rate(http_requests_total{status=~"5.."}[1m]) > 0.1
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Critical error rate"
          description: "Error rate is {{ $value | humanizePercentage }}"
      
      - alert: HighResponseTime
        expr: histogram_quantile(0.95, http_request_duration_ms) > 300
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High response time detected"
          description: "P95 latency is {{ $value }}ms"
      
      - alert: LowThroughput
        expr: rate(http_requests_total[1m]) < 30
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Low throughput detected"
          description: "Throughput is {{ $value }} req/s"
      
      - alert: ServiceDown
        expr: up{job="rag-agent"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "RAG Agent service is down"
          description: "Cannot reach RAG Agent service"
      
      # ========================================
      # Phase 5 メトリクスアラート
      # ========================================
      
      - alert: LowSuccessRate
        expr: phase5_success_rate < 0.5
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Low task success rate"
          description: "Success rate is {{ $value | humanizePercentage }}"
      
      - alert: CriticalLowSuccessRate
        expr: phase5_success_rate < 0.3
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Critical success rate drop"
          description: "Success rate is {{ $value | humanizePercentage }}"
      
      - alert: LowCacheHitRate
        expr: phase5_cache_hit_rate < 0.4
        for: 15m
        labels:
          severity: warning
        annotations:
          summary: "Low cache hit rate"
          description: "Cache hit rate is {{ $value | humanizePercentage }}"
      
      - alert: SlowTraceRecording
        expr: phase5_trace_record_time_ms > 5
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Slow trace recording detected"
          description: "Recording time is {{ $value }}ms"
      
      - alert: HighMemoryPerTrace
        expr: phase5_memory_per_trace_bytes > 4000
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "High memory usage per trace"
          description: "Memory per trace is {{ $value }}B"
      
      - alert: SlowIndexSearch
        expr: phase5_index_search_time_ms > 5
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Slow index search"
          description: "Search time is {{ $value }}ms"
```

---

## 🔔 Alertmanager 設定

### 通知ルーティング設定

```yaml
# config/alertmanager.yml
global:
  resolve_timeout: 5m
  slack_api_url: 'YOUR_SLACK_WEBHOOK_URL'

route:
  receiver: 'default'
  group_by: ['alertname', 'job']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 12h
  
  routes:
    # Critical アラート → 即座に通知
    - match:
        severity: critical
      receiver: 'critical'
      continue: true
      repeat_interval: 30m
    
    # Warning アラート → 定期通知
    - match:
        severity: warning
      receiver: 'warning'
      repeat_interval: 4h
    
    # Information → Slack
    - match:
        severity: info
      receiver: 'slack'
      repeat_interval: 24h

receivers:
  - name: 'default'
    slack_configs:
      - channel: '#alerts'
        title: 'Alert: {{ .GroupLabels.alertname }}'
        text: '{{ range .Alerts }}{{ .Annotations.description }}{{ end }}'
  
  - name: 'critical'
    slack_configs:
      - channel: '#critical-alerts'
        title: '🔴 CRITICAL: {{ .GroupLabels.alertname }}'
        text: '{{ range .Alerts }}{{ .Annotations.description }}{{ end }}'
    email_configs:
      - to: 'sre-team@company.com'
        from: 'alertmanager@company.com'
        smarthost: 'smtp.gmail.com:587'
        auth_username: 'alerts@company.com'
        auth_password: 'password'
  
  - name: 'warning'
    slack_configs:
      - channel: '#warnings'
        title: '⚠️ WARNING: {{ .GroupLabels.alertname }}'
        text: '{{ range .Alerts }}{{ .Annotations.description }}{{ end }}'
  
  - name: 'slack'
    slack_configs:
      - channel: '#rag-agent-logs'
        title: 'ℹ️ INFO: {{ .GroupLabels.alertname }}'
        text: '{{ range .Alerts }}{{ .Annotations.description }}{{ end }}'

inhibit_rules:
  # Critical が発火すれば Warning を抑制
  - source_match:
      severity: 'critical'
    target_match:
      severity: 'warning'
    equal: ['alertname', 'job']
```

---

## 📈 Grafana ダッシュボード設定

### ダッシュボード 1: システム概観

```
Title: RAG Agent - System Overview

Panels:
1. Service Status (ゲージ)
   - Query: up{job="rag-agent"}
   - Thresholds: 0=red, 1=green
   
2. CPU Usage (折れ線グラフ)
   - Query: rate(process_cpu_percent[5m])
   - Threshold: 80% warning
   
3. Memory Usage (折れ線グラフ)
   - Query: process_memory_mb
   - Threshold: 800MB warning
   
4. Request Count (バーグラフ)
   - Query: rate(http_requests_total[1m])
   - Breakdown by status code
   
5. Error Rate (折れ線グラフ)
   - Query: rate(http_requests_total{status=~"5.."}[5m])
   - Threshold: 5% warning
   
6. Response Time P95 (折れ線グラフ)
   - Query: histogram_quantile(0.95, http_request_duration_ms)
   - Threshold: 300ms warning
```

### ダッシュボード 2: Phase 5 メトリクス

```
Title: Phase 5 Learning Systems Metrics

Panels:
1. Success Rate (ゲージ)
   - Query: phase5_success_rate
   - Range: 0-100%
   
2. Cache Hit Rate (ゲージ)
   - Query: phase5_cache_hit_rate
   - Range: 0-100%
   
3. Trace Recording Time (折れ線グラフ)
   - Query: phase5_trace_record_time_ms
   - Threshold: 1ms optimal
   
4. Memory per Trace (折れ線グラフ)
   - Query: phase5_memory_per_trace_bytes
   - Threshold: 1100B optimal
   
5. Index Search Time (折れ線グラフ)
   - Query: phase5_index_search_time_ms
   - Threshold: 1ms optimal
   
6. Task Distribution (パイチャート)
   - Query: phase5_task_count by (task_family)
   
7. Learning System Status (テーブル)
   - Query: phase5_system_status
   - Columns: System, Active?, Last Update
```

---

## 📊 ダッシュボード作成手順

### Grafana にログイン

```
1. URL: http://localhost:3000
2. ユーザー: admin
3. パスワード: (.env.production から取得)
4. 言語: 日本語に変更 (Profile > Language)
```

### Prometheus データソース追加

```
1. Settings (左下ギア) > Data Sources
2. Add data source
3. Prometheus を選択
4. URL: http://prometheus:9090
5. Save & Test
```

### ダッシュボード作成

```
1. + (左サイドバー) > Dashboard
2. + Add Panel
3. データソース: Prometheus を選択
4. Metric を入力（例: phase5_success_rate）
5. Panel Title を設定
6. Visualization 設定
7. Save
```

### テンプレート変数設定

```
1. Dashboard Settings > Variables
2. + Add variable
3. 名前: job
4. Query: label_values(up, job)
5. 保存
```

---

## 🎯 監視アラート応答フロー

### Critical アラート発火時

```
1. Alert 発火
   ↓
2. Slack に通知 (3秒以内)
   - #critical-alerts に投稿
   - @here でメンション
   ↓
3. Email 送信 (SRE チーム)
   ↓
4. PagerDuty 作成 (オンコール)
   ↓
5. Grafana ダッシュボード確認
   - 対象メトリクス表示
   - タイムラインで問題検出
   ↓
6. ログ確認
   - kubectl logs -f rag-agent-app
   ↓
7. 原因判定
   - インフラ問題 → SRE 対応
   - アプリ問題 → 開発チーム対応
   ↓
8. 対応実施
   - ロールバック / スケール / 再起動
   ↓
9. 検証
   - メトリクス確認
   - ヘルスチェック実行
   ↓
10. ポストモーテム作成
```

### Warning アラート対応

```
1. Slack に通知 (定期的)
   ↓
2. 当番者が確認
   ↓
3. Grafana でトレンド確認
   ↓
4. パフォーマンス改善提案
   ↓
5. 次のメンテナンス窓で対応
```

---

## 📋 監視チェックリスト

### 毎日

- [ ] Alert Manager でアラートをチェック
- [ ] Grafana メインダッシュボード確認
- [ ] エラーログをスキャン
- [ ] メモリ使用量トレンド確認

### 毎週

- [ ] Phase 5 メトリクスレビュー
- [ ] パフォーマンストレンド分析
- [ ] キャッシュ効率評価
- [ ] ユーザーからのフィードバック収集

### 毎月

- [ ] アップタイムレポート生成
- [ ] パフォーマンスレポート作成
- [ ] セキュリティレビュー実施
- [ ] キャパシティプランニング更新

---

## 🛠️ デバッグコマンド

### メトリクス確認

```bash
# 全メトリクス取得
curl -s http://localhost:9090/api/v1/query?query=up | jq

# 特定メトリクス取得
curl -s 'http://localhost:9090/api/v1/query?query=phase5_success_rate' | jq

# メトリクス範囲クエリ
curl -s 'http://localhost:9090/api/v1/query_range?query=phase5_cache_hit_rate&start=1672531200&end=1672617600&step=300' | jq
```

### アラート確認

```bash
# アラート一覧
curl -s http://localhost:9090/api/v1/alerts | jq

# 発火中のアラート
curl -s http://localhost:9090/api/v1/alerts | jq '.data.alerts[] | select(.state=="firing")'
```

### ログ確認

```bash
# Prometheus ログ
docker logs rag-prometheus | grep ERROR

# Alertmanager ログ
docker logs rag-alertmanager | grep ERROR

# アプリケーションログ
docker logs rag-agent-app | grep ERROR
```

---

## 📞 監視チーム連絡先

**オンコール体制**: 24/7 rotating

**連絡先**:
- **主任 SRE**: abemc
- **副任 SRE**: Team Lead
- **緊急時**: +81-90-xxxx-xxxx (Slack 優先)

**Slack チャンネル**:
- #rag-agent-alerts: Critical & Warning
- #rag-agent-logs: Info & Debug
- #rag-agent-deployment: デプロイメント情報

---

**監視設定準備完了**: 🟢 **本番環境対応可能**

