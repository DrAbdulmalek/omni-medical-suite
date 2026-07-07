"""
AI Fuel Engine - PHI Protection Module

Detects, masks, tags, and removes Protected Health Information (PHI) from
text content.  Supports seven PHI categories relevant to healthcare data
processing pipelines:

    - **EMAIL**: Email addresses
    - **PHONE**: Phone numbers (international and local)
    - **DATE**: Dates in various formats
    - **ID**: National / identification numbers
    - **NAME_AR**: Arabic person names
    - **NAME_EN**: English person names
    - **MRN**: Medical Record Numbers

All detections are audit-logged for compliance traceability.
"""

from __future__ import annotations

import logging
import re
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from core.schemas import PHIDetection

logger = logging.getLogger(__name__)


# ======================================================================
# PHI Type Registry
# ======================================================================

# Each entry maps a PHI type name to a list of regex patterns.
# Patterns are compiled lazily on first use to avoid startup cost.

_PHI_PATTERNS: Dict[str, List[str]] = {
    "EMAIL": [
        # Standard email regex
        r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
    ],
    "PHONE": [
        # International format +XXXXXXXXXX
        r"(?:\+?966|\+?971|\+?974|\+?965|\+?968|\+?20|\+?1)?[\\s\-]?"
        r"\(?\d{2,4}\)?[\\s\-]?\d{3,4}[\\s\-]?\d{3,4}",
        # Local Saudi format 05XXXXXXXX
        r"0[35]\d{8}",
        # With dashes
        r"\d{3}[-\s]\d{4}[-\s]\d{4}",
    ],
    "DATE": [
        # ISO / YYYY-MM-DD
        r"\d{4}[-/]\d{1,2}[-/]\d{1,2}",
        # DD/MM/YYYY or DD-MM-YYYY
        r"\d{1,2}[-/]\d{1,2}[-/]\d{4}",
        # DD Mon YYYY or Mon DD, YYYY
        r"\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
        r"[a-z]*[\s,]+\d{4}",
        # Month DD, YYYY
        r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
        r"[a-z]*\s+\d{1,2},?\s+\d{4}",
        # Hijri dates (approximate): YYYY/MM/DD or DD/MM/YYYY with Arabic numerals
        r"\d{4}[\/\-]\d{1,2}[\/\-]\d{1,2}",
    ],
    "ID": [
        # Saudi National ID: 10 digits
        r"\b[12]\d{9}\b",
        # Qatar ID: 11 digits
        r"\b2[789]\d{9}\b",
        # UAE ID: starts with 784, 11 digits
        r"\b784\d{8}\b",
        # General numeric ID (8-14 digits, not a year-like pattern)
        r"\b(?!\d{4}[-/])\d{8,14}\b",
    ],
    "MRN": [
        # MRN followed by number, or common patterns
        r"(?:MRN|mrn|Medical\s*Record|medical\s*record|Patient\s*ID|patient\s*id)"
        r"[\s:]*#?\s*\d{4,12}",
        # Standalone MRN-like identifiers with prefix
        r"\b(?:MRN|mrn)[-]?\d{4,12}\b",
    ],
    "NAME_EN": [
        # Title + Name pattern (Mr./Ms./Dr. + capitalized words)
        r"(?:Mr|Ms|Mrs|Miss|Dr|Prof|Sir|Madam)[.]\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3}",
        # All-caps name blocks (e.g., "JOHN SMITH" common in medical forms)
        r"\b[A-Z]{2,}(?:\s+[A-Z]{2,}){1,3}\b",
    ],
    "NAME_AR": [
        # Arabic name pattern: 2-4 consecutive Arabic words with common name prefixes
        r"(?:عبد[ال]?\s+)?[\u0621-\u064A]{2,8}(?:\s+[\u0621-\u064A]{2,8}){1,4}",
    ],
}

# Mask character for each PHI type
_MASK_CHAR: Dict[str, str] = {
    "EMAIL": "*",
    "PHONE": "X",
    "DATE": "X",
    "ID": "X",
    "MRN": "X",
    "NAME_EN": "[REDACTED]",
    "NAME_AR": "[محذوف]",
}


# ======================================================================
# Audit Log Entry
# ======================================================================

@dataclass
class _PHIAuditEntry:
    """Internal record for audit-trail logging."""

    phi_type: str
    value: str
    start_pos: int
    end_pos: int
    mode: str  # tag, mask, remove
    source_file: Optional[str] = None


