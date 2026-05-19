# Phase 5 実装ガイド＆ベストプラクティス

**バージョン**: 1.0  
**対象者**: デベロッパー、システム設計者  
**レベル**: 初級～中級  

---

## 目次

1. [アーキテクチャ概要](#アーキテクチャ概要)
2. [システム設計](#システム設計)
3. [統合パターン](#統合パターン)
4. [パフォーマンス最適化](#パフォーマンス最適化)
5. [本番運用](#本番運用)
6. [テストガイド](#テストガイド)
7. [デバッグ方法](#デバッグ方法)

---

## アーキテクチャ概要

### レイヤー構成

```
┌──────────────────────────────────────────┐
│     Application Layer                    │
│   (RAG Agent, Streamlit App)             │
└──────────────────┬───────────────────────┘
                   │
┌──────────────────▼───────────────────────┐
│   Integration Layer                      │
│   Phase5IntegrationManager               │
│   ├─ Orchestration                       │
│   ├─ Trace Recording                     │
│   └─ Learning Trigger                    │
└──────────────────┬───────────────────────┘
                   │
┌──────────────────▼───────────────────────┐
│   Learning Systems Layer (7 Systems)     │
│   ├─ Meta Memory                         │
│   ├─ Procedural Memory                   │
│   ├─ Context-Aware Retrieval             │
│   ├─ Transfer Learning                   │
│   ├─ Reinforcement Learning              │
│   ├─ Meta Learning                       │
│   └─ Adaptive Forgetting                 │
└──────────────────┬───────────────────────┘
                   │
┌──────────────────▼───────────────────────┐
│   Optimization Layer (4 Components)      │
│   ├─ LRU Memory Cache                    │
│   ├─ Batch Processor                     │
│   ├─ Index Optimizer                     │
│   └─ Performance Monitor                 │
└──────────────────┬───────────────────────┘
                   │
┌──────────────────▼───────────────────────┐
│   Storage & Persistence Layer            │
│   ├─ In-Memory Storage                   │
│   ├─ FAISS Vector DB                     │
│   └─ Cache Layer                         │
└──────────────────────────────────────────┘
```

### データフロー

```
Agent Execution
      ↓
record_execution_trace()
      ↓
Trace → RL Manager
      → Meta Memory
      → Procedural Memory
      → Context Retriever
      ↓
Batch Processor (50 items)
      ↓
learn_from_experience()
      ↓
All 7 Systems Update
      ↓
Metrics → Cache
       → Index
       → Monitor
```

---

## システム設計

### 設計原則

#### 1. 単一責任原則 (SRP)

各システムは専門領域を担当：

| システム | 責任 | 入力 | 出力 |
|--------|------|------|------|
| Meta Memory | メモリ品質評価 | Trace | Score |
| Procedural | 手順最適化 | Task | Procedure |
| Context | 文脈検索 | Query+Context | Results |
| Transfer | 知識転移 | Task Pair | Knowledge |
| RL | 報酬学習 | Decision+Reward | Policy |
| Meta | 学習最適化 | Task | Config |
| Forgetting | 忘却管理 | Memory | Retention |

#### 2. 依存性逆転

```python
# ❌ BAD: 直接依存
from src.rag.agent import RAGAgent
agent = RAGAgent(...)
agent.meta_memory = MetaMemory()

# ✅ GOOD: マネージャー経由
from src.rag.phase5_integration import initialize_phase5
manager = initialize_phase5()
# manager が全システムを管理
```

#### 3. キャッシング戦略

```python
# キャッシュレイアウト
┌─ LRU Cache (1000 items)
│  ├─ Frequently accessed memories
│  ├─ Recent solutions
│  └─ Hot task procedures
│
├─ Permanent Store (DB)
│  ├─ All memories
│  ├─ History
│  └─ Audit log
│
└─ Index Layer
   ├─ Task family index
   ├─ Success/failure index
   └─ Quality range index
```

---

## 統合パターン

### パターン 1: シンプル統合

**シナリオ**: 既存エージェントに学習機能を追加

```python
from src.rag.phase5_integration import initialize_phase5
from src.rag.agent import RAGAgent

# 1. Phase 5 初期化
phase5_mgr = initialize_phase5(agent_id="simple_agent")

# 2. エージェント作成（自動的にマネージャーを使用）
agent = RAGAgent(
    question="クエリ",
    retriever=retriever,
    reranker=reranker
)

# 3. 実行（自動で Phase 5 がトレース記録）
result = agent.run_agent()

# 4. 学習実行
phase5_mgr.learn_from_experience()
```

### パターン 2: カスタム統合

**シナリオ**: 特定の学習システムをカスタマイズ

```python
from src.rag.phase5_integration import Phase5IntegrationManager
from src.self_improvement.transfer_learning import TransferLearningManager

# マネージャー作成
manager = Phase5IntegrationManager()

# カスタムトレース
for task in tasks:
    # 1. 実行
    result = run_task(task)
    
    # 2. トレース記録（詳細）
    manager.record_execution_trace(
        task_id=task['id'],
        task_family=task['family'],
        query=task['query'],
        execution_time_ms=result['time'],
        success=result['success'],
        output_quality=calculate_quality(result),
        tools_used=result['tools'],
        error_message=result.get('error')
    )
    
    # 3. 知識転移確認
    if manager.transfer_learning:
        similar = manager.transfer_learning.find_similar_tasks(task)
        if similar:
            knowledge = manager.transfer_learning.transfer_knowledge(
                similar['id'], task['id']
            )
```

### パターン 3: マルチエージェント統合

**シナリオ**: 複数エージェント間での知識共有

```python
from src.rag.phase5_integration import Phase5IntegrationManager

# 共有マネージャー
shared_manager = Phase5IntegrationManager(agent_id="shared")

# エージェント 1
agent1_traces = []
for _ in range(10):
    result = agent1.run_step()
    shared_manager.record_execution_trace(...)
    agent1_traces.append(result)

# エージェント 2
agent2_traces = []
for _ in range(10):
    result = agent2.run_step()
    shared_manager.record_execution_trace(...)
    agent2_traces.append(result)

# 統合学習
shared_manager.learn_from_experience()

# 統計確認
stats = shared_manager.get_learning_statistics()
print(f"Combined success rate: {stats['success_rate']:.1%}")
```

---

## パフォーマンス最適化

### 1. キャッシュ最適化

#### キャッシュサイズ決定

```python
# メモリ予算: 50 MB
# 1アイテム ~50 KB と仮定
max_cache_size = 50 * 1024 * 1024 / 50000  # 約 1000 items

cache = LRUMemoryCache(max_size=1000)

# 監視
stats = cache.get_stats()
if stats.hit_rate < 0.5:  # 50% 未満なら警告
    logger.warning(f"Low cache hit rate: {stats.hit_rate:.1%}")
```

#### キャッシュウォーミング

```python
def warm_up_cache(cache, frequently_used_ids):
    """キャッシュを予め充填"""
    for mem_id in frequently_used_ids:
        memory = retrieve_from_db(mem_id)
        cache.put(mem_id, memory)
    
    stats = cache.get_stats()
    logger.info(f"Cache warmed: {stats.size} items")

# 起動時に実行
warm_up_cache(manager.memory_cache, top_100_memories)
```

### 2. バッチ処理最適化

#### バッチサイズチューニング

```python
# 初期値: 50
# メトリクス: タスク完了時間 vs メモリ使用

def auto_tune_batch_size(current_size, metrics):
    """バッチサイズを自動調整"""
    if metrics['memory_usage'] > 100 * 1024 * 1024:  # 100MB超過
        return max(current_size // 2, 10)
    elif metrics['task_time'] > 1000:  # 1秒超
        return min(current_size * 2, 200)
    return current_size

new_size = auto_tune_batch_size(50, metrics)
processor = BatchProcessor(batch_size=new_size)
```

### 3. インデックス最適化

#### マルチインデックス戦略

```python
# 典型的クエリパターン:
# 1. "data_analysis タスクを検索" → by_family
# 2. "成功したタスクを検索" → by_success
# 3. "高品質（>0.8）を検索" → by_quality_range

indexer = IndexOptimizer()

# インデックス追加時に記録
indexer.add_memory(
    "mem_1", 
    task_family="data_analysis",  # by_family に追加
    success=True,                  # by_success に追加
    quality=0.92                   # by_quality_range に追加
)

# 効率的検索
high_success = indexer.find_by_family("data_analysis")  # O(1)
successful = indexer.find_successful()  # O(1)
excellent = indexer.find_by_quality_range(0.8, 1.0)  # O(1)
```

### 4. メモリ監視

```python
from src.rag.phase5_optimizer import get_performance_monitor

monitor = get_performance_monitor()

# 定期的に記録
monitor.record_operation("trace_recording", duration_ms)
monitor.record_memory_usage(current_memory_mb)

# レポート生成
report = monitor.get_performance_report()

print(f"Avg trace time: {report['operations']['trace_recording']['avg_ms']:.2f} ms")
print(f"Peak memory: {report['memory']['peak_mb']:.1f} MB")

# アラート設定
if report['memory']['peak_mb'] > 500:
    logger.warning("Memory peak exceeded!")
```

---

## 本番運用

### 1. デプロイメントチェックリスト

- [ ] 全テスト合格 (`pytest -v`)
- [ ] ログレベル設定確認 (本番は WARNING 以上)
- [ ] キャッシュサイズ設定確認
- [ ] バッチサイズ最適化完了
- [ ] パフォーマンスモニタ有効化
- [ ] アラート閾値設定
- [ ] バックアップ計画作成
- [ ] ロールバック計画作成

### 2. 監視メトリクス

```python
# 毎分集計
metrics_to_track = {
    'execution_count': stats['total_executions'],
    'success_rate': stats['success_rate'],
    'avg_quality': stats['average_quality'],
    'cache_hit_rate': stats['cache_hit_rate'],
    'memory_usage_mb': get_current_memory(),
    'p95_execution_time': calculate_percentile(95),
}

# CloudWatch / Prometheus へ送信
send_metrics(metrics_to_track)

# アラート条件
if metrics['success_rate'] < 0.70:
    send_alert("Success rate dropped below 70%")
if metrics['cache_hit_rate'] < 0.40:
    send_alert("Cache hit rate too low")
```

### 3. ログ管理

```python
import logging

# 本番設定
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/phase5.log'),
        logging.handlers.RotatingFileHandler(
            '/var/log/phase5.log',
            maxBytes=10*1024*1024,  # 10MB
            backupCount=10
        )
    ]
)

# アプリケーション内
logger = logging.getLogger(__name__)
logger.info(f"Learning completed: {stats}")
```

### 4. 障害復旧

```python
# メモリ不足時の対応
def handle_out_of_memory():
    """OOM発生時の回復処理"""
    # 1. キャッシュクリア
    manager.memory_cache.clear()
    logger.warning("Cache cleared due to OOM")
    
    # 2. 古いトレース削除
    manager.execution_traces = manager.execution_traces[-1000:]
    
    # 3. インデックスリセット
    manager.index_optimizer = IndexOptimizer()
    
    # 4. アラート
    send_alert("OOM recovery executed")

# エラーハンドリング
try:
    manager.learn_from_experience()
except MemoryError:
    handle_out_of_memory()
except Exception as e:
    logger.error(f"Learning failed: {e}")
    # フォールバック: 次回リトライ
```

---

## テストガイド

### 1. ユニットテスト

```bash
# 個別システムテスト
pytest tests/test_phase5_enhancement.py::TestMetaMemory -v
pytest tests/test_phase5_advanced.py::TestTransferLearning -v

# 全テスト実行
pytest tests/test_phase5_*.py -v --cov=src/

# カバレッジレポート
pytest --cov=src/self_improvement --cov=src/rag --cov-report=html
```

### 2. 統合テスト

```python
def test_full_integration():
    """全システムの統合テスト"""
    # 1. 初期化
    manager = Phase5IntegrationManager(agent_id="test")
    
    # 2. 複数トレース記録
    for i in range(50):
        manager.record_execution_trace(
            task_id=f"task_{i}",
            task_family=random.choice(["data", "nlp", "api"]),
            query="test query",
            execution_time_ms=100 + random.random() * 50,
            success=random.random() > 0.2,  # 80% success
            output_quality=0.5 + random.random() * 0.5,
        )
    
    # 3. 学習実行
    manager.learn_from_experience()
    
    # 4. 検証
    stats = manager.get_learning_statistics()
    assert stats['total_executions'] == 50
    assert 0.7 < stats['success_rate'] < 0.9
    assert 0.5 < stats['average_quality'] < 1.0
```

### 3. パフォーマンステスト

```python
def test_performance():
    """パフォーマンステスト"""
    import time
    
    manager = Phase5IntegrationManager()
    
    # 1000 トレース記録の時間計測
    start = time.time()
    for i in range(1000):
        manager.record_execution_trace(...)
    elapsed = time.time() - start
    
    avg_time = elapsed * 1000 / 1000  # ms per trace
    assert avg_time < 1.0, f"Too slow: {avg_time:.2f} ms/trace"
    
    # メモリ確認
    import psutil
    process = psutil.Process()
    memory = process.memory_info().rss / 1024 / 1024  # MB
    assert memory < 500, f"Memory too high: {memory:.1f} MB"
```

---

## デバッグ方法

### 1. ログレベル調整

```python
# デバッグモード有効化
import logging
logging.basicConfig(level=logging.DEBUG)

# 特定モジュールのみ
logging.getLogger('src.self_improvement').setLevel(logging.DEBUG)
```

### 2. 統計情報確認

```python
# 詳細統計表示
stats = manager.get_learning_statistics()
for key, value in stats.items():
    print(f"{key:30s}: {value}")

# キャッシュ詳細
cache_stats = manager.memory_cache.get_stats()
print(f"Cache hit ratio: {cache_stats.hit_rate:.1%}")

# パフォーマンス詳細
perf_report = manager.perf_monitor.get_performance_report()
for op, metrics in perf_report['operations'].items():
    print(f"{op}: {metrics['avg_ms']:.2f} ms (n={metrics['count']})")
```

### 3. トレース確認

```python
# 最新トレース確認
latest = manager.execution_traces[-1]
print(f"Latest trace: {latest.task_id}")
print(f"  Time: {latest.execution_time_ms:.1f} ms")
print(f"  Quality: {latest.output_quality:.2f}")
print(f"  Success: {latest.success}")

# タスク別統計
from collections import Counter
task_families = Counter(t.task_family for t in manager.execution_traces)
for family, count in task_families.most_common():
    print(f"{family}: {count} traces")
```

### 4. 問題診断フロー

```
問題: 学習が実行されない
  ↓
1. should_process() → False?
   ├─ バッチサイズ確認
   ├─ タイムアウト時間確認
   └─ batch.batch の内容確認
  ↓
2. learn_from_experience() 実行?
   ├─ 例外ないか確認
   ├─ RL マネージャー確認
   └─ 経験リプレイデータ確認
  ↓
3. 統計更新されたか?
   ├─ stats に新しいデータあるか
   ├─ メモリサイズ増加したか
   └─ インデックス更新されたか
```

---

## チェックリスト

### 開発時
- [ ] ローカルで全テスト実行
- [ ] カバレッジ 90% 以上
- [ ] ログ出力確認
- [ ] メモリリーク確認

### 本番デプロイ前
- [ ] パフォーマンステスト実施
- [ ] ロードテスト実施（1000+ traces）
- [ ] フェイルオーバー計画確認
- [ ] ロールバック計画確認

### 本番運用
- [ ] 日次メトリクス確認
- [ ] 週次パフォーマンスレビュー
- [ ] 月次ログ分析
- [ ] 四半期ごと容量計画見直し

---

**作成日**: 2026-05-18  
**対象バージョン**: Phase 5 v1.0  
**レビュー予定**: 2026-08-18
