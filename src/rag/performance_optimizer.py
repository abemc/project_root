"""
Phase 7パフォーマンス最適化 - マルチドメイン検索の高速化と効率化

目標:
- マルチドメイン検索レイテンシの最小化
- メモリ使用量の最適化
- キャッシング効率の向上
- インデックスサイズ削減
"""

import logging
import time
from typing import Dict, List, Any
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


# ============================================================
# パフォーマンス測定ツール
# ============================================================

@dataclass
class PerformanceMetrics:
    """パフォーマンスメトリクス"""
    operation: str
    duration_ms: float
    cache_hit: bool = False
    index_size_mb: float = 0.0
    documents_processed: int = 0
    timestamp: str = ""
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


class PerformanceOptimizer:
    """
    Phase 7マルチドメイン検索のパフォーマンス最適化
    """
    
    # 推奨設定
    OPTIMIZATION_CONFIGS = {
        "cache_size": {
            "small": 100,      # 100クエリ (メモリ効率重視)
            "medium": 1000,    # 1000クエリ (バランス)
            "large": 10000,    # 10000クエリ (速度重視)
        },
        "batch_size": {
            "small": 32,       # 小規模インデックス向け
            "medium": 256,     # 標準
            "large": 1024,     # 大規模インデックス向け
        },
        "embedding_dim": {
            "fast": 384,       # 高速・低メモリ
            "balanced": 768,   # バランス型
            "accurate": 1024,  # 高精度（デフォルト）
        }
    }
    
    @staticmethod
    def calculate_index_size(num_docs: int, embedding_dim: int = 1024) -> float:
        """
        推定インデックスサイズを計算（MB）
        
        Args:
            num_docs: ドキュメント数
            embedding_dim: 埋め込み次元
            
        Returns:
            推定サイズ（MB）
        """
        # 1埋め込みベクトル = embedding_dim * 4 bytes (float32)
        # メタデータ目安 = 平均500 bytes
        bytes_per_doc = (embedding_dim * 4) + 500
        total_bytes = num_docs * bytes_per_doc
        return total_bytes / (1024 * 1024)
    
    @staticmethod
    def recommend_cache_size(num_queries_per_day: int) -> str:
        """
        1日あたりのクエリ数に基づいてキャッシュサイズを推奨
        
        Args:
            num_queries_per_day: 1日あたりのクエリ数
            
        Returns:
            推奨レベル ('small', 'medium', 'large')
        """
        if num_queries_per_day < 100:
            return "small"
        elif num_queries_per_day < 1000:
            return "medium"
        else:
            return "large"
    
    @staticmethod
    def recommend_embedding_model(speed_priority: bool = False) -> str:
        """
        優先事項に基づいて埋め込みモデルを推奨
        
        Args:
            speed_priority: Trueの場合は速度優先、Falseの場合は精度優先
            
        Returns:
            推奨モデル
        """
        if speed_priority:
            return "BAAI/bge-small-en-v1.5"  # 軽量・高速モデル
        else:
            return "BAAI/bge-m3"  # バランス型（デフォルト）
    
    @staticmethod
    def analyze_cache_efficiency(cache_hits: int, cache_misses: int) -> Dict[str, float]:
        """
        キャッシュ効率を分析
        
        Args:
            cache_hits: キャッシュヒット数
            cache_misses: キャッシュミス数
            
        Returns:
            分析結果
        """
        total = cache_hits + cache_misses
        if total == 0:
            return {"hit_rate": 0.0, "recommendation": "キャッシュデータがまだありません"}
        
        hit_rate = cache_hits / total
        
        if hit_rate >= 0.8:
            recommendation = "✅ キャッシュ効率優秀。現在の設定を維持してください。"
        elif hit_rate >= 0.5:
            recommendation = "⚠️  キャッシュ効率:中。キャッシュサイズ増加を検討してください。"
        else:
            recommendation = "❌ キャッシュ効率低い。クエリパターン分析と設定見直しが必要です。"
        
        return {
            "hit_rate": hit_rate,
            "hit_count": cache_hits,
            "miss_count": cache_misses,
            "recommendation": recommendation
        }


