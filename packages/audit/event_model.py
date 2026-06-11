"""
Unified Audit Event Model
==========================
Defines the standard event schema for the entire Medical OCR Ecosystem.
All audit events across omni-medical-suite, postprocessor, trainer, and benchmarks
should conform to this model for traceability and compliance.

Author: Dr. Abdulmalek
Version: 1.0.0
"""

import json
import uuid
import hashlib
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field, asdict


class EventCategory(str, Enum):
    OCR_PROCESSING = "ocr_processing"
    CORRECTION = "correction"
    PHI_DETECTION = "phi_detection"
    AUTH = "auth"
    DATA_ACCESS = "data_access"
    DATA_EXPORT = "data_export"
    SYSTEM = "system"
    TRAINING = "training"
    BENCHMARK = "benchmark"
    CONFIG_CHANGE = "config_change"


class EventSeverity(str, Enum):
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class PHIAction(str, Enum):
    DETECTED = "detected"
    MASKED = "masked"
    REDACTED = "redacted"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass
class AuditEvent:
    """
    Unified audit event for the Medical OCR Ecosystem.
    
    Every auditable action in the system produces an AuditEvent.
    Events are stored as JSONL (one JSON object per line) for
    efficient append-only logging and easy parsing.
    
    Traceability Chain:
        Each event links to its parent via parent_event_id,
        creating a full traceable chain of who did what, when,
        and what changed.
    """
    # Identity
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    parent_event_id: Optional[str] = None
    correlation_id: str = ""  # Groups related events (e.g., one document processing run)
    
    # Timing
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    # Classification
    category: EventCategory = EventCategory.SYSTEM
    severity: EventSeverity = EventSeverity.INFO
    action: str = ""  # Specific action: "ocr_run", "correction_apply", "phi_mask", etc.
    
    # Actor
    actor_type: str = "system"  # "user", "system", "api", "cron"
    actor_id: str = ""  # User ID, API key hash, or "system"
    actor_ip: str = ""
    
    # Resource
    resource_type: str = ""  # "document", "image", "model", "config"
    resource_id: str = ""
    
    # Details
    description: str = ""
    before_state: Optional[Dict[str, Any]] = None
    after_state: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # PHI tracking
    phi_detected: bool = False
    phi_action: Optional[PHIAction] = None
    phi_entities: List[Dict[str, str]] = field(default_factory=list)
    
    # Outcome
    success: bool = True
    error_message: str = ""
    duration_ms: float = 0.0
    
    # Integrity
    checksum: str = ""  # SHA-256 of all other fields for tamper detection

    def __post_init__(self):
        """Compute checksum after all fields are set."""
        if not self.checksum:
            self.checksum = self._compute_checksum()
        if not self.correlation_id:
            self.correlation_id = self.event_id

    def _compute_checksum(self) -> str:
        """Compute SHA-256 checksum of event data for tamper detection."""
        data = {
            "event_id": self.event_id,
            "parent_event_id": self.parent_event_id,
            "correlation_id": self.correlation_id,
            "timestamp": self.timestamp,
            "category": self.category.value if isinstance(self.category, Enum) else self.category,
            "action": self.action,
            "actor_id": self.actor_id,
            "resource_id": self.resource_id,
            "description": self.description,
            "success": self.success,
        }
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()

    def verify_checksum(self) -> bool:
        """Verify that the event has not been tampered with."""
        expected = self._compute_checksum()
        return expected == self.checksum

    def to_jsonl(self) -> str:
        """Serialize to JSONL format (single line JSON)."""
        data = asdict(self)
        # Convert enums to strings
        data["category"] = self.category.value if isinstance(self.category, Enum) else self.category
        data["severity"] = self.severity.value if isinstance(self.severity, Enum) else self.severity
        data["phi_action"] = self.phi_action.value if self.phi_action and isinstance(self.phi_action, Enum) else self.phi_action
        return json.dumps(data, ensure_ascii=False, default=str)

    @classmethod
    def from_jsonl(cls, line: str) -> "AuditEvent":
        """Deserialize from JSONL format."""
        data = json.loads(line)
        # Convert string enums back
        if "category" in data and isinstance(data["category"], str):
            data["category"] = EventCategory(data["category"])
        if "severity" in data and isinstance(data["severity"], str):
            data["severity"] = EventSeverity(data["severity"])
        if "phi_action" in data and data["phi_action"] and isinstance(data["phi_action"], str):
            data["phi_action"] = PHIAction(data["phi_action"])
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class AuditTrail:
    """
    Manages a chain of audit events for a single operation.
    
    Usage:
        trail = AuditTrail(correlation_id="doc-123", actor_id="user-456")
        trail.start("document_processing", "Processing medical document")
        trail.add_event("ocr_run", "PaddleOCR completed", after_state={"cer": 0.04})
        trail.add_event("correction_apply", "Applied 15 corrections")
        trail.add_event("phi_mask", "Masked 3 PHI entities", phi_detected=True)
        trail.end(success=True)
        
        for line in trail.to_jsonl():
            print(line)
    """

    def __init__(self, correlation_id: str = "", actor_id: str = "", actor_type: str = "system"):
        self.correlation_id = correlation_id or str(uuid.uuid4())
        self.actor_id = actor_id
        self.actor_type = actor_type
        self.events: List[AuditEvent] = []
        self._start_time: Optional[datetime] = None

    def start(self, action: str, description: str, resource_type: str = "", resource_id: str = "") -> AuditEvent:
        """Start a new audit trail."""
        self._start_time = datetime.now(timezone.utc)
        event = AuditEvent(
            correlation_id=self.correlation_id,
            category=EventCategory.SYSTEM,
            action=action,
            description=description,
            actor_type=self.actor_type,
            actor_id=self.actor_id,
            resource_type=resource_type,
            resource_id=resource_id,
        )
        self.events.append(event)
        return event

    def add_event(
        self,
        action: str,
        description: str,
        category: EventCategory = EventCategory.SYSTEM,
        severity: EventSeverity = EventSeverity.INFO,
        before_state: Optional[Dict] = None,
        after_state: Optional[Dict] = None,
        phi_detected: bool = False,
        phi_action: Optional[PHIAction] = None,
        phi_entities: Optional[List[Dict]] = None,
        success: bool = True,
        error_message: str = "",
        duration_ms: float = 0.0,
        resource_type: str = "",
        resource_id: str = "",
    ) -> AuditEvent:
        """Add an event to the trail."""
        parent_id = self.events[-1].event_id if self.events else None
        event = AuditEvent(
            parent_event_id=parent_id,
            correlation_id=self.correlation_id,
            category=category,
            severity=severity,
            action=action,
            description=description,
            actor_type=self.actor_type,
            actor_id=self.actor_id,
            before_state=before_state,
            after_state=after_state,
            phi_detected=phi_detected,
            phi_action=phi_action,
            phi_entities=phi_entities or [],
            success=success,
            error_message=error_message,
            duration_ms=duration_ms,
            resource_type=resource_type,
            resource_id=resource_id,
        )
        self.events.append(event)
        return event

    def end(self, success: bool = True, description: str = "Operation completed") -> AuditEvent:
        """End the audit trail."""
        duration = 0.0
        if self._start_time:
            duration = (datetime.now(timezone.utc) - self._start_time).total_seconds() * 1000
        
        parent_id = self.events[-1].event_id if self.events else None
        event = AuditEvent(
            parent_event_id=parent_id,
            correlation_id=self.correlation_id,
            category=EventCategory.SYSTEM,
            action="operation_complete",
            description=description,
            actor_type=self.actor_type,
            actor_id=self.actor_id,
            success=success,
            duration_ms=duration,
        )
        self.events.append(event)
        return event

    def to_jsonl(self) -> List[str]:
        """Export the full trail as JSONL lines."""
        return [event.to_jsonl() for event in self.events]

    def verify_integrity(self) -> bool:
        """Verify that no events in the trail have been tampered with."""
        return all(event.verify_checksum() for event in self.events)

    @property
    def event_count(self) -> int:
        return len(self.events)

    @property
    def has_errors(self) -> bool:
        return any(not e.success for e in self.events)

    @property
    def total_duration_ms(self) -> float:
        if len(self.events) < 2:
            return 0.0
        start = datetime.fromisoformat(self.events[0].timestamp)
        end = datetime.fromisoformat(self.events[-1].timestamp)
        return (end - start).total_seconds() * 1000