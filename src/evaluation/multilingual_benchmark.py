"""
多言語統合測定フレームワーク

英語と日本語の両ベンチマークを統合して、
モデルの多言語性能を評価します。
"""

import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class MultilingualBenchmarkRunner:
    """
    多言語ベンチマーク実行エンジン
    
    Features:
    - 複数言語ベンチマーク統合
    - 言語別メトリクス計算
    - 比較分析機能
    - 結果永続化
    """
    
    def __init__(
        self,
        output_dir: str = "results/benchmarks",
        model_name: str = "multilingual-model"
    ):
        """
        初期化
        
        Args:
            output_dir: 結果出力ディレクトリ
            model_name: モデル名
        """
        self.output_dir = Path(output_dir)
        self.model_name = model_name
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.results = {
            "en": {},
            "ja": {},
            "overall": {}
        }
        
        logger.info(f"Initialized MultilingualBenchmarkRunner: {model_name}")
    
    def add_benchmark_result(
        self,
        language: str,
        benchmark_name: str,
        accuracy: float,
        num_samples: int,
        details: Optional[Dict] = None
    ) -> None:
        """
        ベンチマーク結果を追加
        
        Args:
            language: 言語コード ('en' or 'ja')
            benchmark_name: ベンチマーク名
            accuracy: 精度 (0-1)
            num_samples: サンプル数
            details: 詳細情報
        """
        if language not in self.results:
            self.results[language] = {}
        
        self.results[language][benchmark_name] = {
            "accuracy": accuracy,
            "num_samples": num_samples,
            "f1_score": self._calculate_f1(accuracy, num_samples),
            "details": details or {}
        }
        
        logger.info(f"Added result: {language}/{benchmark_name}: {accuracy:.1%}")
    
    def calculate_language_metrics(self, language: str) -> Dict:
        """
        言語別メトリクスを計算
        
        Args:
            language: 言語コード
            
        Returns:
            言語別メトリクス
        """
        if language not in self.results or not self.results[language]:
            return {"accuracy": 0, "num_benchmarks": 0}
        
        benchmarks = self.results[language]
        accuracies = [b["accuracy"] for b in benchmarks.values()]
        total_samples = sum(b["num_samples"] for b in benchmarks.values())
        
        return {
            "average_accuracy": sum(accuracies) / len(accuracies),
            "num_benchmarks": len(benchmarks),
            "total_samples": total_samples,
            "benchmarks": list(benchmarks.keys())
        }
    
    def calculate_overall_metrics(self) -> Dict:
        """
        全体メトリクスを計算
        
        Returns:
            全体メトリクス
        """
        all_accuracies = []
        total_samples = 0
        
        for lang in ["en", "ja"]:
            for benchmark_data in self.results.get(lang, {}).values():
                all_accuracies.append(benchmark_data["accuracy"])
                total_samples += benchmark_data["num_samples"]
        
        if not all_accuracies:
            return {"overall_accuracy": 0, "total_samples": 0}
        
        return {
            "overall_accuracy": sum(all_accuracies) / len(all_accuracies),
            "total_samples": total_samples,
            "total_benchmarks": len(all_accuracies),
            "languages": list(self.results.keys())
        }
    
    def compare_languages(self) -> Dict:
        """
        言語間の比較分析
        
        Returns:
            言語間比較結果
        """
        en_metrics = self.calculate_language_metrics("en")
        ja_metrics = self.calculate_language_metrics("ja")
        
        en_acc = en_metrics.get("average_accuracy", 0)
        ja_acc = ja_metrics.get("average_accuracy", 0)
        
        return {
            "english": en_acc,
            "japanese": ja_acc,
            "difference": en_acc - ja_acc,
            "better_language": "English" if en_acc > ja_acc else ("Japanese" if ja_acc > en_acc else "Equal")
        }
    
    def generate_report(self) -> str:
        """
        テキストレポートを生成
        
        Returns:
            レポート文字列
        """
        report_lines = []
        report_lines.append("\n" + "="*80)
        report_lines.append("📊 多言語ベンチマーク測定レポート")
        report_lines.append("="*80)
        
        # モデル情報
        report_lines.append(f"\nモデル: {self.model_name}")
        report_lines.append(f"測定日時: {datetime.now().isoformat()}")
        
        # 英語結果
        report_lines.append("\n【英語 (English) ベンチマーク】")
        en_metrics = self.calculate_language_metrics("en")
        report_lines.append(f"  平均精度: {en_metrics.get('average_accuracy', 0):.1%}")
        report_lines.append(f"  対象ベンチマーク: {en_metrics.get('num_benchmarks', 0)}個")
        for name, data in self.results.get("en", {}).items():
            report_lines.append(f"    - {name}: {data['accuracy']:.1%} ({data['num_samples']}問)")
        
        # 日本語結果
        report_lines.append("\n【日本語 (Japanese) ベンチマーク】")
        ja_metrics = self.calculate_language_metrics("ja")
        report_lines.append(f"  平均精度: {ja_metrics.get('average_accuracy', 0):.1%}")
        report_lines.append(f"  対象ベンチマーク: {ja_metrics.get('num_benchmarks', 0)}個")
        for name, data in self.results.get("ja", {}).items():
            report_lines.append(f"    - {name}: {data['accuracy']:.1%} ({data['num_samples']}問)")
        
        # 比較分析
        comparison = self.compare_languages()
        report_lines.append("\n【言語間比較】")
        report_lines.append(f"  英語性能: {comparison['english']:.1%}")
        report_lines.append(f"  日本語性能: {comparison['japanese']:.1%}")
        report_lines.append(f"  差分: {comparison['difference']:+.1%}")
        report_lines.append(f"  優位言語: {comparison['better_language']}")
        
        # 全体メトリクス
        overall = self.calculate_overall_metrics()
        report_lines.append("\n【全体メトリクス】")
        report_lines.append(f"  全体精度: {overall.get('overall_accuracy', 0):.1%}")
        report_lines.append(f"  総サンプル数: {overall.get('total_samples', 0)}問")
        report_lines.append(f"  総ベンチマーク数: {overall.get('total_benchmarks', 0)}個")
        
        report_lines.append("\n" + "="*80 + "\n")
        
        return "\n".join(report_lines)
    
    def save_results(self, filename: Optional[str] = None) -> Path:
        """
        結果をJSONで保存
        
        Args:
            filename: ファイル名（デフォルト: タイムスタンプ）
            
        Returns:
            保存パス
        """
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"multilingual_metrics_{timestamp}.json"
        
        filepath = self.output_dir / filename
        
        output_data = {
            "model": self.model_name,
            "timestamp": datetime.now().isoformat(),
            "results": self.results,
            "language_metrics": {
                "english": self.calculate_language_metrics("en"),
                "japanese": self.calculate_language_metrics("ja")
            },
            "overall_metrics": self.calculate_overall_metrics(),
            "comparison": self.compare_languages()
        }
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Results saved to: {filepath}")
        return filepath
    
    @staticmethod
    def _calculate_f1(accuracy: float, num_samples: int) -> float:
        """
        簡略的なF1スコアを計算
        
        Args:
            accuracy: 精度
            num_samples: サンプル数
            
        Returns:
            F1スコア
        """
        # 簡略実装：精度と投票数を基にした推定
        return accuracy
    
    def __str__(self) -> str:
        """文字列表現"""
        return self.generate_report()


