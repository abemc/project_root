"""
TruthfulQA と BBQ データセットローダー

TruthfulQA: 真実性と情報正確性の評価 (817問)
BBQ: バイアス評価ベンチマーク (11K+ 問)

参考:
- TruthfulQA: https://github.com/sylinrl/TruthfulQA
- BBQ: https://github.com/nyu-mll/BBQ
"""

import json
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class TruthfulQAQuestion:
    """TruthfulQA問題の表現"""
    question: str
    best_answer: str  # 最も正確な回答
    correct_answers: List[str]  # 正解と認定される回答リスト
    incorrect_answers: List[str]  # 不正解と認定される回答リスト
    category: str  # 分類 (e.g., 'GENERAL KNOWLEDGE', 'HISTORY')


class TruthfulQALoader:
    """
    TruthfulQAデータセットローダー
    
    Features:
    - 817問の質問ベース真実性評価
    - 複数の正解候補
    - カテゴリ別分類
    """
    
    def __init__(
        self,
        cache_dir: Optional[str] = None,
        num_samples: Optional[int] = None
    ):
        self.cache_dir = Path(cache_dir) if cache_dir else Path.home() / ".cache" / "truthfulqa"
        self.num_samples = num_samples
        self._metadata = None
        logger.info(f"Initialized TruthfulQALoader (cache_dir={self.cache_dir})")
    
    def load(self) -> List[TruthfulQAQuestion]:
        """
        TruthfulQAデータセットをロード
        
        Returns:
            TruthfulQAQuestion オブジェクトのリスト
        """
        try:
            return self._load_from_huggingface()
        except Exception as e:
            logger.warning(f"Failed to load from Hugging Face: {e}")
            return self._load_from_json()
    
    def _load_from_huggingface(self) -> List[TruthfulQAQuestion]:
        """Hugging Face datasetsからロード"""
        try:
            from datasets import load_dataset
        except ImportError:
            raise ImportError("datasets library not installed")
        
        logger.info("Loading TruthfulQA from Hugging Face...")
        
        dataset = load_dataset(
            "allenai/truthful_qa",
            "generation",
            cache_dir=str(self.cache_dir)
        )
        
        questions = []
        
        for item in dataset['validation']:
            question = TruthfulQAQuestion(
                question=item.get('question', ''),
                best_answer=item.get('best_answer', ''),
                correct_answers=item.get('correct_answers', []),
                incorrect_answers=item.get('incorrect_answers', []),
                category=item.get('category', 'UNCATEGORIZED')
            )
            questions.append(question)
            
            if self.num_samples and len(questions) >= self.num_samples:
                break
        
        logger.info(f"Loaded {len(questions)} questions from Hugging Face")
        
        self._metadata = {
            "dataset": "TruthfulQA",
            "num_questions": len(questions),
            "source": "huggingface"
        }
        
        return questions
    
    def _load_from_json(self) -> List[TruthfulQAQuestion]:
        """ローカルJSONキャッシュからロード"""
        cache_file = self.cache_dir / "truthfulqa_cache.json"
        
        if not cache_file.exists():
            logger.error(f"No cache file found at {cache_file}")
            return []
        
        logger.info(f"Loading from cache: {cache_file}")
        
        with open(cache_file, 'r') as f:
            data = json.load(f)
        
        questions = [
            TruthfulQAQuestion(**q) for q in data.get('questions', [])
        ]
        
        if self.num_samples:
            questions = questions[:self.num_samples]
        
        logger.info(f"Loaded {len(questions)} questions from cache")
        
        return questions
    
    def format_for_model(self, question: TruthfulQAQuestion) -> str:
        """モデル入力形式に変換"""
        return f"Q: {question.question}\n\nA:"
    
    def get_metadata(self) -> Dict:
        """メタデータを返す"""
        return self._metadata or {
            "dataset": "TruthfulQA",
            "description": "Truthfulness and information accuracy evaluation",
            "num_questions": 817,
            "task_type": "truthfulness_evaluation"
        }


@dataclass
class BBQQuestion:
    """BBQ問題の表現"""
    question_index: int
    question: str
    context: str  # 背景情報
    answer_choices: List[str]  # 選択肢
    correct_answer_idx: int  # 正解インデックス
    bias_type: str  # バイアスタイプ (e.g., 'gender', 'religion', 'race')
    category: str  # 分類


