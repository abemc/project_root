#!/usr/bin/env python3
"""
Chain-of-Thought (CoT) 推論エンジン

ステップバイステップの推論能力を強化するための
プロンプトテンプレートと推論ロジックを実装します。

参考:
- "Chain-of-Thought Prompting Elicits Reasoning in Large Language Models"
  (Wei et al., 2022)
- https://arxiv.org/abs/2201.11903
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import re
import logging

logger = logging.getLogger(__name__)


@dataclass
class CoTPromptTemplate:
    """Chain-of-Thoughtプロンプトテンプレート"""
    
    # MMLU用テンプレート
    MMLU_COT = """
Question: {question}

Options:
{options}

Let me think step by step:
1. First, I need to understand what this question is asking.
2. I'll analyze each option carefully.
3. I'll use my knowledge to determine the correct answer.

Step-by-step reasoning:
{reasoning}

The correct answer is: """
    
    # GSM8K用テンプレート
    GSM8K_COT = """
Problem: {problem}

Let me solve this step by step:

Step 1: Understand what the problem is asking
- We need to find: {what_to_find}

Step 2: Identify the given information
- Given: {given_info}

Step 3: Plan the solution approach
- Strategy: {strategy}

Step 4: Solve step by step
{solution_steps}

Step 5: Verify the answer
- The answer makes sense because: {verification}

Therefore, the answer is: """
    
    # 一般的な推論用テンプレート
    GENERAL_COT = """
Question: {question}

Let me think through this carefully:

1. What is being asked?
   - I need to find/determine: {what_asked}

2. What information do I have?
   - Key facts: {facts}

3. What reasoning approach should I use?
   - Approach: {approach}

4. Let me work through this step by step:
{steps}

5. Conclusion
   - The answer is: {answer}

Because: {justification}
"""


class CoTReasoner:
    """
    Chain-of-Thoughtベースの推論エンジン
    """
    
    def __init__(self, model=None):
        """
        初期化
        
        Args:
            model: 推論に使用するLLMモデル
        """
        self.model = model
        self.prompt_templates = CoTPromptTemplate()
        logger.info("Initialized CoTReasoner")
    
    def reason_mmlu(
        self,
        question: str,
        choices: List[str],
        task_context: Optional[str] = None
    ) -> Tuple[str, str]:
        """
        MMUのCoT推論
        
        Args:
            question: 質問テキスト
            choices: 選択肢リスト
            task_context: 追加コンテキスト
            
        Returns:
            (推論過程, 最終回答) のタプル
        """
        # オプションのフォーマット
        options_str = "\n".join([
            f"{chr(65+i)}. {choice}"
            for i, choice in enumerate(choices)
        ])
        
        # プロンプト構築
        self.prompt_templates.MMLU_COT.format(
            question=question,
            options=options_str,
            reasoning="{reasoning_placeholder}"  # 後で入力
        )
        
        # ダミー推論（実装用プレースホルダー）
        reasoning = self._generate_dummy_reasoning(question, choices)
        
        # 最終回答抽出
        answer = self._extract_answer_from_reasoning(reasoning, choices)
        
        return reasoning, answer
    
    def reason_gsm8k(
        self,
        problem: str,
        context: Optional[Dict] = None
    ) -> Tuple[str, str]:
        """
        GSM8KのCoT推論
        
        Args:
            problem: 問題テキスト
            context: 問題コンテキスト
            
        Returns:
            (推論過程, 最終回答) のタプル
        """
        # ダミー実装
        reasoning = self._generate_math_reasoning(problem)
        
        # 答え抽出
        answer = self._extract_math_answer(reasoning)
        
        return reasoning, answer
    
    def _generate_dummy_reasoning(self, question: str, choices: List[str]) -> str:
        """ダミー推論生成（プレースホルダー）"""
        return f"""
Analyzing the question: "{question[:50]}..."

