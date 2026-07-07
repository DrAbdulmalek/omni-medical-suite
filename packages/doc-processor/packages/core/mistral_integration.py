"""
Mistral AI Integration for Medical Document Processing.
Features: OCR 3, Document Classification, Structured Extraction, FHIR Generation.
"""

import os
import json
import base64
import logging
import tempfile
import shutil
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

# Try to import mistral client
try:
    from mistralai import Mistral
    HAS_MISTRAL = True
except ImportError:
    HAS_MISTRAL = False
    logger.warning("mistralai package not installed. Mistral features disabled.")


class MistralOCR:
    """Mistral OCR 3 engine for document OCR."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("MISTRAL_API_KEY")
        self.client = None
        if self.api_key and HAS_MISTRAL:
            self.client = Mistral(api_key=self.api_key)

    def is_available(self) -> bool:
        return self.client is not None

    def ocr_document(self, file_path: str) -> Dict[str, Any]:
        """
        Run OCR on a document using Mistral OCR 3.

        Returns:
            Dict with pages, each containing markdown text, tables, and images.
        """
        if not self.is_available():
            return {"error": "Mistral API not available", "available": False}

        try:
            # Upload file
            with open(file_path, "rb") as f:
                uploaded = self.client.files.upload(
                    file={"file_name": os.path.basename(file_path), "content": f.read()},
                    purpose="ocr"
                )

            # Get signed URL
            signed_url = self.client.files.get_signed_url(file_id=uploaded.id)

            # Run OCR
            ocr_response = self.client.ocr.process(
                model="mistral-ocr-latest",
                document={
                    "type": "document_url",
                    "document_url": signed_url.url
                }
            )

            # Parse results
            pages = []
            for page in ocr_response.pages:
                page_data = {
                    "index": page.index,
                    "markdown": page.markdown,
                    "images": [],
                }
                # Extract images if present
                for img in getattr(page, 'images', []):
                    page_data["images"].append({
                        "id": img.id,
                        "top_left_x": img.top_left_x,
                        "top_left_y": img.top_left_y,
                        "bottom_right_x": img.bottom_right_x,
                        "bottom_right_y": img.bottom_right_y,
                    })

                pages.append(page_data)

            return {
                "available": True,
                "pages": pages,
                "total_pages": len(pages),
                "model": "mistral-ocr-latest",
            }

        except Exception as e:
            logger.error(f"Mistral OCR failed: {e}")
            return {"error": str(e), "available": False}


class DocumentClassifier:
    """Classify medical documents using Mistral AI."""

    DOCUMENT_TYPES = [
        "admission_form", "vitals", "lab_results", "prescription",
        "radiology_report", "discharge_summary", "referral",
        "consent_form", "insurance_claim", "pathology_report",
        "unknown"
    ]

    URGENCY_LEVELS = ["routine", "urgent", "critical"]

    CLASSIFICATION_PROMPT = """أنت مساعد طبي متخصص. صنّف المستند الطبي التالي.

أجب بصيغة JSON فقط بدون أي نص إضافي:
{
  "document_type": "نوع_المستند",
  "confidence": 0.95,
  "routing_department": "القسم_المسؤول",
  "urgency": "routine|urgent|critical",
  "key_identifiers_found": ["MRN", "اسم المريض"],
  "requires_signature": false,
  "summary": "ملخص مختصر"
}

أنواع المستندات المتاحة: admission_form, vitals, lab_results, prescription,
radiology_report, discharge_summary, referral, consent_form, insurance_claim,
pathology_report, unknown

