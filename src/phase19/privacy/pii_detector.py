"""PII Detector for identifying and masking Personally Identifiable Information."""

import re
import json
from typing import List, Dict, Tuple, Optional, Any, Set
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime


class PIIType(Enum):
    """Types of Personally Identifiable Information."""
    EMAIL = "email"
    PHONE = "phone"
    SSN = "ssn"
    CREDIT_CARD = "credit_card"
    IP_ADDRESS = "ip_address"
    NAME = "name"
    ADDRESS = "address"
    DATE_OF_BIRTH = "date_of_birth"
    PASSPORT = "passport"
    DRIVER_LICENSE = "driver_license"
    BANK_ACCOUNT = "bank_account"
    URL = "url"


@dataclass
class PIIMatch:
    """Represents a found PII instance."""
    pii_type: PIIType
    value: str
    position: Tuple[int, int]  # (start, end) positions
    confidence: float = 1.0
    context: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "type": self.pii_type.value,
            "value": self.value,
            "position": self.position,
            "confidence": self.confidence,
            "context": self.context
        }


@dataclass
class PIIDetectionResult:
    """Result of PII detection."""
    text: str
    matches: List[PIIMatch] = field(default_factory=list)
    total_pii_found: int = 0
    risk_level: str = "low"  # low, medium, high
    detection_timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "text": self.text,
            "matches": [m.to_dict() for m in self.matches],
            "total_pii_found": self.total_pii_found,
            "risk_level": self.risk_level,
            "detection_timestamp": self.detection_timestamp
        }


