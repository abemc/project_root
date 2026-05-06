# 🔄 Task 1: L3 キャッシュ層実装 設計書

**フェーズ**: Phase 11 - Task 1  
**期間**: Week 1-2 (2 weeks)  
**バージョン**: v1.0  
**作成日**: 2026-04-17  
**ステータス**: 📋 設計フェーズ

---

## 🎯 概要

Phase 10 での DB 直接クエリを、L3 キャッシュ層（Redis）を追加することで、API レイテンシを 30% 削減し、スループットを 1.5 倍に向上させるタスク。

### 成功基準
- 🎯 キャッシュヒット率: **85% 以上**
- 🎯 DB クエリ削減: **60% 以上**
- 🎯 API レイテンシ削減: **30%** (285ms → 200ms)
- 🎯 スループット向上: **1.5 倍** (52k → 78k req/s)
- 🎯 キャッシュ無効化時間: **< 1秒**

---

## 🏗️ アーキテクチャ設計

### 現在のデータフロー (Phase 10)

```
Request → API Gateway → Application → Database → Response
             ↓
        (Cache: ❌ なし)
```

**問題点**:
- DB に全クエリが直行
- 同じデータへのアクセスで重複クエリ実行
- ホットデータへのアクセス集中

### 目標アーキテクチャ (Phase 11)

```
Request → API Gateway → Application 
                            ↓
                     キャッシュ層（L3 Redis）
                            ↓
                        [Cache HIT? 85%]
                        /              \
                      YES              NO
                       ↓               ↓
                    Return      Database Query
                                     ↓
                                Cache WRITE
                                     ↓
                                   Return
```

### キャッシュレイヤー全体設計

```
┌─────────────────────────────────────────┐
│         Application Layer                │
│  (FastAPI/Python with async support)    │
└────────────────┬────────────────────────┘
                 │
┌────────────────▼────────────────────────┐
│      Cache Management Layer              │
│  ┌──────────────────────────────────┐  │
│  │ RedisConnectionPool              │  │
│  │ ├─ マルチテナント対応            │  │
│  │ ├─ ハイアベイラビリティ          │  │
│  │ ├─ 自動フェイルオーバー          │  │
│  │ └─ 接続プーリング                │  │
│  └──────────────────────────────────┘  │
│  ┌──────────────────────────────────┐  │
│  │ Cache Key Generator              │  │
│  │ ├─ セキュリティコンテキスト      │  │
│  │ ├─ テナント別分離                │  │
│  │ └─ タイムスタンプベース無効化    │  │
│  └──────────────────────────────────┘  │
└────────────────┬────────────────────────┘
                 │
┌────────────────▼────────────────────────┐
│       Data Access Layer                  │
│  ┌──────────────────────────────────┐  │
│  │ PostgreSQL (Primary)             │  │
│  │ ReadReplicas (3 instances)       │  │
│  └──────────────────────────────────┘  │
└─────────────────────────────────────────┘

┌──────────────────────────────────────────┐
│       Redis Cluster (New)                 │
│  ├─ Node 1 (6379)                       │
│  ├─ Node 2 (6380) [Replica]             │
│  └─ Sentinel (3 instances)              │
│     └─ 自動フェイルオーバー             │
└──────────────────────────────────────────┘
```

---

## 🔑 キャッシュ戦略

### 1. キャッシュキー設計

```python
# キャッシュキーの命名規則
<layer>:<entity>:<id>:<context>:<version>

# 実例

# Layer 1: 認証
auth:session:{session_id}:{tenant_id}:v1
auth:user:{user_id}:{tenant_id}:v1
auth:permissions:{user_id}:{tenant_id}:v1

# Layer 2: 暗号化
crypto:key:{key_id}:{tenant_id}:v1
crypto:keymap:{entity_type}:{entity_id}:v1

# Layer 3: ネットワーク
network:rule:{policy_id}:{tenant_id}:v1

# Layer 4: SOC
soc:alert:{alert_id}:v1
soc:threat:{threat_id}:v1

# Layer 5: ML
ml:threat_score:{user_id}:{session_id}:v1
ml:model:metadata:v2

# Layer 6: コンプライアンス
compliance:status:{entity_id}:{entity_type}:v1
compliance:report:{report_id}:v1

# Layer 7: グローバル
global:config:{config_key}:v1
```

