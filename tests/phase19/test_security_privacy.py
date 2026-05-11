"""
Phase 19 Task 2: セキュリティ・プライバシー テスト

テスト体系: 30個テスト
- 暗号化エンジン: 7個テスト
- PII検出・マスキング: 8個テスト
- 監査ログ: 6個テスト
- GDPR・SOC2対応: 5個テスト
- 統合テスト: 4個テスト
"""

import pytest

# Import security modules
from src.phase19.security.encryption_engine import (
    CryptoEngine,
)
from src.phase19.security.pii_detector import (
    PIIDetector,
    PIIType,
    MaskingStrategy,
)
from src.phase19.security.audit_log import (
    AuditLog,
    EventType,
)
from src.phase19.security.compliance import (
    ComplianceChecker,
    GDPRRight,
)
from src.phase19.security_manager import (
    SecurityManager,
)


# ============================================================================
# 暗号化エンジン テスト (7個)
# ============================================================================

@pytest.fixture
def crypto_engine():
    """暗号化エンジンフィクスチャ"""
    engine = CryptoEngine()
    engine.key_manager.generate_master_key()
    engine.key_manager.generate_rsa_keypair()
    return engine


def test_aes256_basic_encryption(crypto_engine):
    """AES-256: 基本的な暗号化・復号化"""
    plaintext = "Hello, World! This is a test message."
    
    # 暗号化
    encrypted = crypto_engine.encrypt(plaintext)
    assert encrypted != plaintext
    assert len(encrypted) > 0
    
    # 復号化
    decrypted = crypto_engine.decrypt(encrypted)
    assert decrypted == plaintext


def test_aes256_multiple_messages(crypto_engine):
    """AES-256: 複数メッセージの暗号化"""
    messages = [
        "Message 1",
        "Message 2",
        "Message 3",
    ]
    
    encrypted_messages = [crypto_engine.encrypt(msg) for msg in messages]
    
    # すべてのメッセージが異なる（IVが異なる）
    assert len(set(encrypted_messages)) == 3
    
    # 復号化して検証
    for orig, encrypted in zip(messages, encrypted_messages):
        assert crypto_engine.decrypt(encrypted) == orig


def test_rsa_encryption(crypto_engine):
    """RSA: 公開鍵暗号化"""
    plaintext = "Secret message for RSA"
    
    # RSA暗号化
    encrypted = crypto_engine.encrypt_with_rsa(plaintext)
    assert encrypted != plaintext
    
    # RSA復号化
    decrypted = crypto_engine.decrypt_with_rsa(encrypted)
    assert decrypted == plaintext


def test_password_hashing(crypto_engine):
    """パスワード: ハッシング・検証"""
    password = "MySecurePassword123!"
    
    # ハッシング
    hash_b64, salt_b64 = crypto_engine.hash_password(password)
    assert hash_b64 is not None
    assert salt_b64 is not None
    
    # 検証（正しいパスワード）
    assert crypto_engine.verify_password(password, hash_b64, salt_b64) is True
    
    # 検証（間違ったパスワード）
    assert crypto_engine.verify_password("WrongPassword", hash_b64, salt_b64) is False


def test_dict_encryption(crypto_engine):
    """辞書: JSON暗号化"""
    data = {"user_id": "123", "name": "John", "email": "john@example.com"}
    
    # 辞書を暗号化
    encrypted = crypto_engine.encrypt_dict(data)
    assert encrypted is not None
    
    # 復号化して辞書に変換
    decrypted = crypto_engine.decrypt_dict(encrypted)
    assert decrypted == data


def test_encryption_metrics(crypto_engine):
    """暗号化: メトリクス"""
    # 複数の暗号化操作
    for i in range(5):
        crypto_engine.encrypt(f"Message {i}")
    
    metrics = crypto_engine.get_metrics()
    assert metrics.total_encryptions == 5
    assert metrics.total_decryptions == 0
    assert metrics.get_success_rate() == 100.0


def test_rsa_public_key_export(crypto_engine):
    """RSA: 公開鍵エクスポート"""
    pem = crypto_engine.key_manager.export_rsa_public_key()
    assert "BEGIN PUBLIC KEY" in pem
    assert "END PUBLIC KEY" in pem


