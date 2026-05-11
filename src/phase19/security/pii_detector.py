"""
PII検出・マスキング実装

個人識別情報（PII）の自動検出と保護
- メールアドレス検出
- 電話番号検出
- 社会保障番号（SSN）検出
- クレジットカード番号検出
- IP アドレス検出
- 個人名検出・トークン化
- リスク評価
"""

import re
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Pattern
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


class PIIType(Enum):
    """PII タイプ"""
    EMAIL = "email"
    PHONE = "phone"
    SSN = "ssn"
    CREDIT_CARD = "credit_card"
    IP_ADDRESS = "ip_address"
    PERSON_NAME = "person_name"
    UNKNOWN = "unknown"


class RiskLevel(Enum):
    """リスクレベル"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class MaskingStrategy(Enum):
    """マスキング戦略"""
    HIDE_ALL = "hide_all"              # xxxxxxxx
    SHOW_FIRST = "show_first"          # xxx@example.com
    SHOW_LAST = "show_last"            # xxxxxxxx@xxxxx.com
    SHOW_EDGES = "show_edges"          # x***x
    REPLACE_CHAR = "replace_char"      # <PII>
    HASH = "hash"                       # <HASH_abc123>


@dataclass
class PIIMatch:
    """PII マッチ結果"""
    pii_type: PIIType
    value: str
    position: int
    length: int
    risk_level: RiskLevel
    context: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "pii_type": self.pii_type.value,
            "position": self.position,
            "length": self.length,
            "risk_level": self.risk_level.value,
            "context": self.context,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class MaskResult:
    """マスキング結果"""
    original: str
    masked: str
    pii_count: int
    risk_level: RiskLevel
    details: List[PIIMatch] = field(default_factory=list)


@dataclass
class PIIMetrics:
    """PII メトリクス"""
    total_scanned: int = 0
    total_pii_found: int = 0
    total_masked: int = 0
    by_type: Dict[str, int] = field(default_factory=dict)
    by_risk: Dict[str, int] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "total_scanned": self.total_scanned,
            "total_pii_found": self.total_pii_found,
            "total_masked": self.total_masked,
            "by_type": self.by_type,
            "by_risk": self.by_risk,
        }


class PIIDetector:
    """PII検出・マスキング"""
    
    def __init__(self):
        """初期化"""
        self.patterns: Dict[PIIType, Pattern] = self._compile_patterns()
        self.metrics = PIIMetrics()
    
    def _compile_patterns(self) -> Dict[PIIType, Pattern]:
        """正規表現パターンをコンパイル"""
        return {
            # メールアドレス
            PIIType.EMAIL: re.compile(
                r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b',
                re.IGNORECASE
            ),
            # 電話番号 (xxx-xxxx-xxxx)
            PIIType.PHONE: re.compile(
                r'\b(?:\d{3}-\d{4}-\d{4}|\d{3}-\d{3}-\d{4}|0\d{1,4}-\d{1,4}-\d{4})\b'
            ),
            # SSN (xxx-xx-xxxx)
            PIIType.SSN: re.compile(
                r'\b\d{3}-\d{2}-\d{4}\b'
            ),
            # クレジットカード番号
            PIIType.CREDIT_CARD: re.compile(
                r'\b\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{4}\b'
            ),
            # IP アドレス
            PIIType.IP_ADDRESS: re.compile(
                r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b'
            ),
        }
    
    def detect(self, text: str) -> List[PIIMatch]:
        """テキストからPIIを検出"""
        self.metrics.total_scanned += 1
        matches = []
        
        for pii_type, pattern in self.patterns.items():
            for match in pattern.finditer(text):
                value = match.group(0)
                position = match.start()
                length = len(value)
                
                # リスクレベルを評価
                risk_level = self._evaluate_risk(pii_type, value)
                
                # コンテキストを抽出
                context_start = max(0, position - 20)
                context_end = min(len(text), position + length + 20)
                context = text[context_start:context_end]
                
                pii_match = PIIMatch(
                    pii_type=pii_type,
                    value=value,
                    position=position,
                    length=length,
                    risk_level=risk_level,
                    context=context,
                )
                
                matches.append(pii_match)
                
                # メトリクス更新
                self.metrics.total_pii_found += 1
                type_key = pii_type.value
                self.metrics.by_type[type_key] = self.metrics.by_type.get(type_key, 0) + 1
                risk_key = risk_level.value
                self.metrics.by_risk[risk_key] = self.metrics.by_risk.get(risk_key, 0) + 1
        
        return matches
    
    def _evaluate_risk(self, pii_type: PIIType, value: str) -> RiskLevel:
        """リスクレベルを評価"""
        risk_map = {
            PIIType.EMAIL: RiskLevel.MEDIUM,
            PIIType.PHONE: RiskLevel.HIGH,
            PIIType.SSN: RiskLevel.CRITICAL,
            PIIType.CREDIT_CARD: RiskLevel.CRITICAL,
            PIIType.IP_ADDRESS: RiskLevel.LOW,
            PIIType.PERSON_NAME: RiskLevel.MEDIUM,
        }
        return risk_map.get(pii_type, RiskLevel.MEDIUM)
    
    def mask(
        self,
        text: str,
        strategy: MaskingStrategy = MaskingStrategy.REPLACE_CHAR,
        detect_all_types: bool = True
    ) -> MaskResult:
        """テキストをマスキング"""
        # PII検出
        matches = self.detect(text)
        
        if not matches:
            self.metrics.total_scanned += 1
            return MaskResult(
                original=text,
                masked=text,
                pii_count=0,
                risk_level=RiskLevel.LOW,
                details=[]
            )
        
        # マスキング実行
        masked_text = text
        overall_risk = RiskLevel.LOW
        
        # 逆順でマスキング（位置がずれないように）
        for match in sorted(matches, key=lambda m: m.position, reverse=True):
            masked_value = self._apply_mask_strategy(match.value, strategy)
            masked_text = (
                masked_text[:match.position] +
                masked_value +
                masked_text[match.position + match.length:]
            )
            
            # リスクレベルを更新
            if match.risk_level.value == RiskLevel.CRITICAL.value:
                overall_risk = RiskLevel.CRITICAL
            elif match.risk_level.value == RiskLevel.HIGH.value and overall_risk != RiskLevel.CRITICAL:
                overall_risk = RiskLevel.HIGH
            elif match.risk_level.value == RiskLevel.MEDIUM.value and overall_risk == RiskLevel.LOW:
                overall_risk = RiskLevel.MEDIUM
        
        # メトリクス更新
        self.metrics.total_scanned += 1
        self.metrics.total_masked += len(matches)
        
        logger.info(f"Masked {len(matches)} PII instances")
        
        return MaskResult(
            original=text,
            masked=masked_text,
            pii_count=len(matches),
            risk_level=overall_risk,
            details=matches
        )
    
    def _apply_mask_strategy(self, value: str, strategy: MaskingStrategy) -> str:
        """マスキング戦略を適用"""
        if strategy == MaskingStrategy.HIDE_ALL:
            return "x" * len(value)
        
        elif strategy == MaskingStrategy.SHOW_FIRST:
            if len(value) <= 3:
                return "x" * len(value)
            return value[:3] + "x" * (len(value) - 3)
        
        elif strategy == MaskingStrategy.SHOW_LAST:
            if len(value) <= 3:
                return "x" * len(value)
            return "x" * (len(value) - 3) + value[-3:]
        
        elif strategy == MaskingStrategy.SHOW_EDGES:
            if len(value) <= 2:
                return "x" * len(value)
            return value[0] + "x" * (len(value) - 2) + value[-1]
        
        elif strategy == MaskingStrategy.REPLACE_CHAR:
            return "<PII>"
        
        elif strategy == MaskingStrategy.HASH:
            import hashlib
            hash_val = hashlib.md5(value.encode()).hexdigest()[:6]
            return f"<HASH_{hash_val}>"
        
        else:
            return "x" * len(value)
    
    def mask_email(self, email: str, strategy: MaskingStrategy = MaskingStrategy.SHOW_FIRST) -> str:
        """メールアドレスをマスキング"""
        if "@" not in email:
            return email
        
        local, domain = email.split("@", 1)
        masked_local = self._apply_mask_strategy(local, strategy)
        return f"{masked_local}@{domain}"
    
    def mask_phone(self, phone: str, show_last: int = 4) -> str:
        """電話番号をマスキング"""
        digits = re.sub(r'\D', '', phone)
        if len(digits) < show_last:
            return "x" * len(digits)
        masked = "x" * (len(digits) - show_last) + digits[-show_last:]
        return masked
    
    def mask_credit_card(self, card: str) -> str:
        """クレジットカード番号をマスキング"""
        digits = re.sub(r'\D', '', card)
        if len(digits) < 4:
            return "x" * len(digits)
        masked = "x" * (len(digits) - 4) + digits[-4:]
        return masked
    
    def assess_risk(self, text: str) -> Dict[str, Any]:
        """テキストのリスクを評価"""
        matches = self.detect(text)
        
        if not matches:
            return {
                "overall_risk": RiskLevel.LOW.value,
                "critical_count": 0,
                "high_count": 0,
                "medium_count": 0,
                "low_count": 0,
                "details": []
            }
        
        risk_counts = {
            RiskLevel.CRITICAL: 0,
            RiskLevel.HIGH: 0,
            RiskLevel.MEDIUM: 0,
            RiskLevel.LOW: 0,
        }
        
        for match in matches:
            risk_counts[match.risk_level] += 1
        
        # 全体リスクを決定
        if risk_counts[RiskLevel.CRITICAL] > 0:
            overall_risk = RiskLevel.CRITICAL
        elif risk_counts[RiskLevel.HIGH] > 0:
            overall_risk = RiskLevel.HIGH
        elif risk_counts[RiskLevel.MEDIUM] > 0:
            overall_risk = RiskLevel.MEDIUM
        else:
            overall_risk = RiskLevel.LOW
        
        return {
            "overall_risk": overall_risk.value,
            "critical_count": risk_counts[RiskLevel.CRITICAL],
            "high_count": risk_counts[RiskLevel.HIGH],
            "medium_count": risk_counts[RiskLevel.MEDIUM],
            "low_count": risk_counts[RiskLevel.LOW],
            "details": [m.to_dict() for m in matches]
        }
    
    def get_metrics(self) -> PIIMetrics:
        """メトリクスを取得"""
        return self.metrics
    
    def get_metrics_dict(self) -> Dict[str, Any]:
        """メトリクスを辞書形式で取得"""
        return self.metrics.to_dict()
    
    def reset_metrics(self) -> None:
        """メトリクスをリセット"""
        self.metrics = PIIMetrics()


# グローバルインスタンス
_global_detector: Optional[PIIDetector] = None


def get_pii_detector() -> PIIDetector:
    """グローバル PII 検出器を取得"""
    global _global_detector
    if _global_detector is None:
        _global_detector = PIIDetector()
    return _global_detector
