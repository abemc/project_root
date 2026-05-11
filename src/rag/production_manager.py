"""
Phase 7 RAG 本番化対応マネージャー
Days 6-7: 本番環境準備
- リソース制約管理
- エラー復旧戦略
- セキュリティ対応
- 本番環境設定
"""

import psutil
from typing import Dict, Optional, List, Any
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import json
from datetime import datetime


class ResourceConstraint(Enum):
    """リソース制約レベル"""
    UNLIMITED = "unlimited"  # 制約なし
    MODERATE = "moderate"    # 適度な制約
    STRICT = "strict"        # 厳しい制約
    EMERGENCY = "emergency"  # 緊急時


@dataclass
class SystemResources:
    """システムリソース情報"""
    total_memory_gb: float
    available_memory_gb: float
    cpu_count: int
    cpu_percent: float
    disk_available_gb: float
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    @property
    def memory_usage_percent(self) -> float:
        """メモリ使用率（%）"""
        if self.total_memory_gb == 0:
            return 0.0
        return (1 - self.available_memory_gb / self.total_memory_gb) * 100
    
    def to_dict(self) -> Dict:
        """辞書形式に変換"""
        return {
            'total_memory_gb': self.total_memory_gb,
            'available_memory_gb': self.available_memory_gb,
            'memory_usage_percent': f"{self.memory_usage_percent:.1f}%",
            'cpu_count': self.cpu_count,
            'cpu_percent': f"{self.cpu_percent:.1f}%",
            'disk_available_gb': self.disk_available_gb,
            'timestamp': self.timestamp
        }


@dataclass
class ProductionConfig:
    """本番環境設定"""
    # リソース設定
    max_cache_size_mb: int = 500
    max_workers: int = 4
    max_query_queue: int = 100
    resource_constraint: ResourceConstraint = ResourceConstraint.MODERATE
    
    # タイムアウト設定（秒）
    query_timeout_sec: int = 30
    retrieval_timeout_sec: int = 20
    integration_timeout_sec: int = 15
    generation_timeout_sec: int = 10
    
    # エラー対応設定
    max_retries: int = 3
    retry_delay_sec: int = 1
    fallback_enabled: bool = True
    emergency_shutdown_enabled: bool = True
    
    # セキュリティ設定
    input_validation_enabled: bool = True
    rate_limiting_enabled: bool = True
    rate_limit_requests_per_minute: int = 60
    log_sensitive_data: bool = False
    
    # ログ設定
    log_query_inputs: bool = True
    log_response_times: bool = True
    log_errors_only: bool = False
    
    def to_dict(self) -> Dict:
        """辞書形式に変換"""
        return {
            'resource': {
                'max_cache_size_mb': self.max_cache_size_mb,
                'max_workers': self.max_workers,
                'max_query_queue': self.max_query_queue,
                'constraint_level': self.resource_constraint.value
            },
            'timeouts': {
                'query_sec': self.query_timeout_sec,
                'retrieval_sec': self.retrieval_timeout_sec,
                'integration_sec': self.integration_timeout_sec,
                'generation_sec': self.generation_timeout_sec
            },
            'error_handling': {
                'max_retries': self.max_retries,
                'retry_delay_sec': self.retry_delay_sec,
                'fallback_enabled': self.fallback_enabled,
                'emergency_shutdown_enabled': self.emergency_shutdown_enabled
            },
            'security': {
                'input_validation': self.input_validation_enabled,
                'rate_limiting': self.rate_limiting_enabled,
                'rate_limit_rpm': self.rate_limit_requests_per_minute,
                'log_sensitive_data': self.log_sensitive_data
            },
            'logging': {
                'log_query_inputs': self.log_query_inputs,
                'log_response_times': self.log_response_times,
                'log_errors_only': self.log_errors_only
            }
        }