def demo():
    """デモンストレーション"""
    print("\n" + "="*80)
    print("多言語統合測定フレームワーク デモ")
    print("="*80)
    
    # ランナー初期化
    runner = MultilingualBenchmarkRunner(model_name="demo-model-v1")
    
    # 英語ベンチマーク結果を追加
    print("\n[1] 英語ベンチマーク結果追加:")
    runner.add_benchmark_result(
        language="en",
        benchmark_name="MMLU",
        accuracy=0.52,
        num_samples=100
    )
    runner.add_benchmark_result(
        language="en",
        benchmark_name="GSM8K",
        accuracy=0.45,
        num_samples=50
    )
    print("  ✓ 英語結果を追加")
    
    # 日本語ベンチマーク結果を追加
    print("\n[2] 日本語ベンチマーク結果追加:")
    runner.add_benchmark_result(
        language="ja",
        benchmark_name="Japanese_MMLU",
        accuracy=0.48,
        num_samples=100
    )
    runner.add_benchmark_result(
        language="ja",
        benchmark_name="Japanese_Math",
        accuracy=0.40,
        num_samples=50
    )
    print("  ✓ 日本語結果を追加")
    
    # レポート生成
    print("\n[3] レポート生成:")
    print(runner.generate_report())
    
    # 結果保存
    print("\n[4] 結果保存:")
    saved_path = runner.save_results("demo_multilingual_results.json")
    print(f"  ✓ 保存完了: {saved_path}")
    
    print("✅ デモ完了")


if __name__ == "__main__":
    demo()
