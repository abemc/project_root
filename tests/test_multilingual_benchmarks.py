"""
多言語ベンチマーク統合テスト
"""

import sys
from pathlib import Path

# パスの追加
current_dir = Path(__file__).parent
project_root = current_dir.parent
sys.path.insert(0, str(project_root))

from src.evaluation.multilingual.language_detection import LanguageDetector
from src.evaluation.multilingual.multilingual_engine import MultilingualInferenceEngine
from src.evaluation.multilingual.japanese_mmlu_loader import (
    JapaneseMMLULoader,
    JapaneseGSM8KLoader,
)


def test_language_detector():
    """言語検出のテスト"""
    print("\n" + "="*60)
    print("🧪 Test 1: Language Detection")
    print("="*60)
    
    detector = LanguageDetector()
    
    test_cases = [
        ("What is machine learning?", "EN"),
        ("機械学習とは何ですか？", "JA"),
        ("Deep learning is a subset of machine learning.", "EN"),
        ("深層学習は機械学習のサブセットです。", "JA"),
        ("混合テスト: This is a mixed text with 日本語 content", "JA"),
    ]
    
    for text, expected_lang in test_cases:
        detected_lang, confidence = detector.detect_with_confidence(text)
        lang_name = detector.get_language_name(detected_lang)
        status = "✅" if detected_lang == expected_lang else "⚠️"
        print(f"{status} Text: {text[:40]}...")
        print(f"   Detected: {detected_lang} ({lang_name}), Confidence: {confidence:.2f}")
        print()


def test_japanese_mmlu_loader():
    """日本語MMLUローダーのテスト"""
    print("\n" + "="*60)
    print("🧪 Test 2: Japanese MMLU Loader")
    print("="*60)
    
    loader = JapaneseMMLULoader()
    
    # 利用可能な分野
    subjects = loader.get_available_subjects()
    print(f"Available subjects: {', '.join(subjects)}\n")
    
    # 各分野の説明
    for subject in subjects[:2]:  # 最初の2つの分野のみ
        description = loader.get_subject_description(subject)
        print(f"📚 {subject}: {description}")
        
        # 問題を読み込み
        questions = loader.load(subjects=[subject], limit=1)
        if questions:
            q = questions[0]
            print(f"   Q: {q['question'][:50]}...")
            print(f"   Choices: {', '.join(q['choices'][:2])}...")
            print(f"   Answer: {q['answer']}")
        print()


def test_japanese_gsm8k_loader():
    """日本語GSM8Kローダーのテスト"""
    print("\n" + "="*60)
    print("🧪 Test 3: Japanese GSM8K Loader")
    print("="*60)
    
    loader = JapaneseGSM8KLoader()
    
    # 問題を読み込み
    problems = loader.load(limit=2)
    
    for i, problem in enumerate(problems, 1):
        print(f"Problem {i}:")
        print(f"  Q: {problem['problem'][:60]}...")
        print(f"  Steps: {len(problem['steps'])} steps")
        print(f"  Answer: {problem['answer']}")
        print()


def test_multilingual_inference_engine():
    """多言語推論エンジンのテスト"""
    print("\n" + "="*60)
    print("🧪 Test 4: Multilingual Inference Engine")
    print("="*60)
    
    engine = MultilingualInferenceEngine()
    
    # 英語分類テスト
    print("📝 English Classification Test:")
    prompt_en = "What is the capital of France?"
    choices_en = ["London", "Paris", "Berlin", "Madrid"]
    answer_en, lang_en, conf_en = engine.predict_multilingual_classification(
        prompt_en, choices_en
    )
    print(f"  Question: {prompt_en}")
    print(f"  Answer: {answer_en}")
    print(f"  Language: {lang_en}, Confidence: {conf_en:.2f}")
    print()
    
    # 日本語分類テスト
    print("📝 Japanese Classification Test:")
    prompt_ja = "フランスの首都は何ですか？"
    choices_ja = ["ロンドン", "パリ", "ベルリン", "マドリッド"]
    answer_ja, lang_ja, conf_ja = engine.predict_multilingual_classification(
        prompt_ja, choices_ja
    )
    print(f"  Question: {prompt_ja}")
    print(f"  Answer: {answer_ja}")
    print(f"  Language: {lang_ja}, Confidence: {conf_ja:.2f}")
    print()
    
    # 英語数学テスト
    print("📝 English Math Test:")
    problem_en = "If John has 5 apples and Mary has 3 apples, how many apples do they have in total?"
    answer_en_math, lang_en_math, conf_en_math = engine.predict_multilingual_math(problem_en)
    print(f"  Problem: {problem_en}")
    print(f"  Answer: {answer_en_math}")
    print(f"  Language: {lang_en_math}, Confidence: {conf_en_math:.2f}")
    print()
    
    # 日本語数学テスト
    print("📝 Japanese Math Test:")
    problem_ja = "太郎は5個のリンゴを持っています。花子は3個のリンゴを持っています。合わせて何個のリンゴを持っていますか？"
    answer_ja_math, lang_ja_math, conf_ja_math = engine.predict_multilingual_math(problem_ja)
    print(f"  Problem: {problem_ja}")
    print(f"  Answer: {answer_ja_math}")
    print(f"  Language: {lang_ja_math}, Confidence: {conf_ja_math:.2f}")
    print()
    
    # 統計情報
    print("📊 Inference Statistics:")
    stats = engine.get_inference_statistics()
    print(f"  Total inferences: {stats.get('total_inferences', 0)}")
    print(f"  Language distribution: {stats.get('language_distribution', {})}")
    print(f"  Average language confidence: {stats.get('average_language_confidence', 0):.2f}")


def main():
    """メイン実行"""
    print("\n" + "="*60)
    print("🚀 Multi-language Benchmark Test Suite")
    print("="*60)
    
    test_language_detector()
    test_japanese_mmlu_loader()
    test_japanese_gsm8k_loader()
    test_multilingual_inference_engine()
    
    print("\n" + "="*60)
    print("✅ All Tests Completed Successfully!")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
