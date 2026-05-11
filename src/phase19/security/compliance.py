"""
GDPR・SOC2 コンプライアンス実装

規制要件への準拠
- GDPR: データ主体の権利
- SOC2: セキュリティ・可用性・処理整合性
- コンプライアンス監視
"""

import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


class GDPRRight(Enum):
    """GDPR データ主体の権利"""
    ACCESS = "access"                  # アクセス権
    DELETION = "deletion"              # 削除権
    PORTABILITY = "portability"        # ポータビリティ権
    OBJECTION = "objection"            # 異議権
    RECTIFICATION = "rectification"    # 訂正権


class SOC2Control(Enum):
    """SOC2 管理体制"""
    ACCESS_CONTROL = "access_control"
    DATA_INTEGRITY = "data_integrity"
    AVAILABILITY = "availability"
    CONFIDENTIALITY = "confidentiality"
    SECURITY_EVENT = "security_event"


@dataclass
class GDPRRequest:
    """GDPR リクエスト"""
    request_id: str
    right: GDPRRight
    user_id: str
    requested_at: datetime
    status: str  # "pending", "approved", "rejected", "completed"
    details: Dict[str, Any] = field(default_factory=dict)
    completed_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "request_id": self.request_id,
            "right": self.right.value,
            "user_id": self.user_id,
            "requested_at": self.requested_at.isoformat(),
            "status": self.status,
            "details": self.details,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


@dataclass
class ComplianceStatus:
    """コンプライアンス状態"""
    gdpr_compliant: bool = True
    soc2_compliant: bool = True
    last_audit: Optional[datetime] = None
    pending_issues: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "gdpr_compliant": self.gdpr_compliant,
            "soc2_compliant": self.soc2_compliant,
            "last_audit": self.last_audit.isoformat() if self.last_audit else None,
            "pending_issues": self.pending_issues,
        }


class GDPRCompliance:
    """GDPR準拠"""
    
    def __init__(self):
        """初期化"""
        self.requests: Dict[str, GDPRRequest] = {}
        self.request_counter = 0
        self.data_processors: List[str] = []  # DPA対象プロセッサ
        self.retention_policies: Dict[str, int] = {}  # データ保持期限（日）
    
    def create_access_request(
        self,
        user_id: str,
        details: Optional[Dict] = None
    ) -> GDPRRequest:
        """アクセス権リクエストを作成"""
        self.request_counter += 1
        request_id = f"GDPR_ACC_{self.request_counter:06d}"
        
        request = GDPRRequest(
            request_id=request_id,
            right=GDPRRight.ACCESS,
            user_id=user_id,
            requested_at=datetime.now(),
            status="pending",
            details=details or {}
        )
        
        self.requests[request_id] = request
        logger.info(f"GDPR access request created: {request_id}")
        return request
    
    def create_deletion_request(
        self,
        user_id: str,
        details: Optional[Dict] = None
    ) -> GDPRRequest:
        """削除権（忘れられる権利）リクエストを作成"""
        self.request_counter += 1
        request_id = f"GDPR_DEL_{self.request_counter:06d}"
        
        request = GDPRRequest(
            request_id=request_id,
            right=GDPRRight.DELETION,
            user_id=user_id,
            requested_at=datetime.now(),
            status="pending",
            details=details or {}
        )
        
        self.requests[request_id] = request
        logger.info(f"GDPR deletion request created: {request_id}")
        return request
    
    def create_portability_request(
        self,
        user_id: str,
        format: str = "json"
    ) -> GDPRRequest:
        """ポータビリティ権リクエストを作成"""
        self.request_counter += 1
        request_id = f"GDPR_PORT_{self.request_counter:06d}"
        
        request = GDPRRequest(
            request_id=request_id,
            right=GDPRRight.PORTABILITY,
            user_id=user_id,
            requested_at=datetime.now(),
            status="pending",
            details={"format": format}
        )
        
        self.requests[request_id] = request
        logger.info(f"GDPR portability request created: {request_id}")
        return request
    
    def approve_request(self, request_id: str) -> GDPRRequest:
        """GDPR リクエストを承認"""
        if request_id not in self.requests:
            raise ValueError(f"Request not found: {request_id}")
        
        request = self.requests[request_id]
        request.status = "approved"
        logger.info(f"GDPR request approved: {request_id}")
        return request
    
    def complete_request(self, request_id: str) -> GDPRRequest:
        """GDPR リクエストを完了"""
        if request_id not in self.requests:
            raise ValueError(f"Request not found: {request_id}")
        
        request = self.requests[request_id]
        request.status = "completed"
        request.completed_at = datetime.now()
        logger.info(f"GDPR request completed: {request_id}")
        return request
    
    def get_request(self, request_id: str) -> Optional[GDPRRequest]:
        """GDPR リクエストを取得"""
        return self.requests.get(request_id)
    
    def get_pending_requests(self, user_id: Optional[str] = None) -> List[GDPRRequest]:
        """保留中のリクエストを取得"""
        requests = [r for r in self.requests.values() if r.status == "pending"]
        if user_id:
            requests = [r for r in requests if r.user_id == user_id]
        return requests
    
    def add_data_processor(self, processor_name: str) -> None:
        """データプロセッサを追加（DPA対象）"""
        if processor_name not in self.data_processors:
            self.data_processors.append(processor_name)
            logger.info(f"Data processor added: {processor_name}")
    
    def set_retention_policy(self, data_type: str, retention_days: int) -> None:
        """データ保持ポリシーを設定"""
        self.retention_policies[data_type] = retention_days
        logger.info(f"Retention policy set: {data_type} = {retention_days} days")
    
    def check_retention_compliance(
        self,
        data_type: str,
        created_date: datetime
    ) -> bool:
        """保持期限コンプライアンスをチェック"""
        if data_type not in self.retention_policies:
            return True
        
        retention_days = self.retention_policies[data_type]
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        return created_date > cutoff_date


