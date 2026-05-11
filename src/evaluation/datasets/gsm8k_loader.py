"""
GSM8Kデータセットローダー

GSM8K（Grade School Math 8K）は、
小学校レベルの数学問題8,500問からなる
算数的推論能力の評価ベンチマークです。

参考: https://github.com/openai/grade-school-math
"""

import json
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass
import logging
import re

try:
    import pyarrow.parquet as pq
    ARROW_AVAILABLE = True
except ImportError:
    ARROW_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class GSM8KProblem:
    """GSM8K問題の表現"""
    problem: str
    solution: str  # ステップバイステップの解法
    answer: str  # 最終的な数値答え
    problem_id: str  # 問題ID


class GSM8KLoader:
    """
    GSM8Kデータセットローダー
    
    Features:
    - 8,500問の算数問題
    - ステップバイステップの解答プロセス
    - 数値答えの抽出
    - バッチ処理対応
    """
    
    def __init__(
        self,
        cache_dir: Optional[str] = None,
        offline: bool = False,
        num_samples: Optional[int] = None
    ):
        """
        初期化
        
        Args:
            cache_dir: キャッシュディレクトリ
            offline: オフラインモード
            num_samples: ロードするサンプル数（デバッグ用）
        """
        self.cache_dir = Path(cache_dir) if cache_dir else Path.home() / ".cache" / "gsm8k"
        self.offline = offline
        self.num_samples = num_samples
        self.dataset = None
        self._metadata = None
        
        logger.info(f"Initialized GSM8KLoader (cache_dir={self.cache_dir}, offline={offline})")
    
    def load(self, split: str = "test") -> List[GSM8KProblem]:
        """
        GSM8Kデータセットをロード
        
        Args:
            split: 'train', 'test'のいずれか
            
        Returns:
            GSM8KProblem オブジェクトのリスト
        """
        try:
            return self._load_from_huggingface(split)
        except Exception as e:
            logger.warning(f"Failed to load from Hugging Face: {e}")
            try:
                return self._load_from_arrow(split)
            except Exception as e2:
                logger.warning(f"Failed to load from Arrow: {e2}")
                return self._load_from_json(split)
    
    def _load_from_huggingface(self, split: str) -> List[GSM8KProblem]:
        """
        Hugging Face datasetsからロード
        
        Args:
            split: データセット分割
            
        Returns:
            GSM8KProblem リスト
        """
        try:
            from datasets import load_dataset
        except ImportError:
            raise ImportError("datasets library not installed")
        
        logger.info(f"Loading GSM8K ({split} split) from Hugging Face...")
        
        try:
            dataset = load_dataset(
                "openai/grade_school_math",
                split=split,
                cache_dir=str(self.cache_dir),
                trust_remote_code=True
            )
        except Exception:
            # フォールバック: データセット名の変更対応
            dataset = load_dataset(
                "gsm8k",
                "main",
                split=split,
                cache_dir=str(self.cache_dir)
            )
        
        problems = []
        
        for idx, item in enumerate(dataset):
            # GSM8K形式の解析
            problem = item.get('question', '')
            solution = item.get('answer', '')  # "... 最後の答え: X"形式
            answer = self._extract_answer(solution)
            
            problem_obj = GSM8KProblem(
                problem=problem,
                solution=solution,
                answer=answer,
                problem_id=f"gsm8k_{split}_{idx}"
            )
            
            problems.append(problem_obj)
            
            # 制限されたサンプル数
            if self.num_samples and len(problems) >= self.num_samples:
                break
        
        logger.info(f"Loaded {len(problems)} problems from Hugging Face")
        
        self._metadata = {
            "dataset": "GSM8K",
            "split": split,
            "num_problems": len(problems),
            "source": "huggingface"
        }
        
        return problems
    
    def _load_from_arrow(self, split: str) -> List[GSM8KProblem]:
        """
        PyArrowキャッシュからロード
        
        Args:
            split: 'train', 'test'のいずれか
            
        Returns:
            GSM8KProblem リスト
        """
        if not ARROW_AVAILABLE:
            raise ImportError("pyarrow not available")
        
        # Arrow ファイルパスを構築
        arrow_path = self.cache_dir / "gsm8k" / "main" / "0.0.0"
        if not arrow_path.exists():
            raise FileNotFoundError(f"Arrow cache not found at {arrow_path}")
        
        # .arrowファイルを検索
        arrow_files = list(arrow_path.glob(f"*/gsm8k-{split}.arrow"))
        if not arrow_files:
            raise FileNotFoundError(f"No Arrow file for split '{split}'")
        
        arrow_file = arrow_files[0]
        logger.info(f"Loading GSM8K ({split}) from Arrow: {arrow_file}")
        
        try:
            import pyarrow as pa
            # Arrowテーブルを読み込み
            table = pa.memory_map(str(arrow_file), 'r').read()
            
            problems = []
            for idx in range(len(table)):
                row = table.slice(idx, 1)
                
                # テーブルのカラムを取得
                question = row['question'][0].as_py() if 'question' in row.column_names else ''
                answer_full = row['answer'][0].as_py() if 'answer' in row.column_names else ''
                answer = self._extract_answer(answer_full)
                
                problem_obj = GSM8KProblem(
                    problem=question,
                    solution=answer_full,
                    answer=answer,
                    problem_id=f"gsm8k_{split}_{idx}"
                )
                problems.append(problem_obj)
                
                if self.num_samples and idx >= self.num_samples:
                    break
            
            self._metadata = {
                "dataset": "GSM8K",
                "split": split,
                "num_problems": len(problems),
                "source": "arrow"
            }
            
            logger.info(f"Loaded {len(problems)} problems from Arrow")
            return problems
        
        except Exception as e:
            logger.error(f"Failed to parse Arrow file: {e}")
            raise
    
    def _load_from_json(self, split: str) -> List[GSM8KProblem]:
        """
        ローカルJSONキャッシュからロード
        
        Args:
            split: データセット分割
            
        Returns:
            GSM8KProblem リスト
        """
        # JSON形式でのキャッシュ
        cache_file = self.cache_dir / f"gsm8k_{split}.json"
        
        if not cache_file.exists():
            logger.error(f"No cache file found at {cache_file}")
            return []
        
        logger.info(f"Loading from cache: {cache_file}")
        
        with open(cache_file, 'r') as f:
            data = json.load(f)
        
        problems = []
        for item in data:
            problem = GSM8KProblem(
                problem=item['problem'],
                solution=item['solution'],
                answer=item['answer'],
                problem_id=item.get('problem_id', '')
            )
            problems.append(problem)
            
            if self.num_samples and len(problems) >= self.num_samples:
                break
        
        logger.info(f"Loaded {len(problems)} problems from cache")
        
        return problems
    
    def prepare_batch(self, problems: List[GSM8KProblem]) -> List[Dict]:
        """
        バッチ処理用に整形
        
        Args:
            problems: 問題リスト
            
        Returns:
            {problem, answer} 辞書のリスト
        """
        batch = []
        for p in problems:
            batch.append({
                "problem": p.problem,
                "answer": p.answer,
                "problem_id": p.problem_id,
            })
        return batch
    
    def format_for_model(self, problem: GSM8KProblem) -> str:
        """
        モデル入力形式に変換
        
        Args:
            problem: GSM8K問題
            
        Returns:
            プロンプトテキスト
        """
        prompt = f"{problem.problem}\n\nAnswer:"
        return prompt.strip()
    
    def format_for_cot(self, problem: GSM8KProblem) -> str:
        """
        Chain-of-Thought形式に変換
        
        Args:
            problem: GSM8K問題
            
        Returns:
            CoT形式プロンプト
        """
        prompt = f"""{problem.problem}

Let me solve this step by step:

"""
        return prompt.strip()
    
    def extract_answer(self, text: str) -> str:
        """
        テキストから数値答えを抽出
        
        Args:
            text: モデル出力
            
        Returns:
            抽出された数値
        """
        return self._extract_answer(text)
    
    @staticmethod
    def _extract_answer(text: str) -> str:
        """
        テキストから最終的な答えを抽出
        
        GSM8Kの解答形式: "... 最後の答え: X"
        モデル出力から数値を抽出
        
        Args:
            text: 解答テキスト
            
        Returns:
            数値答え
        """
        # パターン1: "#### X" 形式（GSM8K標準）
        match = re.search(r'####\s*([\d,\.\-\+\/]+)', text)
        if match:
            return match.group(1).strip()
        
        # パターン2: "Answer: X" 形式
        match = re.search(r'[Aa]nswer[:\s]+([^\n]+)', text)
        if match:
            answer = match.group(1).strip()
            # 最後の数値を抽出
            numbers = re.findall(r'[\d,\.\-\+\/]+', answer)
            if numbers:
                return numbers[-1]
        
        # パターン3: 最後の数値を抽出
        numbers = re.findall(r'[\d,\.\-\+\/]+', text)
        if numbers:
            return numbers[-1]
        
        return ""
    
    def get_metadata(self) -> Dict:
        """メタデータを返す"""
        return self._metadata or {
            "dataset": "GSM8K",
            "description": "Grade School Math - 8K problems",
            "expected_problems": 8500,
            "task_type": "math_reasoning"
        }


