"""GDPR Manager for handling GDPR compliance requirements."""

import json
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass, field


class ConsentType(Enum):
    """Types of user consent."""
    MARKETING = "marketing"
    ANALYTICS = "analytics"
    PERSONALIZATION = "personalization"
    DATA_PROCESSING = "data_processing"
    DATA_SHARING = "data_sharing"
    PROFILING = "profiling"
    AUTOMATED_DECISION_MAKING = "automated_decision_making"


class RequestStatus(Enum):
    """Status of GDPR requests."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    DENIED = "denied"
    EXPIRED = "expired"


@dataclass
class ConsentRecord:
    """Record of user consent."""
    user_id: str
    consent_type: ConsentType
    given: bool = True
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    expiry: Optional[str] = None
    channel: str = "web"  # web, email, app, etc.
    version: str = "1.0"
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

    def is_valid(self) -> bool:
        """Check if consent is still valid.
        
        Returns:
            True if consent hasn't expired
        """
        if not self.expiry:
            return True
        return datetime.fromisoformat(self.expiry) > datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "user_id": self.user_id,
            "consent_type": self.consent_type.value,
            "given": self.given,
            "timestamp": self.timestamp,
            "expiry": self.expiry,
            "channel": self.channel,
            "version": self.version,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "is_valid": self.is_valid()
        }


@dataclass
class GDPRRequest:
    """GDPR request (access, erasure, portability)."""
    request_id: str
    user_id: str
    request_type: str  # access, erasure, portability, rectification, restriction
    status: RequestStatus = RequestStatus.PENDING
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    deadline: Optional[str] = None
    reason: Optional[str] = None
    data_categories: List[str] = field(default_factory=list)
    notes: str = ""

    def is_overdue(self) -> bool:
        """Check if request is overdue (30 days is standard GDPR limit).
        
        Returns:
            True if request exceeds 30 days
        """
        created = datetime.fromisoformat(self.created_at)
        return (datetime.utcnow() - created).days > 30

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "request_id": self.request_id,
            "user_id": self.user_id,
            "request_type": self.request_type,
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "deadline": self.deadline,
            "reason": self.reason,
            "data_categories": self.data_categories,
            "notes": self.notes,
            "is_overdue": self.is_overdue()
        }


class GDPRManager:
    """Manages GDPR compliance and user rights.
    
    Handles:
    - Right to access
    - Right to erasure
    - Right to data portability
    - Right to rectification
    - Right to restriction
    - Consent management
    - Processing activity records
    """

    def __init__(self):
        """Initialize GDPR manager."""
        self.consents: Dict[str, List[ConsentRecord]] = {}
        self.requests: Dict[str, GDPRRequest] = {}
        self.data_categories: Dict[str, List[str]] = {}  # user_id -> categories
        self.processing_records: List[Dict[str, Any]] = []

    def record_consent(
        self,
        user_id: str,
        consent_type: ConsentType,
        given: bool = True,
        expiry_days: Optional[int] = None,
        **kwargs
    ) -> ConsentRecord:
        """Record user consent.
        
        Args:
            user_id: User identifier
            consent_type: Type of consent
            given: Whether consent is given
            expiry_days: Days until consent expires (None = no expiry)
            **kwargs: Additional parameters (channel, version, ip_address, user_agent)
            
        Returns:
            ConsentRecord
        """
        expiry = None
        if expiry_days:
            expiry = (datetime.utcnow() + timedelta(days=expiry_days)).isoformat()

        consent = ConsentRecord(
            user_id=user_id,
            consent_type=consent_type,
            given=given,
            expiry=expiry,
            **kwargs
        )

        if user_id not in self.consents:
            self.consents[user_id] = []

        self.consents[user_id].append(consent)
        return consent

    def withdraw_consent(self, user_id: str, consent_type: ConsentType) -> bool:
        """Withdraw user consent.
        
        Args:
            user_id: User identifier
            consent_type: Type of consent to withdraw
            
        Returns:
            True if consent was withdrawn
        """
        if user_id not in self.consents:
            return False

        withdrawn = False
        for consent in self.consents[user_id]:
            if consent.consent_type == consent_type and consent.given:
                consent.given = False
                withdrawn = True

        return withdrawn

    def has_consent(self, user_id: str, consent_type: ConsentType) -> bool:
        """Check if user has valid consent.
        
        Args:
            user_id: User identifier
            consent_type: Type of consent
            
        Returns:
            True if user has given, valid consent
        """
        if user_id not in self.consents:
            return False

        for consent in self.consents[user_id]:
            if (consent.consent_type == consent_type and
                consent.given and
                consent.is_valid()):
                return True

        return False

    def get_consent_status(self, user_id: str) -> Dict[str, bool]:
        """Get all consent statuses for user.
        
        Args:
            user_id: User identifier
            
        Returns:
            Dictionary mapping consent type to status
        """
        status = {ct.value: False for ct in ConsentType}

        if user_id in self.consents:
            for consent in self.consents[user_id]:
                if consent.given and consent.is_valid():
                    status[consent.consent_type.value] = True

        return status

    def create_access_request(
        self,
        user_id: str,
        request_id: Optional[str] = None,
        reason: Optional[str] = None
    ) -> GDPRRequest:
        """Create right to access request.
        
        Args:
            user_id: User identifier
            request_id: Request ID (generated if not provided)
            reason: Request reason
            
        Returns:
            GDPRRequest
        """
        if not request_id:
            request_id = f"access_{user_id}_{int(datetime.utcnow().timestamp())}"

        deadline = (datetime.utcnow() + timedelta(days=30)).isoformat()

        request = GDPRRequest(
            request_id=request_id,
            user_id=user_id,
            request_type="access",
            deadline=deadline,
            reason=reason,
            data_categories=self._get_user_data_categories(user_id)
        )

        self.requests[request_id] = request
        return request

    def create_erasure_request(
        self,
        user_id: str,
        request_id: Optional[str] = None,
        reason: Optional[str] = None
    ) -> GDPRRequest:
        """Create right to erasure (right to be forgotten) request.
        
        Args:
            user_id: User identifier
            request_id: Request ID (generated if not provided)
            reason: Erasure reason
            
        Returns:
            GDPRRequest
        """
        if not request_id:
            request_id = f"erasure_{user_id}_{int(datetime.utcnow().timestamp())}"

        deadline = (datetime.utcnow() + timedelta(days=30)).isoformat()

        request = GDPRRequest(
            request_id=request_id,
            user_id=user_id,
            request_type="erasure",
            deadline=deadline,
            reason=reason,
            data_categories=self._get_user_data_categories(user_id)
        )

        self.requests[request_id] = request
        return request

    def create_portability_request(
        self,
        user_id: str,
        format_type: str = "json",
        request_id: Optional[str] = None
    ) -> GDPRRequest:
        """Create right to data portability request.
        
        Args:
            user_id: User identifier
            format_type: Requested data format (json, csv, xml)
            request_id: Request ID (generated if not provided)
            
        Returns:
            GDPRRequest
        """
        if not request_id:
            request_id = f"portability_{user_id}_{int(datetime.utcnow().timestamp())}"

        deadline = (datetime.utcnow() + timedelta(days=30)).isoformat()

        request = GDPRRequest(
            request_id=request_id,
            user_id=user_id,
            request_type="portability",
            deadline=deadline,
            data_categories=self._get_user_data_categories(user_id),
            notes=f"Format: {format_type}"
        )

        self.requests[request_id] = request
        return request

    def process_request(
        self,
        request_id: str,
        status: RequestStatus,
        notes: str = ""
    ) -> Optional[GDPRRequest]:
        """Update request processing status.
        
        Args:
            request_id: Request identifier
            status: New status
            notes: Processing notes
            
        Returns:
            Updated GDPRRequest or None if not found
        """
        if request_id not in self.requests:
            return None

        request = self.requests[request_id]
        request.status = status
        request.updated_at = datetime.utcnow().isoformat()
        if notes:
            request.notes = notes

        return request

    def complete_request(self, request_id: str, notes: str = "") -> Optional[GDPRRequest]:
        """Mark request as completed.
        
        Args:
            request_id: Request identifier
            notes: Completion notes
            
        Returns:
            Updated GDPRRequest or None if not found
        """
        return self.process_request(request_id, RequestStatus.COMPLETED, notes)

    def deny_request(self, request_id: str, reason: str) -> Optional[GDPRRequest]:
        """Deny a GDPR request.
        
        Args:
            request_id: Request identifier
            reason: Denial reason
            
        Returns:
            Updated GDPRRequest or None if not found
        """
        return self.process_request(request_id, RequestStatus.DENIED, reason)

    def get_request(self, request_id: str) -> Optional[GDPRRequest]:
        """Get request by ID.
        
        Args:
            request_id: Request identifier
            
        Returns:
            GDPRRequest or None if not found
        """
        return self.requests.get(request_id)

    def get_user_requests(self, user_id: str) -> List[GDPRRequest]:
        """Get all requests for user.
        
        Args:
            user_id: User identifier
            
        Returns:
            List of user's requests
        """
        return [r for r in self.requests.values() if r.user_id == user_id]

    def get_pending_requests(self) -> List[GDPRRequest]:
        """Get all pending requests.
        
        Returns:
            List of pending requests
        """
        return [r for r in self.requests.values() if r.status == RequestStatus.PENDING]

    def get_overdue_requests(self) -> List[GDPRRequest]:
        """Get all overdue requests.
        
        Returns:
            List of overdue requests
        """
        return [r for r in self.requests.values() if r.is_overdue()]

    def record_processing_activity(
        self,
        purpose: str,
        legal_basis: str,
        data_categories: List[str],
        recipients: List[str] = None,
        retention_period: Optional[str] = None
    ) -> Dict[str, Any]:
        """Record data processing activity.
        
        Args:
            purpose: Processing purpose
            legal_basis: Legal basis for processing
            data_categories: Categories of data processed
            recipients: Recipients of data
            retention_period: Data retention period
            
        Returns:
            Processing activity record
        """
        activity = {
            "id": f"activity_{int(datetime.utcnow().timestamp())}",
            "timestamp": datetime.utcnow().isoformat(),
            "purpose": purpose,
            "legal_basis": legal_basis,
            "data_categories": data_categories,
            "recipients": recipients or [],
            "retention_period": retention_period
        }

        self.processing_records.append(activity)
        return activity

    def register_user_data(self, user_id: str, data_categories: List[str]) -> None:
        """Register data categories for user.
        
        Args:
            user_id: User identifier
            data_categories: List of data categories
        """
        if user_id not in self.data_categories:
            self.data_categories[user_id] = []

        for category in data_categories:
            if category not in self.data_categories[user_id]:
                self.data_categories[user_id].append(category)

    def _get_user_data_categories(self, user_id: str) -> List[str]:
        """Get data categories for user.
        
        Args:
            user_id: User identifier
            
        Returns:
            List of data categories
        """
        return self.data_categories.get(user_id, [])

    def get_stats(self) -> Dict[str, Any]:
        """Get GDPR manager statistics.
        
        Returns:
            Statistics dictionary
        """
        total_requests = len(self.requests)
        requests_by_type = {}
        requests_by_status = {}

        for request in self.requests.values():
            requests_by_type[request.request_type] = requests_by_type.get(request.request_type, 0) + 1
            status_str = request.status.value
            requests_by_status[status_str] = requests_by_status.get(status_str, 0) + 1

        return {
            "total_users": len(self.consents) + len(self.data_categories),
            "total_requests": total_requests,
            "requests_by_type": requests_by_type,
            "requests_by_status": requests_by_status,
            "processing_activities": len(self.processing_records),
            "overdue_requests": len(self.get_overdue_requests())
        }