# ============================================================================
# PII検出・マスキング テスト (8個)
# ============================================================================

@pytest.fixture
def pii_detector():
    """PII検出器フィクスチャ"""
    return PIIDetector()


def test_email_detection(pii_detector):
    """PII: メールアドレス検出"""
    text = "Contact us at support@example.com for help."
    matches = pii_detector.detect(text)
    
    assert len(matches) > 0
    email_match = [m for m in matches if m.pii_type == PIIType.EMAIL]
    assert len(email_match) > 0
    assert "support@example.com" in email_match[0].value


def test_phone_number_detection(pii_detector):
    """PII: 電話番号検出"""
    text = "Call me at 090-1234-5678 anytime."
    matches = pii_detector.detect(text)
    
    phone_match = [m for m in matches if m.pii_type == PIIType.PHONE]
    assert len(phone_match) > 0
    assert "090-1234-5678" in phone_match[0].value


def test_ssn_detection(pii_detector):
    """PII: SSN検出"""
    text = "Social security number: 123-45-6789"
    matches = pii_detector.detect(text)
    
    ssn_match = [m for m in matches if m.pii_type == PIIType.SSN]
    assert len(ssn_match) > 0
    assert "123-45-6789" in ssn_match[0].value


def test_credit_card_detection(pii_detector):
    """PII: クレジットカード番号検出"""
    text = "Card number: 1234 5678 9012 3456"
    matches = pii_detector.detect(text)
    
    cc_match = [m for m in matches if m.pii_type == PIIType.CREDIT_CARD]
    assert len(cc_match) > 0


def test_masking_strategies(pii_detector):
    """PII: マスキング戦略"""
    text = "Email: user@example.com"
    
    # REPLACE_CHAR戦略
    result = pii_detector.mask(text, strategy=MaskingStrategy.REPLACE_CHAR)
    assert "<PII>" in result.masked
    
    # SHOW_FIRST戦略
    result = pii_detector.mask(text, strategy=MaskingStrategy.SHOW_FIRST)
    assert "user" not in result.masked


def test_risk_assessment(pii_detector):
    """PII: リスク評価"""
    text = "SSN: 123-45-6789, Card: 1234 5678 9012 3456"
    risk = pii_detector.assess_risk(text)
    
    assert risk["overall_risk"] == "critical"
    assert risk["critical_count"] > 0


def test_pii_metrics(pii_detector):
    """PII: メトリクス"""
    texts = [
        "Email: john@example.com",
        "Phone: 090-1234-5678",
    ]
    
    for text in texts:
        pii_detector.detect(text)
    
    metrics = pii_detector.get_metrics()
    assert metrics.total_scanned == 2
    assert metrics.total_pii_found > 0


# ============================================================================
# 監査ログ テスト (6個)
# ============================================================================

@pytest.fixture
def audit_log():
    """監査ログフィクスチャ"""
    return AuditLog()


def test_event_logging(audit_log):
    """監査: イベント記録"""
    event = audit_log.log_event(
        event_type=EventType.CREATE,
        user_id="user123",
        resource_type="document",
        resource_id="doc456",
        action="create",
        status="success"
    )
    
    assert event.event_id is not None
    assert event.user_id == "user123"


def test_user_tracing(audit_log):
    """監査: ユーザートレース"""
    user_id = "user123"
    
    # 複数のイベントを記録
    for i in range(3):
        audit_log.log_create(
            user_id=user_id,
            resource_type="document",
            resource_id=f"doc{i}"
        )
    
    trail = audit_log.get_user_audit_trail(user_id)
    assert len(trail) >= 3


def test_audit_queries(audit_log):
    """監査: クエリ"""
    # イベントを記録
    audit_log.log_create("user1", "doc", "doc1")
    audit_log.log_update("user1", "doc", "doc1", changes={"title": "new"})
    audit_log.log_delete("user2", "doc", "doc2")
    
    # クエリ実行
    user1_events = audit_log.query_events(user_id="user1")
    assert len(user1_events) >= 2
    
    creates = audit_log.query_events(event_type=EventType.CREATE)
    assert len(creates) >= 1


