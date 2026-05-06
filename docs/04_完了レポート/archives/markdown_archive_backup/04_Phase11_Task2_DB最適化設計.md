# 🔄 Task 2: DB クエリ最適化 設計書

**フェーズ**: Phase 11 - Task 2  
**期間**: Week 2-3 (2 週間)  
**バージョン**: v1.0  
**作成日**: 2026-04-17  
**ステータス**: 📋 設計フェーズ

---

## 🎯 概要

Phase 10 での DB クエリのスロー化を、インデックス戦略・クエリリライト・Connection Pool 最適化により、DB CPU を 40% 削減し、API レイテンシを 40% 削減するタスク。

### 成功基準
- 🎯 スロークエリ削減: **-89%** (45個 → 5個以下)
- 🎯 平均クエリ時間: **-67%** (120ms → 35ms)
- 🎯 DB CPU: **-40%** (75% → 45%)
- 🎯 DB コネクション: **-40%** (200 → 120)
- 🎯 API レイテンシ削減: **-40%** (全体)

---

## 📊 現在の問題点

### Phase 10 DB 分析結果

```
Total Queries/sec:          52,000 req/s
Slow Queries (>100ms):      45 クエリパターン
Slow Query %:               8.7% (4,524 req/s)

Average Query Time:         120ms
Query Time Distribution:
  < 10ms:   35,000 req/s (67%)
  10-100ms: 11,000 req/s (21%)
  > 100ms:  6,000 req/s  (12%) ← 問題範囲

DB CPU Usage:               75%
DB Memory Usage:            82%
DB Connections:             200 (max)
Connection Pool Utilization: 85%

Index Count:                15 個
Missing Indexes:            12 個 (推定)
Table Scans:                234 queries/sec
N+1 Queries:                8 パターン

Bottlenecks:
  1. フルテーブルスキャン (audit_logs, activity_logs)
  2. 権限チェックの N+1 クエリ
  3. ログ集計の複雑なジョイン
  4. コネクションプール飽和
```

---

## 🔧 最適化戦略

### 1. インデックス戦略

#### 1.1 追加予定インデックス (12個)

```sql
-- Layer 1: Authentication (3個)
CREATE INDEX idx_auth_sessions_user_role 
  ON auth_sessions(user_id, role, created_at DESC)
  WHERE is_active = true;

CREATE INDEX idx_auth_sessions_tenant_status 
  ON auth_sessions(tenant_id, status, expiry DESC)
  WHERE is_active = true;

CREATE INDEX idx_users_tenant_role 
  ON users(tenant_id, role, last_login DESC);

-- Layer 2: Encryption (2個)
CREATE INDEX idx_encryption_keys_context_status 
  ON encryption_keys(context_id, status, expiry DESC)
  WHERE status IN ('active', 'rotating');

CREATE INDEX idx_key_versions_key_id_date 
  ON key_versions(key_id, created_at DESC);

-- Layer 3: Network (1個)
CREATE INDEX idx_network_policies_tenant_status 
  ON network_policies(tenant_id, status, priority DESC)
  WHERE status = 'active';

-- Layer 4: SOC (2個)
CREATE INDEX idx_threat_alerts_timestamp_level 
  ON threat_alerts(created_at DESC, severity)
  WHERE status = 'open';

CREATE INDEX idx_threat_intelligence_indicators 
  ON threat_intelligence(indicator_type, indicator_value)
  WHERE is_current = true;

-- Layer 6: Compliance (2個)
CREATE INDEX idx_compliance_checks_entity_date 
  ON compliance_checks(entity_type, entity_id, check_date DESC);

CREATE INDEX idx_audit_logs_timestamp_level 
  ON audit_logs(created_at DESC, severity)
  WHERE created_at > CURRENT_DATE - INTERVAL '90 days';
```

**期待効果**:
- フルテーブルスキャン: 234 → 15 queries/sec (-94%)
- インデックスヒット率: 50% → 85% (+70%)
- 平均クエリ時間: 120ms → 50ms (-58%)

#### 1.2 インデックス設計原則

```
複合インデックス (Composite Index):
  - WHERE 句条件を最初に配置
  - 結果絞り込み条件を次に配置
  - SELECT 句カラムを最後に配置（Covering Index）

例: WHERE tenant_id = ? AND status = 'active' ORDER BY created_at DESC
    → idx_table(tenant_id, status, created_at DESC) ✅

部分インデックス (Partial Index):
  - WHERE is_active = true など頻度の高い条件
  - ストレージ 50% 削減可能
  - クエリ実行速度 +30% 改善

Covering Index:
  - すべての必要カラムを含める
  - テーブルスキャン不要
  - メモリ使用量 +20% (許容)
```

