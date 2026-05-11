"""
Phase 10 テスト用フィクスチャ

pytest conftest - 共通フィクスチャ・モック設定
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from src.phase10 import (
    SecurityEvent, EventType
)

# ---------------------------------------------------------------------------
# 依存パッケージ不足によるコレクションエラーを防ぐため、
# 環境依存のテストファイルを条件付きでスキップする。
# ---------------------------------------------------------------------------

def _module_available(name: str) -> bool:
    import importlib.util
    return importlib.util.find_spec(name) is not None

collect_ignore: list[str] = []

# urllib3 未インストール → tiktoken / requests 経由で失敗するテスト
if not _module_available("urllib3"):
    collect_ignore += [
        "test_chunk_text.py",
        "security_integration_test.py",
    ]

# fitz (PyMuPDF) 未インストール
if not _module_available("fitz"):
    collect_ignore.append("test_extract_pdf.py")

# redis 未インストール
if not _module_available("redis"):
    collect_ignore.append("test_cache_redis.py")


@pytest.fixture(scope="session")
def event_loop():
    """asyncio イベントループ"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ========== Dict ベースのフィクスチャ（互換性のため） ==========

@pytest.fixture
def sample_auth_event():
    """認証イベントサンプル"""
    return {
        'event_type': 'authentication',
        'timestamp': datetime.now().isoformat(),
        'username': 'testuser',
        'source_ip': '192.168.1.100',
        'result': 'success',
        'auth_method': 'mfa',
        'mfa_used': True,
        'device': 'desktop'
    }


@pytest.fixture
def sample_access_event():
    """アクセスイベントサンプル"""
    return {
        'event_type': 'access',
        'timestamp': datetime.now().isoformat(),
        'user': 'testuser',
        'source_ip': '192.168.1.100',
        'resource': 'admin_panel',
        'action': 'read',
        'access_type': 'web',
        'permission': 'admin',
        'granted': True
    }


@pytest.fixture
def sample_data_event():
    """データイベントサンプル"""
    return {
        'event_type': 'data',
        'timestamp': datetime.now().isoformat(),
        'user': 'testuser',
        'source_ip': '192.168.1.100',
        'data_resource': 'customer_db',
        'operation': 'read',
        'record_count': 50,
        'data_classification': 'internal',
        'encrypted': True
    }


@pytest.fixture
def sample_infra_event():
    """インフライベントサンプル"""
    return {
        'event_type': 'infrastructure',
        'timestamp': datetime.now().isoformat(),
        'actor': 'admin',
        'source_ip': '10.0.0.1',
        'resource': 'firewall-01',
        'action': 'config_change',
        'resource_type': 'network',
        'change_type': 'rule_modification',
        'severity': 'high'
    }


# ========== SecurityEvent ベースのフィクスチャ（correlate_events 用） ==========

@pytest.fixture
def malicious_auth_events_objects():
    """ブルートフォース攻撃イベント (SecurityEvent オブジェクト)"""
    base_time = datetime(2026, 4, 15, 10, 0, 0)
    events = []
    
    for i in range(5):
        event = SecurityEvent(
            event_id=f"auth_fail_{i}",
            timestamp=base_time + timedelta(minutes=i),
            event_type=EventType.AUTHENTICATION,
            source_user='target_user',
            source_ip='203.0.113.42',
            resource='login_portal',
            action='failed_login',
            details={
                'success': False,
                'auth_method': 'password',
                'mfa_used': False,
                'device': 'unknown'
            }
        )
        events.append(event)
    
    return events


@pytest.fixture
def data_exfil_events_objects():
    """データ流出イベント (SecurityEvent オブジェクト)"""
    base_time = datetime(2026, 4, 15, 14, 0, 0)
    events = []
    
    for i in range(10):
        event = SecurityEvent(
            event_id=f"data_read_{i}",
            timestamp=base_time + timedelta(seconds=i*30),
            event_type=EventType.DATA,
            source_user='suspicious_user',
            source_ip='192.168.1.150',
            resource='sensitive_db',
            action='read_bulk',
            details={
                'record_count': 50000,
                'data_classification': 'secret',
                'encrypted': False,
                'operation': 'read_bulk',
                'granted': True
            }
        )
        events.append(event)
    
    return events


@pytest.fixture
def privilege_escalation_events_objects():
    """権限昇格シーケンス (SecurityEvent オブジェクト)"""
    base_time = datetime(2026, 4, 15, 15, 0, 0)
    
    priv_event = SecurityEvent(
        event_id="priv_escalation",
        timestamp=base_time,
        event_type=EventType.ACCESS,
        source_user='attacker',
        source_ip='10.0.0.100',
        resource='system_admin',
        action='privilege_escalation',
        details={
            'permission': 'root',
            'granted': True,
            'action': 'privilege_escalation'
        }
    )
    
    data_event = SecurityEvent(
        event_id="secret_data_read",
        timestamp=base_time + timedelta(seconds=15),
        event_type=EventType.DATA,
        source_user='attacker',
        source_ip='10.0.0.100',
        resource='password_vault',
        action='read',
        details={
            'record_count': 1000,
            'data_classification': 'secret',
            'encrypted': True,
            'operation': 'read'
        }
    )
    
    return [priv_event, data_event]


