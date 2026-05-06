"""
HumanEvalデータセットローダー

HumanEval は、
プログラミング能力を測定するための
164個のPython関数補完問題からなる
コード生成ベンチマークです。

参考: https://github.com/openai/human-eval
"""

import json
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass
import logging
import re
import subprocess
import tempfile

logger = logging.getLogger(__name__)


@dataclass
class HumanEvalProblem:
    """HumanEval問題の表現"""
    task_id: str  # e.g., "HumanEval/0"
    prompt: str  # 関数のシグネチャとdocstring
    canonical_solution: str  # 正解となるコード
    test: str  # テストケース
    entry_point: str  # 関数名


class HumanEvalLoader:
    """
    HumanEvalデータセットローダー
    
    Features:
    - 164個のPython関数補完問題
    - テストケース付き
    - コード実行検証対応
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
        self.cache_dir = Path(cache_dir) if cache_dir else Path.home() / ".cache" / "humaneval"
        self.offline = offline
        self.num_samples = num_samples
        self.dataset = None
        self._metadata = None
        
        logger.info(f"Initialized HumanEvalLoader (cache_dir={self.cache_dir}, offline={offline})")
    
    def load(self) -> List[HumanEvalProblem]:
        """
        HumanEvalデータセットをロード
        
        Returns:
            HumanEvalProblem オブジェクトのリスト
        """
        try:
            return self._load_from_huggingface()
        except Exception as e:
            logger.warning(f"Failed to load from Hugging Face: {e}")
            return self._load_from_json()
    
    def _load_from_huggingface(self) -> List[HumanEvalProblem]:
        """
        Hugging Face datasetsからロード
        
        Returns:
            HumanEvalProblem リスト
        """
        try:
            from datasets import load_dataset
        except ImportError:
            raise ImportError("datasets library not installed")
        
        logger.info("Loading HumanEval from Hugging Face...")
        
        try:
            dataset = load_dataset(
                "openai_humaneval",
                cache_dir=str(self.cache_dir),
                trust_remote_code=True
            )
        except Exception:
            # フォールバック
            dataset = load_dataset(
                "OctoAI/humaneval",
                cache_dir=str(self.cache_dir)
            )
        
        problems = []
        
        for item in dataset['test']:
            problem = HumanEvalProblem(
                task_id=item.get('task_id', ''),
                prompt=item.get('prompt', ''),
                canonical_solution=item.get('canonical_solution', ''),
                test=item.get('test', ''),
                entry_point=item.get('entry_point', '')
            )
            problems.append(problem)
            
            # 制限されたサンプル数
            if self.num_samples and len(problems) >= self.num_samples:
                break
        
        logger.info(f"Loaded {len(problems)} problems from Hugging Face")
        
        self._metadata = {
            "dataset": "HumanEval",
            "num_problems": len(problems),
            "source": "huggingface"
        }
        
        return problems
    
    def _load_from_json(self) -> List[HumanEvalProblem]:
        """
        ローカルJSONキャッシュからロード
        
        Returns:
            HumanEvalProblem リスト
        """
        cache_file = self.cache_dir / "humaneval.jsonl"
        
        if not cache_file.exists():
            logger.error(f"No cache file found at {cache_file}")
            return []
        
        logger.info(f"Loading from cache: {cache_file}")
        
        problems = []
        with open(cache_file, 'r') as f:
            for line in f:
                if line.strip():
                    item = json.loads(line)
                    problem = HumanEvalProblem(
                        task_id=item.get('task_id', ''),
                        prompt=item.get('prompt', ''),
                        canonical_solution=item.get('canonical_solution', ''),
                        test=item.get('test', ''),
                        entry_point=item.get('entry_point', '')
                    )
                    problems.append(problem)
                    
                    if self.num_samples and len(problems) >= self.num_samples:
                        break
        
        logger.info(f"Loaded {len(problems)} problems from cache")
        
        return problems
    
    def prepare_batch(self, problems: List[HumanEvalProblem]) -> List[Dict]:
        """
        バッチ処理用に整形
        
        Args:
            problems: 問題リスト
            
        Returns:
            {task_id, prompt, entry_point} 辞書のリスト
        """
        batch = []
        for p in problems:
            batch.append({
                "task_id": p.task_id,
                "prompt": p.prompt,
                "entry_point": p.entry_point,
            })
        return batch
    
    def format_for_model(self, problem: HumanEvalProblem) -> str:
        """
        モデル入力形式に変換
        
        Args:
            problem: HumanEval問題
            
        Returns:
            プロンプトテキスト
        """
        return problem.prompt.strip()
    
    def get_metadata(self) -> Dict:
        """メタデータを返す"""
        return self._metadata or {
            "dataset": "HumanEval",
            "description": "Human-level Python code generation benchmark",
            "num_problems": 164,
            "task_type": "code_generation"
        }


class HumanEvalEvaluator:
    """
    HumanEval評価ユーティリティ
    
    Note: コード実行による検証が必要
    セキュリティのため、サンドボックス実行が推奨
    """
    
    def __init__(self, loader: HumanEvalLoader):
        self.loader = loader
    
    def evaluate_code(self, code: str, problem: HumanEvalProblem, timeout: int = 5) -> bool:
        """
        生成されたコードをテスト
        
        Args:
            code: モデルが生成したコード
            problem: HumanEval問題
            timeout: 実行タイムアウト（秒）
            
        Returns:
            テスト成功か否か
        """
        # テストコードを組み立て
        test_code = self._build_test_code(code, problem)
        
        try:
            # 一時ファイルで実行
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(test_code)
                temp_file = f.name
            
            # Pythonコードを実行
            result = subprocess.run(
                ['python', temp_file],
                capture_output=True,
                timeout=timeout,
                text=True
            )
            
            # テスト成功判定
            success = result.returncode == 0
            
            if not success and result.stderr:
                logger.debug(f"Test failed for {problem.task_id}: {result.stderr}")
            
            return success
            
        except subprocess.TimeoutExpired:
            logger.debug(f"Timeout for {problem.task_id}")
            return False
        except Exception as e:
            logger.debug(f"Error evaluating {problem.task_id}: {e}")
            return False
    
    def evaluate(self, predictions: List[str], problems: List[HumanEvalProblem]) -> Dict:
        """
        複数の予測を評価
        
        Args:
            predictions: モデルの出力（コード形式）
            problems: 問題リスト
            
        Returns:
            {total, passed, pass_rate}
        """
        assert len(predictions) == len(problems), "Length mismatch"
        
        passed = 0
        details = []
        
        for pred_code, problem in zip(predictions, problems):
            success = self.evaluate_code(pred_code, problem)
            passed += success
            
            if len(details) < 10:  # 最初の10件のみ詳細記録
                details.append({
                    'task_id': problem.task_id,
                    'passed': success
                })
        
        pass_rate = passed / len(problems)
        
        return {
            'total': len(problems),
            'passed': passed,
            'pass_rate': pass_rate,
            'details': details
        }
    
    @staticmethod
    def _build_test_code(code: str, problem: HumanEvalProblem) -> str:
        """
        テストコードを構築
        
        Args:
            code: 生成されたコード
            problem: 問題
            
        Returns:
            実行可能なテストコード
        """
        test_code = f"""
import sys
import traceback

def check(candidate):
{self._indent(problem.test, 4)}

try:
{self._indent(code, 4)}
    check({problem.entry_point})
    print("OK")
except Exception as e:
    traceback.print_exc()
    sys.exit(1)
"""
        return test_code
    
    @staticmethod
    def _indent(text: str, spaces: int) -> str:
        """テキストをインデント"""
        indent = ' ' * spaces
        return '\n'.join(indent + line if line.strip() else line for line in text.split('\n'))


def demo():
    """デモンストレーション"""
    import logging
    logging.basicConfig(level=logging.INFO)
    
    # ローダー作成
    loader = HumanEvalLoader(num_samples=3)  # デバッグ用に3問だけロード
    
    # ロード
    problems = loader.load()
    
    print(f"\n✓ Loaded {len(problems)} problems\n")
    
    # 最初の問題を表示
    if problems:
        p = problems[0]
        print(f"Task ID: {p.task_id}")
        print(f"Entry Point: {p.entry_point}")
        print(f"Prompt:\n{p.prompt}\n")
        print(f"Canonical Solution:\n{p.canonical_solution}\n")


if __name__ == "__main__":
    demo()
