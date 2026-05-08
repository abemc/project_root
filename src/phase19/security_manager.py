"""
統合セキュリティ管理

セキュリティコンポーネント統合管理システム
- 暗号化エンジン管理
- PII検出・マスキング
- 監査ログ
- コンプライアンス
- ポリシー管理
"""

import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime

from src.phase19.security.encryption_engine import (
    CryptoEngine,
    EncryptionConfig,
    initialize_crypto,
)
from src.phase19.security.pii_detector import (
    PIIDetector,
    MaskingStrategy,
)
from src.phase19.security.audit_log import (
    AuditLog,
    EventType,
    Severity,
)
from src.phase19.security.compliance import (
    ComplianceChecker,
    GDPRRight,
)

logger = logging.getLogger(__name__)


@dataclass
class SecurityPolicy:
    """セキュリティポリシー"""
    name: str
    description: str
    encryption_enabled: bool = True
    pii_masking_enabled: bool = True
    audit_logging_enabled: bool = True
    compliance_mode: str = "strict"  # "strict", "moderate", "permissive"
    password_policy: Dict[str, Any] = field(default_factory=dict)
    data_retention_days: int = 90


@dataclass
class SecurityEvent:
    """セキュリティイベント"""
    timestamp: datetime
    event_type: str
    severity: str
    message: str
    details: Dict[str, Any] = field(default_factory=dict)