class ResourceMonitor:
    """リソース監視"""
    
    def __init__(self, 
                 alert_memory_percent: float = 80.0,
                 alert_cpu_percent: float = 85.0,
                 alert_disk_percent: float = 90.0):
        """
        Args:
            alert_memory_percent: メモリ使用率 アラート閾値(%)
            alert_cpu_percent: CPU使用率 アラート閾値(%)
            alert_disk_percent: ディスク使用率 アラート閾値(%)
        """
        self.alert_memory_percent = alert_memory_percent
        self.alert_cpu_percent = alert_cpu_percent
        self.alert_disk_percent = alert_disk_percent
        
        self.alerts: List[Dict] = []
    
    def get_system_resources(self) -> SystemResources:
        """システムリソース取得"""
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        resources = SystemResources(
            total_memory_gb=mem.total / (1024**3),
            available_memory_gb=mem.available / (1024**3),
            cpu_count=psutil.cpu_count(),
            cpu_percent=psutil.cpu_percent(interval=0.1),
            disk_available_gb=disk.free / (1024**3)
        )
        
        return resources
    
    def check_resource_constraints(
        self,
        resources: SystemResources
    ) -> tuple[ResourceConstraint, List[str]]:
        """
        リソース制約レベルを判定
        
        Returns:
            (constraint_level, alerts): 制約レベルとアラートメッセージ
        """
        alerts = []
        
        # メモリチェック
        if resources.memory_usage_percent > self.alert_memory_percent:
            alerts.append(
                f"メモリ使用率が高い: {resources.memory_usage_percent:.1f}% "
                f"(利用可能: {resources.available_memory_gb:.1f}GB)"
            )
        
        # CPU チェック
        if resources.cpu_percent > self.alert_cpu_percent:
            alerts.append(
                f"CPU使用率が高い: {resources.cpu_percent:.1f}%"
            )
        
        # ディスク チェック
        disk_total = psutil.disk_usage('/').total / (1024**3)
        disk_used = (disk_total - resources.disk_available_gb) / disk_total * 100
        if disk_used > self.alert_disk_percent:
            alerts.append(
                f"ディスク使用率が高い: {disk_used:.1f}% "
                f"(利用可能: {resources.disk_available_gb:.1f}GB)"
            )
        
        # 制約レベル判定
        if len(alerts) >= 3 or resources.memory_usage_percent > 95:
            constraint_level = ResourceConstraint.EMERGENCY
        elif len(alerts) >= 2 or resources.memory_usage_percent > 85:
            constraint_level = ResourceConstraint.STRICT
        elif len(alerts) >= 1:
            constraint_level = ResourceConstraint.MODERATE
        else:
            constraint_level = ResourceConstraint.UNLIMITED
        
        self.alerts.extend(alerts)
        return constraint_level, alerts
    
    def print_status(self) -> None:
        """ステータス表示"""
        resources = self.get_system_resources()
        constraint, alerts = self.check_resource_constraints(resources)
        
        print("\n📊 リソースモニタ状態:")
        print(f"  メモリ: {resources.available_memory_gb:.1f}GB / {resources.total_memory_gb:.1f}GB "
              f"({resources.memory_usage_percent:.1f}%)")
        print(f"  CPU: {resources.cpu_percent:.1f}% ({resources.cpu_count}コア)")
        print(f"  ディスク: {resources.disk_available_gb:.1f}GB 利用可能")
        print(f"  制約レベル: {constraint.value.upper()}")
        
        if alerts:
            print(f"\n  ⚠️  アラート ({len(alerts)}件):")
            for alert in alerts:
                print(f"    - {alert}")