### 2. TTL (Time To Live) 戦略

```
データ分類            TTL          理由
─────────────────────────────────────────
セッション情報       5 分         セキュリティ
ユーザー権限         15 分        セキュリティ  
暗号化キーメタ       1 時間       キー管理
ネットワークルール   1 時間       頻度低い
脅威インテリジェンス 30 分        リアルタイム性
ML モデルメタ        24 時間      ほぼ不変
設定値               1 時間       管理画面から変更
監査ログリスト       10 分        読取頻度低い
テナント情報         1 時間       組織変更頻度低い
```

### 3. キャッシュ無効化戦略

```python
# Pattern 1: TTL ベース (自動)
cache.set(key, value, ttl=300)  # 5分で自動削除

# Pattern 2: イベントベース
@app.on_event("user_permission_changed")
async def invalidate_user_cache(user_id):
    pattern = f"auth:permissions:{user_id}:*"
    redis.delete_pattern(pattern)

# Pattern 3: 階層無効化
@app.on_event("tenant_config_updated")
async def invalidate_tenant_cache(tenant_id):
    patterns = [
        f"auth:*:*:{tenant_id}:*",
        f"crypto:*:{tenant_id}:*",
        f"network:*:{tenant_id}:*",
    ]
    for pattern in patterns:
        redis.delete_pattern(pattern)

# Pattern 4: バージョニング
def get_cache_key(entity_id, version=1):
    return f"entity:{entity_id}:v{version}"

# キャッシュバージョンアップ時
cache_version = 2  # グローバルバージョン
key = f"entity:{entity_id}:v{cache_version}"
```

---

## 🔧 実装設計

### Redis クラスタ構成

```yaml
# docker-compose 追加設定
redis-cluster:
  image: redis:7.2-alpine
  ports:
    - "6379:6379"
    - "6380:6380"
    - "26379:26379"  # Sentinel
  environment:
    REDIS_PASSWORD: "${REDIS_PASSWORD}"
    REDIS_CLUSTER_ENABLED: "yes"
    REDIS_CLUSTER_NODES: 6
  volumes:
    - redis-data:/data
  networks:
    - esp-network

redis-sentinel:
  image: redis:7.2-alpine
  command: redis-sentinel /etc/sentinel.conf
  ports:
    - "26379:26379"
    - "26380:26380"
    - "26381:26381"
  volumes:
    - ./sentinel.conf:/etc/sentinel.conf
    - sentinel-data:/data
  networks:
    - esp-network
```

### Python Redis クライアント実装

