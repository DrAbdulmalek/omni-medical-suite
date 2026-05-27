"""
FHIR R4 / HL7 v2 Exporter
Exports processed medical documents to standard healthcare formats.
Supports: FHIR R4 Bundle, HL7 v2.5 messages, and custom JSON.
"""

import json
import hashlib
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

# Maximum text length for hex encoding in DocumentReference attachments.
# Text exceeding this limit will be truncated with a warning log.
MAX_TEXT_LENGTH = 10000


class ExportFormat(Enum):
    FHIR_R4 = "fhir_r4"
    HL7_V2 = "hl7_v2"
    JSON = "json"


@dataclass
class MedicalEntity:
    """Extracted medical entity."""
    type: str
    text: str
    code: Optional[str] = None
    system: Optional[str] = None
    confidence: float = 1.0


@dataclass
class PatientInfo:
    """Patient demographic information."""
    id: Optional[str] = None
    name: Optional[str] = None
    birth_date: Optional[str] = None
    gender: Optional[str] = None
    mrn: Optional[str] = None  # Medical Record Number


@dataclass
class DocumentMetadata:
    """Document processing metadata."""
    document_id: str
    source_type: str  # "prescription", "report", "lab", "discharge"
    created_at: str
    processed_at: str
    ocr_confidence: float
    validator_confidence: float
    language: str


