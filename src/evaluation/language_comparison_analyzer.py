#!/usr/bin/env python3
"""
Week 3 Day 4-5 追加実装: 言語別精度比較エンジン

英語と日本語のベンチマーク結果を比較し、
言語別パフォーマンス差を分析

実行方法:
  python language_comparison_analyzer.py --en results_en.json --ja results_ja.json
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from statistics import mean

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class LanguageBenchmarkMetrics:
    """言語別ベンチマークメトリクス"""
    language: str  # 'EN' or 'JA'
    benchmark: str
    accuracy: float
    f1_score: float
    processing_time_sec: float
    
    def to_dict(self):
        return asdict(self)


@dataclass
class LanguageComparisonResult:
    """言語比較結果"""
    benchmark: str
    en_accuracy: float
    ja_accuracy: float
    accuracy_diff: float  # EN - JA
    en_processing_time: float
    ja_processing_time: float
    time_diff: float  # EN - JA
    recommendation: str
    
    def to_dict(self):
        return asdict(self)


class LanguageComparisonAnalyzer:
    """言語別精度比較エンジン"""
    
    def __init__(self):
        """初期化"""
        self.en_results = {}
        self.ja_results = {}
        self.comparison = {}
    
    def load_results(
        self,
        en_filepath: str,
        ja_filepath: str
    ) -> Tuple[Dict, Dict]:
        """
        英語と日本語の結果を読込
        
        Args:
            en_filepath: 英語結果ファイル
            ja_filepath: 日本語結果ファイル
        
        Returns:
            (英語結果, 日本語結果)
        """
        logger.info(f"Loading English results from {en_filepath}")
        with open(en_filepath, 'r') as f:
            self.en_results = json.load(f)
        
        logger.info(f"Loading Japanese results from {ja_filepath}")
        with open(ja_filepath, 'r') as f:
            self.ja_results = json.load(f)
        
        return self.en_results, self.ja_results
    
    def compare_accuracy(self) -> Dict:
        """精度比較"""
        logger.info("Comparing accuracy metrics by language...")
        
        en_benchmarks = {
            r['benchmark_name']: r
            for r in self.en_results.get('results', [])
        }
        ja_benchmarks = {
            r['benchmark_name']: r
            for r in self.ja_results.get('results', [])
        }
        
        comparison_results = []
        
        # 共通ベンチマークのみ比較
        common_benchmarks = set(en_benchmarks.keys()) & set(ja_benchmarks.keys())
        
        for benchmark_name in common_benchmarks:
            en_acc = en_benchmarks[benchmark_name].get('accuracy', 0.0)
            ja_acc = ja_benchmarks[benchmark_name].get('accuracy', 0.0)
            acc_diff = en_acc - ja_acc
            
            # 推奨事項生成
            if abs(acc_diff) < 0.05:
                recommendation = "✅ 両言語で同等の性能"
            elif acc_diff > 0.05:
                recommendation = "⚠️ 英語の方が高精度（日本語改善推奨）"
            else:
                recommendation = "🎯 日本語の方が高精度（英語改善推奨）"
            
            result = LanguageComparisonResult(
                benchmark=benchmark_name,
                en_accuracy=en_acc,
                ja_accuracy=ja_acc,
                accuracy_diff=acc_diff,
                en_processing_time=en_benchmarks[benchmark_name].get('total_time_sec', 0.0),
                ja_processing_time=ja_benchmarks[benchmark_name].get('total_time_sec', 0.0),
                time_diff=en_benchmarks[benchmark_name].get('total_time_sec', 0.0) - 
                         ja_benchmarks[benchmark_name].get('total_time_sec', 0.0),
                recommendation=recommendation
            )
            comparison_results.append(result)
        
        # 統計量計算
        if comparison_results:
            en_accs = [r.en_accuracy for r in comparison_results]
            ja_accs = [r.ja_accuracy for r in comparison_results]
            acc_diffs = [r.accuracy_diff for r in comparison_results]
            
            analysis = {
                "comparisons": [r.to_dict() for r in comparison_results],
                "summary": {
                    "benchmarks_compared": len(comparison_results),
                    "avg_en_accuracy": mean(en_accs),
                    "avg_ja_accuracy": mean(ja_accs),
                    "avg_accuracy_diff": mean(acc_diffs),
                    "en_advantages": len([d for d in acc_diffs if d > 0.05]),
                    "ja_advantages": len([d for d in acc_diffs if d < -0.05]),
                    "equal_performance": len([d for d in acc_diffs if abs(d) <= 0.05]),
                }
            }
        else:
            analysis = {"comparisons": [], "summary": {}}
        
        logger.info(f"Accuracy comparison complete")
        self.comparison['accuracy'] = analysis
        return analysis
    
    def compare_performance(self) -> Dict:
        """パフォーマンス比較"""
        logger.info("Comparing performance by language...")
        
        en_benchmarks = {
            r['benchmark_name']: r
            for r in self.en_results.get('results', [])
        }
        ja_benchmarks = {
            r['benchmark_name']: r
            for r in self.ja_results.get('results', [])
        }
        
        common_benchmarks = set(en_benchmarks.keys()) & set(ja_benchmarks.keys())
        
        performance_data = []
        
        for benchmark_name in common_benchmarks:
            en_throughput = en_benchmarks[benchmark_name].get('throughput_samples_per_sec', 0.0)
            ja_throughput = ja_benchmarks[benchmark_name].get('throughput_samples_per_sec', 0.0)
            
            performance_data.append({
                "benchmark": benchmark_name,
                "en_throughput": en_throughput,
                "ja_throughput": ja_throughput,
                "throughput_diff": en_throughput - ja_throughput,
                "performance_ratio": en_throughput / ja_throughput if ja_throughput > 0 else 0.0,
            })
        
        if performance_data:
            en_throughputs = [p['en_throughput'] for p in performance_data if p['en_throughput'] > 0]
            ja_throughputs = [p['ja_throughput'] for p in performance_data if p['ja_throughput'] > 0]
            
            analysis = {
                "performance": performance_data,
                "summary": {
                    "avg_en_throughput": mean(en_throughputs) if en_throughputs else 0,
                    "avg_ja_throughput": mean(ja_throughputs) if ja_throughputs else 0,
                    "avg_performance_ratio": mean([p['performance_ratio'] for p in performance_data if p['performance_ratio'] > 0]),
                }
            }
        else:
            analysis = {"performance": [], "summary": {}}
        
        logger.info(f"Performance comparison complete")
        self.comparison['performance'] = analysis
        return analysis
    
    def analyze_domain_performance(self) -> Dict:
        """ドメイン別パフォーマンス分析"""
        logger.info("Analyzing domain performance by language...")
        
        # MMLU の場合は学科別分析
        en_mmlu = next(
            (r for r in self.en_results.get('results', []) 
             if 'MMLU' in r.get('benchmark_name', '')),
            None
        )
        ja_mmlu = next(
            (r for r in self.ja_results.get('results', []) 
             if 'MMLU' in r.get('benchmark_name', '')),
            None
        )
        
        if en_mmlu and ja_mmlu:
            domain_analysis = {
                "benchmark": "MMLU",
                "en_model": self.en_results.get('model', 'Unknown'),
                "ja_model": self.ja_results.get('model', 'Unknown'),
                "en_accuracy": en_mmlu.get('accuracy', 0.0),
                "ja_accuracy": ja_mmlu.get('accuracy', 0.0),
                "accuracy_gap": en_mmlu.get('accuracy', 0.0) - ja_mmlu.get('accuracy', 0.0),
                "en_samples": en_mmlu.get('total_samples', 0),
                "ja_samples": ja_mmlu.get('total_samples', 0),
            }
        else:
            domain_analysis = {}
        
        logger.info(f"Domain analysis complete")
        return domain_analysis
    
    def generate_report(self, output_path: Optional[str] = None) -> Dict:
        """
        比較レポートを生成
        
        Args:
            output_path: 出力ファイルパス
        
        Returns:
            レポートデータ
        """
        logger.info("Generating language comparison report...")
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "en_model": self.en_results.get('model', 'Unknown'),
            "ja_model": self.ja_results.get('model', 'Unknown'),
            "comparison": {
                "accuracy": self.compare_accuracy(),
                "performance": self.compare_performance(),
                "domain_analysis": self.analyze_domain_performance(),
            },
            "recommendations": self._generate_recommendations(),
        }
        
        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Report saved to {output_path}")
        
        return report
    
    def _generate_recommendations(self) -> List[str]:
        """推奨事項を生成"""
        recommendations = []
        
        if 'accuracy' in self.comparison:
            acc_summary = self.comparison['accuracy'].get('summary', {})
            en_advantages = acc_summary.get('en_advantages', 0)
            ja_advantages = acc_summary.get('ja_advantages', 0)
            
            if en_advantages > ja_advantages:
                recommendations.append("📌 英語の方が全般的に高精度。日本語の最適化推奨。")
            elif ja_advantages > en_advantages:
                recommendations.append("🎯 日本語の方が全般的に高精度。言語特性に合わせた最適化実施中。")
            else:
                recommendations.append("✅ 両言語で均衡した性能。言語別チューニングで更なる改善可能。")
        
        if 'performance' in self.comparison:
            perf_summary = self.comparison['performance'].get('summary', {})
            ratio = perf_summary.get('avg_performance_ratio', 1.0)
            
            if ratio > 1.1:
                recommendations.append(f"⚡ 英語が{ratio:.2f}倍高速。インフラ最適化推奨。")
            elif ratio < 0.9:
                recommendations.append(f"⚡ 日本語が{1/ratio:.2f}倍高速。言語別処理パイプライン活用。")
        
        return recommendations
    
    def print_summary(self):
        """サマリーを表示"""
        print("\n" + "="*70)
        print("🌍 言語別精度比較レポート")
        print("="*70)
        
        print(f"\n📊 比較対象:")
        print(f"  英語モデル: {self.en_results.get('model', 'Unknown')}")
        print(f"  日本語モデル: {self.ja_results.get('model', 'Unknown')}")
        
        if 'accuracy' in self.comparison:
            print("\n📈 精度比較:")
            acc = self.comparison['accuracy']['summary']
            print(f"  英語平均精度: {acc.get('avg_en_accuracy', 0):.4f}")
            print(f"  日本語平均精度: {acc.get('avg_ja_accuracy', 0):.4f}")
            print(f"  平均精度差: {acc.get('avg_accuracy_diff', 0):.4f}")
            print(f"  英語優位: {acc.get('en_advantages', 0)}")
            print(f"  日本語優位: {acc.get('ja_advantages', 0)}")
            print(f"  同等性能: {acc.get('equal_performance', 0)}")
        
        if 'performance' in self.comparison:
            print("\n⚡ パフォーマンス比較:")
            perf = self.comparison['performance']['summary']
            print(f"  英語平均スループット: {perf.get('avg_en_throughput', 0):.0f} samples/sec")
            print(f"  日本語平均スループット: {perf.get('avg_ja_throughput', 0):.0f} samples/sec")
            ratio = perf.get('avg_performance_ratio', 1.0)
            faster = "英語" if ratio > 1.0 else "日本語"
            print(f"  {faster}が{abs(ratio - 1.0) * 100:.1f}%高速")
        
        print("\n💡 推奨事項:")
        for rec in self.comparison.get('recommendations', []):
            print(f"  {rec}")


def main():
    """メイン処理"""
    import argparse
    
    parser = argparse.ArgumentParser(description="言語別精度比較")
    parser.add_argument(
        "--en",
        type=str,
        required=True,
        help="英語結果ファイルパス"
    )
    parser.add_argument(
        "--ja",
        type=str,
        required=True,
        help="日本語結果ファイルパス"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="language_comparison_report.json",
        help="出力ファイルパス"
    )
    
    args = parser.parse_args()
    
    analyzer = LanguageComparisonAnalyzer()
    analyzer.load_results(args.en, args.ja)
    
    # 比較分析実行
    report = analyzer.generate_report(output_path=args.output)
    
    # サマリー表示
    analyzer.print_summary()
    
    print(f"\n📄 詳細レポート: {args.output}")


if __name__ == "__main__":
    main()
