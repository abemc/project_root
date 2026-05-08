#!/usr/bin/env python3
"""
CoT統合ベンチマーク測定スクリプト

Chain-of-Thoughtを使用した推論能力の強化を測定します。
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import json
from datetime import datetime
import logging

from evaluation.metrics.metric_calculator import MetricCalculator
from evaluation.datasets.mmlu_loader import MMULoader
from evaluation.datasets.gsm8k_loader import GSM8KLoader
from evaluation.cot_reasoning import CoTReasoner, TreeOfThoughtReasoner, PromptOptimizer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CoTBenchmarkRunner:
    """
    CoT推論を使用したベンチマーク測定実行エンジン
    """
    
    def __init__(self):
        self.calculator = MetricCalculator()
        self.cot_reasoner = CoTReasoner()
        self.tot_reasoner = TreeOfThoughtReasoner()
        self.prompt_optimizer = PromptOptimizer()
        
        logger.info("Initialized CoTBenchmarkRunner")
    
    def measure_mmlu_with_cot(self, num_samples: int = 50) -> Dict:
        """
        MMUをCoT推論で測定
        
        Args:
            num_samples: 測定問題数
            
        Returns:
            測定結果
        """
        logger.info(f"Starting MMLU measurement with CoT (n={num_samples})")
        
        loader = MMULoader(num_samples=num_samples)
        questions = loader.load(subjects=['abstract_algebra', 'anatomy'])
        
        logger.info(f"Loaded {len(questions)} questions")
        
        predictions = []
        confidences = []
        
        for i, q in enumerate(questions):
            # CoT推論
            prompt, choices = loader.format_for_model(q)
            reasoning, answer = self.cot_reasoner.reason_mmlu(q.question, q.choices)
            
            predictions.append(answer)
            # ダミー信頼度
            confidences.append(0.5)
            
            if (i + 1) % 10 == 0:
                logger.info(f"  Processed {i+1}/{len(questions)}")
        
        # メトリクス計算
        references = [q.answer for q in questions]
        metrics = self.calculator.compute_all_metrics(predictions, references, 'classification')
        
        result = {
            'benchmark': 'MMLU',
            'method': 'CoT',
            'num_samples': len(predictions),
            'metrics': {k: float(v) if hasattr(v, '__float__') else v 
                       for k, v in metrics.items()},
            'avg_confidence': float(sum(confidences) / len(confidences)) if confidences else 0.0,
            'timestamp': datetime.now().isoformat()
        }
        
        logger.info(f"MMLU CoT - Accuracy: {metrics['accuracy']:.4f}")
        
        return result
    
    def measure_gsm8k_with_cot(self, num_samples: int = 30) -> Dict:
        """
        GSM8KをCoT推論で測定
        
        Args:
            num_samples: 測定問題数
            
        Returns:
            測定結果
        """
        logger.info(f"Starting GSM8K measurement with CoT (n={num_samples})")
        
        loader = GSM8KLoader(num_samples=num_samples)
        problems = loader.load()
        
        logger.info(f"Loaded {len(problems)} problems")
        
        predictions = []
        
        # デモなので10問のみ
        for i, p in enumerate(problems[:min(len(problems), 10)]):
            # CoT推論
            reasoning, answer = self.cot_reasoner.reason_gsm8k(p.problem)
            
            predictions.append(answer)
            
            if (i + 1) % 5 == 0:
                logger.info(f"  Processed {i+1}")
        
        # メトリクス計算
        references = [p.answer for p in problems[:len(predictions)]]
        metrics = self.calculator.compute_all_metrics(predictions, references, 'classification')
        
        result = {
            'benchmark': 'GSM8K',
            'method': 'CoT',
            'num_samples': len(predictions),
            'metrics': {k: float(v) if hasattr(v, '__float__') else v 
                       for k, v in metrics.items()},
            'timestamp': datetime.now().isoformat()
        }
        
        logger.info(f"GSM8K CoT - Accuracy: {metrics['accuracy']:.4f}")
        
        return result
    
    def measure_with_tot(self, num_samples: int = 20) -> Dict:
        """
        Tree-of-Thoughtで測定
        
        Args:
            num_samples: 測定問題数
            
        Returns:
            測定結果
        """
        logger.info(f"Starting Tree-of-Thought measurement (n={num_samples})")
        
        loader = MMULoader(num_samples=num_samples)
        questions = loader.load(subjects=['abstract_algebra'])
        
        predictions = []
        confidences = []
        
        for i, q in enumerate(questions[:min(len(questions), 10)]):
            reasoning, answer, confidence = self.tot_reasoner.reason(q.question, q.choices)
            
            predictions.append(answer)
            confidences.append(confidence)
            
            if (i + 1) % 5 == 0:
                logger.info(f"  Processed {i+1}")
        
        # メトリクス計算
        references = [q.answer for q in questions[:len(predictions)]]
        metrics = self.calculator.compute_all_metrics(predictions, references, 'classification')
        
        result = {
            'benchmark': 'MMLU (subset)',
            'method': 'Tree-of-Thought',
            'num_samples': len(predictions),
            'metrics': {k: float(v) if hasattr(v, '__float__') else v 
                       for k, v in metrics.items()},
            'avg_confidence': float(sum(confidences) / len(confidences)) if confidences else 0.0,
            'timestamp': datetime.now().isoformat()
        }
        
        logger.info(f"ToT - Accuracy: {metrics['accuracy']:.4f}, Avg Confidence: {sum(confidences)/len(confidences):.4f}")
        
        return result


def main():
    """メイン処理"""
    print("\n" + "="*80)
    print("✅ CoT統合ベンチマーク測定")
    print("="*80)
    
    runner = CoTBenchmarkRunner()
    results = {}
    
    # MMLU + CoT
    print("\n[1/3] MMLU with CoT...")
    try:
        results['mmlu_cot'] = runner.measure_mmlu_with_cot(num_samples=50)
    except Exception as e:
        logger.error(f"MMLU CoT failed: {e}")
        results['mmlu_cot'] = None
    
    # GSM8K + CoT
    print("\n[2/3] GSM8K with CoT...")
    try:
        results['gsm8k_cot'] = runner.measure_gsm8k_with_cot(num_samples=30)
    except Exception as e:
        logger.error(f"GSM8K CoT failed: {e}")
        results['gsm8k_cot'] = None
    
    # Tree-of-Thought
    print("\n[3/3] Tree-of-Thought...")
    try:
        results['tot'] = runner.measure_with_tot(num_samples=20)
    except Exception as e:
        logger.error(f"ToT measurement failed: {e}")
        results['tot'] = None
    
    # 結果保存
    output = {
        'timestamp': datetime.now().isoformat(),
        'method': 'Chain-of-Thought Reasoning',
        'results': results
    }
    
    output_path = Path('results/benchmarks/cot_measurements.json')
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)
    
    print("\n" + "="*80)
    print("✅ CoT測定完成")
    print("="*80)
    print(f"Results saved to: {output_path}")
    
    # 結果概要表示
    print("\n結果概要:")
    for key, result in results.items():
        if result:
            metrics = result.get('metrics', {})
            acc = metrics.get('accuracy', 0.0)
            print(f"  {key}: accuracy={acc:.4f}")


if __name__ == "__main__":
    main()
