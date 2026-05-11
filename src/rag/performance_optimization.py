"""
Phase 7 パフォーマンス最適化モジュール
キャッシング、非同期処理、ボトルネック対策
"""

import time
import functools
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
import logging
import sys
import os

# プロジェクトルートをsys.pathに追加
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

logger = logging.getLogger(__name__)


class PerformanceCache:
    """キャッシング機構"""
    
    def __init__(self, ttl_seconds: int = 3600):
        """
        初期化
        
        Args:
            ttl_seconds: キャッシュのTTL（秒）
        """
        self.cache = {}
        self.ttl = ttl_seconds
        self.hits = 0
        self.misses = 0
    
    def get(self, key: str) -> Optional[Any]:
        """キャッシュを取得"""
        if key in self.cache:
            value, timestamp = self.cache[key]
            if datetime.now() - timestamp < timedelta(seconds=self.ttl):
                self.hits += 1
                return value
            else:
                del self.cache[key]
                self.misses += 1
                return None
        self.misses += 1
        return None
    
    def set(self, key: str, value: Any) -> None:
        """キャッシュを設定"""
        self.cache[key] = (value, datetime.now())
    
    def clear(self) -> None:
        """キャッシュをクリア"""
        self.cache.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """キャッシュ統計を取得"""
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0
        return {
            'hits': self.hits,
            'misses': self.misses,
            'hit_rate': hit_rate,
            'cache_size': len(self.cache)
        }


