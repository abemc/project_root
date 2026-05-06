"""
Phase 10: インテリジェント セキュリティ運用プラットフォーム

24/7 Security Operations Center + 次世代認証 + ML脅威検出 + グローバル統合

モジュール構成:
- Step 1: 24_7_soc - Security Operations Center エンジン
- Step 2: next_gen_auth - FIDO2 + 生体認証エンジン
- Step 3: threat_detection - ML駆動型脅威検出
- Step 4: global_security - グローバル統合プラットフォーム
"""

from datetime import datetime

__version__ = "1.0.0"
__phase__ = "Phase 10"
__title__ = "Intelligent Security Operations Platform"
__release_date__ = datetime(2026, 4, 15)

# 24/7 SOC インポート
from .soc_24_7 import (
    SecurityOperationsCenter,
    EventProcessor,
    ThreatClassifier,
    AutoResponder,
    EscalationManager,
    SecurityEvent,
    Incident,
    ThreatSignal,
    ThreatLevel,
    EventType,
    ResponseAction
)

from .soc_24_7_components import (
    EventCollector,
    RealtimeAnalyzer,
    CorrelationEngine,
    IncidentGenerator,
    SOCDashboard
)

# 次世代認証インポート
from .next_gen_auth import (
    FIDO2AuthEngine,
    BiometricAuthEngine,
    AdaptiveAuthStrategy,
    DeviceTrustVerifier,
    FIDO2Credential,
    BiometricTemplate,
    AuthenticationSession,
    UserAuthContext,
    AuthenticationMethod,
    BiometricType,
    UserRiskLevel
)

from .next_gen_auth_components import (
    WebAuthnLibWrapper,
    BiometricTemplateManager,
    DeviceTrustManager,
    AuthenticationSessionManager
)

# ML脅威検出インポート
from .threat_detection import (
    AnomalyDetector,
    BehaviorProfiler,
    ThreatPredictor,
    MLPipelineManager,
    AnomalyDetectionResult,
    BehavioralProfile,
    ThreatPrediction
)

# グローバル統合インポート
from .global_security import (
    GlobalSecurityOrchestrator,
    RegionalSecurityManager,
    GlobalPolicyEngine,
    ComplianceEngine,
    SecurityMetricsAggregator,
    Region,
    RegulatoryFramework,
    RegionalSecurityConfig,
    GlobalSecurityPolicy,
    ComplianceStatus
)

__all__ = [
    # Phase 10 メタデータ
    '__version__',
    '__phase__',
    '__title__',
    '__release_date__',
    
    # SOC コンポーネント
    'SecurityOperationsCenter',
    'EventProcessor',
    'ThreatClassifier',
    'AutoResponder',
    'EscalationManager',
    'EventCollector',
    'RealtimeAnalyzer',
    'CorrelationEngine',
    'IncidentGenerator',
    'SOCDashboard',
    
    # 認証コンポーネント
    'FIDO2AuthEngine',
    'BiometricAuthEngine',
    'AdaptiveAuthStrategy',
    'DeviceTrustVerifier',
    'WebAuthnLibWrapper',
    'BiometricTemplateManager',
    'DeviceTrustManager',
    'AuthenticationSessionManager',
    'AuthenticationMethod',
    'BiometricType',
    'UserRiskLevel',
    'FIDO2Credential',
    'BiometricTemplate',
    'AuthenticationSession',
    'UserAuthContext',
    
    # ML脅威検出
    'AnomalyDetector',
    'BehaviorProfiler',
    'ThreatPredictor',
    'MLPipelineManager',
    
    # グローバル統合
    'GlobalSecurityOrchestrator',
    'RegionalSecurityManager',
    'GlobalPolicyEngine',
    'ComplianceEngine',
    'SecurityMetricsAggregator',
    'Region',
    'RegulatoryFramework',
]
