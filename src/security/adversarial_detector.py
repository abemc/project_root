"""
敵対的プロンプト検出フレームワーク

ギャップ3: セキュリティ強化のための
敵対的・悪意のあるプロンプトの検出システム
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from enum import Enum
import re


class AdvancedThreatType(Enum):
    """高度な脅威タイプ"""
    PROMPT_INJECTION = "prompt_injection"  # プロンプトインジェクション
    JAILBREAK_ATTEMPT = "jailbreak_attempt"  # ジェイルブレイク試行
    HARMFUL_REQUEST = "harmful_request"  # 有害リクエスト
    MANIPULATION = "manipulation"  # マニピュレーション
    TOXICITY = "toxicity"  # 中毒性/有害性
    SYSTEM_PROMPT_LEAKAGE = "system_prompt_leakage"  # システムプロンプト漏洩試行
    ROLE_PLAY_BYPASS = "role_play_bypass"  # ロールプレイ回避
    ENCODING_BYPASS = "encoding_bypass"  # エンコーディング回避


class ThreatLevel(Enum):
    """脅威レベル"""
    CRITICAL = "critical"  # 重大 (3.0 以上)
    HIGH = "high"  # 高 (2.0-2.99)
    MEDIUM = "medium"  # 中 (1.0-1.99)
    LOW = "low"  # 低 (0.1-0.99)
    NONE = "none"  # なし (0.0)


@dataclass
class AdversarialIndicator:
    """敵対的インジケータ"""
    indicator_type: AdvancedThreatType
    pattern: str
    severity: float  # 0-3 スケール
    description: str
    detected: bool
    context: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class AdversarialAnalysis:
    """敵対的分析結果"""
    prompt_id: str
    threat_level: ThreatLevel
    threat_score: float  # 0-3
    indicators: List[AdversarialIndicator] = field(default_factory=list)
    is_malicious: bool = False
    risk_factors: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class PromptSecurityLog:
    """プロンプトセキュリティログ"""
    log_id: str
    prompt_id: str
    analysis: AdversarialAnalysis
    action_taken: str  # "ALLOWED", "FLAGGED", "BLOCKED"
    user_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


class PromptInjectionDetector:
    """プロンプトインジェクション検出器"""

    def __init__(self):
        self.injection_patterns = [
            # SQL/コマンドインジェクション
            r"(?i)(union|select|insert|update|delete|drop|exec|execute)",
            # シェルコマンド
            r"(?i)(bash|cmd|powershell|sh|\|\||;|\$\(|`)",
            # システムプロンプト露出試行
            r"(?i)(system\s*prompt|system\s*instruction|ignore\s*instruction|override)",
            # 設定ファイル読み込み試行
            r"(?i)(\.env|\.git|config|secret|password|api[_-]?key)",
        ]

    def detect_injection(self, prompt: str) -> List[AdversarialIndicator]:
        """プロンプトインジェクションを検出"""
        results = []
        prompt.lower()

        for pattern in self.injection_patterns:
            if re.search(pattern, prompt):
                matches = len(re.findall(pattern, prompt))
                severity = min(matches * 0.3, 2.5)

                results.append(AdversarialIndicator(
                    indicator_type=AdvancedThreatType.PROMPT_INJECTION,
                    pattern=pattern,
                    severity=severity,
                    description=f"潜在的なプロンプトインジェクションパターン検出: {pattern}",
                    detected=True,
                    context=prompt[:100],
                ))

        return results


class JailbreakDetector:
    """ジェイルブレイク試行検出器"""

    def __init__(self):
        self.jailbreak_patterns = {
            # 逆心理学
            "reverse_psychology": [
                r"(?i)(don't.*answer|you.*can't|you.*won't|pretend|imagine|fiction)",
                r"(?i)(for a story|for entertainment|hypothetically|what if)",
            ],
            # ロールプレイ
            "role_play": [
                r"(?i)(i am|i'm|assume i'm|pretend i'm|you are|act as|be a)",
                r"(?i)(character|persona|roleplay|scenario|fantasy)",
            ],
            # 迂回指示
            "bypass_attempts": [
                r"(?i)(ignore.*instruction|forget.*instruction|new instructions)",
                r"(?i)(override|bypass|disable|deactivate|cancel)",
            ],
        }

    def detect_jailbreak(self, prompt: str) -> List[AdversarialIndicator]:
        """ジェイルブレイク試行を検出"""
        results = []

        for jailbreak_type, patterns in self.jailbreak_patterns.items():
            for pattern in patterns:
                if re.search(pattern, prompt):
                    severity = self._calculate_jailbreak_severity(prompt, pattern)

                    results.append(AdversarialIndicator(
                        indicator_type=AdvancedThreatType.JAILBREAK_ATTEMPT,
                        pattern=pattern,
                        severity=severity,
                        description=f"ジェイルブレイク試行: {jailbreak_type}",
                        detected=True,
                    ))

        return results

    def _calculate_jailbreak_severity(self, prompt: str, pattern: str) -> float:
        """ジェイルブレイク重大度を計算"""
        matches = len(re.findall(pattern, prompt, re.IGNORECASE))

        # 複数のジェイルブレイクパターンの組み合わせを検出
        jailbreak_count = sum(
            1 for patterns in self.jailbreak_patterns.values()
            for p in patterns if re.search(p, prompt)
        )

        return min(matches * 0.3 + jailbreak_count * 0.2, 2.5)


class HarmfulContentDetector:
    """有害コンテンツ検出器"""

    def __init__(self):
        self.harmful_keywords = {
            "violence": [
                "殺害", "暴力", "テロ", "銃", "爆弾", "攻撃",
                "kill", "harm", "hurt", "violence", "bomb"
            ],
            "illegal": [
                "違法", "犯罪", "詐欺", "盗難", "贈収賄",
                "illegal", "drug", "steal", "fraud", "hack"
            ],
            "hate_speech": [
                "差別", "いじめ", "ヘイト", "侮辱",
                "hate", "racist", "discrimination", "slur"
            ],
            "sexual": [
                "性的", "児童", "未成年", "搾取",
                "sexual", "child", "abuse", "exploit"
            ],
        }

    def detect_harmful_content(self, prompt: str) -> List[AdversarialIndicator]:
        """有害コンテンツを検出"""
        results = []
        prompt_lower = prompt.lower()

        for category, keywords in self.harmful_keywords.items():
            found_keywords = [
                kw for kw in keywords if kw.lower() in prompt_lower
            ]

            if found_keywords:
                severity = min(len(found_keywords) * 0.4, 3.0)

                results.append(AdversarialIndicator(
                    indicator_type=AdvancedThreatType.HARMFUL_REQUEST,
                    pattern=f"Category: {category}",
                    severity=severity,
                    description=f"有害コンテンツの可能性: {category}",
                    detected=True,
                    context=str(found_keywords[:3]),
                ))

        return results


class ManipulationDetector:
    """マニピュレーション検出器"""

    def __init__(self):
        self.manipulation_patterns = {
            # 社会的エンジニアリング
            "social_engineering": [
                r"(?i)(authority|urgent|limited\s*time|act\s*now|immediate)",
                r"(?i)(admin|ceo|executive|vip|premium)",
            ],
            # 感情的操作
            "emotional_manipulation": [
                r"(?i)(please help|emergency|desperate|life or death)",
                r"(?i)(must help|have to|need to|critical)",
            ],
            # 誘導的質問
            "leading_questions": [
                r"\?.*\?.*\?",  # 複数の連続する質問
                r"(?i)(certainly|obviously|of course|as you know)",
            ],
        }

    def detect_manipulation(self, prompt: str) -> List[AdversarialIndicator]:
        """マニピュレーションを検出"""
        results = []

        for manip_type, patterns in self.manipulation_patterns.items():
            for pattern in patterns:
                if re.search(pattern, prompt):
                    severity = 1.2

                    results.append(AdversarialIndicator(
                        indicator_type=AdvancedThreatType.MANIPULATION,
                        pattern=pattern,
                        severity=severity,
                        description=f"マニピュレーション検出: {manip_type}",
                        detected=True,
                    ))

        return results


class ToxicityDetector:
    """中毒性・有害性検出器"""

    def __init__(self):
        self.toxicity_patterns = [
            r"(?i)(curse|profanity|swear|offensive|abusive)",
            r"(?i)(stupid|idiot|moron|dumb|worthless)",
            r"(?i)(hell|damn|fuck|shit|crap)",
        ]

    def detect_toxicity(self, prompt: str) -> float:
        """中毒性レベルを計算（0-3）"""
        matches = sum(
            len(re.findall(pattern, prompt))
            for pattern in self.toxicity_patterns
        )

        return min(matches * 0.3, 2.0)


class EncodingBypassDetector:
    """エンコーディング回避検出器"""

    def __init__(self):
        self.encoding_patterns = [
            # ROT13
            r"(?i)(rot13|rot-13)",
            # Base64
            r"(?i)(base64|decode|encode)[\s:=]+[A-Za-z0-9+/=]{20,}",
            # Hex
            r"0x[0-9a-f]{8,}",
            # Unicode escapes
            r"\\u[0-9a-f]{4}",
        ]

    def detect_encoding_bypass(self, prompt: str) -> List[AdversarialIndicator]:
        """エンコーディング回避を検出"""
        results = []

        for pattern in self.encoding_patterns:
            if re.search(pattern, prompt):
                results.append(AdversarialIndicator(
                    indicator_type=AdvancedThreatType.ENCODING_BYPASS,
                    pattern=pattern,
                    severity=0.8,
                    description=f"エンコーディング回避パターン: {pattern}",
                    detected=True,
                ))

        return results


class AdversarialPromptDetector:
    """敵対的プロンプト統合検出器"""

    def __init__(self):
        self.injection_detector = PromptInjectionDetector()
        self.jailbreak_detector = JailbreakDetector()
        self.harmful_detector = HarmfulContentDetector()
        self.manipulation_detector = ManipulationDetector()
        self.toxicity_detector = ToxicityDetector()
        self.encoding_detector = EncodingBypassDetector()

        self.security_logs: Dict[str, PromptSecurityLog] = {}
        self.threat_thresholds = {
            "critical": 2.5,
            "high": 1.5,
            "medium": 0.8,
            "low": 0.1,
        }

    def analyze_prompt(
        self,
        prompt_id: str,
        prompt: str,
        user_id: Optional[str] = None
    ) -> AdversarialAnalysis:
        """
        プロンプトを敵対的分析

        Args:
            prompt_id: プロンプトID
            prompt: 分析対象のプロンプト
            user_id: ユーザーID

        Returns:
            敵対的分析結果
        """
        indicators: List[AdversarialIndicator] = []

        # 各検出器を実行
        indicators.extend(self.injection_detector.detect_injection(prompt))
        indicators.extend(self.jailbreak_detector.detect_jailbreak(prompt))
        indicators.extend(self.harmful_detector.detect_harmful_content(prompt))
        indicators.extend(self.manipulation_detector.detect_manipulation(prompt))
        indicators.extend(self.encoding_detector.detect_encoding_bypass(prompt))

        # 中毒性を計算
        toxicity = self.toxicity_detector.detect_toxicity(prompt)

        # 総合脅威スコアを計算
        threat_score = self._calculate_threat_score(indicators, toxicity)

        # 脅威レベルを判定
        threat_level = self._determine_threat_level(threat_score)

        # 是否悪意があるか判定
        is_malicious = threat_level in [
            ThreatLevel.CRITICAL,
            ThreatLevel.HIGH
        ]

        # リスク要因を特定
        risk_factors = self._identify_risk_factors(indicators, threat_score)

        # 推奨事項を生成
        recommendations = self._generate_recommendations(
            threat_level, indicators
        )

        analysis = AdversarialAnalysis(
            prompt_id=prompt_id,
            threat_level=threat_level,
            threat_score=threat_score,
            indicators=[ind for ind in indicators if ind.detected],
            is_malicious=is_malicious,
            risk_factors=risk_factors,
            recommendations=recommendations,
        )

        # ログに記録
        self._log_analysis(prompt_id, analysis, user_id)

        return analysis

    def _calculate_threat_score(
        self,
        indicators: List[AdversarialIndicator],
        toxicity: float
    ) -> float:
        """脅威スコアを計算"""
        if not indicators:
            threat_score = toxicity
        else:
            max_severity = max((ind.severity for ind in indicators), default=0)
            avg_severity = sum(ind.severity for ind in indicators) / len(indicators)
            threat_score = (max_severity * 0.6 + avg_severity * 0.4) + toxicity * 0.2

        return min(threat_score, 3.0)

    def _determine_threat_level(self, threat_score: float) -> ThreatLevel:
        """脅威レベルを判定"""
        if threat_score >= self.threat_thresholds["critical"]:
            return ThreatLevel.CRITICAL
        elif threat_score >= self.threat_thresholds["high"]:
            return ThreatLevel.HIGH
        elif threat_score >= self.threat_thresholds["medium"]:
            return ThreatLevel.MEDIUM
        elif threat_score > self.threat_thresholds["low"]:
            return ThreatLevel.LOW
        else:
            return ThreatLevel.NONE

    def _identify_risk_factors(
        self,
        indicators: List[AdversarialIndicator],
        threat_score: float
    ) -> List[str]:
        """リスク要因を特定"""
        factors = []

        threat_types_detected = set(ind.indicator_type for ind in indicators)

        if AdvancedThreatType.PROMPT_INJECTION in threat_types_detected:
            factors.append("プロンプトインジェクション潜在性")

        if AdvancedThreatType.JAILBREAK_ATTEMPT in threat_types_detected:
            factors.append("ジェイルブレイク試行の兆候")

        if AdvancedThreatType.HARMFUL_REQUEST in threat_types_detected:
            factors.append("有害コンテンツリクエスト")

        if AdvancedThreatType.MANIPULATION in threat_types_detected:
            factors.append("マニピュレーション試行")

        if AdvancedThreatType.ENCODING_BYPASS in threat_types_detected:
            factors.append("エンコーディング回避の可能性")

        if threat_score > 2.0:
            factors.append("複数の脅威パターン同時検出")

        return factors

    def _generate_recommendations(
        self,
        threat_level: ThreatLevel,
        indicators: List[AdversarialIndicator]
    ) -> List[str]:
        """推奨事項を生成"""
        recommendations = []

        if threat_level == ThreatLevel.CRITICAL:
            recommendations.append("🛑 プロンプトをブロック")
            recommendations.append("🔔 セキュリティチームに通知")
            recommendations.append("📝 ユーザーアクティビティを記録")

        elif threat_level == ThreatLevel.HIGH:
            recommendations.append("⚠️ プロンプトに警告フラグ")
            recommendations.append("👁️ 追加の人間レビュー推奨")
            recommendations.append("📊 分析ログに記録")

        elif threat_level == ThreatLevel.MEDIUM:
            recommendations.append("🔍 文脈を確認してから処理")
            recommendations.append("📝 分析結果をログに記録")

        else:
            recommendations.append("✅ 標準的な処理を続行")

        return recommendations

    def _log_analysis(
        self,
        prompt_id: str,
        analysis: AdversarialAnalysis,
        user_id: Optional[str]
    ):
        """分析結果をログに記録"""
        log_id = f"sec_log_{prompt_id}_{int(datetime.now().timestamp())}"

        # アクション判定
        if analysis.is_malicious:
            action = "BLOCKED"
        elif analysis.threat_level in [
            ThreatLevel.HIGH,
            ThreatLevel.MEDIUM
        ]:
            action = "FLAGGED"
        else:
            action = "ALLOWED"

        log = PromptSecurityLog(
            log_id=log_id,
            prompt_id=prompt_id,
            analysis=analysis,
            action_taken=action,
            user_id=user_id,
        )

        self.security_logs[log_id] = log

    def get_security_report(self, hours: int = 24) -> Dict[str, Any]:
        """セキュリティレポートを生成"""
        now = datetime.now()
        cutoff_time = now - timedelta(hours=hours)

        relevant_logs = [
            log for log in self.security_logs.values()
            if log.timestamp >= cutoff_time
        ]

        blocked_count = sum(
            1 for log in relevant_logs if log.action_taken == "BLOCKED"
        )
        flagged_count = sum(
            1 for log in relevant_logs if log.action_taken == "FLAGGED"
        )

        avg_threat_score = (
            sum(log.analysis.threat_score for log in relevant_logs) /
            len(relevant_logs)
            if relevant_logs else 0.0
        )

        return {
            "period_hours": hours,
            "total_analyses": len(relevant_logs),
            "blocked_count": blocked_count,
            "flagged_count": flagged_count,
            "allowed_count": len(relevant_logs) - blocked_count - flagged_count,
            "average_threat_score": avg_threat_score,
            "threat_types_detected": self._get_threat_type_distribution(
                relevant_logs
            ),
            "timestamp": now.isoformat(),
        }

    def _get_threat_type_distribution(
        self,
        logs: List[PromptSecurityLog]
    ) -> Dict[str, int]:
        """脅威タイプの分布を取得"""
        distribution: Dict[str, int] = {}

        for log in logs:
            for indicator in log.analysis.indicators:
                threat_type = indicator.indicator_type.value
                distribution[threat_type] = distribution.get(threat_type, 0) + 1

        return distribution

    def export_security_logs(self) -> Dict[str, Any]:
        """セキュリティログをエクスポート"""
        return {
            "total_logs": len(self.security_logs),
            "logs": [
                {
                    "log_id": log.log_id,
                    "prompt_id": log.prompt_id,
                    "threat_level": log.analysis.threat_level.value,
                    "threat_score": log.analysis.threat_score,
                    "action_taken": log.action_taken,
                    "timestamp": log.timestamp.isoformat(),
                }
                for log in self.security_logs.values()
            ],
        }

    def reset_logs(self):
        """ログをリセット"""
        self.security_logs.clear()