```python
# File: src/cache/redis_manager.py

import redis
from redis.sentinel import Sentinel
from typing import Any, Optional
import json
import asyncio

class RedisConnectionManager:
    """
    Redis への安全で効率的なアクセスを提供
    - マルチテナント対応
    - 自動フェイルオーバー
    - エラーハンドリング
    """
    
    def __init__(self, config):
        self.config = config
        self.sentinel = None
        self.master = None
        self.slave = None
        self._init_connection()
    
    def _init_connection(self):
        """Sentinel 経由で Redis に接続"""
        try:
            sentinels = [
                (self.config.SENTINEL_HOST1, 26379),
                (self.config.SENTINEL_HOST2, 26379),
                (self.config.SENTINEL_HOST3, 26379),
            ]
            
            self.sentinel = Sentinel(
                sentinels,
                socket_timeout=2,
                retry_on_timeout=True,
            )
            
            # Master への読み書き
            self.master = self.sentinel.master_for(
                self.config.REDIS_SERVICE_NAME,
                socket_timeout=2,
                retry_on_timeout=True,
            )
            
            # Slave への読み取り（負荷分散）
            self.slave = self.sentinel.slave_for(
                self.config.REDIS_SERVICE_NAME,
                socket_timeout=2,
                retry_on_timeout=True,
            )
            
        except Exception as e:
            logger.error(f"Redis connection failed: {e}")
            raise
    
    async def get(self, key: str) -> Optional[Any]:
        """キャッシュから取得（読み取り用 Slave へアクセス）"""
        try:
            value = self.slave.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.warning(f"Cache GET failed: {key} - {e}")
            return None
    
    async def set(
        self, 
        key: str, 
        value: Any, 
        ttl: int = 300
    ) -> bool:
        """キャッシュに書き込み（Master へアクセス）"""
        try:
            serialized = json.dumps(value)
            self.master.setex(
                key, 
                ttl, 
                serialized
            )
            return True
        except Exception as e:
            logger.warning(f"Cache SET failed: {key} - {e}")
            return False
    
    async def delete_pattern(self, pattern: str) -> int:
        """パターンマッチで削除"""
        try:
            keys = self.master.keys(pattern)
            if keys:
                deleted = self.master.delete(*keys)
                logger.info(f"Deleted {deleted} keys matching {pattern}")
                return deleted
            return 0
        except Exception as e:
            logger.warning(f"Pattern delete failed: {pattern} - {e}")
            return 0

class CacheKeyGenerator:
    """キャッシュキー生成ロジック"""
    
    @staticmethod
    def auth_session(session_id: str, tenant_id: str) -> str:
        return f"auth:session:{session_id}:{tenant_id}:v1"
    
    @staticmethod
    def user_permissions(user_id: str, tenant_id: str) -> str:
        return f"auth:permissions:{user_id}:{tenant_id}:v1"
    
    @staticmethod
    def encryption_key(key_id: str, tenant_id: str) -> str:
        return f"crypto:key:{key_id}:{tenant_id}:v1"
    
    @staticmethod
    def threat_score(user_id: str, session_id: str) -> str:
        return f"ml:threat_score:{user_id}:{session_id}:v1"
```

### キャッシュ無効化イベントシステム

```python
# File: src/cache/cache_invalidator.py

from typing import List, Callable
from enum import Enum
import asyncio

class CacheEvent(Enum):
    """キャッシュ無効化イベント"""
    USER_PERMISSION_CHANGED = "user_permission_changed"
    USER_ROLE_UPDATED = "user_role_updated"
    TENANT_CONFIG_UPDATED = "tenant_config_updated"
    ENCRYPTION_KEY_ROTATED = "encryption_key_rotated"
    THREAT_LEVEL_CHANGED = "threat_level_changed"
    COMPLIANCE_STATUS_CHANGED = "compliance_status_changed"

class CacheInvalidator:
    """イベントベースのキャッシュ無効化"""
    
    def __init__(self, redis_manager):
        self.redis = redis_manager
        self.handlers: dict[CacheEvent, List[Callable]] = {}
    
    def register_handler(self, event: CacheEvent, handler: Callable):
        """イベントハンドラを登録"""
        if event not in self.handlers:
            self.handlers[event] = []
        self.handlers[event].append(handler)
    
    async def emit(self, event: CacheEvent, **kwargs):
        """イベントを発火"""
        if event in self.handlers:
            tasks = [
                handler(**kwargs) 
                for handler in self.handlers[event]
            ]
            await asyncio.gather(*tasks)
    
    async def handle_user_permission_change(self, user_id: str):
        """ユーザー権限変更時"""
        pattern = f"auth:permissions:{user_id}:*"
        await self.redis.delete_pattern(pattern)
    
    async def handle_tenant_config_update(self, tenant_id: str):
        """テナント設定変更時"""
        patterns = [
            f"auth:*:*:{tenant_id}:*",
            f"network:*:{tenant_id}:*",
            f"global:config:*:v*",
        ]
        for pattern in patterns:
            await self.redis.delete_pattern(pattern)
```