class SOC2Compliance:
    """SOC2準拠"""
    
    def __init__(self):
        """初期化"""
        self.controls: Dict[SOC2Control, Dict[str, Any]] = {
            control: {
                "implemented": False,
                "tested": False,
                "last_test": None,
                "status": "not_started"
            }
            for control in SOC2Control
        }
        self.incidents: List[Dict[str, Any]] = []
        self.incident_counter = 0
    
    def implement_control(self, control: SOC2Control) -> None:
        """管理体制を実装"""
        self.controls[control]["implemented"] = True
        logger.info(f"SOC2 control implemented: {control.value}")
    
    def test_control(self, control: SOC2Control, test_result: bool) -> None:
        """管理体制をテスト"""
        self.controls[control]["tested"] = True
        self.controls[control]["last_test"] = datetime.now()
        self.controls[control]["status"] = "passed" if test_result else "failed"
        logger.info(f"SOC2 control tested: {control.value} - {self.controls[control]['status']}")
    
    def report_incident(
        self,
        incident_type: str,
        severity: str,
        description: str,
        details: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """インシデントを報告"""
        self.incident_counter += 1
        incident_id = f"INC{self.incident_counter:06d}"
        
        incident = {
            "incident_id": incident_id,
            "type": incident_type,
            "severity": severity,
            "description": description,
            "reported_at": datetime.now().isoformat(),
            "details": details or {},
            "resolved": False,
        }
        
        self.incidents.append(incident)
        logger.warning(f"Incident reported: {incident_id} ({severity})")
        return incident
    
    def resolve_incident(self, incident_id: str) -> Optional[Dict]:
        """インシデントを解決"""
        for incident in self.incidents:
            if incident["incident_id"] == incident_id:
                incident["resolved"] = True
                incident["resolved_at"] = datetime.now().isoformat()
                logger.info(f"Incident resolved: {incident_id}")
                return incident
        return None
    
    def get_control_status(self) -> Dict[str, Dict[str, Any]]:
        """管理体制のステータスを取得"""
        return {
            control.value: self.controls[control]
            for control in SOC2Control
        }
    
    def get_unresolved_incidents(self) -> List[Dict[str, Any]]:
        """未解決のインシデントを取得"""
        return [i for i in self.incidents if not i.get("resolved", False)]


class ComplianceChecker:
    """コンプライアンス確認"""
    
    def __init__(self):
        """初期化"""
        self.gdpr = GDPRCompliance()
        self.soc2 = SOC2Compliance()
        self.status = ComplianceStatus()
    
    def check_overall_compliance(self) -> ComplianceStatus:
        """全体的なコンプライアンスをチェック"""
        # GDPR確認
        pending_gdpr = len(self.gdpr.get_pending_requests())
        self.status.gdpr_compliant = pending_gdpr == 0
        
        # SOC2確認
        control_status = self.soc2.get_control_status()
        failed_controls = sum(1 for c in control_status.values() if c["status"] == "failed")
        unresolved_incidents = len(self.soc2.get_unresolved_incidents())
        self.status.soc2_compliant = (failed_controls == 0 and unresolved_incidents == 0)
        
        # 保留中の問題
        pending_issues = []
        if pending_gdpr > 0:
            pending_issues.append(f"GDPR: {pending_gdpr} pending requests")
        if failed_controls > 0:
            pending_issues.append(f"SOC2: {failed_controls} failed controls")
        if unresolved_incidents > 0:
            pending_issues.append(f"SOC2: {unresolved_incidents} unresolved incidents")
        
        self.status.pending_issues = pending_issues
        self.status.last_audit = datetime.now()
        
        return self.status
    
    def generate_compliance_report(self) -> Dict[str, Any]:
        """コンプライアンスレポートを生成"""
        status = self.check_overall_compliance()
        
        control_status = self.soc2.get_control_status()
        implemented_count = sum(1 for c in control_status.values() if c["implemented"])
        tested_count = sum(1 for c in control_status.values() if c["tested"])
        
        return {
            "report_generated": datetime.now().isoformat(),
            "overall_status": {
                "gdpr_compliant": status.gdpr_compliant,
                "soc2_compliant": status.soc2_compliant,
                "compliant": status.gdpr_compliant and status.soc2_compliant,
            },
            "gdpr": {
                "pending_requests": len(self.gdpr.get_pending_requests()),
                "completed_requests": sum(1 for r in self.gdpr.requests.values() if r.status == "completed"),
                "data_processors": len(self.gdpr.data_processors),
            },
            "soc2": {
                "implemented_controls": implemented_count,
                "tested_controls": tested_count,
                "unresolved_incidents": len(self.soc2.get_unresolved_incidents()),
                "control_details": control_status,
            },
            "pending_issues": status.pending_issues,
        }


# グローバルインスタンス
_global_compliance_checker: Optional[ComplianceChecker] = None


def get_compliance_checker() -> ComplianceChecker:
    """グローバル コンプライアンスチェッカーを取得"""
    global _global_compliance_checker
    if _global_compliance_checker is None:
        _global_compliance_checker = ComplianceChecker()
    return _global_compliance_checker
