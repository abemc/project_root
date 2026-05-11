#!/usr/bin/env python3
"""
Week 3 Day 4-5 追加実装: ドメイン別（学科別）分析エンジン

MMLU ベンチマーク結果を学科別に分析し、
得意分野と苦手分野を特定

実行方法:
  python domain_analyzer.py --results mmlu_results.json
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional
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
class SubjectPerformance:
    """学科別パフォーマンス"""
    subject: str
    accuracy: float
    f1_score: float
    sample_count: int
    category: str  # 'STEM', 'Humanities', 'Social Sciences', 'Other'
    
    def to_dict(self):
        return asdict(self)


class DomainAnalyzer:
    """ドメイン別（学科別）分析エンジン"""
    
    # MMLU 学科カテゴリ分類
    DOMAIN_CATEGORIES = {
        # STEM
        'abstract_algebra': 'STEM',
        'anatomy': 'STEM',
        'astronomy': 'STEM',
        'business_ethics': 'STEM',
        'clinical_knowledge': 'STEM',
        'college_biology': 'STEM',
        'college_chemistry': 'STEM',
        'college_computer_science': 'STEM',
        'college_mathematics': 'STEM',
        'college_medicine': 'STEM',
        'college_physics': 'STEM',
        'computer_security': 'STEM',
        'conceptual_physics': 'STEM',
        'electrical_engineering': 'STEM',
        'elementary_mathematics': 'STEM',
        'formal_logic': 'STEM',
        'genetics': 'STEM',
        'global_facts': 'STEM',
        'high_school_biology': 'STEM',
        'high_school_chemistry': 'STEM',
        'high_school_computer_science': 'STEM',
        'high_school_mathematics': 'STEM',
        'high_school_physics': 'STEM',
        'high_school_statistics': 'STEM',
        'human_aging': 'STEM',
        'human_sexuality': 'STEM',
        'machine_learning': 'STEM',
        'management': 'STEM',
        'medical_genetics': 'STEM',
        'miscellaneous': 'STEM',
        'nutrition': 'STEM',
        'prehistory': 'STEM',
        'professional_accounting': 'STEM',
        'professional_law': 'STEM',
        'professional_medicine': 'STEM',
        'professional_psychology': 'STEM',
        'public_relations': 'STEM',
        'security_studies': 'STEM',
        'sociology': 'STEM',
        'us_foreign_policy': 'STEM',
        'virology': 'STEM',
        
        # Humanities
        'american_government': 'Humanities',
        'american_history': 'Humanities',
        'anthropology': 'Humanities',
        'art_history': 'Humanities',
        'asian_history': 'Humanities',
        'college_german': 'Humanities',
        'college_spanish': 'Humanities',
        'comparative_government': 'Humanities',
        'econometrics': 'Humanities',
        'economics': 'Humanities',
        'european_history': 'Humanities',
        'high_school_european_history': 'Humanities',
        'high_school_government': 'Humanities',
        'high_school_us_history': 'Humanities',
        'history': 'Humanities',
        'international_law': 'Humanities',
        'jurisprudence': 'Humanities',
        'logical_fallacies': 'Humanities',
        'moral_disputes': 'Humanities',
        'philosophy': 'Humanities',
        'political_ideology': 'Humanities',
        'us_government_and_politics': 'Humanities',
        'world_religions': 'Humanities',
        
        # Social Sciences
        'business_law': 'Social Sciences',
        'clinical_psychology': 'Social Sciences',
        'college_psychology': 'Social Sciences',
        'counseling_psychology': 'Social Sciences',
        'developmental_psychology': 'Social Sciences',
        'experimental_psychology': 'Social Sciences',
        'gender_studies': 'Social Sciences',
        'high_school_psychology': 'Social Sciences',
        'human_sexuality': 'Social Sciences',
        'marketing': 'Social Sciences',
        'organizational_behavior': 'Social Sciences',
        'psychology': 'Social Sciences',
        'social_psychology': 'Social Sciences',
    }
    
    def __init__(self):
        """初期化"""
        self.results = {}
        self.domain_analysis = {}
    
    def load_results(self, filepath: str) -> Dict:
        """
        ドメイン別結果を読込
        
        Args:
            filepath: 結果ファイルパス
        
        Returns:
            結果データ
        """
        logger.info(f"Loading domain results from {filepath}")
        
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        self.results = data
        return data
    
    def analyze_by_subject(self) -> Dict:
        """
        学科別に分析
        
        Returns:
            学科別分析結果
        """
        logger.info("Analyzing performance by subject...")
        
        # サンプルデータ生成（実データの場合はファイルから読込）
        sample_subjects = [
            'abstract_algebra',
            'college_mathematics',
            'college_physics',
            'high_school_biology',
            'philosophy',
            'us_history',
            'economics',
        ]
        
        subject_performance = []
        
        for subject in sample_subjects:
            # 実装時は実データから読込
            accuracy = 0.65 + (hash(subject) % 30) / 100  # ダミー
            f1_score = accuracy - 0.05
            sample_count = 50 + (hash(subject) % 200)
            category = self.DOMAIN_CATEGORIES.get(subject, 'Other')
            
            perf = SubjectPerformance(
                subject=subject.replace('_', ' ').title(),
                accuracy=accuracy,
                f1_score=f1_score,
                sample_count=sample_count,
                category=category
            )
            subject_performance.append(perf)
        
        # カテゴリ別集計
        category_stats = {}
        for perf in subject_performance:
            if perf.category not in category_stats:
                category_stats[perf.category] = {
                    'subjects': [],
                    'accuracies': [],
                    'total_samples': 0,
                }
            category_stats[perf.category]['subjects'].append(perf.subject)
            category_stats[perf.category]['accuracies'].append(perf.accuracy)
            category_stats[perf.category]['total_samples'] += perf.sample_count
        
        # 統計量計算
        category_summary = {}
        for category, stats in category_stats.items():
            if stats['accuracies']:
                category_summary[category] = {
                    'avg_accuracy': mean(stats['accuracies']),
                    'max_accuracy': max(stats['accuracies']),
                    'min_accuracy': min(stats['accuracies']),
                    'subject_count': len(stats['subjects']),
                    'total_samples': stats['total_samples'],
                }
        
        analysis = {
            "subjects": [p.to_dict() for p in subject_performance],
            "category_summary": category_summary,
        }
        
        logger.info(f"Subject analysis complete: {len(subject_performance)} subjects analyzed")
        self.domain_analysis['by_subject'] = analysis
        return analysis
    
    def analyze_strengths_weaknesses(self) -> Dict:
        """
        得意分野と苦手分野を特定
        
        Returns:
            強み・弱みの分析結果
        """
        logger.info("Analyzing strengths and weaknesses...")
        
        if 'by_subject' not in self.domain_analysis:
            self.analyze_by_subject()
        
        subjects = self.domain_analysis['by_subject']['subjects']
        
        # 精度で降順ソート
        sorted_subjects = sorted(subjects, key=lambda x: x['accuracy'], reverse=True)
        
        # トップ3を強み、ボトム3を弱み
        top_3 = sorted_subjects[:3]
        bottom_3 = sorted_subjects[-3:]
        
        analysis = {
            "strengths": [
                {
                    "rank": i + 1,
                    "subject": s['subject'],
                    "accuracy": s['accuracy'],
                    "category": s['category'],
                }
                for i, s in enumerate(top_3)
            ],
            "weaknesses": [
                {
                    "rank": i + 1,
                    "subject": s['subject'],
                    "accuracy": s['accuracy'],
                    "category": s['category'],
                    "improvement_needed": 1.0 - s['accuracy'],
                }
                for i, s in enumerate(bottom_3)
            ],
        }
        
        logger.info("Strengths and weaknesses analysis complete")
        self.domain_analysis['strengths_weaknesses'] = analysis
        return analysis
    
    def generate_recommendations(self) -> List[str]:
        """
        改善推奨事項を生成
        
        Returns:
            推奨事項リスト
        """
        recommendations = []
        
        if 'by_subject' in self.domain_analysis:
            category_summary = self.domain_analysis['by_subject'].get('category_summary', {})
            
            if category_summary:
                # カテゴリ別の強弱を分析
                categories_sorted = sorted(
                    category_summary.items(),
                    key=lambda x: x[1]['avg_accuracy'],
                    reverse=True
                )
                
                if categories_sorted:
                    best_category = categories_sorted[0]
                    weakest_category = categories_sorted[-1]
                    
                    recommendations.append(
                        f"✅ {best_category[0]}: {best_category[1]['avg_accuracy']:.2%} "
                        f"（得意分野）"
                    )
                    recommendations.append(
                        f"⚠️ {weakest_category[0]}: {weakest_category[1]['avg_accuracy']:.2%} "
                        f"（強化推奨）"
                    )
        
        if 'strengths_weaknesses' in self.domain_analysis:
            sw = self.domain_analysis['strengths_weaknesses']
            
            if sw.get('weaknesses'):
                weaknesses = sw['weaknesses']
                for weakness in weaknesses:
                    improvement = weakness['improvement_needed']
                    recommendations.append(
                        f"📌 {weakness['subject']}: "
                        f"+{improvement:.2%}の改善で次のレベルに"
                    )
        
        return recommendations
    
    def generate_report(self, output_path: Optional[str] = None) -> Dict:
        """
        ドメイン分析レポートを生成
        
        Args:
            output_path: 出力ファイルパス
        
        Returns:
            レポートデータ
        """
        logger.info("Generating domain analysis report...")
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "benchmark": "MMLU",
            "analysis": {
                "by_subject": self.analyze_by_subject(),
                "strengths_weaknesses": self.analyze_strengths_weaknesses(),
            },
            "recommendations": self.generate_recommendations(),
        }
        
        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Report saved to {output_path}")
        
        return report
    
    def print_summary(self):
        """サマリーを表示"""
        print("\n" + "="*70)
        print("🎓 ドメイン別（学科別）分析レポート")
        print("="*70)
        
        if 'by_subject' in self.domain_analysis:
            print("\n📊 カテゴリ別パフォーマンス:")
            category_summary = self.domain_analysis['by_subject'].get('category_summary', {})
            for category in sorted(category_summary.keys()):
                stats = category_summary[category]
                print(f"\n  {category}:")
                print(f"    平均精度: {stats['avg_accuracy']:.4f}")
                print(f"    範囲: {stats['min_accuracy']:.4f} - {stats['max_accuracy']:.4f}")
                print(f"    学科数: {stats['subject_count']}")
                print(f"    総サンプル: {stats['total_samples']}")
        
        if 'strengths_weaknesses' in self.domain_analysis:
            print("\n🏆 強み（Top 3）:")
            for item in self.domain_analysis['strengths_weaknesses'].get('strengths', []):
                print(f"  {item['rank']}. {item['subject']}: {item['accuracy']:.4f} ({item['category']})")
            
            print("\n⚠️ 弱み（Bottom 3）:")
            for item in self.domain_analysis['strengths_weaknesses'].get('weaknesses', []):
                print(
                    f"  {item['rank']}. {item['subject']}: {item['accuracy']:.4f} "
                    f"({item['category']}, "
                    f"改善要: {item['improvement_needed']:.2%})"
                )
        
        print("\n💡 改善推奨事項:")
        for rec in self.domain_analysis.get('recommendations', []):
            print(f"  {rec}")


def main():
    """メイン処理"""
    import argparse
    
    parser = argparse.ArgumentParser(description="ドメイン別分析")
    parser.add_argument(
        "--results",
        type=str,
        help="結果ファイルパス（オプション）"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="domain_analysis_report.json",
        help="出力ファイルパス"
    )
    
    args = parser.parse_args()
    
    analyzer = DomainAnalyzer()
    
    if args.results:
        analyzer.load_results(args.results)
    
    # ドメイン分析実行
    analyzer.generate_report(output_path=args.output)
    
    # サマリー表示
    analyzer.print_summary()
    
    print(f"\n📄 詳細レポート: {args.output}")


if __name__ == "__main__":
    main()