class FHIRExporter:
    """
    FHIR R4 / HL7 v2 exporter for medical documents.

    Features:
    - FHIR R4 Bundle with DocumentReference, Patient, Observation, MedicationRequest
    - HL7 v2.5 ORU^R01 and MDM^T02 messages
    - LOINC/SNOMED coding where applicable
    - Arabic text support in FHIR extensions
    - SHA-256 integrity hashing

    Usage:
        exporter = FHIRExporter()
        bundle = exporter.to_fhir_r4(
            text="...",
            entities=[...],
            patient=PatientInfo(...),
            metadata=DocumentMetadata(...)
        )
    """

    # LOINC codes for common document types
    LOINC_CODES = {
        "prescription": {"code": "57833-6", "display": "Prescription for medication"},
        "discharge": {"code": "18842-5", "display": "Discharge summary"},
        "lab": {"code": "11502-2", "display": "Laboratory report"},
        "radiology": {"code": "18748-4", "display": "Diagnostic imaging study"},
        "progress_note": {"code": "11506-3", "display": "Progress note"},
    }

    # SNOMED CT for common findings (simplified)
    SNOMED_CODES = {
        "hypertension": "38341003",
        "diabetes": "73211009",
        "fever": "386661006",
        "fracture": "125605004",
        "infection": "40733004",
    }

    def __init__(self):
        self.fhir_version = "4.0.1"

    def to_fhir_r4(
        self,
        text: str,
        entities: List[MedicalEntity],
        patient: Optional[PatientInfo] = None,
        metadata: Optional[DocumentMetadata] = None
    ) -> Dict[str, Any]:
        """
        Export to FHIR R4 Bundle.

        Args:
            text: Extracted document text
            entities: List of extracted medical entities
            patient: Patient demographic info
            metadata: Document processing metadata

        Returns:
            FHIR R4 Bundle as dict
        """
        bundle_id = self._generate_id("bundle")
        now = datetime.now(timezone.utc).isoformat()

        bundle = {
            "resourceType": "Bundle",
            "id": bundle_id,
            "meta": {
                "versionId": "1",
                "lastUpdated": now,
                "profile": ["http://hl7.org/fhir/StructureDefinition/Bundle"]
            },
            "identifier": {
                "system": "https://omnimedical.local/bundle-id",
                "value": bundle_id
            },
            "type": "document",
            "timestamp": now,
            "entry": []
        }

        # 1. Composition (document structure)
        composition = self._create_composition(text, metadata, now)
        bundle["entry"].append({"resource": composition})

        # 2. Patient
        if patient:
            patient_resource = self._create_patient(patient)
            bundle["entry"].append({"resource": patient_resource})
            patient_ref = f"Patient/{patient.id or 'unknown'}"
        else:
            patient_ref = "Patient/unknown"

        # 3. DocumentReference
        doc_ref = self._create_document_reference(text, metadata, patient_ref, now)
        bundle["entry"].append({"resource": doc_ref})

        # 4. Observations from entities
        for entity in entities:
            if entity.type in ["symptom", "finding", "diagnosis"]:
                obs = self._create_observation(entity, patient_ref, now)
                bundle["entry"].append({"resource": obs})

        # 5. MedicationRequest from medication entities
        for entity in entities:
            if entity.type == "medication":
                med_req = self._create_medication_request(entity, patient_ref, now)
                bundle["entry"].append({"resource": med_req})

        # 6. Provenance (processing audit)
        provenance = self._create_provenance(metadata, now)
        bundle["entry"].append({"resource": provenance})

        return bundle

    def to_hl7_v2(
        self,
        text: str,
        entities: List[MedicalEntity],
        patient: Optional[PatientInfo] = None,
        metadata: Optional[DocumentMetadata] = None,
        message_type: str = "ORU^R01"
    ) -> str:
        """
        Export to HL7 v2.5 message.

        Args:
            text: Extracted document text
            entities: Medical entities
            patient: Patient info
            metadata: Document metadata
            message_type: HL7 message type (ORU^R01, MDM^T02)

        Returns:
            HL7 v2.5 message string
        """
        now = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        msg_id = self._generate_id("hl7")

        # MSH segment
        msh = (
            f"MSH|^~\\&|OmniMedical|OmniMedicalSuite|"
            f"RECEIVING_APP|RECEIVING_FACILITY|{now}||{message_type}|{msg_id}|P|2.5"
        )

        # PID segment
        pid = "PID|1"
        if patient:
            pid += f"||{patient.mrn or ''}^^^MRN||{patient.name or ''}||"
            pid += f"{patient.birth_date or ''}|{patient.gender or ''}||||||||||||||||||||||"

        # OBR segment (observation request)
        loinc = self.LOINC_CODES.get(metadata.source_type if metadata else "discharge", 
                                     self.LOINC_CODES["discharge"])
        obr = (
            f"OBR|1||{metadata.document_id if metadata else ''}|"
            f"{loinc['code']}^{loinc['display']}^LOINC|||{now}||||||||||||||"
        )

        # OBX segments (observations)
        obx_segments = []
        for i, entity in enumerate(entities, 1):
            obx = (
                f"OBX|{i}|ST|{entity.code or 'unknown'}^{entity.text}^SNOMED||"
                f"{entity.text}|{entity.confidence}|N|||F|||{now}"
            )
            obx_segments.append(obx)

        # NTE segment (notes)
        nte = f"NTE|1||{text[:500]}"  # Truncated for HL7 compatibility

        segments = [msh, pid, obr] + obx_segments + [nte]
        return "\r".join(segments)

    def to_json(
        self,
        text: str,
        entities: List[MedicalEntity],
        patient: Optional[PatientInfo] = None,
        metadata: Optional[DocumentMetadata] = None
    ) -> Dict[str, Any]:
        """Export to custom JSON format (simplified)."""
        return {
            "format": "omnimedical_custom_v1",
            "document": {
                "text": text,
                "entities": [self._entity_to_dict(e) for e in entities],
                "patient": self._patient_to_dict(patient) if patient else None,
                "metadata": self._metadata_to_dict(metadata) if metadata else None,
                "integrity_hash": hashlib.sha256(text.encode()).hexdigest()[:16]
            },
            "export_info": {
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "exporter_version": "2.1.0"
            }
        }

    def _create_composition(self, text: str, metadata: Optional[DocumentMetadata], now: str) -> Dict[str, Any]:
        """Create FHIR Composition resource."""
        source_type = metadata.source_type if metadata else "discharge"
        loinc = self.LOINC_CODES.get(source_type, self.LOINC_CODES["discharge"])

        return {
            "resourceType": "Composition",
            "id": self._generate_id("composition"),
            "status": "final",
            "type": {
                "coding": [{
                    "system": "http://loinc.org",
                    "code": loinc["code"],
                    "display": loinc["display"]
                }],
                "text": loinc["display"]
            },
            "subject": {"reference": "Patient/unknown"},
            "date": now,
            "author": [{"reference": "Device/omnimedical-processor"}],
            "title": f"OmniMedical Processed {source_type.title()}",
            "section": [{
                "title": "Extracted Text",
                "text": {
                    "status": "generated",
                    "div": f"<div xmlns=\"http://www.w3.org/1999/xhtml\"><p>{text[:1000]}</p></div>"
                }
            }]
        }

    def _create_patient(self, patient: PatientInfo) -> Dict[str, Any]:
        """Create FHIR Patient resource."""
        resource = {
            "resourceType": "Patient",
            "id": patient.id or self._generate_id("patient"),
            "meta": {
                "security": [{
                    "system": "http://terminology.hl7.org/CodeSystem/v3-Confidentiality",
                    "code": "R",
                    "display": "Restricted"
                }]
            }
        }

        if patient.name:
            resource["name"] = [{"text": patient.name}]
        if patient.birth_date:
            resource["birthDate"] = patient.birth_date
        if patient.gender:
            resource["gender"] = patient.gender.lower()
        if patient.mrn:
            resource["identifier"] = [{
                "system": "http://omnimedical.local/mrn",
                "value": patient.mrn,
                "type": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/v2-0203", "code": "MR"}]}
            }]

        return resource

    def _create_document_reference(
        self, 
        text: str, 
        metadata: Optional[DocumentMetadata],
        patient_ref: str,
        now: str
    ) -> Dict[str, Any]:
        """Create FHIR DocumentReference resource."""
        source_type = metadata.source_type if metadata else "discharge"
        loinc = self.LOINC_CODES.get(source_type, self.LOINC_CODES["discharge"])

        # Truncate text for hex encoding if it exceeds MAX_TEXT_LENGTH
        encoded_text = text
        if len(text) > MAX_TEXT_LENGTH:
            logger.warning(
                "Document text exceeds MAX_TEXT_LENGTH (%d > %d). Truncating for hex encoding.",
                len(text), MAX_TEXT_LENGTH
            )
            encoded_text = text[:MAX_TEXT_LENGTH]

        return {
            "resourceType": "DocumentReference",
            "id": self._generate_id("docref"),
            "status": "current",
            "docStatus": "final",
            "type": {
                "coding": [{
                    "system": "http://loinc.org",
                    "code": loinc["code"],
                    "display": loinc["display"]
                }]
            },
            "subject": {"reference": patient_ref},
            "date": now,
            "content": [{
                "attachment": {
                    "contentType": "text/plain",
                    "data": encoded_text.encode("utf-8").hex(),
                    "hash": hashlib.sha256(text.encode()).hexdigest(),
                    "size": len(text)
                },
                "format": {
                    "system": "urn:ietf:bcp:13",
                    "code": "text/plain",
                    "display": "Plain Text"
                }
            }],
            "context": {
                "event": [{
                    "coding": [{
                        "system": "http://snomed.info/sct",
                        "code": "308335008",
                        "display": "Patient encounter procedure"
                    }]
                }]
            }
        }

    def _create_observation(self, entity: MedicalEntity, patient_ref: str, now: str) -> Dict[str, Any]:
        """Create FHIR Observation resource."""
        code = entity.code or self.SNOMED_CODES.get(entity.text.lower(), "unknown")

        return {
            "resourceType": "Observation",
            "id": self._generate_id("obs"),
            "status": "final",
            "category": [{
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                    "code": "exam",
                    "display": "Examination"
                }]
            }],
            "code": {
                "coding": [{
                    "system": "http://snomed.info/sct",
                    "code": code,
                    "display": entity.text
                }],
                "text": entity.text
            },
            "subject": {"reference": patient_ref},
            "effectiveDateTime": now,
            "valueString": entity.text,
            "note": [{"text": f"Extracted with confidence {entity.confidence}"}]
        }

    def _create_medication_request(self, entity: MedicalEntity, patient_ref: str, now: str) -> Dict[str, Any]:
        """Create FHIR MedicationRequest resource."""
        return {
            "resourceType": "MedicationRequest",
            "id": self._generate_id("medreq"),
            "status": "active",
            "intent": "order",
            "medicationCodeableConcept": {
                "text": entity.text,
                "coding": [{
                    "system": "http://www.nlm.nih.gov/research/umls/rxnorm",
                    "code": entity.code or "unknown",
                    "display": entity.text
                }]
            },
            "subject": {"reference": patient_ref},
            "authoredOn": now,
            "dosageInstruction": [{
                "text": entity.text,
                "patientInstruction": "Follow physician instructions"
            }]
        }

    def _create_provenance(self, metadata: Optional[DocumentMetadata], now: str) -> Dict[str, Any]:
        """Create FHIR Provenance resource for audit trail."""
        return {
            "resourceType": "Provenance",
            "id": self._generate_id("prov"),
            "target": [{"reference": "DocumentReference/unknown"}],
            "recorded": now,
            "activity": {
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/v3-DataOperation",
                    "code": "CREATE",
                    "display": "create"
                }]
            },
            "agent": [{
                "type": {
                    "coding": [{
                        "system": "http://terminology.hl7.org/CodeSystem/provenance-participant-type",
                        "code": "assembler",
                        "display": "Assembler"
                    }]
                },
                "who": {"reference": "Device/omnimedical-processor"},
                "onBehalfOf": {"display": "OmniMedical Suite v2.1.0"}
            }],
            "entity": [{
                "role": "source",
                "what": {"display": metadata.document_id if metadata else "unknown"}
            }] if metadata else []
        }

    def _generate_id(self, prefix: str) -> str:
        """Generate unique FHIR resource ID."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        hash_suffix = hashlib.sha256(f"{prefix}{timestamp}".encode()).hexdigest()[:8]
        return f"{prefix}-{timestamp}-{hash_suffix}"

    def _entity_to_dict(self, entity: MedicalEntity) -> Dict[str, Any]:
        return {
            "type": entity.type,
            "text": entity.text,
            "code": entity.code,
            "system": entity.system,
            "confidence": entity.confidence
        }

    def _patient_to_dict(self, patient: PatientInfo) -> Dict[str, Any]:
        return {
            "id": patient.id,
            "name": patient.name,
            "birth_date": patient.birth_date,
            "gender": patient.gender,
            "mrn": patient.mrn
        }

    def _metadata_to_dict(self, metadata: DocumentMetadata) -> Dict[str, Any]:
        return {
            "document_id": metadata.document_id,
            "source_type": metadata.source_type,
            "created_at": metadata.created_at,
            "processed_at": metadata.processed_at,
            "ocr_confidence": metadata.ocr_confidence,
            "validator_confidence": metadata.validator_confidence,
            "language": metadata.language
        }
