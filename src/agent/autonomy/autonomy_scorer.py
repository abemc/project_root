"""
エージェント自律性スコア計算モジュール

複数次元での自律性を測定し、総合スコアを算出します。
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum
import math


class AutonomyDimension(Enum):
    """
    自律性の評価次元
    
    エージェントの自律性を5つの独立した次元で測定します。
    各次元は0-1の範囲で評価され、異なる重み付けで総合スコアに寄与します。
    """
    # ゴール達成能力: タスク成功率を測定（最も重要：30%の重み）
    # 例：10個のタスク中9個成功 = 90%
    # 目標値: 90%以上で「優秀」と判定
    GOAL_ACHIEVEMENT = "goal_achievement"
    
    # 意思決定独立性: ユーザー介入なしで決定した割合を測定（重み：25%）
    # 例：100個の決定中90個がユーザー介入なし = 90%の独立性
    # 目標値: 80%以上で「良好」と判定
    DECISION_INDEPENDENCE = "decision_independence"
    
    # エラー回復能力: エラーから自動回復した割合を測定（重み：20%）
    # 例：100個のエラー中85個を自動修復 = 85%
    # 目標値: 85%以上で「適切」と判定
    ERROR_RECOVERY = "error_recovery"
    
    # 戦略適応性: 状況に応じた戦略変更の適切性を測定（重み：15%）
    # 計算式: 最適な変更回数と実際の変更回数の差に基づき評価
    # 例：最適2回に対し実際3回 → スコア低下
    STRATEGY_ADAPTATION = "strategy_adaptation"
    
    # 学習能力: 試行を通じた改善率を測定（重み：10%）
    # 例：初回50%成功 → 最終80%成功 = 30%の改善（学習率0.3）
    # 目標値: 60%以上の改善で「学習している」と判定
    LEARNING_CAPABILITY = "learning_capability"


@dataclass
class DimensionalAutonomy:
    """
    各次元における自律性スコアのコンテナクラス
    
    エージェントの自律性を5つの独立した指標で保持します。
    各スコアは0.0（最悪）から1.0（最高）の範囲です。
    
    用途：
    - スコアの詳細分析: どの次元が強いか/弱いかの判定
    - レポート生成: 次元別の強み・弱みの表示
    - 改善方針の決定: どの次元を改善すべきかの判断
    """
    # タスク成功率: 実行したタスクのうち成功した割合
    # 計算: (成功タスク数) / (総タスク数)
    # 例: 10/10 = 1.0（完璧）, 7/10 = 0.7（良好）
    goal_achievement: float = 0.0
    
    # 意思決定独立性: ユーザー介入なしで決定した割合
    # 計算: (介入不要な決定数) / (総決定数)
    # 例: 80/100 = 0.8（ほぼ自律的）, 50/100 = 0.5（半自律的）
    decision_independence: float = 0.0
    
    # エラー回復能力: エラーから自動修復できた割合
    # 計算: (自動修復されたエラー数) / (総エラー数)
    # 例: 17/20 = 0.85（良好）, 10/20 = 0.5（要改善）
    error_recovery: float = 0.0
    
    # 戦略適応性: 状況に応じた戦略変更の適切性スコア
    # 計算: 最適変更回数に対する実際の変更回数の比較
    # 例: 0.8（適切な頻度）, 0.3（変更なし）, 0.4（変更が多すぎる）
    strategy_adaptation: float = 0.0
    
    # 学習能力: 試行を通じた改善の度合い
    # 計算: (最終パフォーマンス - 初期) / 初期 で成長率を計算
    # 例: 0.2（20%改善）, 0.0（改善なし）, -0.1（悪化）
    learning_capability: float = 0.0
    
    def to_dict(self) -> Dict[str, float]:
        """
        現在のスコアを辞書形式に変換
        
        レポート生成やJSON出力時に使用します。
        キーは各次元の識別子（ゴール達成能力など）で、値はスコア（0-1）です。
        
        戻り値:
            {
                "goal_achievement": 0.92,
                "decision_independence": 0.85,
                "error_recovery": 0.88,
                "strategy_adaptation": 0.76,
                "learning_capability": 0.68
            }
        """
        return {
            "goal_achievement": self.goal_achievement,
            "decision_independence": self.decision_independence,
            "error_recovery": self.error_recovery,
            "strategy_adaptation": self.strategy_adaptation,
            "learning_capability": self.learning_capability,
        }
    
    def get_average(self) -> float:
        """
        全5次元の平均スコアを計算（加重なし）
        
        各次元を等しく扱い、5つのスコアの算術平均を返します。
        加重平均ではないため、実際の「自律性レベル判定」には使用されず、
        参考情報として使用されます。
        
        計算例:
        - goal_achievement = 0.92
        - decision_independence = 0.85
        - error_recovery = 0.88
        - strategy_adaptation = 0.76
        - learning_capability = 0.68
        - 平均 = (0.92 + 0.85 + 0.88 + 0.76 + 0.68) / 5 = 0.818
        
        戻り値:
            float: 5次元の平均スコア（0.0-1.0）
        """
        dimensions = [
            self.goal_achievement,
            self.decision_independence,
            self.error_recovery,
            self.strategy_adaptation,
            self.learning_capability,
        ]
        return sum(dimensions) / len(dimensions) if dimensions else 0.0


@dataclass
class AutonomyScore:
    """
    エージェント自律性の総合評価スコア（最終結果）
    
    calculate_score() メソッドの戻り値として使用されます。
    このクラスには、詳細なスコア分析と改善推奨が含まれます。
    
    属性：
    - dimensions: 5次元の詳細スコア（DimensionalAutonomy）
    - overall_score: 加重平均による総合スコア（0-100）
    - autonomy_level: スコアから決定された自律性レベル文字列
    - strengths: 強みのリスト（スコア0.75以上の次元）
    - weaknesses: 弱みのリスト（スコア0.40以下の次元）
    - recommendations: 改善推奨のリスト
    - timestamp: 評価を実施した日時
    
    使用例:
        score = AutonomyScore(
            dimensions=dim_autonomy,
            overall_score=82.5,
            autonomy_level="Semi-Autonomous",
            strengths=["Goal Achievement: 92%"],
            weaknesses=["Learning Capability: 68%"],
            recommendations=["学習メカニズムを改善してください"],
            timestamp="2025-04-21T10:30:00"
        )
    """
    # 5次元の詳細スコアを保持
    # to_dict()メソッドで各次元の個別スコアにアクセス可能
    dimensions: DimensionalAutonomy
    
    # 総合スコア（0-100の10進数スケール）
    # 計算式: 各次元スコア × 重み付け係数 の合計
    # 例: 0.82 × 100 = 82点
    overall_score: float
    
    # 自律性レベルの文字列表現
    # 値: "Autonomous", "Semi-Autonomous", "Guided", "Assisted", "Dependent"
    # 判定基準: overall_score に基づき自動決定
    autonomy_level: str
    
    # 強みのリスト（優れた次元）
    # スコアが0.75以上の次元のみが含まれる
    # 例: ["Goal Achievement: 92%", "Error Recovery: 88%"]
    strengths: List[str] = field(default_factory=list)
    
    # 弱みのリスト（改善が必要な次元）
    # スコアが0.40以下の次元のみが含まれる
    # 例: ["Learning Capability: 38%"]
    weaknesses: List[str] = field(default_factory=list)
    
    # 改善推奨のリスト
    # 自律性レベルと弱みに基づき自動生成
    # 例: ["学習メカニズムの改善が必要です"]
    recommendations: List[str] = field(default_factory=list)
    
    # 評価実施日時（ISO 8601形式）
    # 例: "2025-04-21T10:30:00"
    timestamp: Optional[str] = None
    
    def __str__(self) -> str:
        """文字列表現"""
        return (
            f"AutonomyScore(overall={self.overall_score:.1f}, "
            f"level={self.autonomy_level})"
        )


class AutonomyScorer:
    """
    エージェント自律性スコアリングエンジン（メインエンジン）
    
    複数の指標（成功率、介入率、エラー回復率など）を受け取り、
    5次元の自律性スコアを計算し、総合評価を返します。
    
    主な役割：
    1. 各次元スコアの計算（正規化、加重平均）
    2. 自律性レベルの決定（5段階）
    3. 強み・弱みの特定
    4. 改善推奨の生成
    5. 評価履歴の管理
    
    使用例:
        scorer = AutonomyScorer()
        score = scorer.calculate_score(
            task_success_rate=0.95,
            user_intervention_rate=0.10,
            error_recovery_rate=0.90,
            strategy_switches=3,
            learning_rate=0.15,
            total_attempts=20
        )
        print(f"スコア: {score.overall_score:.1f} ({score.autonomy_level})")
    """
    
    # 自律性レベルの定義
    # スコアの範囲に基づいて5つのレベルに分類
    # 例: overall_score = 85 → "Semi-Autonomous"
    LEVEL_DEFINITIONS = {
        "Autonomous": (80, 100),        # 完全自律: 80-100点
        "Semi-Autonomous": (60, 79),    # 半自律: 60-79点
        "Guided": (40, 59),             # ガイド付き: 40-59点
        "Assisted": (20, 39),           # 支援的: 20-39点
        "Dependent": (0, 19),           # 依存的: 0-19点
    }
    
    # 次元別重み付け係数
    # 各次元がスコアに寄与する割合（合計100%）
    # ゴール達成能力が最も重要（30%）であるという仮定に基づく
    DIMENSION_WEIGHTS = {
        AutonomyDimension.GOAL_ACHIEVEMENT: 0.30,      # 最も重要: 30%
        AutonomyDimension.DECISION_INDEPENDENCE: 0.25,  # 次点: 25%
        AutonomyDimension.ERROR_RECOVERY: 0.20,         # 20%
        AutonomyDimension.STRATEGY_ADAPTATION: 0.15,    # 15%
        AutonomyDimension.LEARNING_CAPABILITY: 0.10,    # 最小: 10%
    }
    
    def __init__(self):
        """
        スコアラーを初期化
        
        evaluation_history（評価履歴）を空リストで初期化します。
        複数回の evaluate_autonomy_simple() 呼び出しで履歴を蓄積し、
        改善傾向を追跡することが可能になります。
        """
        # 評価結果の履歴を保持（時系列分析用）
        # 例: [score1, score2, score3, ...]
        # get_improvement_trend() で成長率を計算するのに使用
        self.evaluation_history: List[AutonomyScore] = []
    
    def calculate_score(
        self,
        task_success_rate: float,
        user_intervention_rate: float,
        error_recovery_rate: float,
        strategy_switches: int,
        learning_rate: float,
        total_attempts: int = 1,
    ) -> AutonomyScore:
        """
        複数の指標から自律性スコアを計算（メインメソッド）
        
        このメソッドは以下の処理を実行します:
        1. 各指標を正規化して各次元スコアに変換
        2. 各次元スコアを加重平均して総合スコア（0-100）を計算
        3. 総合スコアから自律性レベル（5段階）を決定
        4. スコアから強み・弱みを特定
        5. 自律性レベルに応じた改善推奨を生成
        6. 結果を AutonomyScore オブジェクトで返す
        
        計算フロー:
        入力指標
          ↓
        各次元スコア計算（正規化）
          ↓
        加重平均で総合スコア（0-100）
          ↓
        自律性レベル決定
          ↓
        強み・弱みを抽出
          ↓
        改善推奨を生成
          ↓
        結果を AutonomyScore で返却
        
        Args:
            task_success_rate: タスク成功率 (0-1)
                - 計算方法: (成功したタスク数) / (総タスク数)
                - 例: 19個のタスク中18個成功 → 0.95
                - 使用先: goal_achievement 次元
            
            user_intervention_rate: ユーザー介入率 (0-1)
                - 計算方法: (ユーザーが介入した決定数) / (総決定数)
                - 例: 100個の決定中10個が介入 → 0.10
                - 使用先: decision_independence（逆数で使用）
                - 注: 1 - intervention_rate で独立性を計算
            
            error_recovery_rate: エラー回復率 (0-1)
                - 計算方法: (自動修復されたエラー数) / (総エラー数)
                - 例: 20個のエラー中18個を自動修復 → 0.90
                - 使用先: error_recovery 次元
                - 注: エラーが発生しない場合でも計算可能
            
            strategy_switches: 戦略変更回数 (整数)
                - 計算方法: 実際に戦略を変更した回数
                - 例: 試行中に3回戦略を変更 → 3
                - 使用先: strategy_adaptation（最適変更回数と比較）
                - 注: 最適値は sqrt(total_attempts) で計算
            
            learning_rate: 学習率 (0-1)
                - 計算方法: (最終パフォーマンス - 初期) / 初期
                - 例: 初期50% → 最終65% = (0.65-0.5)/0.5 = 0.3
                - 使用先: learning_capability 次元
                - 負の値でも許容（悪化を示す）
            
            total_attempts: 総試行回数 (整数、デフォルト=1)
                - 計算方法: エージェントが試行した総数
                - 例: 5回の試行 → 5
                - 使用先: strategy_adaptation の最適値計算
                - 注: 1以下の場合は strategy_adaptation がデフォルト値
        
        Returns:
            AutonomyScore: 詳細な評価結果
                - dimensions: 5次元の詳細スコア
                - overall_score: 総合スコア（0-100）
                - autonomy_level: レベル文字列
                - strengths: 強みリスト
                - weaknesses: 弱みリスト
                - recommendations: 改善推奨リスト
                - timestamp: 評価日時
        
        使用例:
            # シンプルな使用例
            score = scorer.calculate_score(
                task_success_rate=0.95,
                user_intervention_rate=0.10,
                error_recovery_rate=0.90,
                strategy_switches=3,
                learning_rate=0.15,
                total_attempts=20
            )
            
            # 結果の確認
            print(f"スコア: {score.overall_score:.1f}")  # 82.5
            print(f"レベル: {score.autonomy_level}")     # Semi-Autonomous
            print(f"強み: {score.strengths}")
            print(f"改善推奨: {score.recommendations}")
        """
        
        # === ステップ1: 各次元スコアの計算 ===
        # 各入力指標を0-1の正規化スコアに変換し、5つの次元スコアを生成
        dimensions = DimensionalAutonomy(
            # ゴール達成: タスク成功率をそのまま使用（既に0-1）
            goal_achievement=self._normalize(task_success_rate, 0, 1),
            
            # 意思決定独立性: 介入率の逆数（1 - 介入率 = 独立性）
            decision_independence=self._normalize(1 - user_intervention_rate, 0, 1),
            
            # エラー回復: エラー回復率をそのまま使用（既に0-1）
            error_recovery=self._normalize(error_recovery_rate, 0, 1),
            
            # 戦略適応: 最適変更回数と実際の変更回数を比較
            strategy_adaptation=self._calculate_strategy_adaptation(
                strategy_switches, total_attempts
            ),
            
            # 学習能力: 学習率をそのまま使用（既に0-1範囲）
            learning_capability=self._normalize(learning_rate, 0, 1),
        )
        
        # === ステップ2: 総合スコアの計算 ===
        # 各次元スコアを重み付け係数で加重平均し、0-100スケールに変換
        overall_score = self._calculate_weighted_score(dimensions)
        
        # === ステップ3: 自律性レベルの決定 ===
        # 総合スコアに基づいて5つのレベルのいずれかを決定
        autonomy_level = self._determine_level(overall_score)
        
        # === ステップ4: 強み・弱みの特定 ===
        # 各次元スコアのしきい値に基づき、強みと弱みをリストアップ
        strengths, weaknesses = self._identify_strengths_weaknesses(dimensions)
        
        # === ステップ5: 改善推奨の生成 ===
        # 自律性レベルと弱みに基づいて、具体的な改善推奨を生成
        recommendations = self._generate_recommendations(
            dimensions, autonomy_level
        )
        
        # === ステップ6: 結果オブジェクトの作成 ===
        score = AutonomyScore(
            dimensions=dimensions,
            overall_score=overall_score,
            autonomy_level=autonomy_level,
            strengths=strengths,
            weaknesses=weaknesses,
            recommendations=recommendations,
        )
        
        # === ステップ7: 履歴に記録 ===
        # 将来的な改善傾向分析のため、履歴に追加
        self.evaluation_history.append(score)
        return score
    
    def _normalize(self, value: float, min_val: float, max_val: float) -> float:
        """
        値を0-1の範囲に正規化（Min-Max正規化）
        
        任意の範囲の値を0-1の標準範囲に変換します。
        スコア計算時に異なるスケールの入力を統一するために使用されます。
        
        正規化式: (value - min_val) / (max_val - min_val)
        
        例1: 成功率 95% を正規化
            _normalize(0.95, 0, 1) = (0.95 - 0) / (1 - 0) = 0.95
        
        例2: 120度を0-180度から0-1に正規化
            _normalize(120, 0, 180) = (120 - 0) / (180 - 0) = 0.67
        
        例3: 範囲外の値（クリップ処理あり）
            _normalize(1.5, 0, 1) = (1.5 - 0) / (1 - 0) = 1.5 → クリップして 1.0
            _normalize(-0.2, 0, 1) = (-0.2 - 0) / (1 - 0) = -0.2 → クリップして 0.0
        
        Args:
            value: 正規化する値
            min_val: 入力値の最小値（下限）
            max_val: 入力値の最大値（上限）
        
        Returns:
            float: 0-1に正規化された値
                - 0.0: 最小値以下
                - 1.0: 最大値以上
                - 0.0-1.0: その間の値
        """
        # 範囲内の値を計算
        if max_val == min_val:
            # 最大値と最小値が同じ場合は0.5を返す（不定状況）
            return 0.5
        
        # 正規化：線形スケーリング
        normalized = (value - min_val) / (max_val - min_val)
        
        # クリップ: 0-1の範囲に収まるようにする
        return max(0.0, min(1.0, normalized))
    
    def _calculate_strategy_adaptation(
        self, strategy_switches: int, total_attempts: int
    ) -> float:
        """
        戦略適応性スコアを計算
        
        エージェントが状況に応じて戦略を適切に変更したかを評価します。
        完全に同じ戦略を使い続けるのも（switches=0）、
        頻繁に変更するのも（switches=high）、どちらも低スコアになります。
        
        理想的な戦略変更回数: sqrt(total_attempts)
        - 少数の試行では少ない変更が最適（適応性は低でOK）
        - 多数の試行では適度な変更が必要（より適応的であるべき）
        
        計算フロー:
        1. total_attempts <= 1 → デフォルト値 0.5を返す
        2. optimal_switches = sqrt(total_attempts) を計算
        3. strategy_switches と optimal_switches を比較
           - switches = 0 → スコア 0.3（適応性なし）
           - switches ≤ optimal → スコア 0.8（最適範囲）
           - switches > optimal → スコア 0.8 - (差分 × 0.1)（過度な変更）
        
        計算例:
        1. total_attempts=4, optimal_switches=2.0
           - actual_switches=0 → score=0.3
           - actual_switches=2 → score=0.8
           - actual_switches=5 → score=0.5 (0.8 - 3*0.1)
        
        2. total_attempts=100, optimal_switches=10.0
           - actual_switches=0 → score=0.3
           - actual_switches=10 → score=0.8
           - actual_switches=15 → score=0.3 (0.8 - 5*0.1)
        
        Args:
            strategy_switches: 実際の戦略変更回数（整数、非負）
            total_attempts: 総試行回数（整数、正数）
        
        Returns:
            float: 戦略適応性スコア（0-1）
                - 0.8: 理想的な変更回数（最適）
                - 0.3-0.8: 許容範囲
                - 0.3: 変更が少なすぎるまたは多すぎる
        """
        # 試行回数が1以下の場合はデフォルト値を返す
        if total_attempts <= 1:
            return 0.5  # 判定不可：デフォルト値
        
        # 理想的な戦略変更回数 = sqrt(総試行回数)
        # 例: 100試行 → 理想は約10回の変更
        optimal_switches = max(1, math.sqrt(total_attempts))
        
        # ケース1: 戦略変更なし → 適応性がない
        if strategy_switches == 0:
            return 0.3  # 適応性が低い
        # ケース2: 理想範囲内の変更 → 最適
        elif strategy_switches <= optimal_switches:
            return 0.8  # 最適な適応性
        # ケース3: 理想より多い変更 → 不安定
        else:
            # 過度な変更に対してペナルティ
            excess_switches = strategy_switches - optimal_switches
            return max(0.3, 0.8 - (excess_switches * 0.1))
    
    def _calculate_weighted_score(self, dimensions: DimensionalAutonomy) -> float:
        """
        加重平均でスコアを計算（総合スコア算出）
        
        5つの次元スコアに対して、DIMENSION_WEIGHTS で定義された重み付けを適用し、
        加重平均を計算します。その後、0-100スケールに変換して返します。
        
        計算式:
        weighted_sum = Σ(dimension_score × dimension_weight)
        overall_score = weighted_sum × 100
        
        計算例：
        次元スコア: goal=0.92, decision=0.85, error=0.88, strategy=0.76, learning=0.68
        重み係数: goal=0.30, decision=0.25, error=0.20, strategy=0.15, learning=0.10
        
        weighted_sum = (0.92×0.30) + (0.85×0.25) + (0.88×0.20) + (0.76×0.15) + (0.68×0.10)
                     = 0.276 + 0.2125 + 0.176 + 0.114 + 0.068
                     = 0.8445
        
        overall_score = 0.8445 × 100 = 84.45 → 約84点
        → レベル判定: Semi-Autonomous (60-79点の範囲)
        
        Args:
            dimensions: DimensionalAutonomy オブジェクト
                各次元のスコア（0-1）を含む
        
        Returns:
            float: 総合スコア（0-100）
                - 0-19点: Dependent（依存的）
                - 20-39点: Assisted（支援的）
                - 40-59点: Guided（ガイド付き）
                - 60-79点: Semi-Autonomous（半自律）
                - 80-100点: Autonomous（完全自律）
        """
        # 各次元のスコアを辞書形式で取得
        dim_dict = dimensions.to_dict()
        
        # 加重平均を計算
        weighted_sum = 0.0
        for dimension, weight in self.DIMENSION_WEIGHTS.items():
            # ディメンション名（英数字）から対応する次元スコアを取得
            dim_name = dimension.value  # 例: "goal_achievement"
            score = dim_dict.get(dim_name, 0.0)
            
            # その次元スコアに重み係数を乗じて加算
            weighted_sum += score * weight
        
        # 0-100スケールに変換
        # weighted_sum は0-1の範囲なので、100を乗じて0-100に変換
        return weighted_sum * 100
    
    def _determine_level(self, score: float) -> str:
        """
        総合スコアから自律性レベルを決定
        
        0-100のスコアを5つのレベルのいずれかに分類します。
        分類は LEVEL_DEFINITIONS で定義された範囲に基づきます。
        
        レベル判定表:
        - Autonomous (80-100): 完全自律
          → エージェントは人間の介入なしに自律的に動作
          → 目標達成率が高く、意思決定も独立している
        
        - Semi-Autonomous (60-79): 半自律
          → エージェントは大部分のタスクを自律的に処理
          → 複雑な判断や重要な決定には人間の確認が必要
        
        - Guided (40-59): ガイド付き
          → エージェントは計画を立てるが、人間のガイダンスが必要
          → エラー回復能力がまだ限定的
        
        - Assisted (20-39): 支援的
          → エージェントはタスク実行を支援するが、ユーザーが主導
          → 多くの決定で人間の介入が必要
        
        - Dependent (0-19): 依存的
          → エージェントは基本的な操作のみ可能
          → 人間の監督と指導に依存
        
        計算例:
        - score = 85 → "Autonomous"（80≤85≤100）
        - score = 70 → "Semi-Autonomous"（60≤70≤79）
        - score = 45 → "Guided"（40≤45≤59）
        - score = 25 → "Assisted"（20≤25≤39）
        - score = 10 → "Dependent"（0≤10≤19）
        - score = 101 → "Unknown"（範囲外）
        
        Args:
            score: 総合スコア（通常は0-100、範囲外の値も許容）
        
        Returns:
            str: 自律性レベル名
                - "Autonomous"
                - "Semi-Autonomous"
                - "Guided"
                - "Assisted"
                - "Dependent"
                - "Unknown"（範囲外）
        """
        # LEVEL_DEFINITIONS を走査し、スコアが範囲内のレベルを探す
        for level, (min_score, max_score) in self.LEVEL_DEFINITIONS.items():
            # min_score ≤ score ≤ max_score を満たすか判定
            if min_score <= score <= max_score:
                return level
        
        # どのレベルにも該当しない場合は"Unknown"を返す
        # これは通常起こらない（0-100が完全にカバーされているため）
        return "Unknown"
    
    def _identify_strengths_weaknesses(
        self, dimensions: DimensionalAutonomy
    ) -> Tuple[List[str], List[str]]:
        """
        各次元のスコアから強みと弱みを抽出
        
        定義されたしきい値に基づいて、エージェントの強みと弱みを特定します。
        これらは改善推奨の生成やレポート作成に使用されます。
        
        基準:
        - 強み: スコア ≥ 0.75（75%以上）
          → 優れた能力、継続すべき領域
        - 弱み: スコア ≤ 0.40（40%以下）
          → 改善が必要な領域、優先的に対応すべき
        - 中立: 0.40 < スコア < 0.75
          → 許容レベル、必須ではない改善
        
        計算例:
        dimensions = {
            "goal_achievement": 0.92,       → 強み
            "decision_independence": 0.85,  → 強み
            "error_recovery": 0.88,         → 強み
            "strategy_adaptation": 0.68,    → 中立
            "learning_capability": 0.38     → 弱み
        }
        
        戻り値:
        strengths = [
            "Goal Achievement: 92.00%",
            "Decision Independence: 85.00%",
            "Error Recovery: 88.00%"
        ]
        weaknesses = [
            "Learning Capability: 38.00%"
        ]
        
        Args:
            dimensions: DimensionalAutonomy オブジェクト
                各次元のスコア（0-1）を含む
        
        Returns:
            Tuple[List[str], List[str]]:
                - 第1要素: 強みのリスト
                  形式: ["次元名: XX.XX%", ...]
                - 第2要素: 弱みのリスト
                  形式: ["次元名: XX.XX%", ...]
        """
        # 各次元のスコアを辞書形式で取得
        scores = dimensions.to_dict()
        
        # しきい値の定義
        threshold_high = 0.75  # 強み: 75%以上
        threshold_low = 0.40   # 弱み: 40%以下
        
        strengths = []
        weaknesses = []
        
        # 各次元をスキャンして強みと弱みを抽出
        for dimension_name, score in scores.items():
            # 次元名を表示用に整形（snake_case → Title Case）
            # 例: "goal_achievement" → "Goal Achievement"
            display_name = dimension_name.replace("_", " ").title()
            
            # 強みか弱みか判定
            if score >= threshold_high:
                # 強み: 75%以上のスコア
                strengths.append(f"{display_name}: {score:.2%}")
            elif score <= threshold_low:
                # 弱み: 40%以下のスコア
                weaknesses.append(f"{display_name}: {score:.2%}")
        
        return strengths, weaknesses
    
    def _generate_recommendations(
        self, dimensions: DimensionalAutonomy, level: str
    ) -> List[str]:
        """
        自律性レベルと次元スコアに基づいて改善推奨を生成
        
        エージェントの現在のレベルと弱い領域に応じて、
        具体的で実行可能な改善推奨を生成します。
        
        推奨生成ルール:
        
        1. Autonomous (80-100点): 現状維持 + 拡張
           - 現在のパフォーマンスを維持する推奨
           - 新しいドメインへの応用を提案
        
        2. Semi-Autonomous (60-79点): 弱点補強
           - goal_achievement < 0.85 → タスク成功率向上
           - error_recovery < 0.80 → エラーハンドリング強化
        
        3. Guided (40-59点): 学習メカニズム改善
           - ユーザーガイダンスの重要性を強調
           - 学習能力の改善が必要な場合はそれを指摘
        
        4. Assisted / Dependent (< 40点): 大規模改善
           - フレームワーク全体の見直し
           - 基本的なタスク成功率を90%以上に
        
        計算例:
        - level = "Semi-Autonomous", goal_achievement = 0.80
          → 推奨: ["タスク成功率の向上に注力してください"]
        
        - level = "Guided", learning_capability = 0.55
          → 推奨: ["ユーザーガイダンスは引き続き重要です",
                   "学習メカニズムの改善が必要です"]
        
        Args:
            dimensions: DimensionalAutonomy オブジェクト
                各次元のスコアを含む
            level: 自律性レベル文字列
                "Autonomous", "Semi-Autonomous", "Guided", 
                "Assisted", "Dependent" のいずれか
        
        Returns:
            List[str]: 改善推奨のリスト
                - 1個以上の推奨を返す
                - 具体的で実行可能な内容
                - 優先度順で並んでいない場合もある
        """
        recommendations = []
        
        # === Autonomous レベルの推奨 ===
        if level == "Autonomous":
            # 現在の良好なパフォーマンスを維持する
            recommendations.append("現在のパフォーマンス水準を維持してください")
            # さらなる拡張の機会を探索
            recommendations.append("新しいドメインでの応用可能性を探索してください")
        
        # === Semi-Autonomous レベルの推奨 ===
        elif level == "Semi-Autonomous":
            # ゴール達成能力が低い場合
            if dimensions.goal_achievement < 0.85:
                recommendations.append("タスク成功率の向上に注力してください")
            # エラー回復能力が低い場合
            if dimensions.error_recovery < 0.80:
                recommendations.append("エラーハンドリングロジックを強化してください")
        
        # === Guided レベルの推奨 ===
        elif level == "Guided":
            # ガイダンスの重要性を強調
            recommendations.append("ユーザーガイダンスは引き続き重要です")
            # 学習能力が低い場合
            if dimensions.learning_capability < 0.60:
                recommendations.append("学習メカニズムの改善が必要です")
        
        # === Assisted / Dependent レベルの推奨 ===
        elif level in ["Assisted", "Dependent"]:
            # 全体的な改善が必要
            recommendations.append("包括的なフレームワークの見直しが必要です")
            # 基本的な成功率の目標を設定
            recommendations.append("基本的なタスク成功率を90%以上に向上させてください")
        
        return recommendations
    
    def get_improvement_trend(self) -> Optional[float]:
        """
        評価履歴から改善傾向を算出（成長率）
        
        複数回の評価結果から、エージェントの時系列での改善度合いを計算します。
        正の値は改善、負の値は悪化を示します。
        
        計算式:
        成長率(%) = ((最新スコア - 初期スコア) / 初期スコア) × 100
        
        計算例:
        1. 初期スコア: 60点, 最新スコア: 75点
           成長率 = ((75 - 60) / 60) × 100 = 25%（25%の改善）
        
        2. 初期スコア: 80点, 最新スコア: 82点
           成長率 = ((82 - 80) / 80) × 100 = 2.5%（わずかな改善）
        
        3. 初期スコア: 70点, 最新スコア: 65点
           成長率 = ((65 - 70) / 70) × 100 = -7.14%（悪化）
        
        戻り値:
        - 正の値: 改善（%単位）
          - 20%以上：大幅改善（推奨）
          - 5-20%：着実な改善
          - 0-5%：わずかな改善
        
        - 負の値: 悪化（%単位）
          - 0%～-10%：軽微な悪化
          - -10%以下：重大な悪化（調査必要）
        
        - None: 計算不可
          - 評価が1回以下
          - 初期スコアが0
        
        Returns:
            Optional[float]: 成長率（%）、または計算不可の場合 None
        """
        # 評価履歴が2回以上必要（最初と最後を比較するため）
        if len(self.evaluation_history) < 2:
            return None
        
        # 最初の評価と最新の評価を取得
        first_score = self.evaluation_history[0].overall_score
        latest_score = self.evaluation_history[-1].overall_score
        
        # ゼロ除算を防ぐ
        if first_score == 0:
            return None
        
        # 成長率を計算（%単位）
        growth_rate = (latest_score - first_score) / first_score
        return growth_rate * 100  # パーセンテージに変換
    
    def get_average_score(self) -> Optional[float]:
        """
        評価履歴から平均スコアを計算
        
        複数回の評価を実施した場合、その平均を算出します。
        これは継続的な監視下での「通常」のパフォーマンスレベルを示します。
        
        計算式:
        平均スコア = Σ(各評価のoverall_score) / 評価回数
        
        計算例:
        評価履歴:
        - 評価1: 65点
        - 評価2: 72点
        - 評価3: 68点
        - 評価4: 75点
        
        平均スコア = (65 + 72 + 68 + 75) / 4 = 70点
        
        用途:
        - 通常パフォーマンスの把握
        - 外れ値の検出（平均から大幅に離れたスコア）
        - 期待値の設定
        
        戻り値:
        - float: 平均スコア（0-100）
        - None: 評価履歴が空の場合
        
        Returns:
            Optional[float]: 平均スコア、または評価なしの場合 None
        """
        # 評価履歴が空の場合は None を返す
        if not self.evaluation_history:
            return None
        
        # すべての評価スコアの合計を計算
        total_score = sum(score.overall_score for score in self.evaluation_history)
        
        # 評価の総数で除算して平均を計算
        average_score = total_score / len(self.evaluation_history)
        
        return average_score
    
    def reset_history(self):
        """
        評価履歴をリセット
        
        evaluation_history をクリアしてから新しい評価サイクルを開始します。
        以前の評価データを削除する場合に使用します。
        
        用途:
        - 新しい環境でのテスト開始
        - 過去の評価を破棄して新規スタート
        - パフォーマンス比較用のベースラインリセット
        
        例:
            scorer = AutonomyScorer()
            # ... 複数回の evaluate_autonomy_simple() ...
            scorer.reset_history()  # 履歴をクリア
            # ... 新しい評価サイクル開始 ...
        """
        # 評価履歴を空リストで初期化
        self.evaluation_history = []


def evaluate_autonomy_simple(
    success_rate: float,
    intervention_rate: float = 0.0,
) -> float:
    """
    簡易版自律性スコア計算（テスト用・デモ用）
    
    AutonomyScorer の calculate_score() をシンプルなインターフェースでラップした関数。
    最小限の入力（成功率と介入率）で自律性スコアを計算するため、
    プロトタイピングやテスト時に便利です。
    
    実装の詳細：
    - calculate_score() を呼び出してスコアを計算
    - その他のパラメータはデフォルト値で自動設定
    - overall_score（0-100）のみを返す
    
    デフォルト設定:
    - error_recovery_rate: success_rate + 0.1（成功率より若干高い）
    - strategy_switches: 1（戦略変更は最小限）
    - learning_rate: 0.5（50%の学習を仮定）
    - total_attempts: 5（5回の試行を仮定）
    
    使用例1: 基本的な使用
        score = evaluate_autonomy_simple(success_rate=0.95)
        print(score)  # 79.5（自動計算されたスコア）
    
    使用例2: 介入率を含む
        score = evaluate_autonomy_simple(
            success_rate=0.90,
            intervention_rate=0.15
        )
        print(score)  # 介入率を考慮したスコア
    
    Args:
        success_rate: タスク成功率 (0.0-1.0)
            - 0.0: 成功なし
            - 0.5: 50%成功
            - 1.0: 完全成功（100%）
            - 必須パラメータ
        
        intervention_rate: ユーザー介入率 (0.0-1.0、デフォルト=0.0)
            - 0.0: 介入なし（完全自律）
            - 0.5: 50%の決定で介入
            - 1.0: すべての決定で介入
            - 省略可能（デフォルト: 0.0 = 介入なし）
    
    Returns:
        float: 自律性スコア（0-100）
            - 0-19: Dependent（依存的）
            - 20-39: Assisted（支援的）
            - 40-59: Guided（ガイド付き）
            - 60-79: Semi-Autonomous（半自律）
            - 80-100: Autonomous（完全自律）
    
    注意:
    - これは簡易版です。詳細な評価には AutonomyScorer.calculate_score() を直接使用
    - 追加パラメータ（strategy_switches, learning_rate など）をカスタマイズ不可
    - 返却値はスコアのみ（DimensionalAutonomy等の詳細情報は不含）
    """
    # スコアラーをインスタンス化
    scorer = AutonomyScorer()
    
    # calculate_score() を呼び出し、必須パラメータのみを指定
    # その他のパラメータはデフォルト値で自動設定
    score = scorer.calculate_score(
        task_success_rate=success_rate,
        user_intervention_rate=intervention_rate,
        # エラー回復率: 成功率より若干高いと仮定
        error_recovery_rate=min(1.0, success_rate + 0.1),
        # 戦略変更: 最小限（1回）と仮定
        strategy_switches=1,
        # 学習率: 50%の改善を仮定
        learning_rate=0.5,
        # 総試行回数: 5回と仮定
        total_attempts=5,
    )
    
    # 総合スコアのみを返す（0-100）
    return score.overall_score
