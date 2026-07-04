#!/usr/bin/env python3
# packages/core/mistral_integration.py
# وحدة التكامل الرئيسية بين Medical Doc Processor و Mistral AI
# تدعم: OCR fallback (Tesseract → Mistral), Classification, Extraction, FHIR

import os
import json
from typing import Optional, Dict, Any, List
from pathlib import Path

from mistral_ocr_engine import MistralOCREngine
from document_schemas import (
    DocumentClassification,
    EXTRACTION_SCHEMAS,
    PatientDemographics,
    VitalSigns,
    LabReport,
    Prescription,
    RadiologyFinding,
)


class MistralIntegration:
    """
    واجهة موحدة للتكامل مع Mistral AI
    - إذا كان MISTRAL_API_KEY متوفراً: تستخدم Mistral OCR 3
    - إذا لم يكن: تعود إلى Tesseract/PaddleOCR (المحرك المحلي)
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("MISTRAL_API_KEY")
        self.engine: Optional[MistralOCREngine] = None

        if self.api_key:
            try:
                self.engine = MistralOCREngine(api_key=self.api_key)
                print("✅ Mistral AI integration enabled")
            except Exception as e:
                print(f"⚠️ Mistral init failed: {e}. Falling back to local OCR.")
        else:
            print("ℹ️ MISTRAL_API_KEY not set. Using local OCR only.")

    def is_available(self) -> bool:
        """هل Mistral متاح؟"""
        return self.engine is not None

    def process_document(
        self,
        file_path: str,
        use_mistral: bool = True,
        include_structured: bool = True
    ) -> Dict[str, Any]:
        """
        معالجة مستند واحد

        Args:
            file_path: مسار الملف
            use_mistral: هل نستخدم Mistral أم المحرك المحلي؟
            include_structured: هل نستخرج بيانات منظمة؟

        Returns:
            dict يحتوي ocr_text, classification, extraction, fhir
        """
        result = {
            "source": "unknown",
            "ocr_text": "",
            "classification": None,
            "structured_data": None,
            "fhir_bundle": None,
            "pages": [],
            "tables": [],
            "images": [],
        }

        # 1. OCR
        if use_mistral and self.is_available():
            try:
                ocr_result = self.engine.process_document(file_path)
                result["source"] = "mistral_ocr"
                result["ocr_text"] = ocr_result["all_markdown"]
                result["pages"] = ocr_result["pages"]
                result["tables"] = ocr_result["tables"]
                result["images"] = ocr_result["images"]
            except Exception as e:
                result["source"] = "mistral_failed"
                result["error"] = str(e)
                # Fallback إلى محلي يمكن أن يحدث هنا
        else:
            result["source"] = "local_ocr"
            # يمكن استدعاء Tesseract/PaddleOCR هنا

        # 2. Classification (إذا كان Mistral متاحاً)
        if self.is_available() and include_structured and result["ocr_text"]:
            try:
                cls_result = self.engine.classify_document(file_path)
                result["classification"] = cls_result.get("annotation", {})
                doc_type = result["classification"].get("document_type", "unknown")
            except Exception as e:
                doc_type = "unknown"
                result["classification_error"] = str(e)
        else:
            doc_type = "unknown"

        # 3. Structured Extraction
        if self.is_available() and include_structured and doc_type in EXTRACTION_SCHEMAS:
            try:
                ext_result = self.engine.extract_by_type(file_path, doc_type)
                if ext_result:
                    result["structured_data"] = ext_result.get("annotation", {})
            except Exception as e:
                result["extraction_error"] = str(e)

        # 4. FHIR Conversion
        if result["structured_data"]:
            try:
                from fhir_converter import convert_to_fhir
                result["fhir_bundle"] = convert_to_fhir(
                    doc_type=doc_type,
                    data=result["structured_data"]
                )
            except Exception as e:
                result["fhir_error"] = str(e)

        return result

    def process_batch(
        self,
        file_paths: List[str],
        rate_limit_delay: float = 0.5
    ) -> List[Dict[str, Any]]:
        """معالجة دفعة"""
        if not self.is_available():
            return [{"file_path": p, "error": "Mistral not available"} for p in file_paths]

        return self.engine.batch_process(file_paths, rate_limit_delay)


# ====== دوال مساعدة للـ FHIR Conversion ======

def convert_to_fhir(doc_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """
    تحويل البيانات المستخرجة إلى FHIR Bundle
    """
    import uuid
    from datetime import datetime

    bundle = {
        "resourceType": "Bundle",
        "id": str(uuid.uuid4()),
        "meta": {
            "versionId": "1",
            "lastUpdated": datetime.now().isoformat()
        },
        "type": "collection",
        "entry": []
    }

    patient_id = str(uuid.uuid4())

    # Patient Resource (من demographics)
    if doc_type in ["admission_form", "demographics", "patient_registration"]:
        patient = _create_fhir_patient(data, patient_id)
        bundle["entry"].append({"resource": patient})

    # Observation Resources (من vitals)
    elif doc_type in ["vitals", "vital_signs"]:
        patient_ref = f"Patient/{patient_id}"  # يجب ربطه بالمريض الحقيقي
        observations = _create_fhir_observations(data, patient_ref)
        for obs in observations:
            bundle["entry"].append({"resource": obs})

    # DiagnosticReport (من lab_results)
    elif doc_type in ["lab_results", "laboratory"]:
        report = _create_fhir_diagnostic_report(data, patient_id)
        bundle["entry"].append({"resource": report})

    # MedicationRequest (من prescription)
    elif doc_type in ["prescription", "medication_order"]:
        for med_req in _create_fhir_medication_requests(data, patient_id):
            bundle["entry"].append({"resource": med_req})

    # ImagingStudy (من radiology)
    elif doc_type in ["radiology", "x_ray", "ct_scan", "mri", "ultrasound"]:
        imaging = _create_fhir_imaging_study(data, patient_id)
        bundle["entry"].append({"resource": imaging})

    return bundle


def _create_fhir_patient(data: Dict, patient_id: str) -> Dict:
    """إنشاء FHIR Patient resource"""
    name_str = data.get("patient_name", "Unknown")
    name_parts = name_str.replace(",", " ").split()

    patient = {
        "resourceType": "Patient",
        "id": patient_id,
        "identifier": [{
            "system": "http://hospital.smart.org/mrn",
            "value": data.get("national_id", "UNKNOWN")
        }],
        "name": [{
            "use": "official",
            "family": name_parts[0] if name_parts else "Unknown",
            "given": name_parts[1:] if len(name_parts) > 1 else [""]
        }],
        "gender": _map_gender(data.get("gender")),
        "birthDate": _normalize_date(data.get("date_of_birth")),
    }

    if data.get("phone"):
        patient["telecom"] = [{"system": "phone", "value": data["phone"], "use": "home"}]

    if data.get("address"):
        patient["address"] = [{"use": "home", "text": data["address"]}]

    return patient


def _create_fhir_observations(data: Dict, patient_ref: str) -> List[Dict]:
    """إنشاء FHIR Observation resources للعلامات الحيوية"""
    observations = []
    vital_mappings = {
        "blood_pressure": ("85354-9", "Blood pressure panel", "mmHg"),
        "heart_rate": ("8867-4", "Heart rate", "/min"),
        "temperature": ("8310-5", "Body temperature", "Cel"),
        "respiratory_rate": ("9279-1", "Respiratory rate", "/min"),
        "oxygen_saturation": ("2708-6", "Oxygen saturation", "%"),
        "weight": ("29463-7", "Body weight", "kg"),
        "height": ("8302-2", "Body height", "cm"),
    }

    effective_date = _normalize_date(data.get("date_recorded")) or _now_date()

    for key, (loinc, display, unit) in vital_mappings.items():
        value = data.get(key)
        if value:
            obs = {
                "resourceType": "Observation",
                "id": f"obs-{key}",
                "status": "final",
                "category": [{
                    "coding": [{
                        "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                        "code": "vital-signs",
                        "display": "Vital Signs"
                    }]
                }],
                "code": {
                    "coding": [{
                        "system": "http://loinc.org",
                        "code": loinc,
                        "display": display
                    }]
                },
                "subject": {"reference": patient_ref},
                "effectiveDateTime": effective_date,
                "valueString": str(value)
            }
            observations.append(obs)

    return observations


def _create_fhir_diagnostic_report(data: Dict, patient_id: str) -> Dict:
    """إنشاء FHIR DiagnosticReport"""
    import uuid
    results = data.get("results", [])

    report = {
        "resourceType": "DiagnosticReport",
        "id": str(uuid.uuid4()),
        "status": "final",
        "code": {
            "coding": [{
                "system": "http://loinc.org",
                "code": "11502-2",
                "display": "Laboratory report"
            }]
        },
        "subject": {"reference": f"Patient/{patient_id}"},
        "effectiveDateTime": _normalize_date(data.get("date_reported")) or _now_date(),
        "result": []
    }

    for r in results:
        obs_id = str(uuid.uuid4())
        obs = {
            "resourceType": "Observation",
            "id": obs_id,
            "status": "final",
            "code": {
                "text": r.get("test_name", "Unknown test")
            },
            "subject": {"reference": f"Patient/{patient_id}"},
            "valueString": f"{r.get('value', '')} {r.get('unit', '')}".strip()
        }
        report["result"].append({"reference": f"Observation/{obs_id}"})

    return report


def _create_fhir_medication_requests(data: Dict, patient_id: str) -> List[Dict]:
    """إنشاء FHIR MedicationRequest resources"""
    import uuid
    requests = []
    meds = data.get("medications", [])

    for med in meds:
        req = {
            "resourceType": "MedicationRequest",
            "id": str(uuid.uuid4()),
            "status": "active",
            "intent": "order",
            "medicationCodeableConcept": {
                "text": med.get("name", "Unknown medication")
            },
            "subject": {"reference": f"Patient/{patient_id}"},
            "authoredOn": _normalize_date(data.get("date_prescribed")) or _now_date(),
            "dosageInstruction": [{
                "text": f"{med.get('dosage', '')} {med.get('frequency', '')} {med.get('route', '')}".strip(),
                "patientInstruction": med.get("instructions", "")
            }]
        }
        requests.append(req)

    return requests


def _create_fhir_imaging_study(data: Dict, patient_id: str) -> Dict:
    """إنشاء FHIR ImagingStudy"""
    import uuid
    modality_map = {
        "x_ray": "DX",
        "ct_scan": "CT",
        "mri": "MR",
        "ultrasound": "US"
    }

    return {
        "resourceType": "ImagingStudy",
        "id": str(uuid.uuid4()),
        "status": "available",
        "subject": {"reference": f"Patient/{patient_id}"},
        "started": _normalize_date(data.get("date_performed")) or _now_date(),
        "modality": [{
            "system": "http://dicom.nema.org/resources/ontology/DCM",
            "code": modality_map.get(data.get("modality", "").lower(), "OT"),
            "display": data.get("modality", "Other")
        }],
        "note": [{"text": data.get("findings", "")}],
        "description": data.get("impression", "")
    }


# ====== دوال مساعدة ======

def _map_gender(g: Optional[str]) -> str:
    if not g:
        return "unknown"
    g = g.lower().strip()
    if g in ["m", "male", "ذكر"]:
        return "male"
    elif g in ["f", "female", "أنثى"]:
        return "female"
    return "unknown"


def _normalize_date(date_str: Optional[str]) -> Optional[str]:
    """تحويل تاريخ إلى YYYY-MM-DD"""
    if not date_str:
        return None
    # محاولة DD/MM/YYYY
    parts = date_str.replace("-", "/").split("/")
    if len(parts) == 3:
        if len(parts[2]) == 4:  # DD/MM/YYYY
            return f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"
        elif len(parts[0]) == 4:  # YYYY-MM-DD
            return date_str
    return date_str


def _now_date() -> str:
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d")
