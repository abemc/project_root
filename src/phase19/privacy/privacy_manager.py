"""Privacy Manager - Unified privacy and data management system."""

from typing import Dict, Any, Optional, Tuple, Union
from datetime import datetime
import json

from .encryption_manager import EncryptionManager
from .pii_detector import PIIDetector
from .audit_logger import AuditLogger, AuditEventType, AuditSeverity
from .gdpr_manager import GDPRManager, ConsentType


class PrivacyManager:
    """Unified privacy and data management system.
    
    Integrates:
    - Encryption management
    - PII detection and masking
    - Audit logging
    - GDPR compliance
    
    Provides a single interface for all privacy operations.
    """

    def __init__(self, master_key: Optional[bytes] = None):
        """Initialize Privacy Manager.
        
        Args:
            master_key: Master encryption key (generated if not provided)
        """
        self.encryption_manager = EncryptionManager(master_key)
        self.pii_detector = PIIDetector()
        self.audit_logger = AuditLogger()
        self.gdpr_manager = GDPRManager()
        self._initialized_at = datetime.utcnow().isoformat()

    def process_and_protect_data(
        self,
        data: Union[str, Dict[str, Any]],
        user_id: Optional[str] = None,
        encrypt: bool = True,
        detect_pii: bool = True,
        mask_pii: bool = True,
        audit: bool = True
    ) -> Dict[str, Any]:
        """Process data with full privacy protection.
        
        Args:
            data: Data to process
            user_id: User identifier for audit logging
            encrypt: Whether to encrypt data
            detect_pii: Whether to detect PII
            mask_pii: Whether to mask detected PII
            audit: Whether to log to audit trail
            
        Returns:
            Protected data with metadata
        """
        result = {
            "original_size": len(str(data)),
            "protected_data": data,
            "pii_detected": None,
            "encrypted": False,
            "masked": False,
            "encrypted_data": None,
            "masked_data": None,
            "processing_timestamp": datetime.utcnow().isoformat()
        }

        # Convert to string if needed
        data_str = data if isinstance(data, str) else json.dumps(data)

        # Detect PII
        if detect_pii:
            pii_result = self.pii_detector.detect(data_str)
            result["pii_detected"] = {
                "count": pii_result.total_pii_found,
                "types": list(set(m.pii_type.value for m in pii_result.matches)),
                "risk_level": pii_result.risk_level
            }

            # Log PII detection
            if audit and pii_result.total_pii_found > 0:
                self.audit_logger.log_pii_detection(
                    pii_types=result["pii_detected"]["types"],
                    count=pii_result.total_pii_found,
                    risk_level=pii_result.risk_level,
                    user_id=user_id
                )

            # Mask PII
            if mask_pii and pii_result.total_pii_found > 0:
                masked_data = self.pii_detector.mask(data_str)
                result["masked_data"] = masked_data
                result["masked"] = True

        # Encrypt data
        if encrypt:
            encrypted = self.encryption_manager.encrypt_aes_256_gcm(data_str)
            result["encrypted_data"] = encrypted
            result["encrypted"] = True

            if audit:
                self.audit_logger.log_event(
                    event_type=AuditEventType.DATA_MODIFICATION,
                    action="Data encrypted",
                    user_id=user_id,
                    details={"algorithm": "aes_256_gcm"}
                )

        return result

    def decrypt_and_verify(
        self,
        encrypted_data: Dict[str, Any],
        user_id: Optional[str] = None,
        verify_integrity: bool = True,
        audit: bool = True
    ) -> Optional[str]:
        """Decrypt data and verify integrity.
        
        Args:
            encrypted_data: Encrypted data dictionary
            user_id: User identifier for audit logging
            verify_integrity: Whether to verify data integrity
            audit: Whether to log to audit trail
            
        Returns:
            Decrypted data or None if verification fails
        """
        try:
            plaintext = self.encryption_manager.decrypt_aes_256_gcm(encrypted_data)

            if audit:
                self.audit_logger.log_event(
                    event_type=AuditEventType.DECRYPTION_ATTEMPT,
                    action="Data decrypted successfully",
                    user_id=user_id,
                    status="success"
                )

            return plaintext

        except Exception as e:
            if audit:
                self.audit_logger.log_event(
                    event_type=AuditEventType.DECRYPTION_ATTEMPT,
                    action=f"Decryption failed: {str(e)}",
                    user_id=user_id,
                    status="failure",
                    severity=AuditSeverity.ERROR
                )
            return None

    def anonymize_data(
        self,
        data: str,
        user_id: Optional[str] = None,
        keep_initials: bool = False,
        audit: bool = True
    ) -> Tuple[str, Dict[str, str]]:
        """Anonymize data by replacing PII.
        
        Args:
            data: Data to anonymize
            user_id: User identifier for audit logging
            keep_initials: Keep name initials
            audit: Whether to log to audit trail
            
        Returns:
            Tuple of (anonymized_data, replacement_mapping)
        """
        anonymized, mapping = self.pii_detector.anonymize(data, keep_initials)

        if audit:
            self.audit_logger.log_event(
                event_type=AuditEventType.MASKING_OPERATION,
                action=f"Data anonymized with {len(mapping)} replacements",
                user_id=user_id,
                details={"mapping_count": len(mapping)}
            )

        return anonymized, mapping

    def check_consent(
        self,
        user_id: str,
        consent_type: ConsentType
    ) -> bool:
        """Check if user has required consent.
        
        Args:
            user_id: User identifier
            consent_type: Type of consent required
            
        Returns:
            True if user has valid consent
        """
        return self.gdpr_manager.has_consent(user_id, consent_type)

    def record_user_consent(
        self,
        user_id: str,
        consent_type: ConsentType,
        given: bool = True,
        **kwargs
    ) -> None:
        """Record user consent.
        
        Args:
            user_id: User identifier
            consent_type: Type of consent
            given: Whether consent is given
            **kwargs: Additional parameters
        """
        self.gdpr_manager.record_consent(user_id, consent_type, given, **kwargs)

        if given:
            self.audit_logger.log_event(
                event_type=AuditEventType.CONSENT_CHANGE,
                action=f"Consent given: {consent_type.value}",
                user_id=user_id,
                details={"consent_type": consent_type.value}
            )

    def withdraw_user_consent(self, user_id: str, consent_type: ConsentType) -> bool:
        """Withdraw user consent.
        
        Args:
            user_id: User identifier
            consent_type: Type of consent
            
        Returns:
            True if consent was withdrawn
        """
        result = self.gdpr_manager.withdraw_consent(user_id, consent_type)

        if result:
            self.audit_logger.log_event(
                event_type=AuditEventType.CONSENT_CHANGE,
                action=f"Consent withdrawn: {consent_type.value}",
                user_id=user_id,
                severity=AuditSeverity.WARNING,
                details={"consent_type": consent_type.value}
            )

        return result

    def request_data_access(
        self,
        user_id: str,
        reason: Optional[str] = None
    ) -> str:
        """Create data access request (GDPR Article 15).
        
        Args:
            user_id: User identifier
            reason: Request reason
            
        Returns:
            Request ID
        """
        request = self.gdpr_manager.create_access_request(user_id, reason=reason)

        self.audit_logger.log_event(
            event_type=AuditEventType.EXPORT_REQUEST,
            action="Data access request created",
            user_id=user_id,
            resource_id=request.request_id,
            details={"request_id": request.request_id}
        )

        return request.request_id

    def request_data_deletion(
        self,
        user_id: str,
        reason: Optional[str] = None
    ) -> str:
        """Create data deletion request (GDPR Article 17).
        
        Args:
            user_id: User identifier
            reason: Deletion reason
            
        Returns:
            Request ID
        """
        request = self.gdpr_manager.create_erasure_request(user_id, reason=reason)

        self.audit_logger.log_event(
            event_type=AuditEventType.DELETE_REQUEST,
            action="Data deletion request created",
            user_id=user_id,
            resource_id=request.request_id,
            severity=AuditSeverity.WARNING,
            details={"request_id": request.request_id, "reason": reason}
        )

        return request.request_id

    def request_data_portability(
        self,
        user_id: str,
        format_type: str = "json"
    ) -> str:
        """Create data portability request (GDPR Article 20).
        
        Args:
            user_id: User identifier
            format_type: Requested format (json, csv, xml)
            
        Returns:
            Request ID
        """
        request = self.gdpr_manager.create_portability_request(user_id, format_type)

        self.audit_logger.log_event(
            event_type=AuditEventType.EXPORT_REQUEST,
            action="Data portability request created",
            user_id=user_id,
            resource_id=request.request_id,
            details={"request_id": request.request_id, "format": format_type}
        )

        return request.request_id

    def get_compliance_report(self) -> Dict[str, Any]:
        """Get comprehensive privacy and compliance report.
        
        Returns:
            Compliance report dictionary
        """
        return {
            "generated_at": datetime.utcnow().isoformat(),
            "system_initialized_at": self._initialized_at,
            "encryption": self.encryption_manager.get_stats(),
            "pii_detection": self.pii_detector.get_stats(),
            "audit_log": self.audit_logger.get_stats(),
            "gdpr": self.gdpr_manager.get_stats()
        }

    def export_audit_log(
        self,
        format_type: str = "json",
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> str:
        """Export audit log in specified format.
        
        Args:
            format_type: Export format (json, csv)
            start_time: Start time filter
            end_time: End time filter
            
        Returns:
            Exported audit log as string
        """
        return self.audit_logger.export_events(format_type, start_time, end_time)

    def rotate_encryption_key(self) -> Tuple[bytes, bytes]:
        """Rotate encryption key.
        
        Returns:
            Tuple of (old_key, new_key)
        """
        old_key, new_key = self.encryption_manager.rotate_key()

        self.audit_logger.log_event(
            event_type=AuditEventType.ENCRYPTION_KEY_ROTATION,
            action="Encryption key rotated",
            severity=AuditSeverity.WARNING
        )

        return old_key, new_key

    def cleanup_expired_data(self) -> Dict[str, int]:
        """Clean up expired audit logs and records.
        
        Returns:
            Cleanup statistics
        """
        removed_events = self.audit_logger.cleanup_expired_events()

        return {
            "removed_audit_events": removed_events,
            "cleanup_timestamp": datetime.utcnow().isoformat()
        }

    def get_health_status(self) -> Dict[str, Any]:
        """Get system health status.
        
        Returns:
            Health status dictionary
        """
        return {
            "status": "healthy",
            "initialized_at": self._initialized_at,
            "components": {
                "encryption": "operational",
                "pii_detection": "operational",
                "audit_logging": "operational",
                "gdpr_management": "operational"
            },
            "timestamp": datetime.utcnow().isoformat()
        }
