"""
FHIR Exporter - تصدير البيانات الطبية إلى تنسيق FHIR
========================================================

This module converts OCR-extracted text and NER results into FHIR
(Fast Healthcare Interoperability Resources) format, enabling
interoperability with healthcare IT systems.

Inspired by the ai-health-records-scanner project's approach to
converting scanned medical documents into structured FHIR resources.

هذه الوحدة تحول النصوص المستخرجة من OCR ونتائج NER إلى تنسيق FHIR
ممكّنة التشغيل البيني مع أنظمة تقنية المعلومات الصحية.

Pure Python implementation - no external FHIR library dependencies.
تنفيذ Python نقي - لا يتطلب مكتبات FHIR خارجية.
"""

import logging
import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Arabic + English messages
_MSG_EXPORT = "جارٍ التصدير إلى تنسيق FHIR | Exporting to FHIR format"
_MSG_EXPORTED = "تم إنشاء مورد FHIR: {resource_type} | Created FHIR resource: {resource_type}"
_MSG_DATE_CONVERT = "تحويل التاريخ العربي: {arabic} -> {iso} | Converting Arabic date: {arabic} -> {iso}"
_MSG_DATE_FAIL = "فشل تحويل التاريخ: {date} | Failed to convert date: {date}"

# Arabic to English month mapping
ARABIC_MONTHS = {
    "يناير": "01", "كانون الثاني": "01",
    "فبراير": "02", "شباط": "02",
    "مارس": "03", "آذار": "03",
    "أبريل": "04", "نيسان": "04",
    "مايو": "05", "أيار": "05",
    "يونيو": "06", "حزيران": "06",
    "يوليو": "07", "تموز": "07",
    "أغسطس": "08", "آب": "08",
    "سبتمبر": "09", "أيلول": "09",
    "أكتوبر": "10", "تشرين الأول": "10",
    "نوفمبر": "11", "تشرين الثاني": "11",
    "ديسمبر": "12", "كانون الأول": "12",
}

# Eastern Arabic numerals to Western
EASTERN_ARABIC = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


