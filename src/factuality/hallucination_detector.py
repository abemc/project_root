"""
Hallucination検出エンジン
モデル生成テキスト内の不正確さを検出
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple, Set
import logging

logger = logging.getLogger(__name__)


class HallucinationType(Enum):
    """Hallucination のタイプ"""
    FACTUAL = "factual"  # 事実エラー
    LOGICAL = "logical"  # 論理エラー
    NUMERICAL = "numerical"  # 数値エラー
    TEMPORAL = "temporal"  # 時間的矛盾
    ENTITY_CONFUSION = "entity_confusion"  # エンティティ混同
    STYLE_INCONSISTENCY = "style_inconsistency"  # スタイル不一致
    REPETITION = "repetition"  # 繰り返し
    SELF_CONTRADICTION = "self_contradiction"  # 自己矛盾


@dataclass
class HallucinationInstance:
    """Hallucination インスタンス"""
    text: str
    type: HallucinationType
    severity: float  # 0-1 (1 = 最も深刻)
    explanation: str
    start_pos: int
    end_pos: int
    suggested_correction: Optional[str] = None
    confidence: float = 1.0


@dataclass
class HallucinationReport:
    """Hallucination 検査レポート"""
    text: str
    hallucination_count: int = 0
    hallucination_instances: List[HallucinationInstance] = field(default_factory=list)
    hallucination_rate: float = 0.0  # 0-1
    severity_score: float = 0.0  # 平均重要度
    is_hallucinatory: bool = False  # 重大なhallucination検出
    recommendations: List[str] = field(default_factory=list)


class SelfConsistencyChecker:
    """テキスト内の自己矛盾を検出"""
    
    @staticmethod
    def check_contradictions(text: str) -> List[Tuple[str, str, float]]:
        """
        テキスト内の矛盾を検出
        
        Returns:
            [(claim1, claim2, contradiction_score), ...]
        """
        contradictions = []
        
        # 文分割
        sentences = text.split('.')
        
        # 簡単な矛盾検出（キーワードベース）
        negation_keywords = ["not", "never", "no", "don't", "isn't", "doesn't"]
        
        for i, sent1 in enumerate(sentences):
            for j, sent2 in enumerate(sentences[i+1:], start=i+1):
                sent1_lower = sent1.lower()
                sent2_lower = sent2.lower()
                
                # 共通キーワードを探す
                words_in_sent1 = set(sent1_lower.split())
                words_in_sent2 = set(sent2_lower.split())
                
                common_words = words_in_sent1 & words_in_sent2
                
                # 一方は否定、もう一方は肯定の場合
                sent1_has_negation = any(neg in sent1_lower for neg in negation_keywords)
                sent2_has_negation = any(neg in sent2_lower for neg in negation_keywords)
                
                if sent1_has_negation != sent2_has_negation and len(common_words) > 2:
                    contradiction_score = len(common_words) / max(len(words_in_sent1), len(words_in_sent2))
                    contradictions.append((sent1.strip(), sent2.strip(), contradiction_score))
        
        return contradictions
    
    @staticmethod
    def check_factual_consistency(text: str, knowledge_base: Optional[Dict] = None) -> List[HallucinationInstance]:
        """
        事実的一貫性をチェック（簡略版）
        """
        instances = []
        
        # デモ用の既知の不正確な事実
        false_facts = {
            "Paris is the capital of Germany": "Paris is the capital of France",
            "Tokyo is in China": "Tokyo is the capital of Japan",
            "the Earth is flat": "the Earth is spherical",
            "2+2=5": "2+2=4",
        }
        
        text_lower = text.lower()
        for false_fact, correction in false_facts.items():
            if false_fact.lower() in text_lower:
                start = text_lower.find(false_fact.lower())
                end = start + len(false_fact)
                
                instances.append(HallucinationInstance(
                    text=false_fact,
                    type=HallucinationType.FACTUAL,
                    severity=0.9,
                    explanation=f"Factual error: {false_fact}",
                    start_pos=start,
                    end_pos=end,
                    suggested_correction=correction,
                    confidence=0.95,
                ))
        
        return instances


class EntityConsistencyChecker:
    """エンティティの一貫性をチェック"""
    
    def __init__(self):
        # エンティティの属性
        self.entity_properties = {
            "Paris": {"country": "France", "type": "city"},
            "Tokyo": {"country": "Japan", "type": "city"},
            "France": {"continent": "Europe", "type": "country"},
            "Japan": {"continent": "Asia", "type": "country"},
        }
    
    def check_entity_attributes(self, text: str) -> List[HallucinationInstance]:
        """エンティティの属性が一貫しているかチェック"""
        instances = []
        
        # テキストから述文を抽出
        # 例: "Paris is in Germany" -> "Paris" is in "Germany"
        
        for entity, properties in self.entity_properties.items():
            if entity in text:
                # よくある属性エラーをチェック
                for prop_key, correct_value in properties.items():
                    # 不正な属性の検出（簡略版）
                    if prop_key == "country":
                        wrong_values = {
                            "Paris": ["Germany", "Italy", "Spain", "Japan"],
                            "Tokyo": ["China", "South Korea", "Thailand"],
                        }
                        
                        if entity in wrong_values:
                            for wrong_value in wrong_values[entity]:
                                if f"{entity} is in {wrong_value}" in text:
                                    instances.append(HallucinationInstance(
                                        text=f"{entity} is in {wrong_value}",
                                        type=HallucinationType.ENTITY_CONFUSION,
                                        severity=0.85,
                                        explanation=f"{entity} is actually in {correct_value}, not {wrong_value}",
                                        start_pos=text.find(f"{entity} is in {wrong_value}"),
                                        end_pos=text.find(f"{entity} is in {wrong_value}") + len(f"{entity} is in {wrong_value}"),
                                        suggested_correction=f"{entity} is in {correct_value}",
                                    ))
        
        return instances


class RepetitionDetector:
    """テキストの過度な繰り返しを検出"""
    
    @staticmethod
    def detect_repetitions(text: str, window_size: int = 50) -> List[HallucinationInstance]:
        """
        window_size文字以内で、同じフレーズが繰り返されているかを検出
        """
        instances = []
        
        words = text.split()
        
        for i in range(len(words) - 5):
            phrase = ' '.join(words[i:i+5])
            
            # 以降のテキストで同じフレーズを検索
            remaining_text = ' '.join(words[i+1:i+20])
            
            if phrase in remaining_text:
                instances.append(HallucinationInstance(
                    text=phrase,
                    type=HallucinationType.REPETITION,
                    severity=0.6,
                    explanation=f"Repetitive phrase detected: '{phrase}'",
                    start_pos=-1,  # 実装省略
                    end_pos=-1,
                    confidence=0.8,
                ))
        
        return instances


class NumericalConsistencyChecker:
    """数値の一貫性をチェック"""
    
    import re
    
    @staticmethod
    def extract_numbers(text: str) -> List[Tuple[str, int, int]]:
        """テキストから数値を抽出"""
        import re
        numbers = []
        for match in re.finditer(r'\d+(?:\.\d+)?', text):
            numbers.append((match.group(), match.start(), match.end()))
        return numbers
    
    def check_numerical_consistency(self, text: str) -> List[HallucinationInstance]:
        """数値の一貫性をチェック"""
        instances = []
        
        import re
        numbers = self.extract_numbers(text)
        
        # 矛盾する数値の例
        # 例: "人口は1000万人です。2億人の都市です。"
        
        # 簡略版: 同じエンティティに対して異なる数値が使用されている場合
        if len(numbers) >= 2:
            # デモ用: 特定の矛盾パターンをチェック
            if "Paris" in text and "population" in text:
                paris_populations = re.findall(r'(?:Paris|Paris population).*?(\d+)', text)
                if len(set(paris_populations)) > 1:
                    instances.append(HallucinationInstance(
                        text=f"Conflicting population figures for Paris: {paris_populations}",
                        type=HallucinationType.NUMERICAL,
                        severity=0.7,
                        explanation="Multiple conflicting population numbers found",
                        start_pos=-1,
                        end_pos=-1,
                    ))
        
        return instances


class HallucinationDetector:
    """メインHallucination検出器"""
    
    def __init__(self):
        self.consistency_checker = SelfConsistencyChecker()
        self.entity_checker = EntityConsistencyChecker()
        self.repetition_detector = RepetitionDetector()
        self.numerical_checker = NumericalConsistencyChecker()
    
    def detect_hallucinations(self, text: str) -> HallucinationReport:
        """テキスト内のhallucination全体を検出"""
        
        all_instances: List[HallucinationInstance] = []
        
        # 1. 自己矛盾チェック
        contradictions = self.consistency_checker.check_contradictions(text)
        for sent1, sent2, score in contradictions:
            if score > 0.5:
                all_instances.append(HallucinationInstance(
                    text=f"{sent1} vs {sent2}",
                    type=HallucinationType.SELF_CONTRADICTION,
                    severity=min(1.0, score),
                    explanation="Self-contradictory statements detected",
                    start_pos=text.find(sent1),
                    end_pos=text.find(sent2) + len(sent2),
                ))
        
        # 2. 事実的一貫性チェック
        factual_instances = self.consistency_checker.check_factual_consistency(text)
        all_instances.extend(factual_instances)
        
        # 3. エンティティ一貫性チェック
        entity_instances = self.entity_checker.check_entity_attributes(text)
        all_instances.extend(entity_instances)
        
        # 4. 繰り返しチェック
        repetition_instances = self.repetition_detector.detect_repetitions(text)
        all_instances.extend(repetition_instances[:3])  # 上位3つのみ
        
        # 5. 数値一貫性チェック
        numerical_instances = self.numerical_checker.check_numerical_consistency(text)
        all_instances.extend(numerical_instances)
        
        # 重み付けによる重要度ソート
        all_instances.sort(key=lambda x: x.severity, reverse=True)
        
        # レポート生成
        hallucination_count = len(all_instances)
        word_count = len(text.split())
        hallucination_rate = hallucination_count / max(1, word_count / 10)  # 10単語ごと
        hallucination_rate = min(1.0, hallucination_rate)
        
        severity_score = sum(inst.severity for inst in all_instances) / max(1, hallucination_count)
        
        # 推奨事項を生成
        recommendations = self._generate_recommendations(all_instances, hallucination_rate)
        
        report = HallucinationReport(
            text=text,
            hallucination_count=hallucination_count,
            hallucination_instances=all_instances,
            hallucination_rate=hallucination_rate,
            severity_score=severity_score,
            is_hallucinatory=hallucination_rate > 0.3 or severity_score > 0.7,
            recommendations=recommendations,
        )
        
        return report
    
    def _generate_recommendations(
        self,
        instances: List[HallucinationInstance],
        hallucination_rate: float,
    ) -> List[str]:
        """推奨事項を生成"""
        recommendations = []
        
        if not instances:
            recommendations.append("✓ No hallucinations detected")
            return recommendations
        
        if hallucination_rate > 0.5:
            recommendations.append("⚠ High hallucination rate - consider regenerating with lower temperature")
        
        # タイプ別の推奨事項
        factual_hallucinations = [i for i in instances if i.type == HallucinationType.FACTUAL]
        if factual_hallucinations:
            recommendations.append(f"✓ {len(factual_hallucinations)} factual errors detected - verify with knowledge base")
        
        entity_confusions = [i for i in instances if i.type == HallucinationType.ENTITY_CONFUSION]
        if entity_confusions:
            recommendations.append(f"✓ {len(entity_confusions)} entity confusions - improve entity embeddings")
        
        contradictions = [i for i in instances if i.type == HallucinationType.SELF_CONTRADICTION]
        if contradictions:
            recommendations.append(f"✓ {len(contradictions)} self-contradictions - improve consistency checking")
        
        return recommendations
    
    def get_hallucination_rate(self, text: str) -> float:
        """テキストのhallucination率を取得"""
        report = self.detect_hallucinations(text)
        return report.hallucination_rate
    
    def correct_hallucinations(self, text: str) -> str:
        """hallucination を検出して修正を試みる"""
        report = self.detect_hallucinations(text)
        
        corrected_text = text
        # 最も重要なhallucination から修正
        for instance in report.hallucination_instances[:5]:
            if instance.suggested_correction:
                corrected_text = corrected_text.replace(
                    instance.text,
                    instance.suggested_correction,
                )
        
        return corrected_text
