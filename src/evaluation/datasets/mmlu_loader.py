"""
MMUデータセットローダー

MMU（Massive Multitask Language Understanding）は、
57個の学科にわたる14,000+の多選択問題を含む
言語理解能力の総合的な評価ベンチマークです。

参考: https://github.com/hendrycks/test
"""

import os
import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import logging

import numpy as np

# Hugging Faceのdatasetsライブラリは、可用性に応じて複数の読込方法をサポート
try:
    from datasets import load_dataset
    HAS_DATASETS = True
except ImportError:
    HAS_DATASETS = False

try:
    import pyarrow.parquet as pq
    ARROW_AVAILABLE = True
except ImportError:
    ARROW_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class MMUQuestion:
    """MMU問題の表現"""
    question: str
    choices: List[str]  # [A, B, C, D]
    answer: str  # 'A', 'B', 'C', 'D'のいずれか
    subject: str  # 学科 (e.g., 'abstract_algebra', 'anatomy')
    grade: str  # 難度 (e.g., 'high_school', 'college')


class MMULoader:
    """
    MMUデータセットローダー
    
    Features:
    - Hugging Face datasetsからの読込
    - ローカルキャッシング対応
    - サブジェクト/グレード別フィルタリング
    - バッチ処理対応
    """
    
    # 利用可能なサブジェクト（一部抜粋）
    SUBJECTS = [
        'abstract_algebra', 'anatomy', 'astronomy', 'auxiliary_creations',
        'biology', 'business_ethics', 'clinical_knowledge', 'college_biology',
        'college_chemistry', 'college_computer_science', 'college_medicine',
        'computer_security', 'conceptual_physics', 'econometrics', 'economics',
        'education', 'electrical_engineering', 'elementary_mathematics',
        'formal_logic', 'global_facts', 'high_school_biology',
        'high_school_chemistry', 'high_school_computer_science',
        'high_school_economics', 'high_school_european_history',
        'high_school_geography', 'high_school_government_and_politics',
        'high_school_macroeconomics', 'high_school_mathematics',
        'high_school_microeconomics', 'high_school_physics',
        'high_school_psychology', 'high_school_statistics',
        'high_school_us_history', 'high_school_world_history',
        'human_aging', 'human_sexuality', 'international_law',
        'jurisprudence', 'logical_fallacies', 'machine_learning',
        'management', 'marketing', 'medical_genetics', 'medicine',
        'middle_school_biology', 'middle_school_chemistry',
        'middle_school_earth_science', 'middle_school_mathematics',
        'middle_school_physics', 'middle_school_psychology',
        'moral_disputes', 'moral_scenarios', 'nutrition', 'philosophy',
        'prehistory', 'professional_accounting', 'professional_law',
        'professional_medicine', 'professional_psychology', 'public_relations',
        'security_studies', 'sociology', 'us_foreign_policy',
        'virology', 'world_religions'
    ]
    
    GRADES = ['high_school', 'college']
    
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
        self.cache_dir = Path(cache_dir) if cache_dir else Path.home() / ".cache" / "mmlu"
        self.offline = offline
        self.num_samples = num_samples
        self.dataset = None
        self._metadata = None
        
        logger.info(f"Initialized MMULoader (cache_dir={self.cache_dir}, offline={offline})")
    
    def load(self, subjects: Optional[List[str]] = None, grade: Optional[str] = None) -> List[MMUQuestion]:
        """
        MMUデータセットをロード
        
        Args:
            subjects: 対象サブジェクト（Noneの場合はすべて）
            grade: 対象グレード（Noneの場合はすべて）
            
        Returns:
            MMUQuestion オブジェクトのリスト
        """
        if not HAS_DATASETS:
            try:
                return self._load_from_arrow(subjects, grade)
            except Exception as e:
                logger.warning(f"Failed to load from Arrow: {e}")
                return self._load_from_json(subjects, grade)
        
        try:
            return self._load_from_huggingface(subjects, grade)
        except Exception as e:
            logger.warning(f"Failed to load from Hugging Face: {e}")
            try:
                return self._load_from_arrow(subjects, grade)
            except Exception as e2:
                logger.warning(f"Failed to load from Arrow: {e2}")
                return self._load_from_json(subjects, grade)
    
    def _load_from_huggingface(
        self,
        subjects: Optional[List[str]] = None,
        grade: Optional[str] = None
    ) -> List[MMUQuestion]:
        """
        Hugging Face datasetsからロード
        
        Args:
            subjects: 対象サブジェクト
            grade: 対象グレード
            
        Returns:
            MMUQuestion リスト
        """
        # サブジェクト決定
        target_subjects = subjects if subjects else self.SUBJECTS
        
        all_questions = []
        
        for subject in target_subjects:
            try:
                logger.info(f"Loading subject: {subject}")
                
                # 問題セットをロード
                dataset = load_dataset(
                    "cais/mmlu",
                    subject,
                    cache_dir=str(self.cache_dir),
                    trust_remote_code=True,
                    split="test"
                )
                
                for item in dataset:
                    question = MMUQuestion(
                        question=item['question'],
                        choices=item['choices'],
                        answer=item['answer'],  # 0-3の数値 → A-Dに変換
                        subject=subject,
                        grade=self._infer_grade(subject)
                    )
                    
                    # グレードフィルタ
                    if grade and question.grade != grade:
                        continue
                    
                    all_questions.append(question)
                    
                    # 制限されたサンプル数
                    if self.num_samples and len(all_questions) >= self.num_samples:
                        return all_questions
                
            except Exception as e:
                logger.warning(f"Failed to load subject {subject}: {e}")
                continue
        
        logger.info(f"Loaded {len(all_questions)} questions")
        self._metadata = {
            "dataset": "MMLU",
            "num_questions": len(all_questions),
            "subjects_loaded": list(set(q.subject for q in all_questions)),
            "source": "huggingface"
        }
        
        return all_questions
    
    def _load_from_arrow(
        self,
        subjects: Optional[List[str]] = None,
        grade: Optional[str] = None
    ) -> List[MMUQuestion]:
        """
        PyArrowキャッシュからロード
        
        Args:
            subjects: 対象サブジェクト
            grade: 対象グレード
            
        Returns:
            MMUQuestion リスト
        """
        if not ARROW_AVAILABLE:
            raise ImportError("pyarrow not available")
        
        import pyarrow as pa
        
        # サブジェクト決定
        target_subjects = subjects if subjects else self.SUBJECTS
        
        all_questions = []
        
        for subject in target_subjects:
            try:
                # Arrow キャッシュパスを構築
                arrow_path = self.cache_dir / f"cais___mmlu" / subject / "0.0.0"
                if not arrow_path.exists():
                    logger.debug(f"Arrow cache not found for {subject}")
                    continue
                
                # .arrowファイルを検索
                arrow_files = list(arrow_path.glob("*/mmlu-test.arrow"))
                if not arrow_files:
                    arrow_files = list(arrow_path.glob("*/mmlu-validation.arrow"))
                
                if not arrow_files:
                    logger.debug(f"No Arrow file for subject '{subject}'")
                    continue
                
                arrow_file = arrow_files[0]
                logger.info(f"Loading {subject} from Arrow: {arrow_file}")
                
                # Arrowテーブルを読み込み
                table = pa.memory_map(str(arrow_file), 'r').read()
                
                for idx in range(len(table)):
                    row = table.slice(idx, 1)
                    
                    # テーブルのカラムを取得
                    question_text = row['question'][0].as_py() if 'question' in row.column_names else ''
                    choices_list = row['choices'][0].as_py() if 'choices' in row.column_names else []
                    answer_idx = row['answer'][0].as_py() if 'answer' in row.column_names else 0
                    
                    # 選択肢をA, B, C, D に変換
                    choices = list(choices_list) if isinstance(choices_list, (list, tuple)) else []
                    answer_letter = chr(65 + int(answer_idx)) if isinstance(answer_idx, int) else 'A'
                    
                    question = MMUQuestion(
                        question=question_text,
                        choices=choices,
                        answer=answer_letter,
                        subject=subject,
                        grade=grade or 'unknown'
                    )
                    
                    if grade and question.grade != grade:
                        continue
                    
                    all_questions.append(question)
                    
                    if self.num_samples and len(all_questions) >= self.num_samples:
                        return all_questions
                
            except Exception as e:
                logger.debug(f"Failed to load subject {subject} from Arrow: {e}")
                continue
        
        logger.info(f"Loaded {len(all_questions)} questions from Arrow")
        self._metadata = {
            "dataset": "MMLU",
            "num_questions": len(all_questions),
            "subjects_loaded": list(set(q.subject for q in all_questions)),
            "source": "arrow"
        }
        
        return all_questions
    
    def _load_from_json(
        self,
        subjects: Optional[List[str]] = None,
        grade: Optional[str] = None
    ) -> List[MMUQuestion]:
        """
        ローカルJSONキャッシュからロード（フォールバック）
        
        Args:
            subjects: 対象サブジェクト
            grade: 対象グレード
            
        Returns:
            MMUQuestion リスト
        """
        logger.warning("Falling back to JSON cache mode")
        cache_file = self.cache_dir / "mmlu_cache.json"
        
        if not cache_file.exists():
            logger.error("No cache file found. Please run with internet connection first.")
            return []
        
        with open(cache_file, 'r') as f:
            data = json.load(f)
        
        all_questions = [
            MMUQuestion(**q) for q in data.get('questions', [])
        ]
        
        # フィルタ
        if subjects:
            all_questions = [q for q in all_questions if q.subject in subjects]
        if grade:
            all_questions = [q for q in all_questions if q.grade == grade]
        
        logger.info(f"Loaded {len(all_questions)} questions from cache")
        return all_questions
    
    def prepare_batch(self, questions: List[MMUQuestion]) -> List[Dict]:
        """
        バッチ処理用に整形
        
        Args:
            questions: 問題リスト
            
        Returns:
            {question, choices, answer} 辞書のリスト
        """
        batch = []
        for q in questions:
            batch.append({
                "question": q.question,
                "choices": q.choices,
                "answer": q.answer,
                "subject": q.subject,
            })
        return batch
    
    def format_for_model(self, question: MMUQuestion) -> Tuple[str, List[str]]:
        """
        モデル入力形式に変換
        
        Args:
            question: MMU問題
            
        Returns:
            (質問テキスト, 選択肢)のタプル
        """
        choices_str = "\n".join([
            f"{chr(65+i)}. {choice}" 
            for i, choice in enumerate(question.choices)
        ])
        
        prompt = f"""
{question.question}

{choices_str}

Answer:"""
        
        return prompt.strip(), question.choices
    
    def get_metadata(self) -> Dict:
        """メタデータを返す"""
        return self._metadata or {
            "dataset": "MMLU",
            "description": "Massive Multitask Language Understanding",
            "num_subjects": len(self.SUBJECTS),
            "expected_questions": 14000,
        }
    
    @staticmethod
    def _infer_grade(subject: str) -> str:
        """
        サブジェクト名からグレードを推測
        
        Args:
            subject: サブジェクト名
            
        Returns:
            グレード ('high_school' or 'college')
        """
        if 'high_school' in subject or 'middle_school' in subject:
            return 'high_school'
        elif 'college' in subject:
            return 'college'
        else:
            return 'college'  # デフォルト