class FHIRExporter:
    """
    Export OCR + NER results to FHIR-compliant resource format.

    تصدير نتائج OCR + NER إلى تنسيق موارد متوافق مع FHIR.

    This class takes structured medical data (typically from OCR text
    extraction combined with NER entity recognition) and converts it
    into standard FHIR resources:
        - Patient: Demographics and identifiers
        - Observation: Lab results, vitals, measurements
        - MedicationRequest: Prescribed medications with dosages
        - Condition: Diagnoses and clinical findings
        - DiagnosticReport: Lab test reports

    No external FHIR library is required - resources are built as
    plain Python dictionaries following the FHIR JSON schema.
    """

    def __init__(self) -> None:
        """Initialize the FHIR exporter."""
        self.resource_type_counter: Dict[str, int] = {}

    def export_to_fhir(self, extracted_data: Dict) -> Dict:
        """
        Convert OCR+NER extracted data into a FHIR Bundle.

        تحويل البيانات المستخرجة من OCR+NER إلى حزمة FHIR.

        Args:
            extracted_data: Dictionary containing:
                - text (str): Full OCR text
                - entities (List[Dict]): NER-extracted entities
                - metadata (Dict, optional): Additional document metadata
                - patient_info (Dict, optional): Patient demographics

        Returns:
            FHIR Bundle dictionary containing Patient, Observation,
            MedicationRequest, and Condition resources.
        """
        logger.info(_MSG_EXPORT)

        bundle_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

        bundle: Dict[str, Any] = {
            "resourceType": "Bundle",
            "id": bundle_id,
            "type": "collection",
            "timestamp": timestamp,
            "entry": [],
        }

        entities = extracted_data.get("entities", [])
        text = extracted_data.get("text", "")
        patient_info = extracted_data.get("patient_info", {})
        metadata = extracted_data.get("metadata", {})

        # --- Patient Resource ---
        patient_resource = self._build_patient_resource(
            patient_info, entities, metadata
        )
        if patient_resource:
            bundle["entry"].append({
                "fullUrl": f"urn:uuid:{patient_resource['id']}",
                "resource": patient_resource,
            })
            logger.info(_MSG_EXPORTED.format(resource_type="Patient"))

        # --- Observation Resources ---
        observations = self._build_observation_resources(entities, text)
        for obs in observations:
            bundle["entry"].append({
                "fullUrl": f"urn:uuid:{obs['id']}",
                "resource": obs,
            })
        logger.info(
            _MSG_EXPORTED.format(
                resource_type=f"Observation ({len(observations)})"
            )
        )

        # --- MedicationRequest Resources ---
        medications = self._build_medication_requests(entities, text)
        for med in medications:
            bundle["entry"].append({
                "fullUrl": f"urn:uuid:{med['id']}",
                "resource": med,
            })
        logger.info(
            _MSG_EXPORTED.format(
                resource_type=f"MedicationRequest ({len(medications)})"
            )
        )

        # --- Condition Resources (from DIAGNOSIS entities) ---
        conditions = self._build_condition_resources(entities, metadata)
        for cond in conditions:
            bundle["entry"].append({
                "fullUrl": f"urn:uuid:{cond['id']}",
                "resource": cond,
            })
        logger.info(
            _MSG_EXPORTED.format(
                resource_type=f"Condition ({len(conditions)})"
            )
        )

        # --- DiagnosticReport Resource ---
        lab_entities = [e for e in entities if e.get("type") == "LAB_TEST"]
        if lab_entities:
            report = self._build_diagnostic_report(entities, metadata, text)
            if report:
                bundle["entry"].append({
                    "fullUrl": f"urn:uuid:{report['id']}",
                    "resource": report,
                })
                logger.info(_MSG_EXPORTED.format(resource_type="DiagnosticReport"))

        return bundle

    def _build_patient_resource(
        self,
        patient_info: Dict,
        entities: List[Dict],
        metadata: Dict,
    ) -> Optional[Dict]:
        """
        Build a FHIR Patient resource.

        إنشاء مورد FHIR للمريض.

        Attempts to extract patient information from the entities and
        provided metadata. If no patient info is found, creates a
        minimal anonymous patient.

        Args:
            patient_info: Explicit patient information dict.
            entities: NER-extracted entities.
            metadata: Document metadata.

        Returns:
            FHIR Patient resource dictionary, or None on failure.
        """
        patient_id = str(uuid.uuid4())
        name = patient_info.get("name", "")
        age = patient_info.get("age", "")
        gender = patient_info.get("gender", "")
        file_number = metadata.get("file_number", "")

        # Try to extract age from entities or text
        if not age:
            for entity in entities:
                val = entity.get("value", "")
                age_match = re.search(r"العمر[:\s]*(\d+)", val)
                if age_match:
                    age = age_match.group(1)
                    break

        # Build name field
        name_field = []
        if name:
            name_field.append({
                "use": "official",
                "text": name,
                "family": name.split()[-1] if name.split() else "",
                "given": name.split()[:-1] if len(name.split()) > 1 else [name],
            })

        patient = {
            "resourceType": "Patient",
            "id": patient_id,
            "text": {
                "status": "generated",
                "div": f"<div>بيانات المريض المستخرجة من OCR</div>",
            },
        }

        if name_field:
            patient["name"] = name_field

        if gender:
            # Normalize Arabic gender to FHIR codes
            gender_map = {"ذكر": "male", "أنثى": "female", "male": "male", "female": "female"}
            patient["gender"] = gender_map.get(gender, "unknown")

        if age:
            try:
                age_int = int(age)
                birth_year = datetime.utcnow().year - age_int
                patient["birthDate"] = f"{birth_year}-01-01"
            except (ValueError, TypeError):
                pass

        if file_number:
            patient["identifier"] = [
                {
                    "use": "official",
                    "type": {
                        "coding": [{
                            "system": "http://terminology.hl7.org/CodeSystem/v2-0203",
                            "code": "MR",
                            "display": "Medical Record Number",
                        }],
                        "text": "رقم الملف الطبي",
                    },
                    "value": str(file_number),
                }
            ]

        return patient

    def _build_observation_resources(
        self,
        entities: List[Dict],
        text: str,
    ) -> List[Dict]:
        """
        Build FHIR Observation resources from lab test entities.

        إنشاء موارد FHIR Observation من كيانات التحاليل.

        Args:
            entities: NER-extracted entities.
            text: Full OCR text for context.

        Returns:
            List of FHIR Observation resource dictionaries.
        """
        observations: List[Dict] = []

        lab_entities = [e for e in entities if e.get("type") == "LAB_TEST"]

        for entity in lab_entities:
            obs_id = str(uuid.uuid4())
            value = entity.get("value", "")

            # Try to find associated values in nearby text
            lab_value = self._find_lab_value(text, value)

            observation = {
                "resourceType": "Observation",
                "id": obs_id,
                "status": "final",
                "category": [{
                    "coding": [{
                        "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                        "code": "laboratory",
                        "display": "Laboratory",
                    }],
                }],
                "code": {
                    "text": value,
                    "coding": [{
                        "display": value,
                    }],
                },
                "subject": {"reference": "urn:uuid:patient"},
            }

            if lab_value:
                try:
                    observation["valueQuantity"] = {
                        "value": float(lab_value["numeric"]),
                        "unit": lab_value.get("unit", ""),
                    }
                except (ValueError, TypeError):
                    observation["valueString"] = str(lab_value.get("raw", ""))

            observations.append(observation)

        return observations

    def _build_medication_requests(
        self,
        entities: List[Dict],
        text: str,
    ) -> List[Dict]:
        """
        Build FHIR MedicationRequest resources from drug entities.

        إنشاء موارد FHIR MedicationRequest من كيانات الأدوية.

        Args:
            entities: NER-extracted entities.
            text: Full OCR text for context.

        Returns:
            List of FHIR MedicationRequest resource dictionaries.
        """
        medications: List[Dict] = []

        drug_entities = [e for e in entities if e.get("type") == "DRUG"]
        dosage_entities = [e for e in entities if e.get("type") == "DOSAGE"]
        freq_entities = [e for e in entities if e.get("type") == "FREQUENCY"]
        dur_entities = [e for e in entities if e.get("type") == "DURATION"]

        for idx, drug in enumerate(drug_entities):
            med_id = str(uuid.uuid4())
            drug_name = drug.get("value", "")

            # Find closest dosage
            dosage_text = self._find_closest_entity(
                drug, dosage_entities, text
            )

            # Find closest frequency
            freq_text = self._find_closest_entity(
                drug, freq_entities, text
            )

            # Find closest duration
            dur_text = self._find_closest_entity(
                drug, dur_entities, text
            )

            # Build dosage instruction
            dosage_instruction = drug_name
            if dosage_text:
                dosage_instruction += f" {dosage_text}"
            if freq_text:
                dosage_instruction += f" {freq_text}"
            if dur_text:
                dosage_instruction += f" {dur_text}"

            med_request = {
                "resourceType": "MedicationRequest",
                "id": med_id,
                "status": "active",
                "intent": "order",
                "medicationCodeableConcept": {
                    "text": drug_name,
                    "coding": [{
                        "display": drug_name,
                    }],
                },
                "subject": {"reference": "urn:uuid:patient"},
                "dosageInstruction": [{
                    "text": dosage_instruction,
                    "patientInstruction": dosage_instruction,
                }],
            }

            if dosage_text:
                # Try to extract numeric dose
                dose_match = re.search(r"(\d+(?:\.\d+)?)\s*(ملغ|مجم|جم|مللي|وحدة)", dosage_text)
                if dose_match:
                    med_request["dosageInstruction"][0]["doseAndRate"] = [{
                        "doseQuantity": {
                            "value": float(dose_match.group(1)),
                            "unit": dose_match.group(2),
                            "system": "http://unitsofmeasure.org",
                        }
                    }]

            medications.append(med_request)

        return medications

    def _build_condition_resources(
        self,
        entities: List[Dict],
        metadata: Dict,
    ) -> List[Dict]:
        """
        Build FHIR Condition resources from diagnosis entities.

        إنشاء موارد FHIR Condition من كيانات التشخيص.

        Args:
            entities: NER-extracted entities.
            metadata: Document metadata (may contain date).

        Returns:
            List of FHIR Condition resource dictionaries.
        """
        conditions: List[Dict] = []

        diag_entities = [e for e in entities if e.get("type") == "DIAGNOSIS"]

        for diag in diag_entities:
            cond_id = str(uuid.uuid4())
            diagnosis_text = diag.get("value", "")

            condition: Dict[str, Any] = {
                "resourceType": "Condition",
                "id": cond_id,
                "clinicalStatus": {
                    "coding": [{
                        "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                        "code": "active",
                        "display": "Active",
                    }],
                },
                "verificationStatus": {
                    "coding": [{
                        "system": "http://terminology.hl7.org/CodeSystem/condition-ver-status",
                        "code": "confirmed",
                        "display": "Confirmed",
                    }],
                },
                "code": {
                    "text": diagnosis_text,
                    "coding": [{
                        "display": diagnosis_text,
                    }],
                },
                "subject": {"reference": "urn:uuid:patient"},
            }

            # Add onset date if available
            doc_date = metadata.get("date", "")
            if doc_date:
                iso_date = self._to_fhir_datetime(doc_date)
                if iso_date:
                    condition["onsetDateTime"] = iso_date

            conditions.append(condition)

        return conditions

    def _build_diagnostic_report(
        self,
        entities: List[Dict],
        metadata: Dict,
        text: str,
    ) -> Optional[Dict]:
        """
        Build a FHIR DiagnosticReport resource.

        إنشاء مورد FHIR DiagnosticReport.

        Args:
            entities: NER entities.
            metadata: Document metadata.
            text: Full OCR text.

        Returns:
            FHIR DiagnosticReport dictionary or None.
        """
        report_id = str(uuid.uuid4())
        lab_entities = [e for e in entities if e.get("type") == "LAB_TEST"]

        if not lab_entities:
            return None

        doc_date = metadata.get("date", "")
        iso_date = self._to_fhir_datetime(doc_date) if doc_date else None

        report = {
            "resourceType": "DiagnosticReport",
            "id": report_id,
            "status": "final",
            "category": [{
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/v2-0074",
                    "code": "LAB",
                    "display": "Laboratory",
                }],
            }],
            "code": {
                "text": "تقرير تحاليل مخبرية | Laboratory Report",
            },
            "subject": {"reference": "urn:uuid:patient"},
            "presentedForm": [{
                "contentType": "text/plain",
                "data": text.encode("utf-8").hex(),
            }],
        }

        if iso_date:
            report["effectiveDateTime"] = iso_date

        # Reference observation results
        result_refs = []
        for i, _ in enumerate(lab_entities):
            result_refs.append({
                "reference": f"urn:uuid:observation-{i}",
                "display": lab_entities[i].get("value", ""),
            })

        if result_refs:
            report["result"] = result_refs

        return report

    def _to_fhir_datetime(self, arabic_date: str) -> Optional[str]:
        """
        Convert Arabic date string to ISO 8601 format.

        تحويل التاريخ العربي إلى صيغة ISO 8601.

        Handles various Arabic date formats:
            - "١٥ يناير ٢٠٢٤" (Arabic numerals + Arabic month)
            - "2024/01/15" (Western format)
            - "15-01-2024" (Dashed format)
            - "15/1/2024" (Short format)

        Args:
            arabic_date: Date string in Arabic or standard format.

        Returns:
            ISO 8601 date string, or None if conversion fails.
        """
        if not arabic_date or not arabic_date.strip():
            return None

        original = arabic_date.strip()

        try:
            # Convert Eastern Arabic numerals to Western
            normalized = original.translate(EASTERN_ARABIC)

            # Try standard date patterns first
            # YYYY/MM/DD or YYYY-MM-DD
            iso_match = re.match(
                r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", normalized
            )
            if iso_match:
                y, m, d = iso_match.groups()
                return f"{y}-{int(m):02d}-{int(d):02d}"

            # DD/MM/YYYY
            dmy_match = re.match(
                r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", normalized
            )
            if dmy_match:
                d, m, y = dmy_match.groups()
                return f"{y}-{int(m):02d}-{int(d):02d}"

            # Arabic format: DD MONTH YYYY
            ar_match = re.match(
                r"(\d{1,2})\s+([\u0600-\u06FF\s]+)\s+(\d{4})", normalized
            )
            if ar_match:
                day = int(ar_match.group(1))
                month_name = ar_match.group(2).strip()
                year = ar_match.group(3)

                # Look up month number
                month_num = None
                for ar_month, num in ARABIC_MONTHS.items():
                    if ar_month in month_name:
                        month_num = num
                        break

                if month_num:
                    return f"{year}-{month_num}-{day:02d}"

            logger.debug(
                _MSG_DATE_FAIL.format(date=original)
            )
            return None

        except Exception as e:
            logger.debug(
                f"خطأ في تحويل التاريخ: {e} | Date conversion error: {e}"
            )
            return None

    @staticmethod
    def _find_lab_value(text: str, lab_name: str) -> Optional[Dict]:
        """
        Try to find a numeric lab value associated with a test name.

        محاولة العثور على قيمة رقمية مرتبطة باسم تحليل.

        Args:
            text: Full text to search in.
            lab_name: Name of the lab test.

        Returns:
            Dict with 'numeric', 'unit', 'raw' or None.
        """
        # Find the lab name in text and look for nearby numbers
        idx = text.find(lab_name)
        if idx == -1:
            return None

        # Search in a window of 80 characters after the lab name
        window = text[idx:idx + len(lab_name) + 80]

        # Pattern: number followed by optional unit
        value_match = re.search(
            r"(\d+(?:\.\d+)?)\s*[/\s:]*\s*(\d+(?:\.\d+)?)?\s*(?:ملغ|مجم|جم|مل|وحدة|mg|g|ml|U|mmol|pg|ng)?",
            window[len(lab_name):],
        )

        if value_match:
            numeric_str = value_match.group(1)
            unit = value_match.group(3) or ""

            try:
                return {
                    "numeric": float(numeric_str),
                    "unit": unit,
                    "raw": value_match.group(0).strip(),
                }
            except ValueError:
                pass

        return None

    @staticmethod
    def _find_closest_entity(
        target: Dict,
        candidates: List[Dict],
        text: str,
        max_distance: int = 100,
    ) -> str:
        """
        Find the candidate entity closest to the target in text.

        البحث عن الكيان المرشح الأقرب إلى الهدف في النص.

        Args:
            target: Target entity with 'start' and 'end' positions.
            candidates: List of candidate entities.
            text: Full text (unused for position-based search).
            max_distance: Maximum character distance to consider.

        Returns:
            The value of the closest candidate, or empty string.
        """
        if not candidates:
            return ""

        target_start = target.get("start", 0)
        target_end = target.get("end", 0)
        target_mid = (target_start + target_end) / 2

        best_value = ""
        best_distance = float("inf")

        for candidate in candidates:
            c_start = candidate.get("start", 0)
            c_end = candidate.get("end", 0)
            c_mid = (c_start + c_end) / 2

            distance = abs(c_mid - target_mid)

            if distance < best_distance and distance <= max_distance:
                best_distance = distance
                best_value = candidate.get("value", "")

        return best_value