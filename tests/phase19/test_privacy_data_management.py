"""Tests for Privacy and Data Management Module."""

import pytest
import json
import os

from src.phase19.privacy.encryption_manager import EncryptionManager
from src.phase19.privacy.pii_detector import PIIDetector, PIIType
from src.phase19.privacy.audit_logger import AuditLogger, AuditEventType, AuditSeverity
from src.phase19.privacy.gdpr_manager import GDPRManager, ConsentType, RequestStatus
from src.phase19.privacy.privacy_manager import PrivacyManager


# ==================== Encryption Manager Tests ====================

class TestEncryptionManager:
    """Test encryption manager functionality."""

    def test_initialization(self):
        """Test EncryptionManager initialization."""
        manager = EncryptionManager()
        assert manager.master_key is not None
        assert len(manager.master_key) == 32

    def test_custom_master_key(self):
        """Test initialization with custom master key."""
        key = os.urandom(32)
        manager = EncryptionManager(key)
        assert manager.master_key == key

    def test_aes_256_gcm_encryption_decryption(self):
        """Test AES-256-GCM encryption and decryption."""
        manager = EncryptionManager()
        plaintext = "sensitive data"

        encrypted = manager.encrypt_aes_256_gcm(plaintext)
        assert "ciphertext" in encrypted
        assert "iv" in encrypted
        assert "tag" in encrypted

        decrypted = manager.decrypt_aes_256_gcm(encrypted)
        assert decrypted == plaintext

    def test_aes_256_cbc_encryption_decryption(self):
        """Test AES-256-CBC encryption and decryption."""
        manager = EncryptionManager()
        plaintext = "sensitive data"

        encrypted = manager.encrypt_aes_256_cbc(plaintext)
        assert "ciphertext" in encrypted
        assert "iv" in encrypted
        assert "hmac" in encrypted

        decrypted = manager.decrypt_aes_256_cbc(encrypted)
        assert decrypted == plaintext

    def test_rsa_key_generation(self):
        """Test RSA key pair generation."""
        manager = EncryptionManager()
        private_pem, public_pem = manager.generate_rsa_keys(2048)

        assert b"BEGIN RSA PRIVATE KEY" in private_pem or b"BEGIN PRIVATE KEY" in private_pem
        assert b"BEGIN PUBLIC KEY" in public_pem

    def test_password_hashing(self):
        """Test password hashing and verification."""
        manager = EncryptionManager()
        password = "my_secure_password"

        hash_result = manager.hash_password(password)
        assert "hash" in hash_result
        assert "salt" in hash_result

        # Verify correct password
        assert manager.verify_password(password, hash_result)

        # Verify incorrect password
        assert not manager.verify_password("wrong_password", hash_result)

    def test_key_rotation(self):
        """Test key rotation."""
        manager = EncryptionManager()
        old_key = manager.master_key

        old_key_result, new_key_result = manager.rotate_key()
        assert old_key_result == old_key
        assert new_key_result != old_key
        assert manager.master_key == new_key_result


# ==================== PII Detector Tests ====================

class TestPIIDetector:
    """Test PII detection and masking."""

    def test_initialization(self):
        """Test PIIDetector initialization."""
        detector = PIIDetector()
        assert detector.patterns is not None
        assert len(detector.patterns) > 0

    def test_email_detection(self):
        """Test email detection."""
        detector = PIIDetector()
        text = "Contact me at john.doe@example.com for more info"

        result = detector.detect(text)
        assert result.total_pii_found == 1
        assert result.matches[0].pii_type == PIIType.EMAIL

    def test_phone_detection(self):
        """Test phone number detection."""
        detector = PIIDetector()
        text = "Call me at (555) 123-4567"

        result = detector.detect(text)
        assert result.total_pii_found >= 1

    def test_credit_card_detection(self):
        """Test credit card number detection."""
        detector = PIIDetector()
        text = "My card is 4532015112830366"

        result = detector.detect(text)
        assert result.total_pii_found >= 1

    def test_pii_masking(self):
        """Test PII masking."""
        detector = PIIDetector()
        text = "Email: john@example.com and phone: 555-123-4567"

        masked = detector.mask(text)
        assert "john@example.com" not in masked
        assert "*" in masked

    def test_anonymization(self):
        """Test data anonymization."""
        detector = PIIDetector()
        text = "john@example.com contacted support"

        anonymized, mapping = detector.anonymize(text)
        assert len(mapping) > 0
        assert "[EMAIL" in anonymized or len(mapping) == 0


# ==================== Audit Logger Tests ====================

class TestAuditLogger:
    """Test audit logging functionality."""

    def test_initialization(self):
        """Test AuditLogger initialization."""
        logger = AuditLogger()
        assert logger.retention_days == 90
        assert len(logger.events) == 0

    def test_log_simple_event(self):
        """Test logging simple event."""
        logger = AuditLogger()
        event = logger.log_event(
            event_type=AuditEventType.DATA_ACCESS,
            action="Accessed user data",
            user_id="user123"
        )

        assert event.event_type == AuditEventType.DATA_ACCESS
        assert event.user_id == "user123"
        assert len(logger.events) == 1

    def test_log_data_access(self):
        """Test logging data access event."""
        logger = AuditLogger()
        event = logger.log_data_access(
            user_id="user123",
            resource_id="resource1",
            data_fields=["name", "email"]
        )

        assert event.event_type == AuditEventType.DATA_ACCESS
        assert "name" in event.details["fields"]

    def test_log_data_deletion(self):
        """Test logging data deletion event."""
        logger = AuditLogger()
        event = logger.log_data_deletion(
            user_id="user123",
            resource_id="resource1",
            reason="GDPR deletion request"
        )

        assert event.event_type == AuditEventType.DATA_DELETION
        assert event.severity == AuditSeverity.WARNING

    def test_query_events(self):
        """Test querying events with filters."""
        logger = AuditLogger()
        logger.log_event(
            event_type=AuditEventType.DATA_ACCESS,
            action="Access 1",
            user_id="user1"
        )
        logger.log_event(
            event_type=AuditEventType.DATA_DELETION,
            action="Delete 1",
            user_id="user2"
        )

        results = logger.query_events(user_id="user1")
        assert len(results) == 1
        assert results[0].user_id == "user1"

    def test_export_events_json(self):
        """Test exporting events as JSON."""
        logger = AuditLogger()
        logger.log_event(
            event_type=AuditEventType.DATA_ACCESS,
            action="Test event",
            user_id="user1"
        )

        exported = logger.export_events(format_type="json")
        data = json.loads(exported)
        assert len(data) == 1
        assert data[0]["user_id"] == "user1"