# ======================================================================
# Compiled Pattern Cache
# ======================================================================

_compiled_cache: Dict[str, List[re.Pattern]] = {}


def _get_compiled_patterns() -> Dict[str, List[re.Pattern]]:
    """Lazily compile and cache regex patterns for all PHI types."""
    if _compiled_cache:
        return _compiled_cache

    for phi_type, patterns in _PHI_PATTERNS.items():
        compiled: List[re.Pattern] = []
        for pattern in patterns:
            try:
                compiled.append(re.compile(pattern, re.IGNORECASE | re.UNICODE))
            except re.error as exc:
                logger.warning("Invalid regex for PHI type %s: %s — skipping", phi_type, exc)
        _compiled_cache[phi_type] = compiled

    return _compiled_cache


# ======================================================================
# PHIMasker
# ======================================================================


class PHIMasker:
    """Detect and protect Protected Health Information in text.

    The masker supports three modes of operation:

    - **tag**: Wrap detected PHI with XML-like tags (e.g. ``<PHI_EMAIL>...</PHI_EMAIL>``).
    - **mask**: Replace detected PHI with a masking string of the same length.
    - **remove**: Remove the PHI value entirely from the text.

    All detections are recorded in an audit log accessible via
    :meth:`get_audit_log`.

    Args:
        masking_mode: One of ``"tag"``, ``"mask"``, ``"remove"``.
        enabled: Whether PHI protection is active (can be toggled at runtime).

    Usage::

        masker = PHIMasker(masking_mode="tag")
        detections = masker.detect("Contact john@example.com for MRN 123456")
        masked = masker.mask("Contact john@example.com for MRN 123456")
        # → "Contact <PHI_EMAIL>john@example.com</PHI_EMAIL> for <PHI_MRN>MRN 123456</PHI_MRN>"
    """

    def __init__(
        self,
        masking_mode: str = "tag",
        enabled: bool = True,
    ) -> None:
        if masking_mode not in {"tag", "mask", "remove"}:
            raise ValueError(
                f"masking_mode must be 'tag', 'mask', or 'remove', got '{masking_mode}'"
            )
        self.masking_mode = masking_mode
        self.enabled = enabled
        self._audit_log: List[_PHIAuditEntry] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect(
        self,
        text: str,
        source_file: Optional[str] = None,
    ) -> List[PHIDetection]:
        """Scan *text* for PHI and return detection results without modifying it.

        Args:
            text: The input text to scan.
            source_file: Optional source file name for audit logging.

        Returns:
            A list of :class:`PHIDetection` objects for each found PHI instance.
        """
        if not self.enabled or not text:
            return []

        detections = self._scan_text(text)
        self._log_detections(detections, mode="detect", source_file=source_file)
        return detections

    def mask(
        self,
        text: str,
        source_file: Optional[str] = None,
    ) -> str:
        """Detect PHI in *text* and return a masked version.

        The masking behavior depends on :attr:`masking_mode`:

        - ``tag``: Wraps PHI with ``<PHI_TYPE>...</PHI_TYPE>`` tags.
        - ``mask``: Replaces characters with ``*`` or ``X``.
        - ``remove``: Strips the PHI value entirely.

        Args:
            text: The input text to protect.
            source_file: Optional source file name for audit logging.

        Returns:
            The protected text string.
        """
        if not self.enabled or not text:
            return text

        detections = self._scan_text(text)
        self._log_detections(detections, mode=self.masking_mode, source_file=source_file)

        # Sort detections by start_pos descending so we can replace from
        # the end without invalidating earlier positions.
        sorted_detections = sorted(detections, key=lambda d: d.start_pos, reverse=True)
        protected_text = list(text)

        for det in sorted_detections:
            if self.masking_mode == "tag":
                replacement = f"<PHI_{det.phi_type}>{det.value}</PHI_{det.phi_type}>"
                protected_text[det.start_pos : det.end_pos] = list(replacement)
            elif self.masking_mode == "mask":
                mask_char = _MASK_CHAR.get(det.phi_type, "X")
                # For multi-char mask strings, use the string as-is
                if len(mask_char) > 1:
                    protected_text[det.start_pos : det.end_pos] = list(mask_char)
                else:
                    for i in range(det.start_pos, det.end_pos):
                        protected_text[i] = mask_char
            elif self.masking_mode == "remove":
                protected_text[det.start_pos : det.end_pos] = []

        return "".join(protected_text)

    def remove(
        self,
        text: str,
        source_file: Optional[str] = None,
    ) -> str:
        """Convenience method that masks with ``remove`` mode.

        Equivalent to calling ``mask(text, source_file)`` with
        ``masking_mode="remove"``.

        Args:
            text: The input text.
            source_file: Optional source file name.

        Returns:
            Text with all PHI removed.
        """
        original_mode = self.masking_mode
        self.masking_mode = "remove"
        try:
            return self.mask(text, source_file=source_file)
        finally:
            self.masking_mode = original_mode

    def tag(
        self,
        text: str,
        source_file: Optional[str] = None,
    ) -> str:
        """Convenience method that masks with ``tag`` mode.

        Equivalent to calling ``mask(text, source_file)`` with
        ``masking_mode="tag"``.

        Args:
            text: The input text.
            source_file: Optional source file name.

        Returns:
            Text with PHI wrapped in XML-like tags.
        """
        original_mode = self.masking_mode
        self.masking_mode = "tag"
        try:
            return self.mask(text, source_file=source_file)
        finally:
            self.masking_mode = original_mode

    def get_audit_log(self) -> List[Dict[str, object]]:
        """Return the full audit log of PHI detections.

        Returns:
            A list of dictionaries with keys: ``phi_type``, ``value``,
            ``start_pos``, ``end_pos``, ``mode``, ``source_file``.
        """
        return [
            {
                "phi_type": entry.phi_type,
                "value": entry.value,
                "start_pos": entry.start_pos,
                "end_pos": entry.end_pos,
                "mode": entry.mode,
                "source_file": entry.source_file,
            }
            for entry in self._audit_log
        ]

    def clear_audit_log(self) -> None:
        """Clear all entries from the audit log."""
        self._audit_log.clear()
        logger.info("PHI audit log cleared")

    def enable(self) -> None:
        """Enable PHI detection and masking."""
        self.enabled = True
        logger.info("PHI protection enabled")

    def disable(self) -> None:
        """Disable PHI detection and masking."""
        self.enabled = False
        logger.warning("PHI protection DISABLED — sensitive data may be exposed")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _scan_text(self, text: str) -> List[PHIDetection]:
        """Run all PHI pattern detectors over *text* and deduplicate overlapping spans."""
        patterns = _get_compiled_patterns()
        all_detections: List[PHIDetection] = []

        for phi_type, compiled_list in patterns.items():
            for pattern in compiled_list:
                for match in pattern.finditer(text):
                    value = match.group()
                    start = match.start()
                    end = match.end()
                    mask_char = _MASK_CHAR.get(phi_type, "X")
                    masked = mask_char if len(mask_char) > 1 else mask_char * len(value)

                    detection = PHIDetection(
                        phi_type=phi_type,
                        value=value,
                        start_pos=start,
                        end_pos=end,
                        masked_value=masked,
                    )
                    all_detections.append(detection)

        return self._resolve_overlaps(all_detections)

    @staticmethod
    def _resolve_overlaps(detections: List[PHIDetection]) -> List[PHIDetection]:
        """Remove overlapping detections, keeping the longest span.

        Overlapping PHI patterns (e.g., a name inside an email) are resolved
        by preferring the detection with the longer character span.  When spans
        are equal length the first detection wins.
        """
        if not detections:
            return []

        # Sort by start position, then by span length (descending)
        detections.sort(key=lambda d: (d.start_pos, -(d.end_pos - d.start_pos)))

        resolved: List[PHIDetection] = []
        last_end = -1

        for det in detections:
            if det.start_pos >= last_end:
                resolved.append(det)
                last_end = det.end_pos

        return resolved

    def _log_detections(
        self,
        detections: List[PHIDetection],
        mode: str,
        source_file: Optional[str] = None,
    ) -> None:
        """Append detections to the audit log."""
        for det in detections:
            entry = _PHIAuditEntry(
                phi_type=det.phi_type,
                value=det.value,
                start_pos=det.start_pos,
                end_pos=det.end_pos,
                mode=mode,
                source_file=source_file,
            )
            self._audit_log.append(entry)

        if detections:
            logger.info(
                "PHI audit: %d detection(s) [%s] in %s",
                len(detections),
                ", ".join(d.phi_type for d in detections),
                source_file or "<unknown>",
            )