---

### 2. クエリリライト戦略

#### 2.1 主要な最適化対象クエリ

**パターン 1: N+1 クエリ (権限チェック)**

```python
# ❌ 現在 (N+1 問題) - 1000+ クエリ実行
users = get_users(tenant_id)  # 1 クエリ
for user in users:
    perms = get_permissions(user.id)  # N クエリ (最大 1000)
    # 合計: 1 + 1000 = 1001 クエリ

# ✅ 最適化後 (1 クエリ + JOIN)
permissions = db.query("""
  SELECT u.id, u.name, p.permission
  FROM users u
  LEFT JOIN permissions p ON u.id = p.user_id
  WHERE u.tenant_id = %s
  ORDER BY u.id, p.permission
""", (tenant_id,))  # 1 クエリ
# 削減: -99.9% (1001 → 1)
```

**パターン 2: ログ集計の複雑なジョイン**

```sql
-- ❌ 現在 (複数ジョイン、集計) - 平均 250ms
SELECT 
  u.user_id,
  COUNT(*) as total_actions,
  MAX(al.created_at) as last_action,
  COUNT(CASE WHEN al.severity = 'ERROR' THEN 1 END) as error_count
FROM users u
JOIN audit_logs al ON u.id = al.user_id
JOIN compliance_records cr ON al.record_id = cr.id
JOIN security_contexts sc ON u.context_id = sc.id
WHERE u.tenant_id = %s
  AND al.created_at > NOW() - INTERVAL '7 days'
GROUP BY u.user_id
HAVING error_count > 0
ORDER BY error_count DESC
LIMIT 100;
-- 実行計画: Full Scan → Hash Join × 3 → Aggregate

-- ✅ 最適化後 (Covering Index + 簡潔化) - 平均 35ms
SELECT 
  user_id,
  COUNT(*) as total_actions,
  MAX(created_at) as last_action,
  COUNT(CASE WHEN severity = 'ERROR' THEN 1 END) as error_count
FROM audit_logs
WHERE tenant_id = %s
  AND created_at > NOW() - INTERVAL '7 days'
GROUP BY user_id
HAVING error_count > 0
ORDER BY error_count DESC
LIMIT 100;
-- 実行計画: Index Range Scan → Stream Aggregate
-- 削減: -86% (250ms → 35ms)
```

**パターン 3: IN 句の大量値**

```python
# ❌ 現在 (IN 句に 1000+ 値) - 平均 180ms
user_ids = [1, 2, 3, ..., 1000]
results = db.query(f"""
  SELECT * FROM user_profiles
  WHERE user_id IN ({','.join(['%s'] * len(user_ids))})
""", user_ids)
# 問題: IN 句内 1000 要素でプランキャッシュ効率低下

# ✅ 最適化後 (一時テーブル + JOIN) - 平均 45ms
db.execute("""
  CREATE TEMP TABLE user_ids_temp (id INT PRIMARY KEY)
""")
db.executemany(
  "INSERT INTO user_ids_temp VALUES (%s)",
  [(uid,) for uid in user_ids]
)
results = db.query("""
  SELECT up.* 
  FROM user_profiles up
  INNER JOIN user_ids_temp ut ON up.user_id = ut.id
""")
# 削減: -75% (180ms → 45ms)
```

**パターン 4: サブクエリの非効率**

```sql
-- ❌ 現在 (サブクエリ × 複数) - 平均 150ms
SELECT u.id, u.name, (
  SELECT COUNT(*) FROM audit_logs 
  WHERE user_id = u.id AND created_at > NOW() - INTERVAL '7 days'
) as recent_actions
FROM users u
WHERE tenant_id = %s
  AND u.id IN (
    SELECT user_id FROM threat_alerts 
    WHERE severity = 'CRITICAL'
  );

-- ✅ 最適化後 (左外結合 + GROUP BY) - 平均 38ms
SELECT 
  u.id,
  u.name,
  COUNT(DISTINCT al.id) as recent_actions
FROM users u
LEFT JOIN audit_logs al ON u.id = al.user_id 
  AND al.created_at > NOW() - INTERVAL '7 days'
INNER JOIN threat_alerts ta ON u.id = ta.user_id 
  AND ta.severity = 'CRITICAL'
WHERE u.tenant_id = %s
GROUP BY u.id, u.name;
-- 削減: -75% (150ms → 38ms)
```

