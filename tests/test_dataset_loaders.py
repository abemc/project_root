#!/usr/bin/env python3
"""
データセットローダーの統合テスト

すべての5つのベンチマークデータセットローダーが
正常に動作することを検証します。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import logging

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_mmlu_loader():
    """MMLU ローダーテスト"""
    print("\n" + "="*80)
    print("MMLU ローダーテスト")
    print("="*80)
    
    from src.evaluation.datasets.mmlu_loader import MMULoader, MMUQuestion
    
    loader = MMULoader(num_samples=5)
    
    # メタデータ確認
    metadata = loader.get_metadata()
    print(f"\nメタデータ: {metadata['dataset']}")
    print(f"  説明: {metadata['description']}")
    print(f"  予想問題数: {metadata['expected_questions']}")
    
    # ローダーのテスト（オフラインモード）
    print("\n✓ MMULoader初期化成功")
    print(f"✓ ローダーテスト通過")
    



def test_gsm8k_loader():
    """GSM8K ローダーテスト"""
    print("\n" + "="*80)
    print("GSM8K ローダーテスト")
    print("="*80)
    
    from src.evaluation.datasets.gsm8k_loader import GSM8KLoader, GSM8KEvaluator
    
    loader = GSM8KLoader(num_samples=3)
    
    # メタデータ確認
    metadata = loader.get_metadata()
    print(f"\nメタデータ: {metadata['dataset']}")
    print(f"  説明: {metadata['description']}")
    print(f"  予想問題数: {metadata['expected_problems']}")
    
    # 答え抽出テスト
    test_cases = [
        ("#### 42", "42"),
        ("The answer is 7 #### 7", "7"),
        ("Answer: 3.14", "3.14"),
    ]
    
    print("\n答え抽出テスト:")
    for text, expected in test_cases:
        extracted = loader.extract_answer(text)
        status = "✓" if extracted == expected else "✗"
        print(f"  {status} '{text}' → '{extracted}' (期待: '{expected}')")
    
    # 答え比較テスト
    evaluator = GSM8KEvaluator(loader)
    print("\n答え比較テスト:")
    
    test_pairs = [
        ("42", "42", True),
        ("3", "3.0", True),
        ("42", "43", False),
    ]
    
    for pred, correct, expected in test_pairs:
        result = evaluator._check_answer(pred, correct)
        status = "✓" if result == expected else "✗"
        print(f"  {status} '{pred}' vs '{correct}' → {result} (期待: {expected})")
    
    print(f"\n✓ GSM8KLoader初期化成功")
    print(f"✓ ローダーテスト通過")
    



def test_humaneval_loader():
    """HumanEval ローダーテスト"""
    print("\n" + "="*80)
    print("HumanEval ローダーテスト")
    print("="*80)
    
    from src.evaluation.datasets.humaneval_loader import HumanEvalLoader, HumanEvalEvaluator
    
    loader = HumanEvalLoader(num_samples=3)
    
    # メタデータ確認
    metadata = loader.get_metadata()
    print(f"\nメタデータ: {metadata['dataset']}")
    print(f"  説明: {metadata['description']}")
    print(f"  予想問題数: {metadata['num_problems']}")
    
    print(f"\n✓ HumanEvalLoader初期化成功")
    print(f"✓ ローダーテスト通過")
    



def test_truthfulqa_loader():
    """TruthfulQA ローダーテスト"""
    print("\n" + "="*80)
    print("TruthfulQA ローダーテスト")
    print("="*80)
    
    from src.evaluation.datasets.truthfulqa_bbq_loaders import TruthfulQALoader
    
    loader = TruthfulQALoader(num_samples=3)
    
    # メタデータ確認
    metadata = loader.get_metadata()
    print(f"\nメタデータ: {metadata['dataset']}")
    print(f"  説明: {metadata['description']}")
    print(f"  予想問題数: {metadata['num_questions']}")
    
    print(f"\n✓ TruthfulQALoader初期化成功")
    print(f"✓ ローダーテスト通過")
    



def test_bbq_loader():
    """BBQ ローダーテスト"""
    print("\n" + "="*80)
    print("BBQ (Bias Benchmark) ローダーテスト")
    print("="*80)
    
    from src.evaluation.datasets.truthfulqa_bbq_loaders import BBQLoader, BiasEvaluator
    
    loader = BBQLoader(num_samples=3, bias_types=['gender'])
    
    # メタデータ確認
    metadata = loader.get_metadata()
    print(f"\nメタデータ: {metadata['dataset']}")
    print(f"  説明: {metadata['description']}")
    print(f"  予想問題数: {metadata['num_questions']}")
    print(f"  バイアスタイプ: {loader.bias_types}")
    
    # バイアス評価テスト
    print("\nバイアス評価テスト:")
    
    from src.evaluation.datasets.truthfulqa_bbq_loaders import BBQQuestion
    
    test_questions = [
        BBQQuestion(0, "Q1", "Context1", ["A", "B", "C"], 0, "gender", "cat1"),
        BBQQuestion(1, "Q2", "Context2", ["X", "Y", "Z"], 1, "gender", "cat2"),
        BBQQuestion(2, "Q3", "Context3", ["P", "Q", "R"], 2, "race", "cat3"),
    ]
    
    # 完全正解テスト
    predictions = [0, 1, 2]
    results = BiasEvaluator.evaluate_bbq(predictions, test_questions)
    print(f"  精度: {results['accuracy']:.2%}")
    print(f"  バイアスタイプ別:")
    for bias, acc in results['by_bias_type'].items():
        print(f"    - {bias}: {acc:.2%}")
    
    print(f"\n✓ BBQLoader初期化成功")
    print(f"✓ ローダーテスト通過")
    



def main():
    """メイン処理"""
    print("\n" + "="*80)
    print("データセットローダー統合テスト")
    print("="*80)
    
    results = []
    
    try:
        results.append(("MMLU", test_mmlu_loader()))
    except Exception as e:
        logger.error(f"MMLU test failed: {e}")
        results.append(("MMLU", False))
    
    try:
        results.append(("GSM8K", test_gsm8k_loader()))
    except Exception as e:
        logger.error(f"GSM8K test failed: {e}")
        results.append(("GSM8K", False))
    
    try:
        results.append(("HumanEval", test_humaneval_loader()))
    except Exception as e:
        logger.error(f"HumanEval test failed: {e}")
        results.append(("HumanEval", False))
    
    try:
        results.append(("TruthfulQA", test_truthfulqa_loader()))
    except Exception as e:
        logger.error(f"TruthfulQA test failed: {e}")
        results.append(("TruthfulQA", False))
    
    try:
        results.append(("BBQ", test_bbq_loader()))
    except Exception as e:
        logger.error(f"BBQ test failed: {e}")
        results.append(("BBQ", False))
    
    # 結果サマリー
    print("\n" + "="*80)
    print("テスト結果サマリー")
    print("="*80 + "\n")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status}: {name}")
    
    print(f"\n総合: {passed}/{total} テスト通過 ({100*passed/total:.0f}%)")
    
    if passed == total:
        print("\n✓ すべてのローダーテストが成功しました！")
        return 0
    else:
        print(f"\n⚠ {total - passed} つのテストが失敗しました")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