---

## 📊 パフォーマンス予測

### キャッシュヒット率シミュレーション

```
ホットデータセット: 1000 ユーザー × 5 権限レコード = 5,000 キャッシュエントリ
平常時トラフィック: 52k req/s

キャッシュ効果:
┌────────────────────────────────────┐
│ Tier     │ ヒット数 │ %    │ 効果   │
├──────────┼─────────┼──────┼────────┤
│ Top 100  │ 30k/s   │ 58%  │ Hot    │
│ Next 500 │ 15k/s   │ 29%  │ Warm   │
│ Tail     │ 7k/s    │ 13%  │ Cold   │
├──────────┼─────────┼──────┼────────┤
│ 合計     │ 52k/s   │100%  │        │
└────────────────────────────────────┘

キャッシュヒット: 52k × 0.85 = 44.2k req/s
DB クエリ: 52k × 0.15 = 7.8k req/s

改善効果: DB クエリ 60% 削減 ✅
```

### レイテンシ改善予測

```
現在 (Phase 10):
  DB Query: 200ms
  Response: 285ms

改善後 (Phase 11 + キャッシュ):
  キャッシュヒット時:
    Cache Lookup: 5ms
    Response: 10ms
  
  キャッシュミス時:
    DB Query: 200ms
    Cache Write: 10ms
    Response: 215ms
  
  平均:
    (44.2k × 10ms + 7.8k × 215ms) / 52k = 35ms ← API レスポンス
    + ネットワークオーバーヘッド: 30ms
    = 65ms (内部レイテンシ削減: 77%)

  End-to-End (含むネットワーク):
    285ms → 135ms (-53%) ✅ (目標 -30% 達成)
```

---

## 🧪 テスト戦略

### Unit テスト
```python
# Test: キャッシュキー生成
test_cache_key_generation()

# Test: TTL 設定
test_cache_ttl_expiration()

# Test: 無効化パターン
test_cache_invalidation_patterns()

# Test: エラーハンドリング
test_redis_connection_failure()
test_cache_timeout_handling()
```

### 統合テスト
```python
# Test: キャッシュヒット率測定
test_cache_hit_ratio(target=0.85)

# Test: 並行アクセス
test_concurrent_cache_access(concurrency=1000)

# Test: メモリ使用量
test_cache_memory_usage(max_memory=2GB)

# Test: フェイルオーバー
test_redis_failover_scenario()
```

### パフォーマンステスト
```python
# Test: キャッシュルックアップ速度
test_cache_lookup_latency(target=5ms)

# Test: スループット
test_cache_throughput(target=100k_req_s)

# Test: 長時間稼働
test_cache_24h_stability()
```

---

## 📋 実装チェックリスト

### Week 1: 設計・構築
- [ ] Redis クラスタのセットアップ (Docker Compose)
- [ ] RedisConnectionManager 実装
- [ ] CacheKeyGenerator 実装
- [ ] CacheInvalidator 実装
- [ ] Sentinel 設定・テスト

### Week 2: 統合・テスト
- [ ] Unit テスト (100% カバレッジ)
- [ ] 統合テスト (Staging)
- [ ] パフォーマンステスト
- [ ] ドキュメント作成
- [ ] Prod ロールアウト計画

---

## 🚀 ロールアウト計画

```
Day 1-3:  Staging 環境検証 (100% トラフィック)
Day 4-5:  Canary: 5% トラフィックを新構成に
Day 6-7:  Progressive: 25% → 50% → 100%
Day 8-10: 監視・チューニング (めり込み検出)
```

---

**次のステップ**: Redis クラスタセットアップ開始