# ========== Dict ベースのフィクスチャ（攻撃パターン） ==========

@pytest.fixture
def malicious_auth_events():
    """ブルートフォース攻撃イベント (5分間に5回失敗)"""
    base_time = datetime(2026, 4, 15, 10, 0, 0)
    events = []
    
    for i in range(5):
        events.append({
            'event_type': 'authentication',
            'timestamp': (base_time + timedelta(minutes=i)).isoformat(),
            'username': 'target_user',
            'source_ip': '203.0.113.42',
            'result': 'failure',
            'auth_method': 'password',
            'mfa_used': False,
            'device': 'unknown'
        })
    
    return events


@pytest.fixture
def data_exfil_events():
    """データ流出イベント"""
    base_time = datetime(2026, 4, 15, 14, 0, 0)
    events = []
    
    for i in range(10):
        events.append({
            'event_type': 'data',
            'timestamp': (base_time + timedelta(seconds=i*30)).isoformat(),
            'user': 'suspicious_user',
            'source_ip': '192.168.1.150',
            'data_resource': 'sensitive_db',
            'operation': 'read_bulk',
            'record_count': 50000,
            'data_classification': 'secret',
            'encrypted': False
        })
    
    return events


@pytest.fixture
def privilege_escalation_events():
    """権限昇格シーケンス"""
    base_time = datetime(2026, 4, 15, 15, 0, 0)
    
    priv_event = {
        'event_type': 'access',
        'timestamp': base_time.isoformat(),
        'user': 'attacker',
        'source_ip': '10.0.0.100',
        'resource': 'system_admin',
        'action': 'privilege_escalation',
        'permission': 'root',
        'granted': True
    }
    
    data_event = {
        'event_type': 'data',
        'timestamp': (base_time + timedelta(seconds=15)).isoformat(),
        'user': 'attacker',
        'source_ip': '10.0.0.100',
        'data_resource': 'password_vault',
        'operation': 'read',
        'record_count': 1000,
        'data_classification': 'secret',
        'encrypted': True
    }
    
    return [priv_event, data_event]


# ========== モックエンジン ==========

@pytest.fixture
def mock_soc_engine():
    """SOC エンジンモック"""
    from src.phase10 import SecurityOperationsCenter
    return SecurityOperationsCenter()


@pytest.fixture
def mock_event_processor():
    """イベントプロセッサモック"""
    from src.phase10 import EventProcessor
    return EventProcessor()


@pytest.fixture
def mock_threat_classifier():
    """脅威分類器モック"""
    from src.phase10 import ThreatClassifier
    return ThreatClassifier()


@pytest.fixture
def mock_auto_responder():
    """自動対応エンジンモック"""
    from src.phase10 import AutoResponder
    return AutoResponder()


@pytest.fixture
def mock_escalation_manager():
    """エスカレーション管理モック"""
    from src.phase10 import EscalationManager
    return EscalationManager()


# ========== Step 2: 次世代認証モック ==========

@pytest.fixture
def mock_fido2_engine():
    """FIDO2 エンジンモック"""
    from src.phase10 import FIDO2AuthEngine
    return FIDO2AuthEngine()


@pytest.fixture
def mock_biometric_engine():
    """生体認証エンジンモック"""
    from src.phase10 import BiometricAuthEngine
    return BiometricAuthEngine()


@pytest.fixture
def mock_adaptive_strategy(mock_fido2_engine, mock_biometric_engine):
    """適応型認証戦略モック"""
    from src.phase10 import AdaptiveAuthStrategy
    return AdaptiveAuthStrategy(mock_fido2_engine, mock_biometric_engine)


# ========== Step 3: ML脅威検出モック ==========

@pytest.fixture
def mock_anomaly_detector():
    """異常検出エンジンモック"""
    from src.phase10 import AnomalyDetector
    return AnomalyDetector()


@pytest.fixture
def mock_behavior_profiler():
    """行動プロファイラーモック"""
    from src.phase10 import BehaviorProfiler
    return BehaviorProfiler()


@pytest.fixture
def mock_threat_predictor():
    """脅威予測エンジンモック"""
    from src.phase10 import ThreatPredictor
    return ThreatPredictor()


@pytest.fixture
def mock_ml_pipeline():
    """ML パイプラインモック"""
    from src.phase10 import MLPipelineManager
    return MLPipelineManager()


