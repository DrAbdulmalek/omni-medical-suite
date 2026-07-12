"""Field extraction helpers for Arabic medical OCR output."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import re

from src.ocr.normalization import arabic_strong_normalize

LABEL_PATTERNS = {
    "patient_name": [
        re.compile(r"(?:اسم\s*المريض|المريض|Patient\s*Name)\s*[:：\-]?\s*(.+)", re.IGNORECASE),
    ],
    "patient_id": [
        re.compile(r"(?:رقم\s*(?:الملف|المريض|الهوية)|Patient\s*ID|MRN|ID)\s*[:：\-]?\s*([A-Z0-9\-/]{3,})", re.IGNORECASE),
    ],
    "date": [
        re.compile(r"(?:التاريخ|تاريخ\s*الزيارة|Date)\s*[:：\-]?\s*([0-9٠-٩\-/]{6,})", re.IGNORECASE),
    ],
    "doctor_name": [
        re.compile(r"(?:اسم\s*الطبيب|الطبيب|Doctor)\s*[:：\-]?\s*(.+)", re.IGNORECASE),
    ],
    "diagnosis": [
        re.compile(r"(?:التشخيص|Diagnosis)\s*[:：\-]?\s*(.+)", re.IGNORECASE),
    ],
    "medications": [
        re.compile(r"(?:الأدوية|العلاج|Rx|Medication[s]?)\s*[:：\-]?\s*(.+)", re.IGNORECASE),
    ],
}

MEDICATION_SPLIT_RE = re.compile(r"\s*[،,؛;\n]\s*")
NON_TEMPLATE_VALUE_RE = re.compile(r"\s*[:：\-]\s*.+$")
MULTISPACE_RE = re.compile(r"\s+")
DIGIT_RE = re.compile(r"[0-9٠-٩]+")


@dataclass(slots=True)
class ExtractedMedicalFields:
    patient_name: str = ""
    patient_id: str = ""
    date: str = ""
    doctor_name: str = ""
    diagnosis: str = ""
    medications: list[str] = field(default_factory=list)
    template_signature: str = ""
    raw_text: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "patient_name": self.patient_name,
            "patient_id": self.patient_id,
            "date": self.date,
            "doctor_name": self.doctor_name,
            "diagnosis": self.diagnosis,
            "medications": self.medications,
            "template_signature": self.template_signature,
            "raw_text": self.raw_text,
            "fingerprint": self.unique_patient_fingerprint(),
        }

    def unique_patient_fingerprint(self) -> str:
        base = "|".join([
            self.patient_name.strip(),
            self.patient_id.strip(),
            self.date.strip(),
            self.doctor_name.strip(),
        ])
        return hashlib.sha1(base.encode("utf-8")).hexdigest() if base.strip("|") else ""


class ArabicMedicalFieldExtractor:
    """Regex-first extractor for template-heavy Arabic medical documents."""

    def __init__(self) -> None:
        self.patterns = LABEL_PATTERNS

    @staticmethod
    def _clean_value(value: str) -> str:
        value = MULTISPACE_RE.sub(" ", value).strip(" -:\u200f\u200e")
        return value

    @staticmethod
    def _extract_medications(value: str) -> list[str]:
        parts = [part.strip() for part in MEDICATION_SPLIT_RE.split(value) if part.strip()]
        return parts

    def _first_match(self, field_name: str, text: str) -> str:
        for pattern in self.patterns[field_name]:
            match = pattern.search(text)
            if match:
                return self._clean_value(match.group(1))
        return ""

    def build_template_signature(self, text: str, fields: ExtractedMedicalFields) -> str:
        template_lines: list[str] = []
        values_to_remove = [
            fields.patient_name,
            fields.patient_id,
            fields.date,
            fields.doctor_name,
            fields.diagnosis,
            *fields.medications,
        ]
        redacted = text
        for value in values_to_remove:
            if value:
                redacted = redacted.replace(value, " ")
        for raw_line in redacted.splitlines():
            line = NON_TEMPLATE_VALUE_RE.sub("", raw_line).strip()
            line = DIGIT_RE.sub("#", line)
            line = arabic_strong_normalize(line)
            if line:
                template_lines.append(line)
        return "\n".join(template_lines)

    def extract_fields(self, text: str) -> ExtractedMedicalFields:
        raw_text = text or ""
        normalized = arabic_strong_normalize(raw_text)
        fields = ExtractedMedicalFields(raw_text=raw_text)
        fields.patient_name = self._first_match("patient_name", raw_text) or self._first_match("patient_name", normalized)
        fields.patient_id = self._first_match("patient_id", raw_text) or self._first_match("patient_id", normalized)
        fields.date = self._first_match("date", raw_text) or self._first_match("date", normalized)
        fields.doctor_name = self._first_match("doctor_name", raw_text) or self._first_match("doctor_name", normalized)
        fields.diagnosis = self._first_match("diagnosis", raw_text) or self._first_match("diagnosis", normalized)
        meds = self._first_match("medications", raw_text) or self._first_match("medications", normalized)
        fields.medications = self._extract_medications(meds) if meds else []
        fields.template_signature = self.build_template_signature(raw_text or normalized, fields)
        return fields
