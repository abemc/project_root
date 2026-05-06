"""
日本語MMLU相当データセットローダー
"""

from typing import List, Dict, Any


class JapaneseMMLULoader:
    """
    日本語ベンチマーク問題データセットローダー
    
    MMLU (Massive Multitask Language Understanding) の日本語版相当
    複数分野から日本語の多肢選択問題を提供
    """
    
    def __init__(self):
        """ローダーの初期化"""
        self.subjects = [
            'abstract_algebra',
            'anatomy',
            'astronomy',
            'business_ethics',
            'clinical_knowledge',
        ]
    
    def load(self, subjects: List[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
        """
        日本語問題データセットを読み込む
        
        Args:
            subjects (List[str]): 対象分野リスト (Noneの場合はすべて)
            limit (int): 返す問題数 (デフォルト: 20)
            
        Returns:
            List[Dict[str, Any]]: 問題データリスト
        """
        if subjects is None:
            subjects = self.subjects
        
        all_questions = []
        
        for subject in subjects:
            questions = self._generate_subject_questions(subject)
            all_questions.extend(questions)
        
        # limitまで返す
        return all_questions[:limit]
    
    def _generate_subject_questions(self, subject: str) -> List[Dict[str, Any]]:
        """
        特定分野の日本語問題を生成
        
        Args:
            subject (str): 分野名
            
        Returns:
            List[Dict[str, Any]]: 問題データリスト
        """
        question_data = {
            'abstract_algebra': [
                {
                    'question': '抽象代数において、群Gの部分群Hが正規部分群である条件は何か？',
                    'choices': [
                        'すべてのg ∈ Gに対して gH = Hg',
                        'すべてのg ∈ Gに対して gH ⊆ Hg',
                        'すべてのh ∈ Hに対して gh = hg',
                        'Hが有限部分群である',
                    ],
                    'answer': 'A',
                },
                {
                    'question': '体Fにおける零環でない可換環の特性が2である場合、Fの元の平方は何を満たすか？',
                    'choices': [
                        'x^2 = 0',
                        'x^2 = 1',
                        'x^2 = x',
                        'x^2 = -x',
                    ],
                    'answer': 'C',
                },
            ],
            'anatomy': [
                {
                    'question': '人間の心臓の右心房から右心室へと血液を流す弁の名称は？',
                    'choices': [
                        '大動脈弁',
                        '肺動脈弁',
                        '三尖弁',
                        '僧帽弁',
                    ],
                    'answer': 'C',
                },
                {
                    'question': '脊椎骨の中で最も大きい椎骨はどれか？',
                    'choices': [
                        '第1頸椎（環椎）',
                        '第7頸椎',
                        '第5腰椎',
                        '第1仙椎',
                    ],
                    'answer': 'C',
                },
            ],
            'astronomy': [
                {
                    'question': '太陽系の惑星の中で、最も大きい惑星はどれか？',
                    'choices': [
                        '土星',
                        '木星',
                        '天王星',
                        '海王星',
                    ],
                    'answer': 'B',
                },
                {
                    'question': '恒星の光度を測定する際に使用される単位は何か？',
                    'choices': [
                        'キャンデラ',
                        'ルーメン',
                        '太陽光度',
                        'ワット',
                    ],
                    'answer': 'C',
                },
            ],
            'business_ethics': [
                {
                    'question': 'ビジネス倫理において、ステークホルダーの利益相反を解決する際の最優先事項は何か？',
                    'choices': [
                        '株主の利益を最大化する',
                        'すべてのステークホルダーの利益のバランスを取る',
                        '従業員の給与を最大化する',
                        '短期的な利益を追求する',
                    ],
                    'answer': 'B',
                },
                {
                    'question': '企業の社会的責任（CSR）の主な目的は何か？',
                    'choices': [
                        '税金を最小化する',
                        '社会と環境への肯定的な影響を生み出す',
                        '顧客からの批判を避ける',
                        '競合他社を打倒する',
                    ],
                    'answer': 'B',
                },
            ],
            'clinical_knowledge': [
                {
                    'question': '高血圧の診断基準は、成人で何mmHg以上とされているか？',
                    'choices': [
                        '120/80 mmHg',
                        '130/80 mmHg',
                        '140/90 mmHg',
                        '150/100 mmHg',
                    ],
                    'answer': 'C',
                },
                {
                    'question': '糖尿病の一つの診断基準となる空腹時血糖値は何mg/dL以上か？',
                    'choices': [
                        '100 mg/dL',
                        '110 mg/dL',
                        '126 mg/dL',
                        '150 mg/dL',
                    ],
                    'answer': 'C',
                },
            ],
        }
        
        return question_data.get(subject, [])
    
    def get_available_subjects(self) -> List[str]:
        """
        利用可能な分野一覧を取得
        
        Returns:
            List[str]: 分野名リスト
        """
        return self.subjects.copy()
    
    def get_subject_description(self, subject: str) -> str:
        """
        分野の説明を取得
        
        Args:
            subject (str): 分野名
            
        Returns:
            str: 分野説明
        """
        descriptions = {
            'abstract_algebra': '抽象代数 - 群論、環論、体論に関する問題',
            'anatomy': '解剖学 - 人間の身体構造に関する問題',
            'astronomy': '天文学 - 天体と宇宙に関する問題',
            'business_ethics': 'ビジネス倫理 - 企業倫理と社会責任に関する問題',
            'clinical_knowledge': '臨床知識 - 医学と診断基準に関する問題',
        }
        return descriptions.get(subject, 'Unknown')


class JapaneseGSM8KLoader:
    """
    日本語数学問題ローダー（GSM8K相当）
    """
    
    def __init__(self):
        """ローダーの初期化"""
        pass
    
    def load(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        日本語の数学問題データセットを読み込む
        
        Args:
            limit (int): 返す問題数 (デフォルト: 20)
            
        Returns:
            List[Dict[str, Any]]: 問題データリスト
        """
        problems = self._generate_japanese_math_problems()
        return problems[:limit]
    
    def _generate_japanese_math_problems(self) -> List[Dict[str, Any]]:
        """日本語の数学問題を生成"""
        return [
            {
                'problem': 'ジェームスは3つのデスクを購入しました。各デスクの価格は60ドルです。各デスクに対して20%の割引を受けました。3つのデスクの総費用はいくらですか？',
                'steps': [
                    'デスク1台の割引額 = 60 * 0.20 = 12ドル',
                    'デスク1台の割引後の価格 = 60 - 12 = 48ドル',
                    '3つのデスクの総費用 = 48 * 3 = 144ドル',
                ],
                'answer': '144',
            },
            {
                'problem': '田中さんは毎日8時間働き、時給は15ドルです。5日間で彼はいくら稼ぎますか？',
                'steps': [
                    '1日の給与 = 8時間 * 15ドル/時間 = 120ドル',
                    '5日間の給与 = 120ドル * 5 = 600ドル',
                ],
                'answer': '600',
            },
            {
                'problem': 'リンゴが12個あります。このうち3分の1をジュースにして、残りの半分をパイに使用します。何個のリンゴがまだ残っていますか？',
                'steps': [
                    'ジュースに使用 = 12 * (1/3) = 4個',
                    '残り = 12 - 4 = 8個',
                    'パイに使用 = 8 * (1/2) = 4個',
                    '最終的に残ったリンゴ = 8 - 4 = 4個',
                ],
                'answer': '4',
            },
            {
                'problem': '本の価格は10ドルです。買い物をするたびに5冊以上購入すると10%の割引が受けられます。5冊購入した場合の総費用はいくらですか？',
                'steps': [
                    '割引なしの価格 = 10 * 5 = 50ドル',
                    '割引額 = 50 * 0.10 = 5ドル',
                    '割引後の総費用 = 50 - 5 = 45ドル',
                ],
                'answer': '45',
            },
            {
                'problem': '30人の学生がいます。男子学生と女子学生の比率は2:1です。男子学生は何人ですか？',
                'steps': [
                    '比率の合計 = 2 + 1 = 3',
                    '男子学生の数 = 30 * (2/3) = 20人',
                ],
                'answer': '20',
            },
        ]