Option A: {choices[0] if len(choices) > 0 else 'N/A'} - This could be correct if...
Option B: {choices[1] if len(choices) > 1 else 'N/A'} - This is less likely because...
Option C: {choices[2] if len(choices) > 2 else 'N/A'} - This doesn't match the facts because...
Option D: {choices[3] if len(choices) > 3 else 'N/A'} - This is not the right answer.

Based on my analysis, Option B seems most correct.
"""
    
    def _generate_math_reasoning(self, problem: str) -> str:
        """数学問題の推論生成"""
        return f"""
Problem: {problem[:100]}...

Step 1: Identify the quantities involved
- I need to extract the relevant numbers from the problem

Step 2: Determine the operation
- This appears to be a {self._infer_operation(problem)} problem

Step 3: Perform the calculation
- Let me work through this carefully

Step 4: Express the final answer
- The answer is a number
"""
    
    def _extract_answer_from_reasoning(self, reasoning: str, choices: List[str]) -> str:
        """推論から回答を抽出"""
        # シンプルなパターンマッチ
        for i, choice in enumerate(choices):
            if f"Option {chr(65+i)}" in reasoning:
                return choice
        
        # デフォルト
        return choices[0] if choices else ""
    
    def _extract_math_answer(self, reasoning: str) -> str:
        """推論から数値答えを抽出"""
        # 数値パターンマッチ
        numbers = re.findall(r'\b\d+(?:\.\d+)?\b', reasoning)
        
        if numbers:
            return numbers[-1]  # 最後の数値
        
        return "0"
    
    def _infer_operation(self, problem: str) -> str:
        """問題から演算タイプを推測"""
        if "add" in problem.lower() or "total" in problem.lower():
            return "addition"
        elif "subtract" in problem.lower() or "left" in problem.lower():
            return "subtraction"
        elif "multiply" in problem.lower() or "times" in problem.lower():
            return "multiplication"
        elif "divide" in problem.lower() or "per" in problem.lower():
            return "division"
        else:
            return "mixed arithmetic"


class TreeOfThoughtReasoner:
    """
    Tree-of-Thought (ToT) 推論エンジン (オプション)
    
    複数の推論経路を探索し、最適なパスを選択します。
    """
    
    def __init__(self, model=None, max_depth: int = 3):
        """
        初期化
        
        Args:
            model: LLMモデル
            max_depth: 探索深さ
        """
        self.model = model
        self.max_depth = max_depth
        self.cot_reasoner = CoTReasoner(model)
        logger.info(f"Initialized TreeOfThoughtReasoner (depth={max_depth})")
    
    def reason(self, question: str, choices: List[str]) -> Tuple[str, str, float]:
        """
        ToT推論: 複数経路探索
        
        Args:
            question: 質問
            choices: 選択肢
            
        Returns:
            (最適推論, 最終回答, 信頼度) のタプル
        """
        # 複数経路を並列探索
        paths = []
        
        for path_idx in range(3):  # 3つの異なる推論経路
            reasoning, answer = self.cot_reasoner.reason_mmlu(question, choices)
            paths.append({
                'path': path_idx,
                'reasoning': reasoning,
                'answer': answer,
                'score': self._score_answer(answer, choices)
            })
        
        # 最高スコアのパスを選択
        best_path = max(paths, key=lambda x: x['score'])
        
        confidence = best_path['score']
        
        return best_path['reasoning'], best_path['answer'], confidence
    
    def _score_answer(self, answer: str, choices: List[str]) -> float:
        """回答スコア計算（簡略版）"""
        # ダミー実装: 常に0.5を返す
        return 0.5


class PromptOptimizer:
    """
    プロンプト最適化エンジン
    """
    
    def __init__(self):
        """初期化"""
        self.cot_reasoner = CoTReasoner()
        logger.info("Initialized PromptOptimizer")
    
    def optimize_for_language(self, prompt: str, language: str = "en") -> str:
        """
        言語別プロンプト最適化
        
        Args:
            prompt: 元のプロンプト
            language: ターゲット言語 ('en', 'ja', etc.)
            
        Returns:
            最適化されたプロンプト
        """
        optimizations = {
            "en": self._optimize_english,
            "ja": self._optimize_japanese,
        }
        
        optimizer = optimizations.get(language, lambda p: p)
        return optimizer(prompt)
    
    def _optimize_english(self, prompt: str) -> str:
        """英語用最適化"""
        # ベストプラクティスの適用
        improvements = [
            ("Let me think", "Let me think step by step"),
            ("Answer:", "Final answer:"),
        ]
        
        result = prompt
        for old, new in improvements:
            result = result.replace(old, new)
        
        return result
    
    def _optimize_japanese(self, prompt: str) -> str:
        """日本語用最適化"""
        # 日本語特化の最適化
        improvements = [
            ("Question:", "問題:"),
            ("Step by step:", "段階を追って:"),
        ]
        
        result = prompt
        for old, new in improvements:
            result = result.replace(old, new)
        
        return result
    
    def optimize_for_task(self, prompt: str, task_type: str) -> str:
        """
        タスク別プロンプト最適化
        
        Args:
            prompt: 元のプロンプト
            task_type: タスクタイプ ('mmlu', 'gsm8k', 'qa')
            
        Returns:
            最適化されたプロンプト
        """
        if task_type == 'mmlu':
            return self._optimize_for_multiple_choice(prompt)
        elif task_type == 'gsm8k':
            return self._optimize_for_math(prompt)
        elif task_type == 'qa':
            return self._optimize_for_qa(prompt)
        else:
            return prompt
    
    def _optimize_for_multiple_choice(self, prompt: str) -> str:
        """多選択問題用最適化"""
        return prompt.replace(
            "Answer:",
            "Based on my reasoning above, the best answer is:"
        )
    
    def _optimize_for_math(self, prompt: str) -> str:
        """数学問題用最適化"""
        return prompt.replace(
            "Answer:",
            "Therefore, the numerical answer is:"
        )
    
    def _optimize_for_qa(self, prompt: str) -> str:
        """質問応答用最適化"""
        return prompt.replace(
            "Answer:",
            "In conclusion, the answer is:"
        )


def demo():
    """デモンストレーション"""
    import logging
    logging.basicConfig(level=logging.INFO)
    
    # CoT推論のデモ
    print("\n" + "="*80)
    print("Chain-of-Thought (CoT) 推論エンジン デモ")
    print("="*80)
    
    reasoner = CoTReasoner()
    
    # MMU推論例
    print("\n[MMLU] CoT推論例:")
    question = "Which of the following is a property of linear equations?"
    choices = [
        "The graph is always a straight line",
        "The highest power of the variable is 2",
        "The coefficients must be integers",
        "The solution is always unique"
    ]
    
    reasoning, answer = reasoner.reason_mmlu(question, choices)
    print(f"Question: {question}")
    print(f"\nReasoning:\n{reasoning}")
    print(f"\nAnswer: {answer}")
    
    # ToT推論のデモ
    print("\n" + "="*80)
    print("Tree-of-Thought (ToT) 推論エンジン デモ")
    print("="*80)
    
    tot_reasoner = TreeOfThoughtReasoner()
    reasoning, answer, confidence = tot_reasoner.reason(question, choices)
    print(f"Best reasoning:\n{reasoning}")
    print(f"Answer: {answer}")
    print(f"Confidence: {confidence:.2f}")
    
    # プロンプト最適化のデモ
    print("\n" + "="*80)
    print("プロンプト最適化デモ")
    print("="*80)
    
    optimizer = PromptOptimizer()
    original = "Let me think about this problem. Answer:"
    optimized_en = optimizer.optimize_for_language(original, "en")
    optimized_ja = optimizer.optimize_for_language(original, "ja")
    
    print(f"Original: {original}")
    print(f"Optimized (EN): {optimized_en}")
    print(f"Optimized (JA): {optimized_ja}")


if __name__ == "__main__":
    demo()