النص:
{text}
"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("MISTRAL_API_KEY")
        self.client = None
        if self.api_key and HAS_MISTRAL:
            self.client = Mistral(api_key=self.api_key)

    def is_available(self) -> bool:
        return self.client is not None

    def classify_text(self, text: str) -> Dict[str, Any]:
        """Classify document from OCR text."""
        if not self.is_available():
            return {"error": "Mistral API not available"}

        try:
            response = self.client.chat.complete(
                model="mistral-small-latest",
                messages=[
                    {"role": "user", "content": self.CLASSIFICATION_PROMPT.format(text=text[:3000])}
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
            )

            content = response.choices[0].message.content
            result = json.loads(content)

            # Validate fields
            if result.get("document_type") not in self.DOCUMENT_TYPES:
                result["document_type"] = "unknown"
            if result.get("urgency") not in self.URGENCY_LEVELS:
                result["urgency"] = "routine"

            result["available"] = True
            return result

        except Exception as e:
            logger.error(f"Classification failed: {e}")
            return {"error": str(e)}

    def classify_file(self, file_path: str, ocr_result: Optional[Dict] = None) -> Dict[str, Any]:
        """Classify document from file (with optional pre-computed OCR)."""
        text = ""
        if ocr_result and ocr_result.get("pages"):
            text = "\n".join(p.get("markdown", "") for p in ocr_result["pages"])

        if not text:
            return {"error": "No text available for classification", "available": False}

        return self.classify_text(text)


class StructuredExtractor:
    """Extract structured data from medical documents."""

    EXTRACTION_SCHEMAS = {
        "vitals": {
            "properties": ["date_recorded", "blood_pressure", "heart_rate", "temperature",
                          "weight", "height", "oxygen_saturation", "respiratory_rate"]
        },
        "lab_results": {
            "properties": ["patient_name", "mrn", "test_date", "tests": [
                {"name": "", "value": "", "unit": "", "reference_range": "", "flag": ""}
            ]]
        },
        "prescription": {
            "properties": ["patient_name", "mrn", "prescription_date", "diagnosis",
                          "medications": [
                              {"name": "", "dose": "", "frequency": "", "duration": "", "route": ""}
                          ]]
        },
        "admission_form": {
            "properties": ["patient_name", "date_of_birth", "mrn", "admission_date",
                          "department", "attending_physician", "reason_for_admission",
                          "insurance_info", "emergency_contact"]
        }
    }

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("MISTRAL_API_KEY")
        self.client = None
        if self.api_key and HAS_MISTRAL:
            self.client = Mistral(api_key=self.api_key)

    def is_available(self) -> bool:
        return self.client is not None

    def extract(self, text: str, doc_type: str) -> Dict[str, Any]:
        """Extract structured data from text based on document type."""
        if not self.is_available():
            return {"error": "Mistral API not available"}

        schema = self.EXTRACTION_SCHEMAS.get(doc_type, {})
        if not schema:
            return {"error": f"Unknown document type: {doc_type}"}

        prompt = f"""أنت مساعد طبي. استخرج البيانات المنظمة من المستند التالي.

نوع المستند: {doc_type}
البيانات المطلوبة: {json.dumps(schema['properties'], ensure_ascii=False)}

أجب بصيغة JSON فقط:
{text[:4000]}"""

        try:
            response = self.client.chat.complete(
                model="mistral-small-latest",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=0.1,
            )

            result = json.loads(response.choices[0].message.content)
            result["available"] = True
            result["document_type"] = doc_type
            return result

        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            return {"error": str(e)}


class FHIRConverter:
    """Convert extracted medical data to FHIR R4 format."""

    @staticmethod
    def vitals_to_fhir(data: Dict[str, Any], patient_id: str = "unknown") -> Dict[str, Any]:
        """Convert vitals data to FHIR Observation resources."""
        resources = []

        vital_mappings = {
            "blood_pressure": {"code": "85354-9", "display": "Blood pressure panel", "system": "http://loinc.org"},
            "heart_rate": {"code": "8867-4", "display": "Heart rate", "system": "http://loinc.org"},
            "temperature": {"code": "8310-5", "display": "Body temperature", "system": "http://loinc.org"},
            "weight": {"code": "29463-7", "display": "Body weight", "system": "http://loinc.org"},
            "height": {"code": "8302-2", "display": "Body height", "system": "http://loinc.org"},
            "oxygen_saturation": {"code": "2708-6", "display": "Oxygen saturation", "system": "http://loinc.org"},
            "respiratory_rate": {"code": "9279-1", "display": "Respiratory rate", "system": "http://loinc.org"},
        }

        for key, mapping in vital_mappings.items():
            value = data.get(key)
            if value is None:
                continue

            resource = {
                "resourceType": "Observation",
                "status": "final",
                "subject": {"reference": f"Patient/{patient_id}"},
                "effectiveDateTime": data.get("date_recorded", ""),
                "code": {
                    "coding": [{"system": mapping["system"], "code": mapping["code"], "display": mapping["display"]}]
                },
                "valueString": str(value),
            }
            resources.append(resource)

        return FHIRConverter._create_bundle(resources, f"Vitals for {patient_id}")

    @staticmethod
    def lab_to_fhir(data: Dict[str, Any], patient_id: str = "unknown") -> Dict[str, Any]:
        """Convert lab results to FHIR DiagnosticReport + Observations."""
        from datetime import datetime

        observations = []
        for test in data.get("tests", []):
            obs = {
                "resourceType": "Observation",
                "status": "final",
                "subject": {"reference": f"Patient/{patient_id}"},
                "effectiveDateTime": data.get("test_date", ""),
                "code": {
                    "coding": [{"display": test.get("name", "Unknown test")}]
                },
                "valueQuantity": {
                    "value": test.get("value"),
                    "unit": test.get("unit", ""),
                },
            }
            if test.get("reference_range"):
                obs["referenceRange"] = [{"text": test["reference_range"]}]
            if test.get("flag"):
                obs["interpretation"] = [{
                    "coding": [{"system": "http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation",
                                "code": test["flag"]}]
                }]
            observations.append(obs)

        report = {
            "resourceType": "DiagnosticReport",
            "status": "final",
            "subject": {"reference": f"Patient/{patient_id}"},
            "effectiveDateTime": data.get("test_date", ""),
            "code": {"text": "Laboratory Results"},
            "result": [{"reference": f"Observation/{i}"} for i in range(len(observations))]
        }

        return FHIRConverter._create_bundle([report] + observations, f"Lab results for {patient_id}")

    @staticmethod
    def prescription_to_fhir(data: Dict[str, Any], patient_id: str = "unknown") -> Dict[str, Any]:
        """Convert prescription to FHIR MedicationRequest resources."""
        resources = []

        for med in data.get("medications", []):
            req = {
                "resourceType": "MedicationRequest",
                "status": "active",
                "intent": "order",
                "subject": {"reference": f"Patient/{patient_id}"},
                "authoredOn": data.get("prescription_date", ""),
                "medicationCodeableConcept": {
                    "text": med.get("name", "Unknown medication")
                },
                "dosageInstruction": [{
                    "text": f"{med.get('dose', '')} {med.get('frequency', '')} {med.get('duration', '')} {med.get('route', '')}",
                }],
            }
            if data.get("diagnosis"):
                req["reasonCode"] = [{"text": data["diagnosis"]}]
            resources.append(req)

        return FHIRConverter._create_bundle(resources, f"Prescription for {patient_id}")

    @staticmethod
    def _create_bundle(entries: List[Dict], title: str = "") -> Dict[str, Any]:
        """Wrap resources in a FHIR Bundle."""
        return {
            "resourceType": "Bundle",
            "type": "collection",
            "title": title,
            "total": len(entries),
            "entry": [{"resource": r} for r in entries]
        }


class MistralIntegration:
    """Unified Mistral AI integration combining OCR, Classification, Extraction, and FHIR."""

    def __init__(self, api_key: Optional[str] = None):
        self.ocr = MistralOCR(api_key)
        self.classifier = DocumentClassifier(api_key)
        self.extractor = StructuredExtractor(api_key)
        self.fhir = FHIRConverter()

    def is_available(self) -> bool:
        return self.ocr.is_available()

    def process_document(self, file_path: str, patient_id: str = "unknown",
                          generate_fhir: bool = True) -> Dict[str, Any]:
        """
        Full document processing pipeline:
        1. OCR
        2. Classification
        3. Structured Extraction
        4. FHIR Generation
        """
        result = {"patient_id": patient_id, "file": os.path.basename(file_path)}

        # Step 1: OCR
        ocr_result = self.ocr.ocr_document(file_path)
        if ocr_result.get("error"):
            return {"error": ocr_result["error"], "available": False}

        result["ocr"] = ocr_result

        # Extract text
        full_text = "\n".join(p.get("markdown", "") for p in ocr_result.get("pages", []))

        # Step 2: Classification
        classification = self.classifier.classify_text(full_text)
        result["classification"] = classification

        # Step 3: Structured Extraction
        doc_type = classification.get("document_type", "unknown")
        if doc_type != "unknown":
            extraction = self.extractor.extract(full_text, doc_type)
            result["extraction"] = extraction

            # Step 4: FHIR Generation
            if generate_fhir and not extraction.get("error"):
                if doc_type == "vitals":
                    result["fhir"] = self.fhir.vitals_to_fhir(extraction, patient_id)
                elif doc_type == "lab_results":
                    result["fhir"] = self.fhir.lab_to_fhir(extraction, patient_id)
                elif doc_type == "prescription":
                    result["fhir"] = self.fhir.prescription_to_fhir(extraction, patient_id)

        result["available"] = True
        return result