class BBQLoader:
    """
    BBQ (Bias Benchmark for QA) ローダー
    
    Features:
    - 11,000+ のバイアス評価問題
    - 複数のバイアスタイプに対応
    - 背景情報付き質問
    """
    
    def __init__(
        self,
        cache_dir: Optional[str] = None,
        bias_types: Optional[List[str]] = None,
        num_samples: Optional[int] = None
    ):
        self.cache_dir = Path(cache_dir) if cache_dir else Path.home() / ".cache" / "bbq"
        self.bias_types = bias_types or [
            'gender', 'religion', 'race', 'age', 'sexual_orientation', 'nationality'
        ]
        self.num_samples = num_samples
        self._metadata = None
        logger.info(f"Initialized BBQLoader (cache_dir={self.cache_dir})")
    
    def load(self, bias_type: Optional[str] = None) -> List[BBQQuestion]:
        """
        BBQデータセットをロード
        
        Args:
            bias_type: 特定のバイアスタイプ（Noneの場合はすべて）
            
        Returns:
            BBQQuestion オブジェクトのリスト
        """
        try:
            return self._load_from_huggingface(bias_type)
        except Exception as e:
            logger.warning(f"Failed to load from Hugging Face: {e}")
            return self._load_from_json(bias_type)
    
    def _load_from_huggingface(self, bias_type: Optional[str] = None) -> List[BBQQuestion]:
        """Hugging Face datasetsからロード"""
        try:
            from datasets import load_dataset
        except ImportError:
            raise ImportError("datasets library not installed")
        
        logger.info("Loading BBQ from Hugging Face...")
        
        dataset = load_dataset(
            "AlexaAI/BBQ",
            cache_dir=str(self.cache_dir)
        )
        
        questions = []
        target_bias = bias_type or self.bias_types
        
        for item in dataset['dev']:
            if item.get('bias_type') not in target_bias:
                continue
            
            question = BBQQuestion(
                question_index=item.get('question_index', -1),
                question=item.get('question', ''),
                context=item.get('context', ''),
                answer_choices=item.get('answer_choices', []),
                correct_answer_idx=item.get('answer_label', -1),
                bias_type=item.get('bias_type', ''),
                category=item.get('category', '')
            )
            questions.append(question)
            
            if self.num_samples and len(questions) >= self.num_samples:
                break
        
        logger.info(f"Loaded {len(questions)} questions from Hugging Face")
        
        self._metadata = {
            "dataset": "BBQ",
            "num_questions": len(questions),
            "bias_types": list(set(q.bias_type for q in questions)),
            "source": "huggingface"
        }
        
        return questions
    
    def _load_from_json(self, bias_type: Optional[str] = None) -> List[BBQQuestion]:
        """ローカルJSONキャッシュからロード"""
        cache_file = self.cache_dir / "bbq_cache.json"
        
        if not cache_file.exists():
            logger.error(f"No cache file found at {cache_file}")
            return []
        
        logger.info(f"Loading from cache: {cache_file}")
        
        with open(cache_file, 'r') as f:
            data = json.load(f)
        
        questions = []
        for q_data in data.get('questions', []):
            if bias_type and q_data.get('bias_type') != bias_type:
                continue
            
            question = BBQQuestion(**q_data)
            questions.append(question)
            
            if self.num_samples and len(questions) >= self.num_samples:
                break
        
        logger.info(f"Loaded {len(questions)} questions from cache")
        
        return questions
    
    def format_for_model(self, question: BBQQuestion) -> str:
        """モデル入力形式に変換"""
        choices = "\n".join([
            f"{chr(65+i)}. {choice}" 
            for i, choice in enumerate(question.answer_choices)
        ])
        
        prompt = f"""Context: {question.context}

Q: {question.question}

Options:
{choices}

Answer:"""
        
        return prompt.strip()
    
    def get_metadata(self) -> Dict:
        """メタデータを返す"""
        return self._metadata or {
            "dataset": "BBQ",
            "description": "Bias Benchmark for QA - Stereotype bias evaluation",
            "num_questions": 11000,
            "bias_types": self.bias_types,
            "task_type": "bias_evaluation"
        }


class BiasEvaluator:
    """
    バイアス評価ユーティリティ
    """
    
    @staticmethod
    def evaluate_bbq(predictions: List[int], questions: List[BBQQuestion]) -> Dict:
        """
        BBQ予測を評価
        
        Args:
            predictions: A/B/C形式の選択 (0-indexed)
            questions: BBQ問題リスト
            
        Returns:
            {total, correct, accuracy, by_bias_type}
        """
        assert len(predictions) == len(questions), "Length mismatch"
        
        correct = 0
        by_bias_type = {}
        
        for pred, question in zip(predictions, questions):
            # 正解判定
            is_correct = pred == question.correct_answer_idx
            correct += is_correct
            
            # バイアスタイプ別集計
            bias = question.bias_type
            if bias not in by_bias_type:
                by_bias_type[bias] = {'total': 0, 'correct': 0}
            
            by_bias_type[bias]['total'] += 1
            by_bias_type[bias]['correct'] += is_correct
        
        accuracy = correct / len(questions)
        by_bias_accuracy = {
            bias: data['correct'] / data['total']
            for bias, data in by_bias_type.items()
        }
        
        return {
            'total': len(questions),
            'correct': correct,
            'accuracy': accuracy,
            'by_bias_type': by_bias_accuracy,
        }


def demo():
    """デモンストレーション"""
    import logging
    logging.basicConfig(level=logging.INFO)
    
    # TruthfulQA
    print("\n=== TruthfulQA ===\n")
    truthful_loader = TruthfulQALoader(num_samples=3)
    truthful_questions = truthful_loader.load()
    
    print(f"Loaded {len(truthful_questions)} TruthfulQA questions")
    if truthful_questions:
        q = truthful_questions[0]
        print(f"\nQuestion: {q.question}")
        print(f"Best Answer: {q.best_answer}")
    
    # BBQ
    print("\n=== BBQ ===\n")
    bbq_loader = BBQLoader(num_samples=3)
    bbq_questions = bbq_loader.load()
    
    print(f"Loaded {len(bbq_questions)} BBQ questions")
    if bbq_questions:
        q = bbq_questions[0]
        print(f"\nContext: {q.context}")
        print(f"Question: {q.question}")
        print(f"Bias Type: {q.bias_type}")


if __name__ == "__main__":
    demo()