# ========== Step 4: グローバル統合テスト用フィクスチャ ==========

class MockGlobalSecurityOrchestrator:
    """テスト用モック GlobalSecurityOrchestrator"""
    
    def __init__(self):
        self.regions = {}
        self.policies = {}
        self.compliance_status = {}
    
    def register_region(self, region):
        """リージョン登録"""
        self.regions[region.get('name')] = region
        return True
    
    def get_active_regions(self):
        """アクティブなリージョン取得"""
        return list(self.regions.keys())
    
    def failover_to_region(self, region_name):
        """フェイルオーバー"""
        return region_name in self.regions
    
    def check_region_health(self, region_name):
        """リージョン健全性チェック"""
        return {
            'status': 'healthy',
            'latency': 50,
            'available': True
        }
    
    def configure_replication(self, config):
        """レプリケーション設定"""
        return True
    
    def create_global_policy(self, policy):
        """グローバルポリシー作成"""
        self.policies[policy.get('name')] = policy
        return True
    
    def enforce_global_policy(self, policy_name, regions):
        """ポリシー適用"""
        return True
    
    def apply_regional_override(self, override):
        """リージョン固有オーバーライド"""
        return True
    
    def verify_policy_compliance(self, policy_name):
        """ポリシーコンプライアンス検証"""
        return True
    
    def activate_business_continuity_plan(self, bcp):
        """ビジネス継続計画を活性化"""
        return True


class MockComplianceEngine:
    """テスト用モック ComplianceEngine"""
    
    def check_gdpr_compliance(self, context):
        """GDPR コンプライアンスチェック"""
        return True
    
    def check_ccpa_compliance(self, context):
        """CCPA コンプライアンスチェック"""
        return True
    
    def check_appi_compliance(self, context):
        """APPI コンプライアンスチェック"""
        return True
    
    def check_pipl_compliance(self, context):
        """PIPL コンプライアンスチェック"""
        return True
    
    def check_multi_framework_compliance(self, context):
        """複数フレームワークコンプライアンス"""
        if isinstance(context, dict):
            frameworks = context.get('frameworks', [])
        else:
            frameworks = ['gdpr', 'ccpa', 'appi']
        
        return {
            'compliant_count': len(frameworks),
            'total_frameworks': len(frameworks),
            'status': 'compliant'
        }


class MockMetricsAggregator:
    """テスト用モック SecurityMetricsAggregator"""
    
    def collect_regional_metrics(self, metrics_dict):
        """リージョナルメトリクス収集"""
        return metrics_dict
    
    def aggregate_global_metrics(self, metrics_by_region=None, **kwargs):
        """グローバルメトリクス集約"""
        if metrics_by_region is None:
            metrics_by_region = {}
        
        total_incidents = sum(m.get('incidents', 0) for m in metrics_by_region.values())
        avg_response_time = sum(
            m.get('avg_response_time', 0) for m in metrics_by_region.values()
        ) / len(metrics_by_region) if metrics_by_region else 0
        
        return {
            'total_incidents': total_incidents,
            'global_avg_response_time': avg_response_time
        }
    
    def calculate_security_posture_score(self, metrics):
        """セキュリティ体勢スコア計算"""
        if not metrics:
            return 0
        
        avg_score = (sum(metrics.values()) / len(metrics)) * 100
        return min(100, max(0, avg_score))
    
    def generate_kpi_dashboard(self, kpis=None):
        """KPI ダッシュボード生成"""
        from datetime import datetime
        return {
            'timestamp': datetime.now().isoformat(),
            'kpis': {
                'mttr': 145,
                'incident_count': 16,
                'detection_rate': 0.97,
                'mtta': 120
            }
        }
    
    def query_performance_metrics(self, metric_type):
        """パフォーマンスメトリクス照会"""
        if metric_type == 'policy_enforcement':
            return {'latency_ms': 8500}
        elif metric_type == 'global_query':
            return {'latency_ms': 1850}
        return {}


@pytest.fixture
def mock_global_orchestrator():
    """グローバル統制オーケストレーターモック"""
    return MockGlobalSecurityOrchestrator()


@pytest.fixture
def mock_compliance_engine():
    """コンプライアンスエンジンモック"""
    return MockComplianceEngine()


@pytest.fixture
def mock_metrics_aggregator():
    """メトリクス集約オーケストレーターモック"""
    return MockMetricsAggregator()


@pytest.fixture
def mock_metrics_aggregator():
    """メトリクス集約エンジンモック"""
    from src.phase10 import SecurityMetricsAggregator
    return SecurityMetricsAggregator()


@pytest.fixture
def mock_password_manager():
    """パスワード管理モック"""
    class MockPasswordManager:
        def force_password_reset(self, user_id):
            return True
    return MockPasswordManager()