---

### 3. Connection Pool 最適化

#### 3.1 現在の設定

```yaml
# Phase 10 設定
PostgreSQL:
  max_connections: 200
  shared_buffers: 25% of RAM
  effective_cache_size: 75% of RAM
  work_mem: shared_buffers / 16

Application Connection Pool:
  pool_size: 20
  max_overflow: 20
  pool_timeout: 30s
  pool_recycle: 3600s
```

**問題点**:
- 接続リサイクル時間が長い (3600s = 1時間)
- アイドル接続が蓄積
- ピーク時に接続飽和 (200/200)

#### 3.2 最適化後の設定

```yaml
# Phase 11 設定
PostgreSQL:
  max_connections: 120  # -40%
  shared_buffers: 25% of RAM (変更なし)
  effective_cache_size: 75% of RAM (変更なし)
  work_mem: shared_buffers / 16 (変更なし)

Application Connection Pool:
  pool_size: 15         # -25%
  max_overflow: 15      # -25%
  pool_timeout: 10s     # -67%
  pool_recycle: 300s    # -92% (5分へ短縮)
  pool_pre_ping: true   # 接続検証追加

Connection Monitoring:
  alert_threshold: 80%  # 96 接続時
  idle_timeout: 5min    # アイドル接続自動切断
```

**期待効果**:
- メモリ使用量: -40%
- 接続確立: -50% (不要な再接続削減)
- リソース競合: -60%

---

### 4. テーブル分割・アーカイビング戦略

#### 4.1 ホットテーブル分析

```
audit_logs:
  - 総行数: 500M 行
  - 1 日新規: 50M 行
  - クエリ: 95% が 90 日以内

activity_logs:
  - 総行数: 300M 行
  - 1 日新規: 30M 行
  - クエリ: 90% が 30 日以内

threat_logs:
  - 総行数: 100M 行
  - 1 日新規: 10M 行
  - クエリ: 95% が 60 日以内
```

#### 4.2 パーティショニング戦略

```sql
-- audit_logs: 日次パーティション
CREATE TABLE audit_logs_2026_04_17 PARTITION OF audit_logs
  FOR VALUES FROM ('2026-04-17') TO ('2026-04-18');

-- 旧データ自動削除ルール
CREATE TABLE audit_logs_archive_2026_01 PARTITION OF audit_logs
  FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');

-- 定期メンテナンス
-- 毎日 00:00: 新しいパーティション作成
-- 毎月 1 日: 90 日以上前のデータをアーカイブ
-- 毎月 5 日: アーカイブ圧縮 (GZIP)
```

**期待効果**:
- クエリ実行時間: -30% (スキャン範囲削減)
- ストレージ: -25% (圧縮)
- メモリ: -20% (バッファプール効率向上)

---

## 🛠️ 実装フェーズ

### Phase 1: インデックス追加 (Day 1-2)

```
Step 1: 現在の低速クエリ分析
  - pg_stat_statements から遅いクエリを抽出
  - EXPLAIN ANALYZE で実行計画確認
  - 不足インデックスを特定

Step 2: 本番環境へのインデックス追加
  - CONCURRENTLY オプションで追加 (テーブルロック回避)
  - 1 インデックスあたり 2-5 分
  - 12 インデックス × 平均 3 分 = 36 分

Step 3: インデックス検証
  - クエリプラン確認
  - パフォーマンス測定
  - 正常性チェック

実行例:
CREATE INDEX CONCURRENTLY idx_auth_sessions_user_role
  ON auth_sessions(user_id, role, created_at DESC)
  WHERE is_active = true;
-- 本番テーブルをロックせず追加
-- 既存クエリは影響なし
```

### Phase 2: クエリリライト (Day 2-3)

```
Step 1: N+1 クエリ検出
  - APM (New Relic/DataDog) でシーケンシャルクエリ検出
  - コード内で SELECT ループ発見

Step 2: クエリ統合
  - JOIN に変更
  - サブクエリの最適化
  - テンポラリテーブル活用

Step 3: テスト
  - 単体テスト (結果の同一性)
  - パフォーマンステスト
  - 回帰テスト

実装例:
# 変更前: N+1
permissions_by_user = {}
for user in users:
  permissions_by_user[user.id] = get_user_permissions(user.id)

# 変更後: JOIN
result = db.query("""
  SELECT u.id, p.permission
  FROM users u
  LEFT JOIN permissions p ON u.id = p.user_id
  WHERE u.tenant_id = %s
""")
permissions_by_user = group_by_user(result)
```