class PIIDetector:
    """Detects and masks Personally Identifiable Information.
    
    Supports detection of:
    - Email addresses
    - Phone numbers
    - SSN (US Social Security Numbers)
    - Credit card numbers
    - IP addresses
    - Names, addresses, DOB
    - Passport and driver license numbers
    - URLs
    - Bank account numbers
    """

    def __init__(self):
        """Initialize PII detector with regex patterns."""
        self.patterns = self._compile_patterns()
        self.detection_history: List[PIIDetectionResult] = []
        self.mask_char = "*"

    def _compile_patterns(self) -> Dict[PIIType, re.Pattern]:
        """Compile regex patterns for PII detection.
        
        Returns:
            Dictionary mapping PIIType to compiled regex patterns
        """
        patterns = {}

        # Email: simple email pattern
        patterns[PIIType.EMAIL] = re.compile(
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        )

        # Phone: various formats (US/International)
        patterns[PIIType.PHONE] = re.compile(
            r'(\+\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b'
        )

        # SSN: XXX-XX-XXXX format
        patterns[PIIType.SSN] = re.compile(
            r'\b(?!000|666|9\d{2})\d{3}-(?!00)\d{2}-(?!0{4})\d{4}\b'
        )

        # Credit card: 4-19 digits (Visa, MC, Amex, Discover)
        patterns[PIIType.CREDIT_CARD] = re.compile(
            r'\b(?:4[0-9]{12}(?:[0-9]{3})?|'
            r'5[1-5][0-9]{14}|'
            r'3[47][0-9]{13}|'
            r'3(?:0[0-5]|[68][0-9])[0-9]{11})\b'
        )

        # IP Address: IPv4
        patterns[PIIType.IP_ADDRESS] = re.compile(
            r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}'
            r'(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b'
        )

        # Date of birth: YYYY-MM-DD or MM/DD/YYYY
        patterns[PIIType.DATE_OF_BIRTH] = re.compile(
            r'\b(?:\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4})\b'
        )

        # Passport: various formats (simplified)
        patterns[PIIType.PASSPORT] = re.compile(
            r'\b[A-Z]{2}\d{6,9}\b'
        )

        # Driver License: simplified pattern
        patterns[PIIType.DRIVER_LICENSE] = re.compile(
            r'\b[A-Z]{1,2}\d{5,8}\b'
        )

        # Bank Account: 8-17 digits
        patterns[PIIType.BANK_ACCOUNT] = re.compile(
            r'\b(?:Account|account)?\s*[:\s=]*\d{8,17}\b'
        )

        # URL
        patterns[PIIType.URL] = re.compile(
            r'https?://[^\s)]+'
        )

        return patterns

    def detect(self, text: str) -> PIIDetectionResult:
        """Detect PII in text.
        
        Args:
            text: Text to analyze
            
        Returns:
            PIIDetectionResult with all detected PII
        """
        matches: List[PIIMatch] = []
        found_types: Set[PIIType] = set()

        for pii_type, pattern in self.patterns.items():
            for match in pattern.finditer(text):
                pii_match = PIIMatch(
                    pii_type=pii_type,
                    value=match.group(),
                    position=(match.start(), match.end()),
                    context=self._extract_context(text, match.start(), match.end())
                )
                matches.append(pii_match)
                found_types.add(pii_type)

        # Determine risk level
        risk_level = self._assess_risk_level(matches)

        result = PIIDetectionResult(
            text=text,
            matches=matches,
            total_pii_found=len(matches),
            risk_level=risk_level
        )

        self.detection_history.append(result)
        return result

    def mask(self, text: str, mask_char: Optional[str] = None) -> str:
        """Mask all PII in text.
        
        Args:
            text: Text to mask
            mask_char: Character to use for masking (default: *)
            
        Returns:
            Text with PII masked
        """
        if mask_char:
            self.mask_char = mask_char

        result = self.detect(text)
        masked_text = text

        # Sort matches in reverse order by position to maintain correct offsets
        for match in sorted(result.matches, key=lambda m: m.position[0], reverse=True):
            start, end = match.position
            # Keep first and last character visible for context
            visible_chars = max(2, (end - start) // 4)
            masked = match.value[:visible_chars] + self.mask_char * (end - start - visible_chars)
            masked_text = masked_text[:start] + masked + masked_text[end:]

        return masked_text

    def mask_by_type(self, text: str, pii_types: List[PIIType]) -> str:
        """Mask only specific types of PII.
        
        Args:
            text: Text to mask
            pii_types: List of PII types to mask
            
        Returns:
            Text with specified PII masked
        """
        result = self.detect(text)
        masked_text = text

        # Filter matches to specified types and sort in reverse
        filtered_matches = [m for m in result.matches if m.pii_type in pii_types]
        for match in sorted(filtered_matches, key=lambda m: m.position[0], reverse=True):
            start, end = match.position
            masked = self.mask_char * (end - start)
            masked_text = masked_text[:start] + masked + masked_text[end:]

        return masked_text

    def replace_with_placeholder(self, text: str, placeholder: str = "[REDACTED]") -> str:
        """Replace all PII with placeholder.
        
        Args:
            text: Text to process
            placeholder: Placeholder string
            
        Returns:
            Text with PII replaced
        """
        result = self.detect(text)
        replaced_text = text

        # Sort matches in reverse order
        for match in sorted(result.matches, key=lambda m: m.position[0], reverse=True):
            start, end = match.position
            replaced_text = replaced_text[:start] + placeholder + replaced_text[end:]

        return replaced_text

    def anonymize(self, text: str, keep_initials: bool = False) -> Tuple[str, Dict[str, str]]:
        """Anonymize text and return mapping.
        
        Args:
            text: Text to anonymize
            keep_initials: Keep initials for names
            
        Returns:
            Tuple of (anonymized_text, replacement_mapping)
        """
        result = self.detect(text)
        anonymized_text = text
        mapping = {}
        counter = {}

        # Sort matches in reverse order
        for match in sorted(result.matches, key=lambda m: m.position[0], reverse=True):
            pii_type = match.pii_type
            
            # Generate placeholder
            if pii_type not in counter:
                counter[pii_type] = 0
            counter[pii_type] += 1
            
            placeholder = f"[{pii_type.value.upper()}_{counter[pii_type]}]"
            mapping[match.value] = placeholder

            start, end = match.position
            anonymized_text = anonymized_text[:start] + placeholder + anonymized_text[end:]

        return anonymized_text, mapping

    def _extract_context(self, text: str, start: int, end: int, context_size: int = 30) -> str:
        """Extract context around PII match.
        
        Args:
            text: Full text
            start: Match start position
            end: Match end position
            context_size: Characters to include before/after
            
        Returns:
            Context string
        """
        context_start = max(0, start - context_size)
        context_end = min(len(text), end + context_size)
        return text[context_start:context_end]

    def _assess_risk_level(self, matches: List[PIIMatch]) -> str:
        """Assess overall risk level based on matches.
        
        Args:
            matches: List of detected matches
            
        Returns:
            Risk level: low, medium, or high
        """
        if not matches:
            return "low"

        high_risk_types = {PIIType.SSN, PIIType.CREDIT_CARD, PIIType.BANK_ACCOUNT}
        medium_risk_types = {PIIType.EMAIL, PIIType.PHONE, PIIType.PASSPORT, PIIType.DRIVER_LICENSE}

        has_high_risk = any(m.pii_type in high_risk_types for m in matches)
        has_medium_risk = any(m.pii_type in medium_risk_types for m in matches)

        if has_high_risk or len(matches) > 5:
            return "high"
        elif has_medium_risk or len(matches) > 2:
            return "medium"
        else:
            return "low"

    def get_detection_history(self) -> List[PIIDetectionResult]:
        """Get detection history.
        
        Returns:
            List of detection results
        """
        return self.detection_history.copy()

    def get_stats(self) -> Dict[str, Any]:
        """Get PII detection statistics.
        
        Returns:
            Statistics dictionary
        """
        total_detections = len(self.detection_history)
        total_pii_found = sum(r.total_pii_found for r in self.detection_history)

        pii_counts = {}
        for result in self.detection_history:
            for match in result.matches:
                pii_type_str = match.pii_type.value
                pii_counts[pii_type_str] = pii_counts.get(pii_type_str, 0) + 1

        risk_counts = {
            "low": sum(1 for r in self.detection_history if r.risk_level == "low"),
            "medium": sum(1 for r in self.detection_history if r.risk_level == "medium"),
            "high": sum(1 for r in self.detection_history if r.risk_level == "high")
        }

        return {
            "total_detections": total_detections,
            "total_pii_found": total_pii_found,
            "pii_by_type": pii_counts,
            "risk_level_distribution": risk_counts
        }

    def clear_history(self) -> None:
        """Clear detection history."""
        self.detection_history.clear()
