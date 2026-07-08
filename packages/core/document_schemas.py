"""
Pydantic schemas for structured medical document extraction.
"""

from enum import StrEnum

from pydantic import BaseModel, Field


class DocumentType(StrEnum):
    ADMISSION_FORM = "admission_form"
    VITALS = "vitals"
    LAB_RESULTS = "lab_results"
    PRESCRIPTION = "prescription"
    RADIOLOGY_REPORT = "radiology_report"
    DISCHARGE_SUMMARY = "discharge_summary"
    REFERRAL = "referral"
    CONSENT_FORM = "consent_form"
    INSURANCE_CLAIM = "insurance_claim"
    PATHOLOGY_REPORT = "pathology_report"
    UNKNOWN = "unknown"


class UrgencyLevel(StrEnum):
    ROUTINE = "routine"
    URGENT = "urgent"
    CRITICAL = "critical"


class LabTest(BaseModel):
    name: str = ""
    value: str = ""
    unit: str = ""
    reference_range: str = ""
    flag: str = ""  # H, L, N


class Medication(BaseModel):
    name: str = ""
    dose: str = ""
    frequency: str = ""
    duration: str = ""
    route: str = ""


class VitalsData(BaseModel):
    date_recorded: str | None = None
    blood_pressure: str | None = None
    heart_rate: str | None = None
    temperature: str | None = None
    weight: float | None = None
    height: float | None = None
    oxygen_saturation: str | None = None
    respiratory_rate: str | None = None


class LabResultsData(BaseModel):
    patient_name: str | None = None
    mrn: str | None = None
    test_date: str | None = None
    tests: list[LabTest] = Field(default_factory=list)


class PrescriptionData(BaseModel):
    patient_name: str | None = None
    mrn: str | None = None
    prescription_date: str | None = None
    diagnosis: str | None = None
    medications: list[Medication] = Field(default_factory=list)


class AdmissionFormData(BaseModel):
    patient_name: str | None = None
    date_of_birth: str | None = None
    mrn: str | None = None
    admission_date: str | None = None
    department: str | None = None
    attending_physician: str | None = None
    reason_for_admission: str | None = None
    insurance_info: str | None = None
    emergency_contact: str | None = None


class ClassificationResult(BaseModel):
    document_type: DocumentType = DocumentType.UNKNOWN
    confidence: float = 0.0
    routing_department: str | None = None
    urgency: UrgencyLevel = UrgencyLevel.ROUTINE
    key_identifiers_found: list[str] = Field(default_factory=list)
    requires_signature: bool = False
    summary: str | None = None


class QualityMetrics(BaseModel):
    blur_score: float = 0.0
    brightness: float = 0.0
    contrast: float = 0.0
    is_sharp: bool = False
    label: str = "unknown"
    color: str = "#666666"
    resolution: str = ""


class ProcessingOptions(BaseModel):
    deskew: bool = True
    auto_crop: bool = True
    remove_borders: bool = True
    remove_shadow: bool = False
    sharpen: bool = False
    rotation: float = 0.0
    flip_h: bool = False
    gray_threshold: int = 230
    extract_page_number: bool = False
    use_mistral: bool = False
    mistral_structured: bool = False
    encrypt: bool = False
    encryption_password: str | None = None
    patient_id: str | None = None
