#!/usr/bin/env python3
"""
Week 3 Day 4-5: ベンチマーク結果分析・比較エンジン

複数のベンチマーク結果を分析し、言語別・ドメイン別の
精度比較・最適化効果検証を実行

実行方法:
  python benchmark_analyzer.py --results results.json --output analysis.json
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from statistics import mean, stdev

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class AccuracyMetrics:
    """精度メトリクス"""
    benchmark: str
    accuracy: float
    f1_score: float
    bleu_score: float
    sample_count: int
    
    def to_dict(self):
        return asdict(self)


@dataclass
class PerformanceMetrics:
    """パフォーマンスメトリクス"""
    benchmark: str
    throughput: float  # samples/sec
    latency: float    # ms
    total_time: float # sec
    
    def to_dict(self):
        return asdict(self)


class BenchmarkAnalyzer:
    """ベンチマーク結果分析エンジン"""
    
    def __init__(self):
        """初期化"""
        self.results = {}
        self.analysis = {}
    
    def load_results(self, filepath: str) -> Dict:
        """
        ベンチマーク結果を読込
        
        Args:
            filepath: 結果ファイルパス
        
        Returns:
            結果データ
        """
        logger.info(f"Loading results from {filepath}")
        
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        self.results = data
        return data
    
    def analyze_accuracy(self) -> Dict:
        """精度分析"""
        logger.info("Analyzing accuracy metrics...")
        
        if 'results' not in self.results:
            logger.warning("No results found in data")
            return {}
        
        accuracy_metrics = []
        
        for result in self.results['results']:
            metric = AccuracyMetrics(
                benchmark=result.get('benchmark_name', 'Unknown'),
                accuracy=result.get('accuracy', 0.0),
                f1_score=result.get('f1_score', 0.0),
                bleu_score=result.get('bleu_score', 0.0),
                sample_count=result.get('total_samples', 0)
            )
            accuracy_metrics.append(metric)
        
        # 統計量計算
        if accuracy_metrics:
            accuracies = [m.accuracy for m in accuracy_metrics]
            analysis = {
                "metrics": [m.to_dict() for m in accuracy_metrics],
                "summary": {
                    "avg_accuracy": mean(accuracies),
                    "max_accuracy": max(accuracies),
                    "min_accuracy": min(accuracies),
                    "std_accuracy": stdev(accuracies) if len(accuracies) > 1 else 0,
                }
            }
        else:
            analysis = {"metrics": [], "summary": {}}
        
        logger.info(f"Accuracy analysis complete: {len(accuracy_metrics)} benchmarks analyzed")
        self.analysis['accuracy'] = analysis
        return analysis
    
    def analyze_performance(self) -> Dict:
        """パフォーマンス分析"""
        logger.info("Analyzing performance metrics...")
        
        if 'results' not in self.results:
            return {}
        
        performance_metrics = []
        
        for result in self.results['results']:
            metric = PerformanceMetrics(
                benchmark=result.get('benchmark_name', 'Unknown'),
                throughput=result.get('throughput_samples_per_sec', 0.0),
                latency=result.get('avg_latency_ms', 0.0),
                total_time=result.get('total_time_sec', 0.0)
            )
            performance_metrics.append(metric)
        
        # 統計量計算
        if performance_metrics:
            throughputs = [m.throughput for m in performance_metrics if m.throughput > 0]
            analysis = {
                "metrics": [m.to_dict() for m in performance_metrics],
                "summary": {
                    "avg_throughput": mean(throughputs) if throughputs else 0,
                    "max_throughput": max(throughputs) if throughputs else 0,
                    "min_throughput": min(throughputs) if throughputs else 0,
                    "total_time_sec": sum(m.total_time for m in performance_metrics),
                }
            }
        else:
            analysis = {"metrics": [], "summary": {}}
        
        logger.info(f"Performance analysis complete")
        self.analysis['performance'] = analysis
        return analysis
    
    def compare_benchmarks(self) -> Dict:
        """ベンチマーク間の比較分析"""
        logger.info("Comparing benchmarks...")
        
        if 'results' not in self.results or len(self.results['results']) < 2:
            logger.warning("Need at least 2 benchmarks to compare")
            return {}
        
        results = self.results['results']
        comparison = {
            "benchmarks": []
        }
        
        # ベンチマークごとの詳細比較
        for i, result in enumerate(results):
            benchmark_data = {
                "rank": i + 1,
                "name": result.get('benchmark_name', 'Unknown'),
                "accuracy": result.get('accuracy', 0.0),
                "f1_score": result.get('f1_score', 0.0),
                "samples": result.get('total_samples', 0),
                "throughput": result.get('throughput_samples_per_sec', 0.0),
                "time_sec": result.get('total_time_sec', 0.0),
            }
            comparison["benchmarks"].append(benchmark_data)
        
        # ランキング作成（精度で降順）
        sorted_by_accuracy = sorted(
            comparison["benchmarks"],
            key=lambda x: x['accuracy'],
            reverse=True
        )
        
        comparison["ranking_by_accuracy"] = [
            {"rank": i+1, "name": b["name"], "accuracy": b["accuracy"]}
            for i, b in enumerate(sorted_by_accuracy)
        ]
        
        logger.info(f"Comparison complete: {len(results)} benchmarks compared")
        self.analysis['comparison'] = comparison
        return comparison
    
    def generate_report(self, output_path: Optional[str] = None) -> Dict:
        """
        分析レポートを生成
        
        Args:
            output_path: 出力ファイルパス
        
        Returns:
            レポートデータ
        """
        logger.info("Generating analysis report...")
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "source_model": self.results.get('model', 'Unknown'),
            "analysis": {
                "accuracy": self.analyze_accuracy(),
                "performance": self.analyze_performance(),
                "comparison": self.compare_benchmarks(),
            },
            "conclusions": self._generate_conclusions(),
        }
        
        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Report saved to {output_path}")
        
        return report
    
    def _generate_conclusions(self) -> List[str]:
        """結論を生成"""
        conclusions = []
        
        if 'accuracy' in self.analysis:
            acc_summary = self.analysis['accuracy'].get('summary', {})
            if acc_summary.get('avg_accuracy'):
                avg_acc = acc_summary['avg_accuracy']
                if avg_acc > 0.8:
                    conclusions.append("✅ 全般的に高い精度を達成")
                elif avg_acc > 0.6:
                    conclusions.append("⚠️ 平均的な精度。改善の余地あり")
                else:
                    conclusions.append("❌ 精度が低め。最適化が必要")
        
        if 'performance' in self.analysis:
            perf_summary = self.analysis['performance'].get('summary', {})
            if perf_summary.get('avg_throughput'):
                throughput = perf_summary['avg_throughput']
                conclusions.append(f"📊 平均スループット: {throughput:.0f} samples/sec")
        
        if 'comparison' in self.analysis:
            comparison = self.analysis['comparison']
            if comparison.get('ranking_by_accuracy'):
                best = comparison['ranking_by_accuracy'][0]
                conclusions.append(f"🏆 最高精度: {best['name']} ({best['accuracy']:.4f})")
        
        return conclusions
    
    def print_summary(self):
        """サマリーを表示"""
        print("\n" + "="*70)
        print("📊 ベンチマーク分析レポート")
        print("="*70)
        
        if 'accuracy' in self.analysis:
            print("\n📈 精度分析:")
            acc = self.analysis['accuracy']['summary']
            print(f"  平均精度: {acc.get('avg_accuracy', 0):.4f}")
            print(f"  最高精度: {acc.get('max_accuracy', 0):.4f}")
            print(f"  最低精度: {acc.get('min_accuracy', 0):.4f}")
        
        if 'performance' in self.analysis:
            print("\n⚡ パフォーマンス分析:")
            perf = self.analysis['performance']['summary']
            print(f"  平均スループット: {perf.get('avg_throughput', 0):.0f} samples/sec")
            print(f"  合計処理時間: {perf.get('total_time_sec', 0):.2f} sec")
        
        if 'comparison' in self.analysis:
            print("\n🏆 ベンチマークランキング:")
            ranking = self.analysis['comparison'].get('ranking_by_accuracy', [])
            for item in ranking:
                print(f"  {item['rank']}. {item['name']}: {item['accuracy']:.4f}")
        
        print("\n💡 結論:")
        for conclusion in self.analysis.get('conclusions', []):
            print(f"  {conclusion}")


def main():
    """メイン処理"""
    import argparse
    
    parser = argparse.ArgumentParser(description="ベンチマーク結果分析")
    parser.add_argument(
        "--results",
        type=str,
        required=True,
        help="結果ファイルパス"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="benchmark_analysis.json",
        help="出力ファイルパス"
    )
    
    args = parser.parse_args()
    
    analyzer = BenchmarkAnalyzer()
    analyzer.load_results(args.results)
    
    # 分析実行
    report = analyzer.generate_report(output_path=args.output)
    
    # サマリー表示
    analyzer.print_summary()
    
    print(f"\n📄 詳細レポート: {args.output}")


if __name__ == "__main__":
    main()
