# Phase 5 API リファレンス完全ガイド

**バージョン**: 1.0  
**最終更新**: 2026-05-18  
**ステータス**: ✅ 本番環境対応

---

## 📖 目次

1. [概要](#概要)
2. [クイックスタート](#クイックスタート)
3. [モジュール別 API](#モジュール別-api)
4. [統合マネージャー](#統合マネージャー)
5. [最適化コンポーネント](#最適化コンポーネント)
6. [ダッシュボード](#ダッシュボード)
7. [使用例](#使用例)
8. [ベストプラクティス](#ベストプラクティス)
9. [トラブルシューティング](#トラブルシューティング)

---

## 概要

Phase 5 学習システムは、AI エージェントの継続的な自己改善を実現する 7 つのサブシステムと 3 つの最適化層から構成されます。

### アーキテクチャ図

```
┌─────────────────────────────────────────────────┐
│       RAG Agent (Main Entry Point)              │
└─────────────────┬───────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────┐
│   Phase5IntegrationManager (Orchestrator)       │
├─────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────┐ │
│ │   7 Learning Systems                        │ │
│ ├─────────────────────────────────────────────┤ │
│ │ • Meta Memory                               │ │
│ │ • Procedural Memory                         │ │
│ │ • Context-Aware Retrieval                   │ │
│ │ • Transfer Learning                         │ │
│ │ • Reinforcement Learning                    │ │
│ │ • Meta Learning                             │ │
│ │ • Adaptive Forgetting                       │ │
│ └─────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────┐ │
│ │   3 Optimization Components                 │ │
│ ├─────────────────────────────────────────────┤ │
│ │ • LRU Memory Cache (O(1) access)            │ │
│ │ • Batch Processor (50 items/batch)          │ │
│ │ • Index Optimizer (Multi-index search)      │ │
│ │ • Performance Monitor (Metrics tracking)    │ │
│ └─────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────┐
│    Streamlit Dashboard (Visualization)          │
└─────────────────────────────────────────────────┘
```

---

## クイックスタート

### 基本的な使用方法

```python
# 1. Phase 5 マネージャーの初期化
from src.rag.phase5_integration import initialize_phase5, get_phase5_manager

manager = initialize_phase5(agent_id="my_agent_001")

# 2. 実行トレースの記録
manager.record_execution_trace(
    task_id="task_1",
    task_family="data_analysis",
    query="SQLクエリを最適化する",
    execution_time_ms=125.5,
    success=True,
    output_quality=0.92,
    tools_used=["sql_optimizer"],
)

# 3. 学習実行
manager.learn_from_experience()

# 4. 統計情報取得
stats = manager.get_learning_statistics()
print(f"Success rate: {stats['success_rate']:.1%}")
```

---

## モジュール別 API

### 5.1 Meta Memory システム

**ファイル**: `src/self_improvement/meta_memory.py`  
**目的**: メモリの品質と価値を継続的に評価・管理

#### 主要クラス

##### `MetaMemory`

```python
class MetaMemory:
    """メモリの品質スコアリングと管理"""
    
    def __init__(self, default_retention_window: int = 30):
        """
        Args:
            default_retention_window: デフォルト保持期間（日数）
        """
        pass
    
    def add_memory(self, memory_id: str, content: str, context: Dict):
        """メモリを追加
        
        Args:
            memory_id: メモリの一意識別子
            content: メモリの内容
            context: 実行コンテキスト
        """
        pass
    
    def compute_quality_score(self, memory_id: str) -> float:
        """メモリの品質スコアを計算 [0.0-1.0]
        
        Returns:
            品質スコア
        """
        pass
    
    def get_retention_status(self, memory_id: str) -> str:
        """保持ステータスを取得
        
        Returns:
            'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'
        """
        pass
```

#### 使用例

```python
from src.self_improvement.meta_memory import MetaMemory

meta = MetaMemory(default_retention_window=30)

# メモリ追加
meta.add_memory(
    memory_id="mem_001",
    content="SQLクエリ最適化パターン",
    context={"task": "database", "success": True}
)

# 品質スコア確認
score = meta.compute_quality_score("mem_001")
print(f"Quality: {score:.2f}")  # 0.00-1.00

# 保持ステータス確認
status = meta.get_retention_status("mem_001")
print(f"Status: {status}")  # CRITICAL / HIGH / MEDIUM / LOW
```

---

### 5.2 Procedural Memory システム

**ファイル**: `src/self_improvement/procedural_memory.py`  
**目的**: タスク実行手順の最適化と信頼度管理

#### 主要クラス

##### `ProcedureExecutor`

```python
class ProcedureExecutor:
    """プロシージャ実行エンジン"""
    
    def store_procedure(self, 
        procedure_name: str,
        steps: List[str],
        parameters: Dict[str, Any],
        execution_time_ms: float,
        success: bool
    ) -> str:
        """プロシージャを保存
        
        Returns:
            プロシージャID
        """
        pass
    
    def get_reliability_score(self, procedure_id: str) -> float:
        """信頼度スコアを取得 [0.0-1.0]"""
        pass
    
    def get_speedup_factor(self, procedure_id: str) -> float:
        """実行高速化倍率を取得"""
        pass
```

#### 使用例

```python
from src.self_improvement.procedural_memory import ProcedureExecutor

executor = ProcedureExecutor()

# プロシージャ保存
proc_id = executor.store_procedure(
    procedure_name="optimize_sql_query",
    steps=[
        "Parse SQL",
        "Analyze indexes",
        "Generate plan",
        "Execute",
    ],
    parameters={"query_type": "SELECT"},
    execution_time_ms=250.0,
    success=True
)

# 信頼度確認
reliability = executor.get_reliability_score(proc_id)
print(f"Reliability: {reliability:.1%}")

# 高速化倍率確認
speedup = executor.get_speedup_factor(proc_id)
print(f"Speedup: {speedup:.1f}x")
```

---

### 5.3 Context-Aware Retrieval システム

**ファイル**: `src/rag/context_aware_retrieval.py`  
**目的**: 文脈を考慮したメモリ検索

#### 主要クラス

##### `ContextAwareRetriever`

```python
class ContextAwareRetriever:
    """文脈認識メモリ検索エンジン"""
    
    def add_memory(self, 
        memory_id: str,
        content: str,
        context_features: Dict[str, Any]
    ) -> bool:
        """メモリを追加
        
        Args:
            memory_id: メモリ識別子
            content: メモリ内容
            context_features: 文脈特徴
        """
        pass
    
    def retrieve_memories(self,
        query: str,
        context: Dict[str, Any],
        top_k: int = 5
    ) -> List[Dict]:
        """文脈付きメモリ検索
        
        Args:
            query: 検索クエリ
            context: 実行文脈
            top_k: 取得数
            
        Returns:
            マッチしたメモリのリスト
        """
        pass
    
    def get_retrieval_stats(self) -> Dict[str, float]:
        """検索統計を取得"""
        pass
```

#### 使用例

```python
from src.rag.context_aware_retrieval import ContextAwareRetriever

retriever = ContextAwareRetriever()

# メモリ追加
retriever.add_memory(
    memory_id="mem_sql_001",
    content="SELECT最適化パターン",
    context_features={
        "task_family": "database",
        "domain": "sql",
        "complexity": "high"
    }
)

# 文脈付き検索
results = retriever.retrieve_memories(
    query="SQLを高速化したい",
    context={
        "current_task": "database",
        "user_level": "advanced"
    },
    top_k=3
)

for mem in results:
    print(f"Memory {mem['id']}: score={mem['relevance']:.2f}")
```

---

### 5.4 Transfer Learning システム

**ファイル**: `src/self_improvement/transfer_learning.py`  
**目的**: タスク間での知識転移

#### 主要クラス

##### `TransferLearningManager`

```python
class TransferLearningManager:
    """知識転移マネージャー"""
    
    def register_task(self,
        task_name: str,
        task_family: str,
        knowledge: Dict[str, Any],
        success: bool
    ):
        """タスクを登録"""
        pass
    
    def compute_task_similarity(self,
        task1_id: str,
        task2_id: str
    ) -> float:
        """タスク類似度を計算 [0.0-1.0]"""
        pass
    
    def transfer_knowledge(self,
        source_task_id: str,
        target_task_id: str
    ) -> Dict[str, Any]:
        """知識転移を実行
        
        Returns:
            転移された知識
        """
        pass
    
    def get_transfer_statistics(self) -> Dict:
        """転移統計を取得"""
        pass
```

#### 使用例

```python
from src.self_improvement.transfer_learning import TransferLearningManager

transfer = TransferLearningManager()

# タスク登録
transfer.register_task(
    task_name="task_1",
    task_family="data_analysis",
    knowledge={"pattern": "sql_optimization"},
    success=True
)

# タスク類似度確認
similarity = transfer.compute_task_similarity("task_1", "task_2")
print(f"Similarity: {similarity:.2f}")

# 知識転移実行
transferred = transfer.transfer_knowledge("task_1", "task_2")
print(f"Transferred knowledge: {transferred}")
```

---

### 5.5 Reinforcement Learning システム

**ファイル**: `src/self_improvement/reinforcement_learning.py`  
**目的**: 報酬ベースの学習

#### 主要クラス

##### `RLManager`

```python
class RLManager:
    """強化学習マネージャー"""
    
    def record_decision(self, decision_id: str, action: str, context: Dict):
        """決定を記録"""
        pass
    
    def add_reward(self,
        decision_id: str,
        signal_type: str,  # 'SUCCESS', 'TIME', 'QUALITY'
        value: float
    ):
        """報酬を追加
        
        Args:
            signal_type: 報酬種別
            value: 報酬値
        """
        pass
    
    def learn_from_experience(self,
        batch_size: int = 32
    ):
        """経験から学習"""
        pass
    
    def get_policy(self, context: Dict) -> Dict:
        """ポリシーを取得"""
        pass
```

#### 使用例

```python
from src.self_improvement.reinforcement_learning import RLManager

rl = RLManager()

# 決定記録
rl.record_decision(
    decision_id="dec_001",
    action="use_index",
    context={"query_type": "SELECT"}
)

# 報酬追加
rl.add_reward("dec_001", "SUCCESS", 1.0)
rl.add_reward("dec_001", "TIME", 0.9)  # 実行時間がスコア 0.9
rl.add_reward("dec_001", "QUALITY", 0.95)

# 学習実行
rl.learn_from_experience(batch_size=32)

# ポリシー確認
policy = rl.get_policy({"query_type": "SELECT"})
print(f"Recommended action: {policy['action']}")
```

---

### 5.6 Meta Learning システム

**ファイル**: `src/self_improvement/meta_learning.py`  
**目的**: 学習プロセス自体の最適化

#### 主要クラス

##### `MetaLearner`

```python
class MetaLearner:
    """メタ学習エンジン"""
    
    def analyze_task(self, task_id: str) -> Dict:
        """タスクを分析
        
        Returns:
            タスク特性
        """
        pass
    
    def compute_optimal_learning_rate(self, task_id: str) -> float:
        """最適学習率を計算"""
        pass
    
    def generate_optimal_config(self, task_id: str) -> Dict:
        """最適設定を生成"""
        pass
    
    def track_config_performance(self,
        config_id: str,
        performance_metric: float
    ):
        """設定パフォーマンスを追跡"""
        pass
```

#### 使用例

```python
from src.self_improvement.meta_learning import MetaLearner

meta_learner = MetaLearner()

# タスク分析
task_analysis = meta_learner.analyze_task("task_001")
print(f"Task complexity: {task_analysis['complexity']}")

# 最適学習率
learning_rate = meta_learner.compute_optimal_learning_rate("task_001")
print(f"Optimal learning rate: {learning_rate:.4f}")

# 最適設定生成
config = meta_learner.generate_optimal_config("task_001")
print(f"Optimal config: {config}")
```

---

### 5.7 Adaptive Forgetting システム

**ファイル**: `src/self_improvement/adaptive_forgetting.py`  
**目的**: 適応的なメモリ削除と復習スケジューリング

#### 主要クラス

##### `AdaptiveForgetfulnessManager`

```python
class AdaptiveForgetfulnessManager:
    """適応的忘却マネージャー"""
    
    def register_memory(self,
        memory_id: str,
        importance: float,
        context: Dict
    ):
        """メモリを登録"""
        pass
    
    def record_access(self, memory_id: str):
        """メモリアクセスを記録"""
        pass
    
    def compute_retention_score(self, memory_id: str) -> float:
        """保持スコアを計算 [0.0-1.0]"""
        pass
    
    def get_spaced_repetition_schedule(self,
        memory_id: str
    ) -> List[float]:
        """間隔反復スケジュール取得
        
        Returns:
            次回復習までの日数リスト
        """
        pass
    
    def get_forgetting_candidates(self) -> List[str]:
        """削除候補メモリを取得"""
        pass
```

#### 使用例

```python
from src.self_improvement.adaptive_forgetting import AdaptiveForgetfulnessManager

forgetting = AdaptiveForgetfulnessManager()

# メモリ登録
forgetting.register_memory(
    memory_id="mem_001",
    importance=0.9,  # 0.0-1.0
    context={"domain": "critical"}
)

# アクセス記録
forgetting.record_access("mem_001")

# 保持スコア確認
score = forgetting.compute_retention_score("mem_001")
print(f"Retention score: {score:.2f}")

# 間隔反復スケジュール
schedule = forgetting.get_spaced_repetition_schedule("mem_001")
print(f"Review schedule (days): {schedule}")  # [1, 3, 7, 14, 30]

# 削除候補
candidates = forgetting.get_forgetting_candidates()
print(f"Candidates for deletion: {candidates}")
```

---

## 統合マネージャー

### Phase5IntegrationManager

**ファイル**: `src/rag/phase5_integration.py`  
**目的**: 全7つの学習システムを統合

#### 初期化

```python
from src.rag.phase5_integration import initialize_phase5, get_phase5_manager

# 方法1: 新しいマネージャー作成
manager = initialize_phase5(agent_id="my_agent_001")

# 方法2: グローバルマネージャー取得
manager = get_phase5_manager()
```

#### 主要メソッド

##### `record_execution_trace()`

```python
manager.record_execution_trace(
    task_id: str,                    # タスク識別子
    task_family: str,                # タスク種別
    query: str,                      # 入力クエリ
    execution_time_ms: float,        # 実行時間
    success: bool,                   # 成功フラグ
    output_quality: float = 0.0,     # 出力品質 [0.0-1.0]
    tools_used: List[str] = None,    # 使用ツール
    error_message: str = None,       # エラーメッセージ
)
```

**例**:
```python
manager.record_execution_trace(
    task_id="step_1_search",
    task_family="document_search",
    query="AIの自己改善について",
    execution_time_ms=120.5,
    success=True,
    output_quality=0.87,
    tools_used=["search_doc", "rank"],
)
```

##### `learn_from_experience()`

```python
manager.learn_from_experience()
```

全RL経験から学習を実行します。

##### `get_learning_statistics()`

```python
stats = manager.get_learning_statistics()
# 返り値:
# {
#     'total_executions': int,
#     'successful': int,
#     'failed': int,
#     'success_rate': float,
#     'average_quality': float,
#     'average_execution_time_ms': float,
#     'cache_hit_rate': float,
#     'cache_size': int,
#     'batch_size': int,
# }
```

##### `retrieve_similar_solutions()`

```python
solutions = manager.retrieve_similar_solutions(
    query: str,
    context: Dict[str, Any],
    limit: int = 5
)
```

---

## 最適化コンポーネント

### LRU Memory Cache

```python
from src.rag.phase5_optimizer import LRUMemoryCache

cache = LRUMemoryCache(max_size=1000)

# キャッシュに追加
cache.put("key_1", {"data": "value"})

# 取得 (O(1))
value = cache.get("key_1")

# 統計確認
stats = cache.get_stats()
print(f"Hit rate: {stats.hit_rate:.1%}")
```

### Batch Processor

```python
from src.rag.phase5_optimizer import BatchProcessor

processor = BatchProcessor(batch_size=50, timeout_seconds=5)

# アイテム追加
processor.add(item)

# バッチ処理が必要か確認
if processor.should_process():
    batch = processor.get_batch()
    process_learning(batch)
```

### Index Optimizer

```python
from src.rag.phase5_optimizer import IndexOptimizer

indexer = IndexOptimizer()

# メモリ追加
indexer.add_memory("mem_1", "data_analysis", success=True, quality=0.9)

# 高速検索
by_family = indexer.find_by_family("data_analysis")
successful = indexer.find_successful()
high_quality = indexer.find_by_quality_range(0.8, 1.0)
```

---

## ダッシュボード

### Streamlit Dashboard

```python
from src.rag.learning_dashboard import render_learning_dashboard

# アプリケーション内で呼び出し
render_learning_dashboard()
```

### タブ構成

1. **Statistics** - 実行メトリクスと タイムライン
2. **Transfer Learning** - 知識転移の追跡
3. **Reinforcement Learning** - ポリシー学習
4. **Memory Management** - キャッシュ状態

---

## 使用例

### 例1: シンプルなエージェント統合

```python
from src.rag.agent import RAGAgent
from src.rag.retriever import Retriever
from src.rag.reranker import Reranker
from src.rag.phase5_integration import initialize_phase5

# Phase 5 初期化
phase5_mgr = initialize_phase5("my_agent")

# エージェント作成
retriever = Retriever()
reranker = Reranker()

agent = RAGAgent(
    question="AIの自己改善について",
    retriever=retriever,
    reranker=reranker,
)

# 実行トレース記録（自動）
# agent.run_step() が呼ばれると自動で記録される

# 学習実行
agent.phase5_manager.learn_from_experience()
```

### 例2: 複数タスクの追跡

```python
from src.rag.phase5_integration import initialize_phase5

manager = initialize_phase5("tracking_agent")

# 複数タスク実行
tasks = [
    ("sql_optimization", "database", "SELECT文最適化", 125),
    ("doc_summarization", "nlp", "ドキュメント要約", 250),
    ("api_integration", "integration", "API呼び出し", 300),
]

for task_id, family, query, time_ms in tasks:
    manager.record_execution_trace(
        task_id=task_id,
        task_family=family,
        query=query,
        execution_time_ms=time_ms,
        success=True,
        output_quality=0.85 + (125/time_ms) * 0.1,
    )

# 統計確認
stats = manager.get_learning_statistics()
print(f"Average quality: {stats['average_quality']:.2f}")
print(f"Success rate: {stats['success_rate']:.1%}")
```

### 例3: 知識転移の実装

```python
from src.self_improvement.transfer_learning import TransferLearningManager

transfer = TransferLearningManager()

# タスク1: SQLクエリ最適化（成功）
transfer.register_task(
    task_name="sql_optimize_1",
    task_family="database",
    knowledge={"pattern": "index_usage"},
    success=True
)

# タスク2: 類似タスク
transfer.register_task(
    task_name="sql_optimize_2",
    task_family="database",
    knowledge={},
    success=False
)

# 知識転移
similarity = transfer.compute_task_similarity(
    "sql_optimize_1", 
    "sql_optimize_2"
)

if similarity > 0.7:
    knowledge = transfer.transfer_knowledge(
        "sql_optimize_1",
        "sql_optimize_2"
    )
    print(f"Transferred: {knowledge}")
```

---

## ベストプラクティス

### 1. 定期的な統計確認

```python
# 毎実行後に統計を確認
stats = manager.get_learning_statistics()

if stats['total_executions'] % 100 == 0:
    print(f"Checkpoint: {stats['success_rate']:.1%} success")
```

### 2. キャッシュの活用

```python
# 検索結果をキャッシュ
solution = manager.memory_cache.get(memory_id)
if solution is None:
    solution = retrieve_from_permanent_store()
    manager.memory_cache.put(memory_id, solution)
```

### 3. バッチ学習

```python
# 定期的に学習を実行
if manager.batch_processor.should_process():
    batch = manager.batch_processor.get_batch()
    manager.learn_from_experience()
```

### 4. 文脈付き検索

```python
# 文脈を含めて検索
context = {
    "current_task": "data_analysis",
    "user_expertise": "advanced",
    "time_constraint": "low"
}

solutions = manager.retrieve_similar_solutions(
    query="SQLを高速化したい",
    context=context,
    limit=3
)
```

### 5. エラーハンドリング

```python
try:
    manager.record_execution_trace(...)
    manager.learn_from_experience()
except Exception as e:
    logger.error(f"Learning failed: {e}")
    # フォールバック処理
```

---

## トラブルシューティング

### Q: キャッシュヒット率が低い

**A**: 
- キャッシュサイズを確認: `cache.get_stats()`
- 関連メモリをプリロード
- キャッシュ削除ポリシーの調整

### Q: 学習が実行されない

**A**:
- `should_process()` の条件確認
- バッチサイズの確認
- `learn_from_experience()` の明示的呼び出し

### Q: メモリ使用が増加し続ける

**A**:
- `get_forgetting_candidates()` で削除対象確認
- 古いメモリの除去スケジュール設定
- キャッシュ容量の調整

### Q: パフォーマンス低下

**A**:
- `perf_monitor.get_performance_report()` でボトルネック確認
- インデックスを活用した検索
- バッチサイズの最適化

---

## API チートシート

```python
# インポート
from src.rag.phase5_integration import initialize_phase5

# 初期化
manager = initialize_phase5("agent_id")

# トレース記録
manager.record_execution_trace(
    task_id, task_family, query, 
    execution_time_ms, success, output_quality
)

# 学習実行
manager.learn_from_experience()

# 統計確認
stats = manager.get_learning_statistics()

# キャッシュ利用
cache = manager.memory_cache
cache.put(key, value)
value = cache.get(key)

# インデックス検索
indexer = manager.index_optimizer
results = indexer.find_by_family(family_name)

# ダッシュボード表示
from src.rag.learning_dashboard import render_learning_dashboard
render_learning_dashboard()
```

---

## サポート情報

- **ドキュメント**: `/docs/PHASE5_*.md`
- **テスト**: `/tests/test_phase5_*.py`
- **ログ**: `logger = logging.getLogger(__name__)`
- **バージョン**: 1.0 (2026-05-18)

---

**作成日**: 2026-05-18  
**最終更新**: 2026-05-18  
**ステータス**: ✅ 本番環境対応
