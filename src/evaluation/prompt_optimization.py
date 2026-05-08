"""
多言語プロンプト最適化エンジン

言語別に最適化されたプロンプトテンプレートを提供し、
推論精度の向上を実現します。

対応言語:
- 英語 (English)
- 日本語 (日本語)
"""

from typing import Dict, List, Optional
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class Language(Enum):
    """サポート言語"""
    ENGLISH = "en"
    JAPANESE = "ja"


class LanguageOptimizedPromptEngine:
    """
    言語別プロンプト最適化エンジン
    
    Features:
    - 言語自動判定
    - 言語別テンプレート管理
    - Chain-of-Thought 対応
    - マルチプロンプト戦略
    """
    
    # 英語プロンプトテンプレート
    ENGLISH_TEMPLATES = {
        "classification": {
            "standard": "Question: {question}\n\nOptions:\nA) {option_a}\nB) {option_b}\nC) {option_c}\nD) {option_d}\n\nPlease select the correct answer.",
            "cot": "Let me think through this step by step.\n\nQuestion: {question}\n\nOptions:\nA) {option_a}\nB) {option_b}\nC) {option_c}\nD) {option_d}\n\nReasoning:\n1. First, let me understand what the question is asking.\n2. Let me consider each option:\n   - Option A: {option_a}\n   - Option B: {option_b}\n   - Option C: {option_c}\n   - Option D: {option_d}\n3. The correct answer is:",
            "zero_shot": "Answer the following multiple choice question by selecting A, B, C, or D.\n\n{question}\n\nA) {option_a}\nB) {option_b}\nC) {option_c}\nD) {option_d}\n\nAnswer:",
        },
        "math": {
            "standard": "Problem: {problem}\n\nSolve this step by step and provide the final numerical answer.",
            "cot": "Let me solve this math problem step by step.\n\nProblem: {problem}\n\nStep 1: Identify what we know\nStep 2: Set up the calculation\nStep 3: Perform the calculation\nStep 4: Verify the answer\n\nFinal answer:",
            "zero_shot": "Solve: {problem}\nAnswer: ",
        }
    }
    
    # 日本語プロンプトテンプレート
    JAPANESE_TEMPLATES = {
        "classification": {
            "standard": "問題：{question}\n\n選択肢：\nA) {option_a}\nB) {option_b}\nC) {option_c}\nD) {option_d}\n\n正しい答えを選んでください。",
            "cot": "この問題を段階的に考えてみましょう。\n\n問題：{question}\n\n選択肢：\nA) {option_a}\nB) {option_b}\nC) {option_c}\nD) {option_d}\n\n理由：\n1. まず、問題が何を聞いているのか理解します。\n2. 各選択肢を検討します：\n   - オプションA：{option_a}\n   - オプションB：{option_b}\n   - オプションC：{option_c}\n   - オプションD：{option_d}\n3. 正しい答えは：",
            "zero_shot": "次の多肢選択問題にA、B、C、またはDで答えてください。\n\n{question}\n\nA) {option_a}\nB) {option_b}\nC) {option_c}\nD) {option_d}\n\n答え：",
        },
        "math": {
            "standard": "問題：{problem}\n\nこれを段階的に解いて、最終的な数値の答えを提供してください。",
            "cot": "この数学の問題を段階的に解いてみましょう。\n\n問題：{problem}\n\n手順1：既知の情報を識別する\n手順2：計算をセットアップする\n手順3：計算を実行する\n手順4：答えを確認する\n\n最終的な答え：",
            "zero_shot": "解け：{problem}\n答え：",
        }
    }
    
    def __init__(self):
        """初期化"""
        logger.info("Initialized LanguageOptimizedPromptEngine")
    
    @staticmethod
    def detect_language(text: str) -> Language:
        """
        テキストから言語を検出
        
        Args:
            text: テキスト
            
        Returns:
            Language enum
        """
        # 日本語文字の検出
        japanese_chars = 0
        for char in text:
            if ord(char) >= 0x3040 and ord(char) <= 0x309F:  # ひらがな
                japanese_chars += 1
            elif ord(char) >= 0x30A0 and ord(char) <= 0x30FF:  # カタカナ
                japanese_chars += 1
            elif ord(char) >= 0x4E00 and ord(char) <= 0x9FFF:  # 漢字
                japanese_chars += 1
        
        if japanese_chars > len(text) * 0.2:  # 20%以上が日本語文字
            return Language.JAPANESE
        else:
            return Language.ENGLISH
    
    def get_classification_prompt(
        self,
        question: str,
        choices: List[str],
        language: Optional[Language] = None,
        strategy: str = "cot"
    ) -> str:
        """
        分類問題のプロンプトを生成
        
        Args:
            question: 問題文
            choices: 選択肢 (A, B, C, D の順)
            language: 言語（自動判定）
            strategy: プロンプト戦略 ('standard', 'cot', 'zero_shot')
            
        Returns:
            フォーマット済みプロンプト
        """
        if language is None:
            language = self.detect_language(question)
        
        templates = self.ENGLISH_TEMPLATES if language == Language.ENGLISH else self.JAPANESE_TEMPLATES
        template = templates["classification"].get(strategy, templates["classification"]["standard"])
        
        prompt = template.format(
            question=question,
            option_a=choices[0] if len(choices) > 0 else "",
            option_b=choices[1] if len(choices) > 1 else "",
            option_c=choices[2] if len(choices) > 2 else "",
            option_d=choices[3] if len(choices) > 3 else ""
        )
        
        return prompt
    
    def get_math_prompt(
        self,
        problem: str,
        language: Optional[Language] = None,
        strategy: str = "cot"
    ) -> str:
        """
        数学問題のプロンプトを生成
        
        Args:
            problem: 問題文
            language: 言語（自動判定）
            strategy: プロンプト戦略 ('standard', 'cot', 'zero_shot')
            
        Returns:
            フォーマット済みプロンプト
        """
        if language is None:
            language = self.detect_language(problem)
        
        templates = self.ENGLISH_TEMPLATES if language == Language.ENGLISH else self.JAPANESE_TEMPLATES
        template = templates["math"].get(strategy, templates["math"]["standard"])
        
        prompt = template.format(problem=problem)
        
        return prompt
    
    def get_language_info(self, language: Language) -> Dict[str, str]:
        """
        言語情報を取得
        
        Args:
            language: 言語
            
        Returns:
            言語情報辞書
        """
        info = {
            Language.ENGLISH: {
                "name": "English",
                "code": "en",
                "direction": "ltr"
            },
            Language.JAPANESE: {
                "name": "日本語",
                "code": "ja",
                "direction": "ltr"
            }
        }
        return info.get(language, {})