class ErrorRecoveryStrategy:
    """エラー復旧戦略"""
    
    def __init__(self, max_retries: int = 3, retry_delay_sec: int = 1):
        """
        Args:
            max_retries: 最大リトライ回数
            retry_delay_sec: リトライ間隔（秒）
        """
        self.max_retries = max_retries
        self.retry_delay_sec = retry_delay_sec
        self.recovery_count = 0
        self.failed_operations: List[Dict] = []
    
    def get_retry_config(self, error_type: str) -> Dict[str, int]:
        """エラー種別に応じたリトライ設定を取得"""
        retry_configs = {
            'QueryProcessingError': {'max_retries': 2, 'delay_sec': 1},
            'RetrievalError': {'max_retries': 3, 'delay_sec': 2},
            'KnowledgeIntegrationError': {'max_retries': 1, 'delay_sec': 1},
            'GenerationError': {'max_retries': 2, 'delay_sec': 3},
            'TimeoutError': {'max_retries': 2, 'delay_sec': 5},
        }
        return retry_configs.get(
            error_type,
            {'max_retries': self.max_retries, 'delay_sec': self.retry_delay_sec}
        )
    
    def record_failed_operation(
        self,
        operation: str,
        error: str,
        context: Dict[str, Any]
    ) -> None:
        """失敗した操作を記録"""
        self.failed_operations.append({
            'timestamp': datetime.now().isoformat(),
            'operation': operation,
            'error': error,
            'context': context,
            'recovery_count': self.recovery_count
        })
    
    def get_recovery_summary(self) -> Dict:
        """復旧サマリー取得"""
        return {
            'total_recovery_attempts': self.recovery_count,
            'total_failures': len(self.failed_operations),
            'recent_failures': self.failed_operations[-5:] if self.failed_operations else []
        }


class SecurityManager:
    """セキュリティマネージャー"""
    
    def __init__(self, config: ProductionConfig):
        """
        Args:
            config: 本番環境設定
        """
        self.config = config
        self.request_log: List[Dict] = []
        self.blocked_requests = 0
    
    def validate_input(self, query: str, max_length: int = 1000) -> tuple[bool, Optional[str]]:
        """
        入力値検証
        
        Returns:
            (is_valid, error_message): 検証結果とエラーメッセージ
        """
        if not self.config.input_validation_enabled:
            return True, None
        
        # 空チェック
        if not query or not query.strip():
            return False, "クエリが空です"
        
        # 長さチェック
        if len(query) > max_length:
            return False, f"クエリが長すぎます (最大{max_length}文字)"
        
        # インジェクション検出（簡易版）
        dangerous_patterns = ['<script', 'javascript:', 'input', ';--', 'union select']
        if any(pattern in query.lower() for pattern in dangerous_patterns):
            return False, "危険な入力パターンが検出されました"
        
        return True, None
    
    def check_rate_limit(self, user_id: str) -> tuple[bool, Optional[str]]:
        """
        レート制限チェック
        
        Returns:
            (is_allowed, error_message): 許可/拒否とメッセージ
        """
        if not self.config.rate_limiting_enabled:
            return True, None
        
        # 1分以内のリクエスト数をカウント
        now = datetime.now().timestamp()
        one_minute_ago = now - 60
        
        user_requests = [
            r for r in self.request_log
            if r['user_id'] == user_id and r['timestamp'] > one_minute_ago
        ]
        
        if len(user_requests) >= self.config.rate_limit_requests_per_minute:
            self.blocked_requests += 1
            return False, f"レート制限に達しました（{self.config.rate_limit_requests_per_minute}リクエスト/分）"
        
        return True, None
    
    def log_request(
        self,
        user_id: str,
        query: str,
        status: str,
        response_time_ms: float
    ) -> None:
        """リクエストログ"""
        entry = {
            'timestamp': datetime.now().timestamp(),
            'user_id': user_id,
            'query': query if self.config.log_query_inputs else '<redacted>',
            'status': status,
            'response_time_ms': response_time_ms
        }
        self.request_log.append(entry)
        
        # ログサイズ制限
        if len(self.request_log) > 10000:
            self.request_log = self.request_log[-5000:]
    
    def get_security_metrics(self) -> Dict:
        """セキュリティメトリクス"""
        return {
            'total_requests': len(self.request_log),
            'blocked_requests': self.blocked_requests,
            'block_rate': f"{self.blocked_requests/max(1, len(self.request_log))*100:.1f}%"
        }


