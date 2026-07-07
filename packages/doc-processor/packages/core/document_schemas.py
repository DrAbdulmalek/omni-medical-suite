"""
Pydantic schemas for structured medical document extraction.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum


class DocumentType(str, Enum):
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


class UrgencyLevel(str, Enum):
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
    date_recorded: Optional[str] = None
    blood_pressure: Optional[str] = None
    heart_rate: Optional[str] = None
    temperature: Optional[str] = None
    weight: Optional[float] = None
    height: Optional[float] = None
    oxygen_saturation: Optional[str] = None
    respiratory_rate: Optional[str] = None


class LabResultsData(BaseModel):
    patient_name: Optional[str] = None
    mrn: Optional[str] = None
    test_date: Optional[str] = None
    tests: List[LabTest] = Field(default_factory=list)


class PrescriptionData(BaseModel):
    patient_name: Optional[str] = None
    mrn: Optional[str] = None
    prescription_date: Optional[str] = None
    diagnosis: Optional[str] = None
    medications: List[Medication] = Field(default_factory=list)


class AdmissionFormData(BaseModel):
    patient_name: Optional[str] = None
    date_of_birth: Optional[str] = None
    mrn: Optional[str] = None
    admission_date: Optional[str] = None
    department: Optional[str] = None
    attending_physician: Optional[str] = None
    reason_for_admission: Optional[str] = None
    insurance_info: Optional[str] = None
    emergency_contact: Optional[str] = None


class ClassificationResult(BaseModel):
    document_type: DocumentType = DocumentType.UNKNOWN
    confidence: float = 0.0
    routing_department: Optional[str] = None
    urgency: UrgencyLevel = UrgencyLevel.ROUTINE
    key_identifiers_found: List[str] = Field(default_factory=list)
    requires_signature: bool = False
    summary: Optional[str] = None


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
    encryption_password: Optional[str] = None
    patient_id: Optional[str] = None