# ==================== GDPR Manager Tests ====================

class TestGDPRManager:
    """Test GDPR compliance functionality."""

    def test_initialization(self):
        """Test GDPRManager initialization."""
        manager = GDPRManager()
        assert len(manager.consents) == 0
        assert len(manager.requests) == 0

    def test_record_consent(self):
        """Test recording user consent."""
        manager = GDPRManager()
        consent = manager.record_consent(
            user_id="user1",
            consent_type=ConsentType.MARKETING,
            given=True
        )

        assert consent.user_id == "user1"
        assert consent.consent_type == ConsentType.MARKETING
        assert consent.given is True

    def test_withdraw_consent(self):
        """Test withdrawing consent."""
        manager = GDPRManager()
        manager.record_consent("user1", ConsentType.MARKETING, given=True)

        result = manager.withdraw_consent("user1", ConsentType.MARKETING)
        assert result is True

        assert manager.has_consent("user1", ConsentType.MARKETING) is False

    def test_create_access_request(self):
        """Test creating access request."""
        manager = GDPRManager()
        manager.register_user_data("user1", ["name", "email"])

        request = manager.create_access_request("user1", reason="User request")
        assert request.request_type == "access"
        assert request.status == RequestStatus.PENDING

    def test_create_erasure_request(self):
        """Test creating erasure request."""
        manager = GDPRManager()
        request = manager.create_erasure_request(
            "user1",
            reason="Right to be forgotten"
        )

        assert request.request_type == "erasure"
        assert request.status == RequestStatus.PENDING

    def test_create_portability_request(self):
        """Test creating data portability request."""
        manager = GDPRManager()
        request = manager.create_portability_request("user1", format_type="json")

        assert request.request_type == "portability"
        assert "json" in request.notes


# ==================== Privacy Manager Integration Tests ====================

class TestPrivacyManager:
    """Test unified privacy manager."""

    def test_initialization(self):
        """Test PrivacyManager initialization."""
        pm = PrivacyManager()
        assert pm.encryption_manager is not None
        assert pm.pii_detector is not None
        assert pm.audit_logger is not None
        assert pm.gdpr_manager is not None

    def test_process_and_protect_data(self):
        """Test full data protection workflow."""
        pm = PrivacyManager()
        data = "Email: john@example.com"

        result = pm.process_and_protect_data(
            data=data,
            user_id="user1",
            encrypt=True,
            detect_pii=True,
            mask_pii=True
        )

        assert result["encrypted"] is True
        assert result["masked"] is True
        assert result["pii_detected"]["count"] >= 1

    def test_decrypt_and_verify(self):
        """Test data decryption and verification."""
        pm = PrivacyManager()
        original_data = "sensitive information"

        # Encrypt
        encrypted = pm.encryption_manager.encrypt_aes_256_gcm(original_data)

        # Decrypt
        decrypted = pm.decrypt_and_verify(encrypted, user_id="user1")
        assert decrypted == original_data

    def test_anonymize_data(self):
        """Test data anonymization."""
        pm = PrivacyManager()
        data = "Contact john@example.com"

        anonymized, mapping = pm.anonymize_data(data, user_id="user1")
        assert len(mapping) > 0

    def test_consent_management(self):
        """Test consent recording and checking."""
        pm = PrivacyManager()

        # Record consent
        pm.record_user_consent("user1", ConsentType.MARKETING, given=True)

        # Check consent
        assert pm.check_consent("user1", ConsentType.MARKETING) is True

    def test_gdpr_requests(self):
        """Test GDPR request creation."""
        pm = PrivacyManager()

        access_id = pm.request_data_access("user1", reason="Data review")
        assert access_id is not None

        delete_id = pm.request_data_deletion("user1", reason="Account deletion")
        assert delete_id is not None

        portability_id = pm.request_data_portability("user1", format_type="json")
        assert portability_id is not None

    def test_get_compliance_report(self):
        """Test getting compliance report."""
        pm = PrivacyManager()

        # Generate some activity
        pm.process_and_protect_data("test data", encrypt=True)
        pm.record_user_consent("user1", ConsentType.ANALYTICS, given=True)

        report = pm.get_compliance_report()
        assert "encryption" in report
        assert "pii_detection" in report
        assert "audit_log" in report
        assert "gdpr" in report

    def test_key_rotation(self):
        """Test encryption key rotation."""
        pm = PrivacyManager()
        old_key, new_key = pm.rotate_encryption_key()

        assert old_key != new_key

    def test_health_status(self):
        """Test health status check."""
        pm = PrivacyManager()
        status = pm.get_health_status()

        assert status["status"] == "healthy"
        assert "components" in status
        assert status["components"]["encryption"] == "operational"
        assert status["components"]["pii_detection"] == "operational"
        assert status["components"]["audit_logging"] == "operational"
        assert status["components"]["gdpr_management"] == "operational"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
