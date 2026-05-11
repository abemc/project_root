"""
Phase 10 Step 1: 24/7 Security Operations Center (SOC) - メインエンジン

850行の総合SOCエンジン実装
- リアルタイムセキュリティイベント処理
- 自動脅威分類・スコアリング
- 自動対応・インシデント生成
- エスカレーション管理・通知

パフォーマンス目標:
- イベント処理: < 100ms
- 脅威分類: < 50ms
- 自動対応: < 2秒
- 検知率: > 99.8%
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from enum import Enum
import logging
from collections import defaultdict, deque
import hashlib

logger = logging.getLogger(__name__)


# ========== 列挙型 ==========

class ThreatLevel(Enum):
    """脅威レベル"""
    CRITICAL = 5
    HIGH = 4
    MEDIUM = 3
    LOW = 2
    INFO = 1


class EventType(Enum):
    """セキュリティイベント種別"""
    AUTHENTICATION = "authentication"
    ACCESS = "access"
    DATA = "data"
    INFRASTRUCTURE = "infrastructure"
    NETWORK = "network"
    MALWARE = "malware"
    POLICY_VIOLATION = "policy_violation"
    CONFIGURATION = "configuration"


class ResponseAction(Enum):
    """自動対応アクション"""
    ALERT = "alert"
    BLOCK_USER = "block_user"
    ISOLATE_SYSTEM = "isolate_system"
    REVOKE_SESSION = "revoke_session"
    ENABLE_MFA = "enable_mfa"
    QUARANTINE_FILE = "quarantine_file"
    DISABLE_API_KEY = "disable_api_key"
    TRIGGER_AUDIT = "trigger_audit"


# ========== データクラス ==========

@dataclass
class SecurityEvent:
    """セキュリティイベント"""
    event_id: str
    timestamp: datetime
    event_type: EventType
    source_user: str
    source_ip: str
    resource: str
    action: str
    details: Dict[str, Any]
    raw_log: str = ""
    
    def to_dict(self) -> Dict:
        data = asdict(self)
        data['event_type'] = self.event_type.value
        data['timestamp'] = self.timestamp.isoformat()
        return data


@dataclass
class ThreatSignal:
    """脅威シグナル（複数のイベントから導出）"""
    signal_id: str
    threat_level: ThreatLevel
    signal_type: str
    description: str
    contributing_events: List[str] = field(default_factory=list)
    confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Incident:
    """セキュリティインシデント"""
    incident_id: str
    created_at: datetime
    threat_level: ThreatLevel
    title: str
    description: str
    affected_users: List[str] = field(default_factory=list)
    affected_resources: List[str] = field(default_factory=list)
    events: List[str] = field(default_factory=list)
    signals: List[str] = field(default_factory=list)
    recommended_actions: List[ResponseAction] = field(default_factory=list)
    status: str = "open"
    severity_score: float = 0.0
    
    def to_dict(self) -> Dict:
        data = asdict(self)
        data['threat_level'] = self.threat_level.value
        data['recommended_actions'] = [a.value for a in self.recommended_actions]
        data['created_at'] = self.created_at.isoformat()
        return data


# ========== イベント処理コンポーネント ==========

class EventProcessor:
    """セキュリティイベント処理・正規化"""
    
    def __init__(self):
        self.event_cache = {}
        self.sequence_buffer = defaultdict(deque)
    
    def process_authentication_event(self, log_entry: Dict) -> Optional[SecurityEvent]:
        """認証イベント処理"""
        try:
            event = SecurityEvent(
                event_id=self._generate_event_id(log_entry),
                timestamp=self._parse_timestamp(log_entry.get('timestamp')),
                event_type=EventType.AUTHENTICATION,
                source_user=log_entry.get('username', 'unknown'),
                source_ip=log_entry.get('source_ip', '0.0.0.0'),
                resource='auth_system',
                action=log_entry.get('result', 'attempt'),
                details={
                    'auth_method': log_entry.get('auth_method'),
                    'success': log_entry.get('result') == 'success',
                    'mfa_used': log_entry.get('mfa_used', False),
                    'device': log_entry.get('device')
                },
                raw_log=json.dumps(log_entry)
            )
            return event
        except Exception as e:
            logger.error(f"Failed to process auth event: {e}")
            return None
    
    def process_access_event(self, log_entry: Dict) -> Optional[SecurityEvent]:
        """アクセスイベント処理"""
        try:
            event = SecurityEvent(
                event_id=self._generate_event_id(log_entry),
                timestamp=self._parse_timestamp(log_entry.get('timestamp')),
                event_type=EventType.ACCESS,
                source_user=log_entry.get('user', 'unknown'),
                source_ip=log_entry.get('source_ip'),
                resource=log_entry.get('resource'),
                action=log_entry.get('action'),
                details={
                    'access_type': log_entry.get('access_type'),
                    'permission': log_entry.get('permission'),
                    'granted': log_entry.get('granted', False)
                },
                raw_log=json.dumps(log_entry)
            )
            return event
        except Exception as e:
            logger.error(f"Failed to process access event: {e}")
            return None
    
    def process_data_event(self, log_entry: Dict) -> Optional[SecurityEvent]:
        """データイベント処理"""
        try:
            event = SecurityEvent(
                event_id=self._generate_event_id(log_entry),
                timestamp=self._parse_timestamp(log_entry.get('timestamp')),
                event_type=EventType.DATA,
                source_user=log_entry.get('user'),
                source_ip=log_entry.get('source_ip'),
                resource=log_entry.get('data_resource'),
                action=log_entry.get('operation'),
                details={
                    'operation': log_entry.get('operation'),
                    'record_count': log_entry.get('record_count'),
                    'data_classification': log_entry.get('data_classification'),
                    'encrypted': log_entry.get('encrypted', False)
                },
                raw_log=json.dumps(log_entry)
            )
            return event
        except Exception as e:
            logger.error(f"Failed to process data event: {e}")
            return None
    
    def process_infrastructure_event(self, log_entry: Dict) -> Optional[SecurityEvent]:
        """インフライベント処理"""
        try:
            event = SecurityEvent(
                event_id=self._generate_event_id(log_entry),
                timestamp=self._parse_timestamp(log_entry.get('timestamp')),
                event_type=EventType.INFRASTRUCTURE,
                source_user=log_entry.get('actor', 'system'),
                source_ip=log_entry.get('source_ip', '0.0.0.0'),
                resource=log_entry.get('resource'),
                action=log_entry.get('action'),
                details={
                    'resource_type': log_entry.get('resource_type'),
                    'change_type': log_entry.get('change_type'),
                    'severity': log_entry.get('severity')
                },
                raw_log=json.dumps(log_entry)
            )
            return event
        except Exception as e:
            logger.error(f"Failed to process infrastructure event: {e}")
            return None
    
    def _generate_event_id(self, log_entry: Dict) -> str:
        """イベントID生成"""
        content = json.dumps(log_entry, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def _parse_timestamp(self, ts_str: str) -> datetime:
        """タイムスタンプ解析"""
        if isinstance(ts_str, str):
            try:
                return datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
            except:
                return datetime.now()
        return datetime.now()


# ========== 脅威分類エンジン ==========

class ThreatClassifier:
    """多層脅威分類・スコアリング"""
    
    def __init__(self):
        self.threat_rules = self._initialize_threat_rules()
        self.event_history = defaultdict(list)
    
    def classify_by_severity(self, event: SecurityEvent) -> ThreatLevel:
        """重大度による脅威分類"""
        if event.event_type == EventType.AUTHENTICATION:
            return self._classify_auth_event(event)
        elif event.event_type == EventType.ACCESS:
            return self._classify_access_event(event)
        elif event.event_type == EventType.DATA:
            return self._classify_data_event(event)
        elif event.event_type == EventType.INFRASTRUCTURE:
            return self._classify_infra_event(event)
        else:
            return ThreatLevel.LOW
    
    def _classify_auth_event(self, event: SecurityEvent) -> ThreatLevel:
        """認証イベント分類ロジック"""
        details = event.details
        
        # 失敗した認証
        if not details.get('success'):
            # MFA未使用 + 失敗 = HIGH
            if not details.get('mfa_used'):
                return ThreatLevel.HIGH
            return ThreatLevel.MEDIUM
        
        # 成功したが MFA 未使用
        if details.get('success') and not details.get('mfa_used'):
            return ThreatLevel.MEDIUM
        
        return ThreatLevel.LOW
    
    def _classify_access_event(self, event: SecurityEvent) -> ThreatLevel:
        """アクセスイベント分類ロジック"""
        details = event.details
        
        if not details.get('granted'):
            return ThreatLevel.MEDIUM
        
        # リソースタイプによる重大度判定
        resource = event.resource.lower()
        if any(x in resource for x in ['admin', 'critical', 'sensitive']):
            return ThreatLevel.HIGH
        
        return ThreatLevel.LOW
    
    def _classify_data_event(self, event: SecurityEvent) -> ThreatLevel:
        """データイベント分類ロジック"""
        details = event.details
        classification = details.get('data_classification', '').lower()
        
        # 機密データ + Delete/Export = CRITICAL
        if classification in ['secret', 'restricted', 'confidential']:
            if details.get('operation') in ['delete', 'export', 'read_bulk']:
                return ThreatLevel.CRITICAL
            return ThreatLevel.HIGH
        
        # 暗号化されていない重要データ
        if not details.get('encrypted') and classification in ['internal', 'sensitive']:
            return ThreatLevel.MEDIUM
        
        return ThreatLevel.LOW
    
    def _classify_infra_event(self, event: SecurityEvent) -> ThreatLevel:
        """インフライベント分類ロジック"""
        severity = event.details.get('severity', '').lower()
        
        if severity in ['critical', 'emergency']:
            return ThreatLevel.CRITICAL
        elif severity in ['high', 'error']:
            return ThreatLevel.HIGH
        elif severity == 'warning':
            return ThreatLevel.MEDIUM
        
        return ThreatLevel.LOW
    
    def correlate_events(self, events: List[SecurityEvent]) -> List[ThreatSignal]:
        """複数イベント相関分析"""
        signals = []
        
        # 1. 同一ユーザーの短時間内の複数失敗ログイン
        failed_logins = self._correlate_failed_logins(events)
        signals.extend(failed_logins)
        
        # 2. 異常なデータアクセスパターン
        data_anomalies = self._correlate_data_anomalies(events)
        signals.extend(data_anomalies)
        
        # 3. 権限昇格 + 機密データアクセス
        privilege_escalation = self._correlate_privilege_escalation(events)
        signals.extend(privilege_escalation)
        
        return signals
    
    def _correlate_failed_logins(self, events: List[SecurityEvent]) -> List[ThreatSignal]:
        """失敗したログイン相関分析"""
        signals = []
        failed_by_user = defaultdict(list)
        
        for event in events:
            if event.event_type == EventType.AUTHENTICATION and not event.details.get('success'):
                failed_by_user[event.source_user].append(event)
        
        for user, user_events in failed_by_user.items():
            # 5分以内に5回以上の失敗 = ブルートフォース攻撃
            if len(user_events) >= 5:
                time_span = (user_events[-1].timestamp - user_events[0].timestamp).total_seconds()
                if time_span < 300:  # 5分以内
                    signal = ThreatSignal(
                        signal_id=f"bruteforce_{user}_{datetime.now().timestamp()}",
                        threat_level=ThreatLevel.CRITICAL,
                        signal_type="brute_force_attack",
                        description=f"Brute force attack detected for user {user}: {len(user_events)} failed attempts",
                        contributing_events=[e.event_id for e in user_events],
                        confidence=0.95
                    )
                    signals.append(signal)
        
        return signals
    
    def _correlate_data_anomalies(self, events: List[SecurityEvent]) -> List[ThreatSignal]:
        """データアクセス異常相関分析"""
        signals = []
        
        # ユーザーごとの大量データアクセス
        data_access_by_user = defaultdict(list)
        for event in events:
            if event.event_type == EventType.DATA and event.details.get('granted'):
                data_access_by_user[event.source_user].append(event)
        
        for user, user_events in data_access_by_user.items():
            total_records = sum(e.details.get('record_count', 0) for e in user_events)
            
            # 短時間に大量データ読み出し = データ流出の可能性
            if len(user_events) >= 10 or total_records > 100000:
                signal = ThreatSignal(
                    signal_id=f"data_exfil_{user}_{datetime.now().timestamp()}",
                    threat_level=ThreatLevel.HIGH,
                    signal_type="potential_data_exfiltration",
                    description=f"Unusual data access pattern for {user}: {len(user_events)} accesses, {total_records} records",
                    contributing_events=[e.event_id for e in user_events],
                    confidence=0.80
                )
                signals.append(signal)
        
        return signals
    
    def _correlate_privilege_escalation(self, events: List[SecurityEvent]) -> List[ThreatSignal]:
        """権限昇格相関分析"""
        signals = []
        
        # 権限昇格 → 機密データアクセス の組み合わせ
        for event in events:
            if event.event_type == EventType.ACCESS and 'privilege' in event.action.lower():
                # その後の機密データアクセスを検索
                for other_event in events:
                    if other_event.event_type == EventType.DATA and other_event.source_user == event.source_user:
                        time_diff = (other_event.timestamp - event.timestamp).total_seconds()
                        if 0 < time_diff < 60:  # 1分以内
                            if other_event.details.get('data_classification') in ['secret', 'restricted']:
                                signal = ThreatSignal(
                                    signal_id=f"priv_esc_{event.source_user}_{datetime.now().timestamp()}",
                                    threat_level=ThreatLevel.CRITICAL,
                                    signal_type="privilege_escalation_and_access",
                                    description=f"Privilege escalation followed by sensitive data access for {event.source_user}",
                                    contributing_events=[event.event_id, other_event.event_id],
                                    confidence=0.92
                                )
                                signals.append(signal)
        
        return signals
    
    def _initialize_threat_rules(self) -> Dict:
        """脅威ルール初期化"""
        return {
            'brute_force': {'threshold': 5, 'window': 300},
            'data_exfil': {'threshold': 100000, 'window': 600},
        }


# ========== 自動対応エンジン ==========

class AutoResponder:
    """自動対応・自動修復エンジン"""
    
    def __init__(self):
        self.response_rules = self._initialize_response_rules()
        self.action_history = []
    
    def respond_to_critical_threat(self, incident: Incident) -> List[ResponseAction]:
        """CRITICAL 脅威への自動対応"""
        actions = []
        
        if "brute_force" in incident.description.lower():
            actions.append(ResponseAction.BLOCK_USER)
            actions.append(ResponseAction.ENABLE_MFA)
            actions.append(ResponseAction.TRIGGER_AUDIT)
        
        if "privilege_escalation" in incident.description.lower():
            actions.append(ResponseAction.REVOKE_SESSION)
            actions.append(ResponseAction.ISOLATE_SYSTEM)
            actions.append(ResponseAction.TRIGGER_AUDIT)
        
        if "data_exfil" in incident.description.lower():
            actions.append(ResponseAction.BLOCK_USER)
            actions.append(ResponseAction.DISABLE_API_KEY)
            actions.append(ResponseAction.QUARANTINE_FILE)
        
        return actions
    
    def respond_to_suspicious_login(self, event: SecurityEvent) -> Optional[ResponseAction]:
        """疑わしいログイン検出時の対応"""
        if not event.details.get('success'):
            return ResponseAction.ALERT
        
        if not event.details.get('mfa_used'):
            return ResponseAction.ENABLE_MFA
        
        return None
    
    def respond_to_unauthorized_access(self, event: SecurityEvent) -> Optional[ResponseAction]:
        """無許可アクセス時の対応"""
        if not event.details.get('granted'):
            return ResponseAction.ALERT
        return None
    
    def respond_to_malware_detection(self, event: SecurityEvent) -> List[ResponseAction]:
        """マルウェア検出時の対応"""
        return [
            ResponseAction.QUARANTINE_FILE,
            ResponseAction.ALERT,
            ResponseAction.TRIGGER_AUDIT
        ]
    
    async def execute_response_action(self, action: ResponseAction, incident: Incident) -> bool:
        """対応アクション実行"""
        try:
            if action == ResponseAction.BLOCK_USER:
                logger.info(f"Blocking users: {incident.affected_users}")
                await self._block_users(incident.affected_users)
            
            elif action == ResponseAction.REVOKE_SESSION:
                logger.info(f"Revoking sessions for users: {incident.affected_users}")
                await self._revoke_sessions(incident.affected_users)
            
            elif action == ResponseAction.ISOLATE_SYSTEM:
                logger.info(f"Isolating systems: {incident.affected_resources}")
                await self._isolate_systems(incident.affected_resources)
            
            elif action == ResponseAction.QUARANTINE_FILE:
                logger.info(f"Quarantining files/resources: {incident.affected_resources}")
                await self._quarantine_resources(incident.affected_resources)
            
            elif action == ResponseAction.TRIGGER_AUDIT:
                logger.info(f"Triggering audit for incident {incident.incident_id}")
                await self._trigger_audit(incident)
            
            self.action_history.append({
                'incident_id': incident.incident_id,
                'action': action.value,
                'timestamp': datetime.now(),
                'status': 'executed'
            })
            return True
        
        except Exception as e:
            logger.error(f"Failed to execute action {action.value}: {e}")
            return False
    
    async def _block_users(self, users: List[str]) -> None:
        """ユーザーブロック処理（シミュレーション）"""
        await asyncio.sleep(0.1)
    
    async def _revoke_sessions(self, users: List[str]) -> None:
        """セッション無効化処理（シミュレーション）"""
        await asyncio.sleep(0.1)
    
    async def _isolate_systems(self, systems: List[str]) -> None:
        """システム分離処理（シミュレーション）"""
        await asyncio.sleep(0.1)
    
    async def _quarantine_resources(self, resources: List[str]) -> None:
        """リソース隔離処理（シミュレーション）"""
        await asyncio.sleep(0.1)
    
    async def _trigger_audit(self, incident: Incident) -> None:
        """監査トリガー処理（シミュレーション）"""
        await asyncio.sleep(0.1)
    
    def _initialize_response_rules(self) -> Dict:
        """対応ルール初期化"""
        return {}


# ========== エスカレーション管理 ==========

class EscalationManager:
    """セキュリティ脅威のエスカレーション管理"""
    
    def __init__(self):
        self.escalation_levels = {
            ThreatLevel.INFO: {'timeout': 3600, 'notify': ['log']},
            ThreatLevel.LOW: {'timeout': 1800, 'notify': ['log', 'dashboard']},
            ThreatLevel.MEDIUM: {'timeout': 900, 'notify': ['log', 'dashboard', 'email']},
            ThreatLevel.HIGH: {'timeout': 300, 'notify': ['log', 'dashboard', 'email', 'sms']},
            ThreatLevel.CRITICAL: {'timeout': 60, 'notify': ['log', 'dashboard', 'email', 'sms', 'pagerduty']}
        }
        self.open_incidents = {}
    
    async def handle_critical_threat(self, incident: Incident) -> None:
        """CRITICAL 脅威処理"""
        logger.critical(f"CRITICAL INCIDENT: {incident.incident_id} - {incident.title}")
        
        # 直ちに通知
        await self._notify_security_team(incident, channels=['pagerduty', 'sms', 'email'])
        
        # 自動対応実行
        responder = AutoResponder()
        for action in incident.recommended_actions:
            await responder.execute_response_action(action, incident)
    
    async def handle_high_threat(self, incident: Incident) -> None:
        """HIGH 脅威処理"""
        logger.warning(f"HIGH INCIDENT: {incident.incident_id} - {incident.title}")
        
        # セキュリティチーム通知
        await self._notify_security_team(incident, channels=['email', 'sms'])
        
        # 一部の自動対応実行
        responder = AutoResponder()
        for action in incident.recommended_actions[:2]:  # 最初の2つのアクションのみ
            await responder.execute_response_action(action, incident)
    
    async def handle_medium_threat(self, incident: Incident) -> None:
        """MEDIUM 脅威処理"""
        logger.warning(f"MEDIUM INCIDENT: {incident.incident_id} - {incident.title}")
        
        # ダッシュボード・ログに記録
        await self._notify_security_team(incident, channels=['dashboard', 'email'])
    
    async def _notify_security_team(self, incident: Incident, channels: List[str]) -> None:
        """セキュリティチーム通知"""
        message = {
            'incident_id': incident.incident_id,
            'title': incident.title,
            'threat_level': incident.threat_level.name,
            'timestamp': incident.created_at.isoformat(),
            'affected_users': incident.affected_users,
            'affected_resources': incident.affected_resources
        }
        
        for channel in channels:
            await self._send_notification(channel, message)
    
    async def _send_notification(self, channel: str, message: Dict) -> None:
        """通知送信（チャネル別）"""
        if channel == 'pagerduty':
            logger.info(f"[PagerDuty] {message}")
        elif channel == 'email':
            logger.info(f"[Email] {message}")
        elif channel == 'sms':
            logger.info(f"[SMS] {message}")
        elif channel == 'dashboard':
            logger.info(f"[Dashboard] {message}")
        elif channel == 'log':
            logger.info(f"[Log] {message}")
        
        await asyncio.sleep(0.05)
    
    def generate_incident_report(self, incident: Incident) -> Dict:
        """インシデント報告書生成"""
        return {
            'incident_id': incident.incident_id,
            'created_at': incident.created_at.isoformat(),
            'threat_level': incident.threat_level.name,
            'title': incident.title,
            'description': incident.description,
            'affected_users': incident.affected_users,
            'affected_resources': incident.affected_resources,
            'event_count': len(incident.events),
            'signal_count': len(incident.signals),
            'recommended_actions': [a.value for a in incident.recommended_actions],
            'severity_score': incident.severity_score,
            'status': incident.status
        }


# ========== 統合SOCエンジン ==========

class SecurityOperationsCenter:
    """24/7 セキュリティ運用センター エンジン"""
    
    def __init__(self):
        self.event_processor = EventProcessor()
        self.threat_classifier = ThreatClassifier()
        self.auto_responder = AutoResponder()
        self.escalation_manager = EscalationManager()
        
        # ストレージ
        self.events = {}
        self.signals = {}
        self.incidents = {}
        
        # メトリクス
        self.metrics = {
            'events_processed': 0,
            'threats_detected': 0,
            'incidents_created': 0,
            'auto_responses': 0,
            'avg_detection_time_ms': 0,
            'avg_response_time_ms': 0
        }
    
    async def process_security_event(self, log_entry: Dict) -> Optional[str]:
        """セキュリティイベント処理（メインパイプライン）"""
        start_time = datetime.now()
        
        # 1. イベント正規化
        event_type = log_entry.get('event_type', 'generic')
        
        if event_type == 'authentication':
            event = self.event_processor.process_authentication_event(log_entry)
        elif event_type == 'access':
            event = self.event_processor.process_access_event(log_entry)
        elif event_type == 'data':
            event = self.event_processor.process_data_event(log_entry)
        elif event_type == 'infrastructure':
            event = self.event_processor.process_infrastructure_event(log_entry)
        else:
            return None
        
        if not event:
            return None
        
        # イベント保存
        self.events[event.event_id] = event
        
        # 2. 脅威分類
        threat_level = self.threat_classifier.classify_by_severity(event)
        
        # 3. イベント相関分析
        events_list = list(self.events.values())
        signals = self.threat_classifier.correlate_events(events_list[-100:])  # 直近100イベント
        
        for signal in signals:
            self.signals[signal.signal_id] = signal
        
        # 4. インシデント生成（必要に応じて）
        incident_id = None
        if threat_level.value >= ThreatLevel.MEDIUM.value or signals:
            incident = self._create_incident(event, threat_level, signals)
            incident_id = incident.incident_id
            
            # エスカレーション処理
            if incident.threat_level == ThreatLevel.CRITICAL:
                await self.escalation_manager.handle_critical_threat(incident)
            elif incident.threat_level == ThreatLevel.HIGH:
                await self.escalation_manager.handle_high_threat(incident)
            
            self.metrics['incidents_created'] += 1
        
        # メトリクス更新
        self.metrics['events_processed'] += 1
        detection_time = (datetime.now() - start_time).total_seconds() * 1000
        self.metrics['avg_detection_time_ms'] = detection_time
        
        if incident_id:
            self.metrics['threats_detected'] += 1
        
        return incident_id
    
    def _create_incident(self, event: SecurityEvent, threat_level: ThreatLevel, 
                        signals: List[ThreatSignal]) -> Incident:
        """インシデント生成"""
        incident = Incident(
            incident_id=f"INC_{datetime.now().timestamp()}",
            created_at=datetime.now(),
            threat_level=threat_level,
            title=f"{threat_level.name} Security Incident",
            description=f"Security event detected: {event.action}",
            affected_users=[event.source_user],
            affected_resources=[event.resource],
            events=[event.event_id],
            signals=[s.signal_id for s in signals],
            recommended_actions=self._recommend_actions(threat_level, event),
            severity_score=threat_level.value / 5.0
        )
        
        self.incidents[incident.incident_id] = incident
        return incident
    
    def _recommend_actions(self, threat_level: ThreatLevel, event: SecurityEvent) -> List[ResponseAction]:
        """対応アクション推奨"""
        actions = []
        
        if threat_level == ThreatLevel.CRITICAL:
            actions = [ResponseAction.ALERT, ResponseAction.TRIGGER_AUDIT]
        elif threat_level == ThreatLevel.HIGH:
            actions = [ResponseAction.ALERT]
        elif threat_level == ThreatLevel.MEDIUM:
            actions = [ResponseAction.ALERT]
        
        return actions
    
    def get_metrics(self) -> Dict:
        """SOC メトリクス取得"""
        return {
            **self.metrics,
            'total_events': len(self.events),
            'total_signals': len(self.signals),
            'total_incidents': len(self.incidents),
            'open_incidents': len([i for i in self.incidents.values() if i.status == 'open'])
        }
    
    def get_incident(self, incident_id: str) -> Optional[Dict]:
        """インシデント取得"""
        incident = self.incidents.get(incident_id)
        return incident.to_dict() if incident else None
    
    def list_incidents(self, status: Optional[str] = None) -> List[Dict]:
        """インシデント一覧"""
        incidents = self.incidents.values()
        if status:
            incidents = [i for i in incidents if i.status == status]
        return [i.to_dict() for i in incidents]
    
    def correlate_events_from_multiple_regions(self, regional_events: Dict[str, List[Dict]]) -> List[Dict]:
        """複数地域のイベントを相関分析
        
        Args:
            regional_events: {'region_name': [events], ...}
            
        Returns:
            相関検出されたイベントグループ
        """
        correlated_groups = []
        
        # 全地域のイベントを時系列で結合
        all_events = []
        for region, events in regional_events.items():
            for event in events:
                all_events.append({**event, 'region': region})
        
        # 時系列ソート
        all_events.sort(key=lambda e: e.get('timestamp', datetime.now()))
        
        # イベント相関ウィンドウ (5分)
        correlation_window = timedelta(minutes=5)
        
        i = 0
        while i < len(all_events):
            base_event = all_events[i]
            correlated = [base_event]
            
            # ウィンドウ内の同一ユーザー/ホストイベントを収集
            for j in range(i + 1, len(all_events)):
                candidate = all_events[j]
                time_diff = candidate.get('timestamp', datetime.now()) - base_event.get('timestamp', datetime.now())
                
                if time_diff > correlation_window:
                    break
                
                # 同一ユーザー/ホストをチェック
                if (base_event.get('user_id') == candidate.get('user_id') or
                    base_event.get('host_id') == candidate.get('host_id')):
                    correlated.append(candidate)
            
            # 複数イベントが相関している場合のみ記録
            if len(correlated) > 1:
                correlated_groups.append({
                    'group_id': f"group_{base_event.get('timestamp', datetime.now()).timestamp()}",
                    'events': correlated,
                    'regions': list(set(e['region'] for e in correlated)),
                    'event_count': len(correlated),
                    'threat_level': 'medium' if len(correlated) >= 3 else 'low'
                })
            
            i += 1
        
        return correlated_groups
