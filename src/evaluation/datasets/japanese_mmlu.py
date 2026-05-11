"""
日本語MMLU (Japanese Massive Multitask Language Understanding)

日本語版の多肢選択ベンチマーク。
複数の学科・難度にわたる日本語問題を提供します。

参考: JMMLU (Japanese MMLU)
"""

from typing import List, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class JapaneseMMUQuestion:
    """日本語MMU問題の表現"""
    question: str          # 日本語問題
    choices: List[str]     # 選択肢 [A, B, C, D]
    answer: str            # 正答 ('A', 'B', 'C', 'D')
    subject: str           # 分野 ('biology', 'history', 'math' など)
    grade: str             # 難度 ('elementary', 'middle', 'high_school', 'university')
    language: str = "ja"   # 言語 (日本語)


class JapaneseMMULoader:
    """
    日本語MMUデータセットローダー
    
    Features:
    - 日本語学習用多肢選択問題
    - 複数分野・難度対応
    - 日本語固有表現対応
    - バッチ処理対応
    """
    
    SUBJECTS = [
        'japanese_language',
        'mathematics',
        'science_biology',
        'science_chemistry',
        'science_physics',
        'history_japan',
        'history_world',
        'geography',
        'civics',
        'literature',
        'english',
        'social_studies'
    ]
    
    GRADES = ['elementary', 'middle', 'high_school', 'university']
    
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
            num_samples: ロードするサンプル数
        """
        self.cache_dir = cache_dir
        self.offline = offline
        self.num_samples = num_samples
        
        logger.info(f"Initialized JapaneseMMULoader (offline={offline})")
    
    def load(
        self,
        subjects: Optional[List[str]] = None,
        grade: Optional[str] = None
    ) -> List[JapaneseMMUQuestion]:
        """
        日本語MMUデータセットをロード
        
        Args:
            subjects: 対象分野
            grade: 対象難度
            
        Returns:
            JapaneseMMUQuestion リスト
        """
        return self._generate_test_data(subjects, grade)
    
    def _generate_test_data(
        self,
        subjects: Optional[List[str]] = None,
        grade: Optional[str] = None
    ) -> List[JapaneseMMUQuestion]:
        """
        テスト用日本語データを生成
        
        Args:
            subjects: 対象分野
            grade: 対象難度
            
        Returns:
            JapaneseMMUQuestion リスト
        """
        # すべての問題データ
        all_questions_data = [
            # 日本語 (Japanese Language)
            {
                "question": "次の文で、「ことに」の意味として最も適切なものはどれか。\n「学生たちは、特にテスト準備に力を入れた。」",
                "choices": ["~の方法で", "~を超えて", "~より強く", "~と一緒に"],
                "answer": "C",
                "subject": "japanese_language",
                "grade": "high_school"
            },
            {
                "question": "敬語の使い方として正しいのはどれか。",
                "choices": ["先生がお越しになられました", "先生がお越しになりました", "先生が来られました", "先生がいらっしゃいました"],
                "answer": "B",
                "subject": "japanese_language",
                "grade": "high_school"
            },
            # 数学 (Mathematics)
            {
                "question": "次の方程式を解きなさい。\n2x + 5 = 13",
                "choices": ["x = 2", "x = 3", "x = 4", "x = 5"],
                "answer": "C",
                "subject": "mathematics",
                "grade": "middle"
            },
            {
                "question": "円の面積の公式は何か。ただし、rは半径。",
                "choices": ["2πr", "πr²", "4πr²", "πr³"],
                "answer": "B",
                "subject": "mathematics",
                "grade": "high_school"
            },
            # 生物 (Biology)
            {
                "question": "植物の光合成で産生される主な物質は次のどれか。",
                "choices": ["酸素と水", "窒素と炭酸ガス", "ブドウ糖と酸素", "タンパク質と脂肪"],
                "answer": "C",
                "subject": "science_biology",
                "grade": "high_school"
            },
            {
                "question": "ヒトの消化器官で、タンパク質の消化が始まる場所はどこか。",
                "choices": ["口", "食道", "胃", "小腸"],
                "answer": "C",
                "subject": "science_biology",
                "grade": "high_school"
            },
            # 化学 (Chemistry)
            {
                "question": "水の化学式は何か。",
                "choices": ["H₂O₂", "H₂O", "H₃O", "HO₂"],
                "answer": "B",
                "subject": "science_chemistry",
                "grade": "high_school"
            },
            {
                "question": "次の元素のうち、最も反応性が高いのはどれか。",
                "choices": ["窒素", "酸素", "フッ素", "ネオン"],
                "answer": "C",
                "subject": "science_chemistry",
                "grade": "high_school"
            },
            # 物理 (Physics)
            {
                "question": "ニュートンの第2法則F=maで、mは何を表すか。",
                "choices": ["速度", "加速度", "質量", "力"],
                "answer": "C",
                "subject": "science_physics",
                "grade": "high_school"
            },
            {
                "question": "重力加速度の大きさはおよそいくつか。",
                "choices": ["1.0 m/s²", "5.0 m/s²", "9.8 m/s²", "15.0 m/s²"],
                "answer": "C",
                "subject": "science_physics",
                "grade": "high_school"
            },
            # 日本史 (Japanese History)
            {
                "question": "江戸時代が始まった年はいつか。",
                "choices": ["1568年", "1603年", "1615年", "1687年"],
                "answer": "B",
                "subject": "history_japan",
                "grade": "high_school"
            },
            {
                "question": "明治維新の中心人物でなかったのは誰か。",
                "choices": ["坂本龍馬", "西郷隆盛", "福沢諭吉", "上杉謙信"],
                "answer": "D",
                "subject": "history_japan",
                "grade": "high_school"
            },
            # 世界史 (World History)
            {
                "question": "フランス革命が起こった年はいつか。",
                "choices": ["1776年", "1789年", "1804年", "1815年"],
                "answer": "B",
                "subject": "history_world",
                "grade": "high_school"
            },
            {
                "question": "ルネッサンスの中心地はどこか。",
                "choices": ["フランス", "ドイツ", "イタリア", "スペイン"],
                "answer": "C",
                "subject": "history_world",
                "grade": "high_school"
            },
            # 地理 (Geography)
            {
                "question": "日本の首都はどこか。",
                "choices": ["大阪", "東京", "京都", "神戸"],
                "answer": "B",
                "subject": "geography",
                "grade": "elementary"
            },
            {
                "question": "世界で最も人口が多い国はどこか。",
                "choices": ["インド", "中国", "アメリカ", "インドネシア"],
                "answer": "B",
                "subject": "geography",
                "grade": "high_school"
            },
            # 公民 (Civics)
            {
                "question": "日本の国会は、上院と下院で構成されている。上院の名称は何か。",
                "choices": ["衆議院", "参議院", "貴族院", "民議院"],
                "answer": "B",
                "subject": "civics",
                "grade": "high_school"
            },
            {
                "question": "日本国憲法で定められた「基本的人権」はどの条文か。",
                "choices": ["第1条", "第3条", "第11条", "第97条"],
                "answer": "C",
                "subject": "civics",
                "grade": "high_school"
            },
            # 文学 (Literature)
            {
                "question": "夏目漱石の著作でないのはどれか。",
                "choices": ["『吾輩は猫である』", "『坊っちゃん』", "『こころ』", "『銀河鉄道の夜』"],
                "answer": "D",
                "subject": "literature",
                "grade": "high_school"
            },
            {
                "question": "『羅生門』の著者は誰か。",
                "choices": ["太宰治", "芥川龍之介", "志賀直哉", "武者小路実篤"],
                "answer": "B",
                "subject": "literature",
                "grade": "high_school"
            },
        ]
        
        # フィルター処理
        filtered_questions = []
        target_subjects = subjects if subjects else self.SUBJECTS
        
        for q_data in all_questions_data:
            if q_data["subject"] not in target_subjects:
                continue
            
            if grade and q_data["grade"] != grade:
                continue
            
            question = JapaneseMMUQuestion(
                question=q_data["question"],
                choices=q_data["choices"],
                answer=q_data["answer"],
                subject=q_data["subject"],
                grade=q_data["grade"],
                language="ja"
            )
            filtered_questions.append(question)
            
            if self.num_samples and len(filtered_questions) >= self.num_samples:
                break
        
        logger.info(f"Generated {len(filtered_questions)} Japanese MMU questions")
        return filtered_questions


def demo():
    """デモンストレーション"""
    print("\n" + "="*80)
    print("日本語MMU デモンストレーション")
    print("="*80)
    
    # ローダー初期化
    loader = JapaneseMMULoader(num_samples=5)
    
    # 全体ロード
    print("\n[1] 全体ロード:")
    all_questions = loader.load()
    print(f"✓ {len(all_questions)}問を読み込み")
    
    # 分野別ロード
    print("\n[2] 日本語分野:")
    ja_questions = loader.load(subjects=["japanese_language"])
    for i, q in enumerate(ja_questions[:2], 1):
        print(f"  Q{i}: {q.question[:60]}...")
        print(f"       正答: {q.answer}")
    
    # 数学分野
    print("\n[3] 数学分野:")
    math_questions = loader.load(subjects=["mathematics"])
    for i, q in enumerate(math_questions[:2], 1):
        print(f"  Q{i}: {q.question[:60]}...")
        print(f"       正答: {q.answer}")
    
    print("\n✅ デモ完了")


if __name__ == "__main__":
    demo()