class ProductionManager:
    """本番化管理マネージャー"""
    
    def __init__(self, config: Optional[ProductionConfig] = None):
        """
        Args:
            config: 本番環境設定
        """
        self.config = config or ProductionConfig()
        
        # ロギング初期化
        from src.rag.error_handling import Phase7Logger
        log_file = Path('/home/abemc/project_root/logs/production.log')
        self.logger = Phase7Logger(
            name='ProductionManager',
            log_file=log_file,
            enable_console=False,
            enable_file=True
        )
        
        self.resource_monitor = ResourceMonitor()
        self.error_recovery = ErrorRecoveryStrategy(
            self.config.max_retries,
            self.config.max_retries
        )
        self.security_manager = SecurityManager(self.config)
    
    def initialize(self) -> Dict[str, Any]:
        """本番化初期化"""
        resources = self.resource_monitor.get_system_resources()
        constraint, alerts = self.resource_monitor.check_resource_constraints(resources)
        
        init_status = {
            'status': 'initialized',
            'timestamp': datetime.now().isoformat(),
            'config': self.config.to_dict(),
            'resources': resources.to_dict(),
            'constraint_level': constraint.value,
            'alerts': alerts
        }
        
        return init_status
    
    def print_production_report(self) -> None:
        """本番化レポート表示"""
        print("\n" + "="*60)
        print("【本番化対応レポート】")
        print("="*60)
        
        print("\n【基本設定】")
        print(f"  リソース制約: {self.config.resource_constraint.value}")
        print(f"  キャッシュサイズ: {self.config.max_cache_size_mb}MB")
        print(f"  ワーカー数: {self.config.max_workers}")
        
        print("\n【タイムアウト設定】")
        print(f"  クエリ処理: {self.config.query_timeout_sec}秒")
        print(f"  検索: {self.config.retrieval_timeout_sec}秒")
        print(f"  知識統合: {self.config.integration_timeout_sec}秒")
        print(f"  生成: {self.config.generation_timeout_sec}秒")
        
        print("\n【エラー対応】")
        print(f"  最大リトライ: {self.config.max_retries}回")
        print(f"  リトライ間隔: {self.config.retry_delay_sec}秒")
        print(f"  フォールバック: {'有効' if self.config.fallback_enabled else '無効'}")
        
        print("\n【セキュリティ】")
        print(f"  入力検証: {'有効' if self.config.input_validation_enabled else '無効'}")
        print(f"  レート制限: {'有効' if self.config.rate_limiting_enabled else '無効'}")
        if self.config.rate_limiting_enabled:
            print(f"  制限: {self.config.rate_limit_requests_per_minute}リクエスト/分")
        
        print("\n【リソース】")
        self.resource_monitor.print_status()
        
        print("\n【セキュリティメトリクス】")
        metrics = self.security_manager.get_security_metrics()
        print(f"  総リクエスト: {metrics['total_requests']}")
        print(f"  拒否: {metrics['blocked_requests']}")
        print(f"  拒否率: {metrics['block_rate']}")
        
        print("\n" + "="*60)
    
    def save_config_to_file(self, filepath: Path) -> None:
        """設定をファイルに保存"""
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        config_dict = {
            'timestamp': datetime.now().isoformat(),
            'config': self.config.to_dict(),
            'resources': self.resource_monitor.get_system_resources().to_dict()
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(config_dict, f, ensure_ascii=False, indent=2)
    
    @staticmethod
    def load_config_from_file(filepath: Path) -> ProductionConfig:
        """ファイルから設定をロード"""
        with open(filepath, 'r', encoding='utf-8') as f:
            config_dict = json.load(f)
        
        cfg = config_dict['config']
        return ProductionConfig(
            max_cache_size_mb=cfg['resource']['max_cache_size_mb'],
            max_workers=cfg['resource']['max_workers'],
            max_query_queue=cfg['resource']['max_query_queue'],
            query_timeout_sec=cfg['timeouts']['query_sec'],
            retrieval_timeout_sec=cfg['timeouts']['retrieval_sec'],
            integration_timeout_sec=cfg['timeouts']['integration_sec'],
            generation_timeout_sec=cfg['timeouts']['generation_sec'],
            max_retries=cfg['error_handling']['max_retries'],
            retry_delay_sec=cfg['error_handling']['retry_delay_sec'],
            fallback_enabled=cfg['error_handling']['fallback_enabled'],
            rate_limiting_enabled=cfg['security']['rate_limiting'],
            rate_limit_requests_per_minute=cfg['security']['rate_limit_rpm']
        )