class PerformanceProfiler:
    """パフォーマンスプロファイラー"""
    
    def __init__(self):
        """初期化"""
        self.measurements = {}
        self.operation_times = []
    
    def measure(self, operation_name: str):
        """デコレータ: 関数の実行時間を測定"""
        def decorator(func):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                start = time.time()
                try:
                    result = func(*args, **kwargs)
                    return result
                finally:
                    elapsed = time.time() - start
                    if operation_name not in self.measurements:
                        self.measurements[operation_name] = []
                    self.measurements[operation_name].append(elapsed)
                    self.operation_times.append((operation_name, elapsed))
                    
                    # ロギング
                    if elapsed > 0.1:  # 100ms以上は記録
                        logger.debug(f"{operation_name}: {elapsed:.3f}秒")
            
            return wrapper
        return decorator
    
    def get_report(self) -> Dict[str, Any]:
        """パフォーマンスレポートを取得"""
        report = {}
        
        for operation, times in self.measurements.items():
            if times:
                avg = sum(times) / len(times)
                max_time = max(times)
                min_time = min(times)
                
                report[operation] = {
                    'calls': len(times),
                    'avg_ms': avg * 1000,
                    'max_ms': max_time * 1000,
                    'min_ms': min_time * 1000,
                    'total_ms': sum(times) * 1000
                }
        
        return report
    
    def get_bottleneck_operations(self, top_n: int = 5) -> List[Tuple[str, float]]:
        """ボトルネック操作を特定"""
        # 総実行時間でソート
        operation_totals = {}
        for op_name, elapsed in self.operation_times:
            if op_name not in operation_totals:
                operation_totals[op_name] = 0
            operation_totals[op_name] += elapsed
        
        sorted_ops = sorted(
            operation_totals.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        return sorted_ops[:top_n]


class OptimizedPhase7QueryPreprocessor:
    """最適化されたクエリプリプロセッサ"""
    
    def __init__(self):
        """初期化"""
        try:
            from src.rag.query_preprocessor import Phase7QueryPreprocessor
            self.base_preprocessor = Phase7QueryPreprocessor()
        except (ImportError, ModuleNotFoundError):
            # テスト環境ではオプショナル
            self.base_preprocessor = None
        
        self.cache = PerformanceCache(ttl_seconds=3600)
        self.profiler = PerformanceProfiler()
        
        # ドメイン推論キャッシュ
        self.domain_inference_cache = {}
        self.intent_detection_cache = {}
    
    @property
    def measure(self):
        """プロファイラーの measure デコレータを公開"""
        return self.profiler.measure
    
    def preprocess_cached(self, query: str, user_id: Optional[str] = None):
        """キャッシュを活用した前処理（改善版）"""
        if self.base_preprocessor is None:
            return None
        
        # キャッシュキー生成
        cache_key = f"preprocess:{query}:{user_id}"
        
        # キャッシュ確認
        cached_result = self.cache.get(cache_key)
        if cached_result:
            logger.debug(f"キャッシュヒット: {query[:30]}")
            return cached_result
        
        # キャッシュミス時は本処理
        result = self.base_preprocessor.preprocess(query, user_id)
        self.cache.set(cache_key, result)
        
        return result
    
    def get_performance_report(self) -> Dict[str, Any]:
        """パフォーマンスレポート"""
        return {
            'cache_stats': self.cache.get_stats(),
            'operation_metrics': self.profiler.get_report(),
            'bottlenecks': self.profiler.get_bottleneck_operations(top_n=5)
        }


class OptimizedKnowledgeIntegrationEngine:
    """最適化された知識統合エンジン"""
    
    def __init__(self):
        """初期化"""
        try:
            from src.rag.knowledge_integration_engine import Phase7KnowledgeIntegrationEngine
            self.base_engine = Phase7KnowledgeIntegrationEngine()
        except (ImportError, ModuleNotFoundError):
            # テスト環境ではオプショナル
            self.base_engine = None
        
        self.cache = PerformanceCache(ttl_seconds=1800)
        self.profiler = PerformanceProfiler()
        
        # ドメイン知識キャッシュ
        self.domain_knowledge_cache = {}
    
    def integrate_and_reason_optimized(
        self,
        preprocessing_result,
        retrieved_documents: Dict[str, List[Any]],
        user_context: Optional[Dict[str, Any]] = None
    ):
        """最適化された知識統合"""
        if self.base_engine is None:
            return None
        
        # キャッシュキー生成
        primary_domain = preprocessing_result.primary_domain
        cache_key = f"integrate:{primary_domain}"
        
        # キャッシュ確認
        cached_result = self.cache.get(cache_key)
        if cached_result:
            logger.debug(f"ドメイン統合キャッシュヒット: {primary_domain}")
            return cached_result
        
        # 本処理
        result = self.base_engine.integrate_and_reason(
            preprocessing_result,
            retrieved_documents,
            user_context
        )
        
        # キャッシュ保存（クエリ固有ではなくドメイン固有）
        self.cache.set(cache_key, result)
        
        return result


class Phase7PerformanceOptimizer:
    """Phase 7パフォーマンス最適化マネージャー"""
    
    def __init__(self):
        """初期化"""
        self.optimized_preprocessor = OptimizedPhase7QueryPreprocessor()
        self.optimized_knowledge_engine = OptimizedKnowledgeIntegrationEngine()
    
    def get_optimization_report(self) -> Dict[str, Any]:
        """最適化レポート"""
        return {
            'preprocessor': self.optimized_preprocessor.get_performance_report(),
            'knowledge_engine': {
                'cache_stats': self.optimized_knowledge_engine.cache.get_stats(),
                'operation_metrics': self.optimized_knowledge_engine.profiler.get_report(),
                'bottlenecks': self.optimized_knowledge_engine.profiler.get_bottleneck_operations()
            }
        }
    
    def get_recommendations(self) -> List[str]:
        """最適化推奨事項"""
        recommendations = []
        
        # キャッシュ効率の分析
        preproc_cache_stats = self.optimized_preprocessor.cache.get_stats()
        if preproc_cache_stats['hit_rate'] < 50:
            recommendations.append(
                "❌ クエリプリプロセッサのキャッシュ効率が低い（50%未満）"
            )
        else:
            recommendations.append(
                f"✅ クエリプリプロセッサのキャッシュ効率が高い（{preproc_cache_stats['hit_rate']:.1f}%）"
            )
        
        # ボトルネック操作の分析
        bottlenecks = self.optimized_preprocessor.profiler.get_bottleneck_operations(top_n=3)
        if bottlenecks:
            recommendations.append("\n📊 ボトルネック操作:")
            for op_name, total_time in bottlenecks:
                if total_time > 0.5:
                    recommendations.append(f"  ⚠️  {op_name}: {total_time*1000:.1f}ms（最適化推奨）")
                else:
                    recommendations.append(f"  ✅ {op_name}: {total_time*1000:.1f}ms")
        
        return recommendations


# グローバルインスタンス
global_optimizer = None


def get_optimizer() -> Phase7PerformanceOptimizer:
    """グローバルオプティマイザを取得"""
    global global_optimizer
    if global_optimizer is None:
        global_optimizer = Phase7PerformanceOptimizer()
    return global_optimizer


if __name__ == "__main__":
    # テスト用
    
    optimizer = Phase7PerformanceOptimizer()
    
    print("=" * 70)
    print("  Phase 7 パフォーマンス最適化 - テスト")
    print("=" * 70)
    print()
    
    # キャッシュ機構テスト
    print("【テスト1】キャッシング機構")
    cache = PerformanceCache()
    cache.set("test_key", {"result": "test_value"})
    result1 = cache.get("test_key")  # ヒット
    result2 = cache.get("test_key")  # ヒット
    result3 = cache.get("missing_key")  # ミス
    
    stats = cache.get_stats()
    print(f"  キャッシュ統計: ヒット={stats['hits']}回, ミス={stats['misses']}回")
    print(f"  ヒット率: {stats['hit_rate']:.1f}%")
    print()
    
    # パフォーマンスプロファイルテスト
    print("【テスト2】パフォーマンスプロファイラー")
    profiler = PerformanceProfiler()
    
    @profiler.measure("test_operation_1")
    def slow_operation():
        time.sleep(0.01)
        return "result"
    
    @profiler.measure("test_operation_2")
    def fast_operation():
        return "result"
    
    slow_operation()
    slow_operation()
    fast_operation()
    
    report = profiler.get_report()
    print(f"  テスト操作1: 平均 {report['test_operation_1']['avg_ms']:.2f}ms")
    print(f"  テスト操作2: 平均 {report['test_operation_2']['avg_ms']:.2f}ms")
    print()
    
    bottlenecks = profiler.get_bottleneck_operations()
    for op_name, total_time in bottlenecks:
        print(f"  ボトルネック: {op_name} ({total_time*1000:.1f}ms)")
    
    print()
    print("✅ パフォーマンス最適化モジュールの初期化完了")
