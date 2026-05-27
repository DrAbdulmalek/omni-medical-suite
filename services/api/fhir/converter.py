"""FHIR R4 converter for OCR-extracted medical data.

Converts structured OCR results into HL7 FHIR R4 resources (Patient,
Observation, MedicationRequest, Bundle) for interoperability with
healthcare information systems.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class FHIRConverter:
    """Convert OCR-extracted medical data to FHIR R4 resources.

    Supports:
    - Patient demographics
    - Medication requests (prescriptions)
    - Clinical observations (lab results, vitals)
    - Bundle packaging of multiple resources
    """

    @staticmethod
    def patient_from_ocr(extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a FHIR Patient resource from OCR extraction results.

        Parameters
        ----------
        extracted_data:
            Dictionary containing patient fields (patient_id, patient_first_name,
            patient_last_name, birth_date, gender, etc.).
        """
        patient: Dict[str, Any] = {
            "resourceType": "Patient",
            "id": extracted_data.get("patient_id", "unknown"),
            "name": [
                {
                    "use": "official",
                    "family": extracted_data.get("patient_last_name", ""),
                    "given": [extracted_data.get("patient_first_name", "")],
                }
            ],
        }

        # Optional fields
        if extracted_data.get("birth_date"):
            patient["birthDate"] = extracted_data["birth_date"]
        if extracted_data.get("gender"):
            patient["gender"] = extracted_data["gender"].lower()

        return patient

    @staticmethod
    def medication_request_from_ocr(
        drug_name: str,
        dosage: str,
        route: str = "oral",
        patient_id: str = "unknown",
    ) -> Dict[str, Any]:
        """Create a FHIR MedicationRequest resource from OCR data.

        Parameters
        ----------
        drug_name:
            Name of the prescribed medication.
        dosage:
            Dosage string (e.g., "500 mg twice daily").
        route:
            Administration route.
        patient_id:
            Reference to the FHIR Patient resource.
        """
        # Parse numeric dose value from dosage string
        dose_value = 1.0
        dose_unit = "mg"
        parts = dosage.strip().split()
        if parts:
            try:
                dose_value = float(parts[0])
            except ValueError:
                pass
            if len(parts) > 1:
                dose_unit = parts[1]

        return {
            "resourceType": "MedicationRequest",
            "id": f"medreq-{datetime.now().timestamp():.0f}",
            "status": "active",
            "intent": "order",
            "subject": {"reference": f"Patient/{patient_id}"},
            "medicationCodeableConcept": {
                "coding": [
                    {
                        "system": "http://www.nlm.nih.gov/research/umls/rxnorm",
                        "code": drug_name.upper().replace(" ", "-"),
                        "display": drug_name,
                    }
                ]
            },
            "dosageInstruction": [
                {
                    "text": f"{dosage} {route}",
                    "doseAndRate": [
                        {
                            "doseQuantity": {
                                "value": dose_value,
                                "unit": dose_unit,
                            }
                        }
                    ],
                }
            ],
        }

    @staticmethod
    def observation_from_ocr(
        code: str,
        display: str,
        value: float,
        unit: str,
        patient_id: str = "unknown",
    ) -> Dict[str, Any]:
        """Create a FHIR Observation resource.

        Parameters
        ----------
        code:
            LOINC or other standard code for the observation.
        display:
            Human-readable name for the observation.
        value:
            Numeric value of the observation.
        unit:
            Unit of measurement.
        patient_id:
            Reference to the FHIR Patient resource.
        """
        return {
            "resourceType": "Observation",
            "id": f"obs-{datetime.now().timestamp():.0f}",
            "status": "final",
            "subject": {"reference": f"Patient/{patient_id}"},
            "effectiveDateTime": datetime.now().isoformat(),
            "code": {
                "coding": [
                    {
                        "system": "http://loinc.org",
                        "code": code,
                        "display": display,
                    }
                ],
                "text": display,
            },
            "valueQuantity": {
                "value": value,
                "unit": unit,
            },
        }

    @staticmethod
    def create_bundle(
        resources: List[Dict[str, Any]],
        bundle_type: str = "collection",
    ) -> Dict[str, Any]:
        """Package multiple FHIR resources into a Bundle.

        Parameters
        ----------
        resources:
            List of FHIR resource dictionaries.
        bundle_type:
            FHIR Bundle type (default: "collection").
            Use "transaction" for batch writes to a FHIR server.
        """
        return {
            "resourceType": "Bundle",
            "type": bundle_type,
            "timestamp": datetime.now().isoformat(),
            "entry": [{"resource": r} for r in resources],
        }