class MMUEvaluator:
    """
    MMLU評価ユーティリティ
    """
    
    def __init__(self, loader: MMULoader):
        self.loader = loader
    
    def evaluate(self, predictions: List[str], questions: List[MMUQuestion]) -> Dict:
        """
        予測を評価
        
        Args:
            predictions: A/B/C/D形式の予測
            questions: 問題リスト
            
        Returns:
            {total, correct, accuracy, by_subject}
        """
        assert len(predictions) == len(questions), "Length mismatch"
        
        correct = 0
        by_subject = {}
        
        for pred, question in zip(predictions, questions):
            # 正解判定
            is_correct = (pred.upper() == question.answer.upper())
            correct += is_correct
            
            # サブジェクト別集計
            if question.subject not in by_subject:
                by_subject[question.subject] = {'total': 0, 'correct': 0}
            
            by_subject[question.subject]['total'] += 1
            by_subject[question.subject]['correct'] += is_correct
        
        # 計算
        accuracy = correct / len(questions)
        by_subject_accuracy = {
            subject: data['correct'] / data['total']
            for subject, data in by_subject.items()
        }
        
        return {
            'total': len(questions),
            'correct': correct,
            'accuracy': accuracy,
            'by_subject': by_subject_accuracy,
        }


def demo():
    """デモンストレーション"""
    import logging
    logging.basicConfig(level=logging.INFO)
    
    # ローダー作成
    loader = MMULoader(num_samples=10)  # デバッグ用に10問だけロード
    
    # 一部のサブジェクトをロード
    questions = loader.load(subjects=['abstract_algebra', 'anatomy'])
    
    print(f"\n✓ Loaded {len(questions)} questions\n")
    
    # 最初の問題を表示
    if questions:
        q = questions[0]
        print(f"Subject: {q.subject}")
        print(f"Question: {q.question}")
        print(f"Choices: {q.choices}")
        print(f"Answer: {q.answer}\n")
        
        # モデル入力形式に変換
        prompt, _ = loader.format_for_model(q)
        print(f"Formatted prompt:\n{prompt}")


if __name__ == "__main__":
    demo()