### Phase 3: Connection Pool 最適化 (Day 3)

```
Step 1: 設定変更
  - pool_size: 20 → 15
  - pool_recycle: 3600s → 300s
  - pool_timeout: 30s → 10s

Step 2: リリース
  - Staging で検証
  - ロールアウト (段階的)

Step 3: 監視
  - コネクション使用率
  - タイムアウト発生数
  - エラーログ
```

### Phase 4: テーブル分割 (Day 4-6)

```
既存テーブル → パーティション テーブルへの移行

Step 1: パーティション テーブル作成
  - audit_logs_partitioned テーブル作成
  - 過去データ移行
  
Step 2: 段階的切り替え
  - ビュー経由でトランスペアレント化
  - アプリケーション側は変更なし

Step 3: 検証・最適化
  - パフォーマンス測定
  - クエリプラン確認

Step 4: 本番切り替え
  - ビューをパーティション テーブルにリダイレクト
  - 旧テーブル削除
```

---

## 📊 パフォーマンス予測

### スロークエリ削減予測

```
現在 (Phase 10):
  Total Queries: 52,000 req/s
  Slow (>100ms): 45 パターン
  Affected: ~6,000 req/s (12%)

改善後 (Phase 11):
  ✅ インデックス追加: -50% (45 → 23 パターン)
  ✅ クエリリライト: -78% (23 → 5 パターン)
  ✅ Connection Pool: -10% (コネクション競合削減)
  ─────────────────────────────────────
  最終: -89% (45 → 5 パターン) ✅

スロークエリ件数:
  6,000 req/s × 12% = 720 req/s が高速化

新しい実行時間分布:
  < 10ms:   48,000 req/s (92%)
  10-100ms:  3,500 req/s (7%)
  > 100ms:     500 req/s (1%) ✅ 目標達成
```

### DB CPU 削減予測

```
現在:
  Query Execution: 60% (75% × 80%)
  Buffer/Cache Ops: 10%
  Other: 5%

改善後:
  Query Execution: 36% (-40%)  ← インデックス効率化
  Buffer/Cache Ops: 6% (-40%)  ← Connection Pool 最適化
  Other: 3%

DB CPU 推移:
  Phase 10: 75%
  Phase 11: 45% (-40%) ✅ 目標達成
```

---

## 🧪 テスト戦略

### Unit テスト
```python
test_index_usage()
  - インデックスが使用されているか確認
  
test_query_result_correctness()
  - クエリ書き換え前後で結果が同一か
  
test_n_plus_one_elimination()
  - N+1 クエリが 1 クエリに統合されているか
```

### パフォーマンステスト
```python
test_query_execution_time()
  - 各クエリの実行時間測定
  - 目標: スロークエリ 120ms → 35ms
  
test_throughput()
  - 52k req/s での処理確認
  
test_connection_pool_stability()
  - 長時間稼働でコネクション増加なし
```

### 回帰テスト
```python
test_all_database_operations()
  - SELECT, INSERT, UPDATE, DELETE
  - すべてが正常に動作
```

---

## ✅ 完了基準

```
✅ インデックス: すべて作成・検証完了
✅ クエリリライト: 45 → 5 以下
✅ スロークエリ: -89% 削減
✅ DB CPU: 75% → 45% (-40%)
✅ DB コネクション: 200 → 120 (-40%)
✅ テスト: 100% PASS
✅ SLA 維持: 99.99%
```

---

## 📋 実装チェックリスト

### Week 2: インデックス・クエリ最適化
- [ ] pg_stat_statements 分析
- [ ] インデックス追加計画書作成
- [ ] インデックス 12 個追加実装
- [ ] クエリ最適化 (45 → 5)
- [ ] Connection Pool 設定変更
- [ ] ユニットテスト (100%)
- [ ] パフォーマンステスト実施
- [ ] Staging 検証

### Week 3: テーブル分割・最終検証
- [ ] パーティショニング計画
- [ ] テーブル分割実装
- [ ] 段階的切り替え
- [ ] 本番切り替え
- [ ] 最終パフォーマンス測定
- [ ] Go Live 判定

---

**次のステップ**: pg_stat_statements 分析開始