def test_report_generation(audit_log):
    """監査: レポート生成"""
    # イベントを記録
    for i in range(5):
        audit_log.log_event(
            event_type=EventType.CREATE,
            user_id=f"user{i}",
            resource_type="document",
            resource_id=f"doc{i}",
            action="create",
            status="success" if i < 4 else "failure"
        )
    
    report = audit_log.generate_audit_report()
    assert report["total_events"] >= 5
    assert report["failure_count"] >= 1


def test_log_storage(audit_log):
    """監査: ストレージ管理"""
    # 100個のイベントを記録
    for i in range(100):
        audit_log.log_event(
            event_type=EventType.READ,
            user_id="system",
            resource_type="log",
            resource_id=f"entry{i}",
            action="read"
        )
    
    metrics = audit_log.get_metrics()
    assert metrics.total_events == 100


# ============================================================================
# GDPR・SOC2対応 テスト (5個)
# ============================================================================

@pytest.fixture
def compliance_checker():
    """コンプライアンスチェッカーフィクスチャ"""
    return ComplianceChecker()


def test_gdpr_access_request(compliance_checker):
    """GDPR: アクセス権リクエスト"""
    user_id = "user123"
    request = compliance_checker.gdpr.create_access_request(user_id)
    
    assert request.right == GDPRRight.ACCESS
    assert request.user_id == user_id
    assert request.status == "pending"


def test_gdpr_deletion_request(compliance_checker):
    """GDPR: 削除権リクエスト"""
    user_id = "user123"
    request = compliance_checker.gdpr.create_deletion_request(user_id)
    
    assert request.right == GDPRRight.DELETION
    assert request.status == "pending"


def test_soc2_control_status(compliance_checker):
    """SOC2: 管理体制ステータス"""
    from src.phase19.security.compliance import SOC2Control
    
    checker = compliance_checker.soc2
    checker.implement_control(SOC2Control.ACCESS_CONTROL)
    
    status = checker.get_control_status()
    assert status["access_control"]["implemented"] is True


def test_incident_reporting(compliance_checker):
    """SOC2: インシデント報告"""
    incident = compliance_checker.soc2.report_incident(
        incident_type="unauthorized_access",
        severity="high",
        description="Unauthorized access attempt detected"
    )
    
    assert incident["incident_id"] is not None
    assert incident["severity"] == "high"


def test_compliance_report(compliance_checker):
    """GDPR・SOC2: コンプライアンスレポート"""
    report = compliance_checker.generate_compliance_report()
    
    assert "overall_status" in report
    assert "gdpr" in report
    assert "soc2" in report


# ============================================================================
# 統合テスト (4個)
# ============================================================================

def test_security_manager_initialization():
    """統合: SecurityManager 初期化"""
    manager = SecurityManager()
    success = manager.initialize_encryption()
    assert success is True


def test_encryption_and_masking():
    """統合: 暗号化 + マスキング"""
    manager = SecurityManager()
    manager.initialize_encryption()
    
    text = "Email: user@example.com, SSN: 123-45-6789"
    
    # PIIをマスキング
    mask_result = manager.mask_pii(text)
    assert mask_result["pii_count"] > 0
    
    # マスキング済みテキストを暗号化
    encrypted = manager.encrypt_data(mask_result["masked"])
    assert encrypted is not None
    
    # 復号化
    decrypted = manager.decrypt_data(encrypted)
    assert "<PII>" in decrypted or "x" in decrypted


def test_audit_trail_with_encryption():
    """統合: 監査ログ + 暗号化"""
    manager = SecurityManager()
    manager.initialize_encryption()
    
    # ユーザー操作をログ
    manager.log_user_action(
        user_id="user123",
        resource_type="document",
        resource_id="doc456",
        action="create"
    )
    
    # 監査証跡を取得
    trail = manager.get_user_audit_trail("user123")
    assert len(trail) > 0


def test_security_manager_gdpr_compliance():
    """統合: SecurityManager + GDPR"""
    manager = SecurityManager()
    manager.initialize_encryption()
    
    # GDPR リクエストを作成
    request_data = manager.create_gdpr_access_request("user123")
    assert request_data["right"] == "access"
    
    # コンプライアンスレポートを生成
    report = manager.get_compliance_report()
    assert "overall_status" in report


# ============================================================================
# Run tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