def demo():
    """デモンストレーション"""
    print("\n" + "="*80)
    print("多言語プロンプト最適化エンジン デモ")
    print("="*80)
    
    engine = LanguageOptimizedPromptEngine()
    
    # [1] 言語検出テスト
    print("\n[1] 言語検出テスト:")
    test_texts = [
        "What is the capital of France?",
        "フランスの首都はどこですか？"
    ]
    
    for text in test_texts:
        lang = engine.detect_language(text)
        info = engine.get_language_info(lang)
        print(f"  テキスト: '{text[:30]}...'")
        print(f"  検出言語: {info['name']} ({info['code']})")
    
    # [2] 英語の分類プロンプト
    print("\n[2] 英語の分類プロンプト (CoT戦略):")
    en_prompt = engine.get_classification_prompt(
        question="What is the powerhouse of the cell?",
        choices=["Nucleus", "Mitochondria", "Ribosome", "Golgi apparatus"],
        language=Language.ENGLISH,
        strategy="cot"
    )
    print(en_prompt[:200] + "...")
    
    # [3] 日本語の分類プロンプト
    print("\n[3] 日本語の分類プロンプト (CoT戦略):")
    ja_prompt = engine.get_classification_prompt(
        question="細胞の『発電所』と呼ばれるのはどの組織か。",
        choices=["核", "ミトコンドリア", "リボソーム", "ゴルジ体"],
        language=Language.JAPANESE,
        strategy="cot"
    )
    print(ja_prompt[:200] + "...")
    
    # [4] 数学プロンプト
    print("\n[4] 数学プロンプト (日本語, CoT戦略):")
    ja_math = engine.get_math_prompt(
        problem="2x + 5 = 13を解きなさい。",
        language=Language.JAPANESE,
        strategy="cot"
    )
    print(ja_math[:150] + "...")
    
    print("\n✅ デモ完了")


if __name__ == "__main__":
    demo()