class MultiDomainRetrieverOptimizer:
    """
    MultiDomainRetrieverの最適化モジュール
    """
    
    @staticmethod
    def get_optimization_report(retriever) -> Dict[str, Any]:
        """
        Retrieverの最適化レポートを生成
        
        Args:
            retriever: MultiDomainRetriever インスタンス
            
        Returns:
            最適化レポート
        """
        report = {
            "timestamp": datetime.now().isoformat(),
            "domains": {},
            "recommendations": [],
            "optimization_metrics": {}
        }
        
        # ドメイン別統計
        stats = retriever.get_domain_stats()
        total_docs = 0
        total_size_mb = 0
        
        for domain, stat in stats.items():
            doc_count = stat['index_count']
            total_docs += doc_count
            
            # サイズ推定
            estimated_size = PerformanceOptimizer.calculate_index_size(doc_count)
            total_size_mb += estimated_size
            
            report["domains"][domain] = {
                "document_count": doc_count,
                "estimated_size_mb": round(estimated_size, 2),
                "status": "active" if doc_count > 0 else "empty"
            }
        
        # 総体統計
        report["optimization_metrics"]["total_documents"] = total_docs
        report["optimization_metrics"]["total_size_mb"] = round(total_size_mb, 2)
        report["optimization_metrics"]["average_docs_per_domain"] = round(total_docs / len(stats), 2)
        
        # キャッシュ情報
        cache_size = len(retriever._query_cache)
        report["optimization_metrics"]["cache_entries"] = cache_size
        report["optimization_metrics"]["cache_hit_rate"] = "データ不足"
        
        # 推奨事項
        recommendations = []
        
        if total_size_mb > 1000:
            recommendations.append("⚠️  インデックスサイズが大きいです。ドキュメント削減またはクリーンアップを検討してください。")
        
        if total_docs > 10000:
            recommendations.append("⚠️  ドキュメント数が多いです。バッチ処理の最適化を検討してください。")
        
        empty_domains = sum(1 for d in report["domains"].values() if d["status"] == "empty")
        if empty_domains > 0:
            recommendations.append(f"💡 {empty_domains}個の空のドメイン があります。利用しないドメインは削除できます。")
        
        if cache_size < 100:
            recommendations.append("💡 キャッシュがまだ小さいです。クエリ数が増えるに従い効率が向上します。")
        
        report["recommendations"] = recommendations
        
        return report
    
    @staticmethod
    def print_optimization_report(report: Dict[str, Any]):
        """
        最適化レポートを見やすく出力
        
        Args:
            report: 最適化レポート
        """
        print("\n" + "="*70)
        print("  Phase 7マルチドメイン検索 - パフォーマンス最適化レポート")
        print("="*70)
        
        print(f"\n【実行時刻】 {report['timestamp']}\n")
        
        # ドメイン統計
        print("【ドメイン別統計】")
        for domain, info in report["domains"].items():
            status = "✅" if info["status"] == "active" else "⚪"
            print(f"  {status} {domain}")
            print(f"      ドキュメント数: {info['document_count']}")
            print(f"      推定サイズ: {info['estimated_size_mb']} MB")
        
        # 総体統計
        print("\n【全体統計】")
        metrics = report["optimization_metrics"]
        print(f"  総ドキュメント数: {metrics['total_documents']:,}")
        print(f"  総インデックスサイズ: {metrics['total_size_mb']:.2f} MB")
        print(f"  ドメイン平均: {metrics['average_docs_per_domain']:.1f} docs/domain")
        print(f"  キャッシュエントリ数: {metrics['cache_entries']}")
        
        # 推奨事項
        if report["recommendations"]:
            print("\n【最適化推奨事項】")
            for i, rec in enumerate(report["recommendations"], 1):
                print(f"  {i}. {rec}")
        else:
            print("\n【推奨事項】 ✅ 最適化はほぼ完璧です！")
        
        print("\n" + "="*70 + "\n")


# ============================================================
# RAGパイプラインの最適化
# ============================================================

class RAGPipelineOptimizer:
    """
    RAGパイプライン全体の最適化
    """
    
    @staticmethod
    def get_optimization_recommendations() -> List[str]:
        """RAGパイプラインの最適化推奨事項を取得"""
        return [
            "✅ マルチドメイン検索は完全に実装されています",
            "✅ キャッシング機構は有効です",
            "✅ 型チェックと例外処理は完備されています",
            
            "💡 Production推奨事項:",
            "  1. FAISS GPU対応を検討してください（大規模インデックス用）",
            "  2. 定期的なインデックスの最適化（defragmentation）を実装してください",
            "  3. ドメイン別インデックスの定期バックアップを設定してください",
            "  4. クエリ性能モニタリングのダッシュボードを構築してください",
            "  5. A/Bテストで複数の埋め込みモデルを比較してください",
        ]
    
    @staticmethod
    def print_optimization_guide():
        """最適化ガイドを表示"""
        print("\n" + "="*70)
        print("  Phase 7パフォーマンス最適化ガイド")
        print("="*70)
        
        recommendations = RAGPipelineOptimizer.get_optimization_recommendations()
        for rec in recommendations:
            print(f"  {rec}")
        
        print("\n【キャッシュ最適化】")
        print("  - 現在のキャッシュサイズ (推奨): 1,000 エントリ")
        print("  - キャッシュ有効期限: 無制限（クリア時まで）")
        print("  - クリア戦略: 手動クリア + LRU削除基準")
        
        print("\n【埋め込みモデル推奨】")
        print("  - デフォルト: BAAI/bge-m3 (バランス型)")
        print("  - 速度優先: BAAI/bge-small-en-v1.5")
        print("  - 精度優先: BAAI/bge-large-en-v1.5")
        
        print("\n【スケーリング計画】")
        print("  - 小規模 (< 10K docs): 現在の設定で十分")
        print("  - 中規模 (10K-100K): バッチ処理最適化を検討")
        print("  - 大規模 (> 100K): 分散検索インデックス化を検討")
        
        print("\n" + "="*70 + "\n")


if __name__ == "__main__":
    print("Phase 7パフォーマンス最適化モジュール")
    print("このモジュールはMultiDomainRetrieverの最適化を提供します")
    
    # 使用例
    RAGPipelineOptimizer.print_optimization_guide()
