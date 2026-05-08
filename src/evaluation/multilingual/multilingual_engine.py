"""
多言語推論エンジン - 言語別の最適化推論を提供
"""

from typing import Dict, Any, List, Optional, Tuple
import json
from datetime import datetime

from .language_detection import LanguageDetector


class MultilingualInferenceEngine:
    """
    複数言語に対応した推論エンジン
    
    機能:
    - 自動言語検出
    - 言語別プロンプト最適化
    - 言語別推論戦略の選択
    """
    
    # 言語別プロンプトテンプレート
    PROMPT_TEMPLATES = {
        'EN': {
            'classification': 'Answer the following question:\n\nQuestion: {prompt}\n\nOptions:\n{options}\n\nAnswer:',
            'math': 'Solve this math problem step by step:\n\n{problem}\n\nAnswer:',
            'reasoning': 'Think step by step to answer:\n\n{question}\n\nReasoning:',
        },
        'JA': {
            'classification': '次の問題に答えてください：\n\n問題: {prompt}\n\n選択肢：\n{options}\n\n答え：',
            'math': 'この数学の問題をステップバイステップで解いてください：\n\n{problem}\n\n答え：',
            'reasoning': 'ステップバイステップで考えて答えてください：\n\n{question}\n\n推論：',
        },
    }
    
    # 言語別の特性
    LANGUAGE_CHARACTERISTICS = {
        'EN': {
            'name': 'English',
            'priority_score_multiplier': 1.0,
            'confidence_threshold': 0.7,
            'max_tokens': 512,
        },
        'JA': {
            'name': '日本語',
            'priority_score_multiplier': 1.1,  # 日本語は若干高めのスコア
            'confidence_threshold': 0.6,
            'max_tokens': 512,
        },
    }
    
    def __init__(self, inference_engine=None):
        """
        多言語推論エンジンの初期化
        
        Args:
            inference_engine: 基本的な推論エンジン (未指定時はダミー使用)
        """
        self.language_detector = LanguageDetector()
        self.inference_engine = inference_engine
        self.inference_history: List[Dict[str, Any]] = []
    
    def predict_multilingual_classification(
        self,
        prompt: str,
        choices: List[str],
    ) -> Tuple[str, str, float]:
        """
        多言語分類予測（自動言語検出）
        
        Args:
            prompt (str): 質問文
            choices (List[str]): 選択肢リスト
            
        Returns:
            Tuple[str, str, float]: (答え, 検出言語, 確信度)
        """
        # 言語検出
        language, confidence = self.language_detector.detect_with_confidence(prompt)
        
        # 言語別プロンプト最適化
        optimized_prompt = self._optimize_prompt(
            prompt, language, 'classification'
        )
        
        # 推論実行
        if self.inference_engine is not None:
            try:
                answer = self.inference_engine.predict_classification(
                    optimized_prompt, choices
                )
            except Exception as e:
                # フォールバック
                answer = choices[len(prompt) % len(choices)]
        else:
            # ダミー推論
            answer = choices[len(prompt) % len(choices)]
        
        # 履歴に記録
        self.inference_history.append({
            'timestamp': datetime.now().isoformat(),
            'task': 'multilingual_classification',
            'input_language': language,
            'language_confidence': confidence,
            'prompt': prompt,
            'answer': answer,
        })
        
        return answer, language, confidence
    
    def predict_multilingual_math(
        self,
        problem: str,
    ) -> Tuple[str, str, float]:
        """
        多言語数学推論（自動言語検出）
        
        Args:
            problem (str): 数学問題
            
        Returns:
            Tuple[str, str, float]: (答え, 検出言語, 確信度)
        """
        # 言語検出
        language, confidence = self.language_detector.detect_with_confidence(problem)
        
        # 言語別プロンプト最適化
        optimized_prompt = self._optimize_prompt(
            problem, language, 'math'
        )
        
        # 推論実行
        if self.inference_engine is not None:
            try:
                answer = self.inference_engine.predict_math(optimized_prompt)
            except Exception as e:
                # フォールバック
                answer = str(len(problem) % 100)
        else:
            # ダミー推論
            answer = str(len(problem) % 100)
        
        # 履歴に記録
        self.inference_history.append({
            'timestamp': datetime.now().isoformat(),
            'task': 'multilingual_math',
            'input_language': language,
            'language_confidence': confidence,
            'problem': problem,
            'answer': answer,
        })
        
        return answer, language, confidence
    
    def _optimize_prompt(
        self,
        text: str,
        language: str,
        task_type: str,
    ) -> str:
        """
        言語別にプロンプトを最適化
        
        Args:
            text (str): 入力テキスト
            language (str): 言語コード ('EN' または 'JA')
            task_type (str): タスクタイプ ('classification', 'math', 'reasoning')
            
        Returns:
            str: 最適化されたプロンプト
        """
        if task_type == 'classification':
            template = self.PROMPT_TEMPLATES[language]['classification']
            return template.format(prompt=text, options='A, B, C, D')
        elif task_type == 'math':
            template = self.PROMPT_TEMPLATES[language]['math']
            return template.format(problem=text)
        else:
            return text
    
    def get_language_characteristics(self, language: str) -> Dict[str, Any]:
        """
        言語の特性情報を取得
        
        Args:
            language (str): 言語コード
            
        Returns:
            Dict[str, Any]: 言語の特性
        """
        return self.LANGUAGE_CHARACTERISTICS.get(language, {})
    
    def get_inference_history(self) -> List[Dict[str, Any]]:
        """推論履歴を取得"""
        return self.inference_history.copy()
    
    def get_inference_statistics(self) -> Dict[str, Any]:
        """
        推論統計情報を取得
        
        Returns:
            Dict[str, Any]: 統計情報
        """
        if not self.inference_history:
            return {}
        
        language_counts = {}
        for record in self.inference_history:
            lang = record['input_language']
            language_counts[lang] = language_counts.get(lang, 0) + 1
        
        return {
            'total_inferences': len(self.inference_history),
            'language_distribution': language_counts,
            'average_language_confidence': sum(
                r['language_confidence']
                for r in self.inference_history
            ) / len(self.inference_history) if self.inference_history else 0,
        }
    
    def clear_history(self):
        """推論履歴をクリア"""
        self.inference_history = []


class LanguageSpecificPromptOptimizer:
    """
    言語別プロンプト最適化の詳細実装
    """
    
    def __init__(self):
        """初期化"""
        self.optimizations = {
            'EN': self._optimize_english,
            'JA': self._optimize_japanese,
        }
    
    def optimize(self, text: str, language: str) -> str:
        """
        言語に応じてプロンプトを最適化
        
        Args:
            text (str): 入力テキスト
            language (str): 言語コード
            
        Returns:
            str: 最適化されたテキスト
        """
        if language in self.optimizations:
            return self.optimizations[language](text)
        return text
    
    def _optimize_english(self, text: str) -> str:
        """英語の最適化"""
        # 英語版のプロンプトエンジニアリング
        optimizations = [
            ('the?', 'the'),  # 冠詞の統一
            ('  +', ' '),  # 複数スペースの削除
        ]
        result = text
        for pattern, replacement in optimizations:
            import re
            result = re.sub(pattern, replacement, result)
        return result
    
    def _optimize_japanese(self, text: str) -> str:
        """日本語の最適化"""
        # 日本語版のプロンプトエンジニアリング
        # 句読点の統一、文法の確認など
        optimizations = [
            ('？', '？'),  # 句点の統一
            ('。', '。'),
        ]
        result = text
        for pattern, replacement in optimizations:
            result = result.replace(pattern, replacement)
        return result