class SecurityManager:
    """統合セキュリティ管理"""
    
    def __init__(self, config: Optional[EncryptionConfig] = None):
        """初期化"""
        self.crypto_engine = CryptoEngine(config or EncryptionConfig())
        self.pii_detector = PIIDetector()
        self.audit_log = AuditLog()
        self.compliance_checker = ComplianceChecker()
        
        self.policies: Dict[str, SecurityPolicy] = {}
        self.security_events: List[SecurityEvent] = []
        self.incident_handlers: List[callable] = []
        
        logger.info("SecurityManager initialized")
    
    # ========================================================================
    # 暗号化管理
    # ========================================================================
    
    def initialize_encryption(self, master_key: Optional[bytes] = None) -> bool:
        """暗号化を初期化"""
        try:
            self.crypto_engine.key_manager.generate_master_key() if not master_key else self.crypto_engine.key_manager.set_master_key(master_key)
            self.crypto_engine.key_manager.generate_rsa_keypair()
            
            self.audit_log.log_security_event(
                user_id="system",
                action="encryption_initialized",
                severity=Severity.INFO
            )
            
            logger.info("Encryption initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Encryption initialization failed: {e}")
            return False
    
    def encrypt_data(self, data: str) -> str:
        """データを暗号化"""
        return self.crypto_engine.encrypt(data)
    
    def decrypt_data(self, encrypted_data: str) -> str:
        """データを復号化"""
        return self.crypto_engine.decrypt(encrypted_data)
    
    def encrypt_with_public_key(self, data: str) -> str:
        """公開鍵でデータを暗号化"""
        return self.crypto_engine.encrypt_with_rsa(data)
    
    def decrypt_with_private_key(self, encrypted_data: str) -> str:
        """秘密鍵でデータを復号化"""
        return self.crypto_engine.decrypt_with_rsa(encrypted_data)
    
    def hash_password(self, password: str):
        """パスワードをハッシュ化"""
        return self.crypto_engine.hash_password(password)
    
    def verify_password(self, password: str, hash_b64: str, salt_b64: str) -> bool:
        """パスワードを検証"""
        return self.crypto_engine.verify_password(password, hash_b64, salt_b64)
    
    # ========================================================================
    # PII管理
    # ========================================================================
    
    def detect_pii(self, text: str) -> Dict[str, Any]:
        """PIIを検出"""
        matches = self.pii_detector.detect(text)
        return {
            "pii_found": len(matches) > 0,
            "count": len(matches),
            "details": [m.to_dict() for m in matches]
        }
    
    def mask_pii(self, text: str, strategy: str = "replace_char") -> Dict[str, Any]:
        """PIIをマスキング"""
        strategy_map = {
            "replace_char": MaskingStrategy.REPLACE_CHAR,
            "show_first": MaskingStrategy.SHOW_FIRST,
            "show_last": MaskingStrategy.SHOW_LAST,
            "hide_all": MaskingStrategy.HIDE_ALL,
        }
        
        strategy_obj = strategy_map.get(strategy, MaskingStrategy.REPLACE_CHAR)
        result = self.pii_detector.mask(text, strategy=strategy_obj)
        
        return {
            "original": result.original,
            "masked": result.masked,
            "pii_count": result.pii_count,
            "risk_level": result.risk_level.value,
        }
    
    def assess_pii_risk(self, text: str) -> Dict[str, Any]:
        """PIIリスクを評価"""
        return self.pii_detector.assess_risk(text)
    
    # ========================================================================
    # 監査ログ管理
    # ========================================================================
    
    def log_user_action(
        self,
        user_id: str,
        resource_type: str,
        resource_id: str,
        action: str,
        status: str = "success",
        details: Optional[Dict] = None,
        **kwargs
    ):
        """ユーザー操作をログ"""
        event_type_map = {
            "create": EventType.CREATE,
            "read": EventType.READ,
            "update": EventType.UPDATE,
            "delete": EventType.DELETE,
        }
        
        event_type = event_type_map.get(action, EventType.OTHER)
        
        return self.audit_log.log_event(
            event_type=event_type,
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            status=status,
            details=details or {},
            **kwargs
        )
    
    def get_user_audit_trail(self, user_id: str, limit: int = 100) -> List[Dict]:
        """ユーザーの監査証跡を取得"""
        return self.audit_log.get_user_audit_trail(user_id, limit)
    
    def get_audit_report(self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> Dict:
        """監査レポートを生成"""
        return self.audit_log.generate_audit_report(start_date, end_date)
    
    # ========================================================================
    # コンプライアンス管理
    # ========================================================================
    
    def create_gdpr_access_request(self, user_id: str) -> Dict[str, Any]:
        """GDPR アクセス権リクエストを作成"""
        request = self.compliance_checker.gdpr.create_access_request(user_id)
        
        self.audit_log.log_security_event(
            user_id=user_id,
            action="gdpr_access_requested",
            severity=Severity.INFO,
            details={"request_id": request.request_id}
        )
        
        return request.to_dict()
    
    def create_gdpr_deletion_request(self, user_id: str) -> Dict[str, Any]:
        """GDPR 削除権リクエストを作成"""
        request = self.compliance_checker.gdpr.create_deletion_request(user_id)
        
        self.audit_log.log_security_event(
            user_id=user_id,
            action="gdpr_deletion_requested",
            severity=Severity.WARNING,
            details={"request_id": request.request_id}
        )
        
        return request.to_dict()
    
    def get_compliance_status(self) -> Dict[str, Any]:
        """コンプライアンスステータスを取得"""
        return self.compliance_checker.check_overall_compliance().to_dict()
    
    def get_compliance_report(self) -> Dict[str, Any]:
        """コンプライアンスレポートを生成"""
        return self.compliance_checker.generate_compliance_report()
    
    # ========================================================================
    # ポリシー管理
    # ========================================================================
    
    def create_security_policy(
        self,
        name: str,
        description: str,
        **kwargs
    ) -> SecurityPolicy:
        """セキュリティポリシーを作成"""
        policy = SecurityPolicy(
            name=name,
            description=description,
            **kwargs
        )
        self.policies[name] = policy
        
        logger.info(f"Security policy created: {name}")
        return policy
    
    def get_policy(self, name: str) -> Optional[SecurityPolicy]:
        """ポリシーを取得"""
        return self.policies.get(name)
    
    def apply_policy(self, name: str, data: str) -> Dict[str, Any]:
        """ポリシーを適用"""
        policy = self.get_policy(name)
        if not policy:
            raise ValueError(f"Policy not found: {name}")
        
        result = {
            "policy": name,
            "original": data,
            "processed": data,
            "transformations": []
        }
        
        # 暗号化
        if policy.encryption_enabled:
            result["processed"] = self.encrypt_data(result["processed"])
            result["transformations"].append("encrypted")
        
        # PII マスキング
        if policy.pii_masking_enabled:
            mask_result = self.pii_detector.mask(result["processed"])
            result["processed"] = mask_result.masked
            result["transformations"].append("pii_masked")
        
        return result
    
    # ========================================================================
    # インシデント対応
    # ========================================================================
    
    def report_security_incident(
        self,
        incident_type: str,
        severity: str,
        description: str,
        details: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """セキュリティインシデントを報告"""
        incident = self.compliance_checker.soc2.report_incident(
            incident_type=incident_type,
            severity=severity,
            description=description,
            details=details
        )
        
        self.audit_log.log_security_event(
            user_id="system",
            action="incident_reported",
            severity=Severity.ERROR if severity == "high" else Severity.WARNING,
            details=incident
        )
        
        # インシデントハンドラーを実行
        for handler in self.incident_handlers:
            try:
                handler(incident)
            except Exception as e:
                logger.error(f"Error in incident handler: {e}")
        
        return incident
    
    def register_incident_handler(self, handler: callable) -> None:
        """インシデントハンドラーを登録"""
        self.incident_handlers.append(handler)
    
    # ========================================================================
    # メトリクス・レポート
    # ========================================================================
    
    def get_security_metrics(self) -> Dict[str, Any]:
        """セキュリティメトリクスを取得"""
        return {
            "encryption": self.crypto_engine.get_metrics_dict(),
            "pii_detection": self.pii_detector.get_metrics_dict(),
            "audit_log": self.audit_log.get_metrics_dict(),
        }
    
    def get_security_report(self) -> Dict[str, Any]:
        """セキュリティレポートを生成"""
        return {
            "report_generated": datetime.now().isoformat(),
            "metrics": self.get_security_metrics(),
            "compliance": self.get_compliance_report(),
            "incidents": self.compliance_checker.soc2.get_unresolved_incidents(),
        }
    
    def print_status_report(self) -> None:
        """ステータスレポートを出力"""
        report = self.get_security_report()
        
        logger.info("=" * 80)
        logger.info("SECURITY STATUS REPORT")
        logger.info("=" * 80)
        
        logger.info("\n[Encryption Metrics]")
        enc_metrics = report["metrics"]["encryption"]
        logger.info(f"  Total Encryptions: {enc_metrics['total_encryptions']}")
        logger.info(f"  Success Rate: {enc_metrics['success_rate']:.2f}%")
        
        logger.info("\n[PII Detection Metrics]")
        pii_metrics = report["metrics"]["pii_detection"]
        logger.info(f"  Total Scanned: {pii_metrics['total_scanned']}")
        logger.info(f"  PII Found: {pii_metrics['total_pii_found']}")
        
        logger.info("\n[Compliance Status]")
        compliance = report["compliance"]["overall_status"]
        logger.info(f"  GDPR Compliant: {compliance['gdpr_compliant']}")
        logger.info(f"  SOC2 Compliant: {compliance['soc2_compliant']}")
        
        if report["incidents"]:
            logger.warning(f"\n[Unresolved Incidents: {len(report['incidents'])}]")
            for incident in report["incidents"][:5]:
                logger.warning(f"  - {incident['incident_id']}: {incident['description']}")


# グローバルインスタンス
_global_security_manager: Optional[SecurityManager] = None


def get_security_manager(config: Optional[EncryptionConfig] = None) -> SecurityManager:
    """グローバル SecurityManager を取得"""
    global _global_security_manager
    if _global_security_manager is None:
        _global_security_manager = SecurityManager(config)
    return _global_security_manager


def initialize_security_system(master_key: Optional[bytes] = None) -> SecurityManager:
    """セキュリティシステムを初期化"""
    manager = get_security_manager()
    manager.initialize_encryption(master_key)
    logger.info("Security system initialized")
    return manager