class GSM8KEvaluator:
    """
    GSM8K評価ユーティリティ
    
    Note: 数学問題の評価は複雑です。
    完全一致評価を基本としますが、
    異なる形式（分数、小数等）の同値判定もサポート。
    """
    
    def __init__(self, loader: GSM8KLoader):
        self.loader = loader
    
    def evaluate(self, predictions: List[str], problems: List[GSM8KProblem]) -> Dict:
        """
        予測を評価
        
        Args:
            predictions: モデルの出力（テキスト形式）
            problems: 問題リスト
            
        Returns:
            {total, correct, accuracy}
        """
        assert len(predictions) == len(problems), "Length mismatch"
        
        correct = 0
        correct_details = []
        
        for pred_text, problem in zip(predictions, problems):
            # 予測から答えを抽出
            predicted_answer = self.loader.extract_answer(pred_text)
            
            # 正解判定
            is_correct = self._check_answer(predicted_answer, problem.answer)
            correct += is_correct
            
            correct_details.append({
                'problem_id': problem.problem_id,
                'predicted': predicted_answer,
                'correct': problem.answer,
                'match': is_correct
            })
        
        accuracy = correct / len(problems)
        
        return {
            'total': len(problems),
            'correct': correct,
            'accuracy': accuracy,
            'details': correct_details if len(correct_details) <= 10 else None
        }
    
    @staticmethod
    def _check_answer(predicted: str, correct: str) -> bool:
        """
        2つの答えが等しいか判定
        
        Args:
            predicted: 予測答え
            correct: 正解
            
        Returns:
            等しいか否か
        """
        if not predicted or not correct:
            return False
        
        # 厳密な比較
        if predicted == correct:
            return True
        
        # 数値として比較
        try:
            pred_val = float(predicted.replace(',', ''))
            correct_val = float(correct.replace(',', ''))
            return abs(pred_val - correct_val) < 1e-6
        except (ValueError, AttributeError):
            pass
        
        # 簡略形式での比較（"3" vs "3.0"等）
        try:
            pred_num = float(predicted)
            correct_num = float(correct)
            return pred_num == correct_num
        except (ValueError, TypeError):
            pass
        
        return False


def demo():
    """デモンストレーション"""
    import logging
    logging.basicConfig(level=logging.INFO)
    
    # ローダー作成
    loader = GSM8KLoader(num_samples=5)  # デバッグ用に5問だけロード
    
    # テストセットをロード
    problems = loader.load(split='test')
    
    print(f"\n✓ Loaded {len(problems)} problems\n")
    
    # 最初の問題を表示
    if problems:
        p = problems[0]
        print(f"Problem ID: {p.problem_id}")
        print(f"Problem: {p.problem}")
        print(f"Answer: {p.answer}")
        print(f"Solution:\n{p.solution}\n")
        
        # モデル入力形式
        prompt = loader.format_for_model(p)
        print(f"Formatted prompt:\n{prompt}\n")
        
        # CoT形式
        cot_prompt = loader.format_for_cot(p)
        print(f"CoT formatted prompt:\n{cot_prompt}")


if __name__ == "__main__":
    demo()
