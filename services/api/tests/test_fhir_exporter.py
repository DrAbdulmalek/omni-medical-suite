"""
Unit tests for FHIR/HL7 Exporter module.
Tests: FHIR R4 Bundle, HL7 v2 messages, JSON export, patient data, integrity.
"""

import pytest
import json
import hashlib
from services.api.fhir.converter import (
    FHIRExporter, MedicalEntity, PatientInfo, DocumentMetadata,
    ExportFormat
)


@pytest.fixture
def exporter():
    """Create a FHIR exporter instance."""
    return FHIRExporter()


@pytest.fixture
def sample_entities():
    """Create sample medical entities."""
    return [
        MedicalEntity(type="diagnosis", text="hypertension", code="38341003", system="http://snomed.info/sct", confidence=0.92),
        MedicalEntity(type="medication", text="amlodipine", code="329526", system="http://www.nlm.nih.gov/research/umls/rxnorm", confidence=0.88),
        MedicalEntity(type="symptom", text="fever", code="386661006", system="http://snomed.info/sct", confidence=0.85),
    ]


@pytest.fixture
def sample_patient():
    """Create sample patient info."""
    return PatientInfo(
        id="p-12345",
        name="أحمد محمد",
        birth_date="1985-03-15",
        gender="male",
        mrn="MRN-2024-001"
    )


@pytest.fixture
def sample_metadata():
    """Create sample document metadata."""
    return DocumentMetadata(
        document_id="doc-67890",
        source_type="discharge",
        created_at="2026-05-20",
        processed_at="2026-05-27T15:00:00Z",
        ocr_confidence=0.94,
        validator_confidence=0.87,
        language="ar"
    )


class TestFHIRExporterCreation:
    """Test exporter initialization."""

    def test_exporter_creation(self):
        """Test exporter can be instantiated."""
        exporter = FHIRExporter()
        assert exporter.fhir_version == "4.0.1"


class TestFHIRR4Export:
    """Test FHIR R4 Bundle export."""

    def test_bundle_structure(self, exporter, sample_entities, sample_patient, sample_metadata):
        """Test FHIR Bundle has correct structure."""
        bundle = exporter.to_fhir_r4(
            text="المريض يعاني من ارتفاع ضغط الدم...",
            entities=sample_entities,
            patient=sample_patient,
            metadata=sample_metadata
        )

        assert bundle["resourceType"] == "Bundle"
        assert bundle["type"] == "document"
        assert "id" in bundle
        assert "meta" in bundle
        assert "entry" in bundle
        assert len(bundle["entry"]) > 0

    def test_bundle_entries(self, exporter, sample_entities, sample_patient, sample_metadata):
        """Test Bundle contains expected resources."""
        bundle = exporter.to_fhir_r4(
            text="Test text",
            entities=sample_entities,
            patient=sample_patient,
            metadata=sample_metadata
        )

        resource_types = [entry["resource"]["resourceType"] for entry in bundle["entry"]]

        assert "Composition" in resource_types
        assert "Patient" in resource_types
        assert "DocumentReference" in resource_types
        assert "Provenance" in resource_types
        assert "Observation" in resource_types
        assert "MedicationRequest" in resource_types

    def test_patient_resource(self, exporter, sample_entities, sample_patient, sample_metadata):
        """Test Patient resource content."""
        bundle = exporter.to_fhir_r4(
            text="Test",
            entities=sample_entities,
            patient=sample_patient,
            metadata=sample_metadata
        )

        patient_entry = next(
            e for e in bundle["entry"] if e["resource"]["resourceType"] == "Patient"
        )
        patient = patient_entry["resource"]

        assert patient["id"] == "p-12345"
        assert patient["gender"] == "male"
        assert patient["birthDate"] == "1985-03-15"
        assert patient["name"][0]["text"] == "أحمد محمد"
        assert "identifier" in patient
        assert patient["identifier"][0]["value"] == "MRN-2024-001"

    def test_document_reference(self, exporter, sample_entities, sample_patient, sample_metadata):
        """Test DocumentReference resource."""
        bundle = exporter.to_fhir_r4(
            text="Medical document text content",
            entities=sample_entities,
            patient=sample_patient,
            metadata=sample_metadata
        )

        doc_ref_entry = next(
            e for e in bundle["entry"] if e["resource"]["resourceType"] == "DocumentReference"
        )
        doc_ref = doc_ref_entry["resource"]

        assert doc_ref["status"] == "current"
        assert doc_ref["docStatus"] == "final"
        assert "content" in doc_ref
        assert "attachment" in doc_ref["content"][0]
        assert "hash" in doc_ref["content"][0]["attachment"]
        assert "size" in doc_ref["content"][0]["attachment"]

    def test_observation_resources(self, exporter, sample_entities, sample_patient, sample_metadata):
        """Test Observation resources from entities."""
        bundle = exporter.to_fhir_r4(
            text="Test",
            entities=sample_entities,
            patient=sample_patient,
            metadata=sample_metadata
        )

        observations = [
            e["resource"] for e in bundle["entry"]
            if e["resource"]["resourceType"] == "Observation"
        ]

        assert len(observations) == 1  # Only symptom entity
        assert observations[0]["status"] == "final"
        assert observations[0]["code"]["text"] == "fever"

    def test_medication_request(self, exporter, sample_entities, sample_patient, sample_metadata):
        """Test MedicationRequest resource."""
        bundle = exporter.to_fhir_r4(
            text="Test",
            entities=sample_entities,
            patient=sample_patient,
            metadata=sample_metadata
        )

        med_reqs = [
            e["resource"] for e in bundle["entry"]
            if e["resource"]["resourceType"] == "MedicationRequest"
        ]

        assert len(med_reqs) == 1
        assert med_reqs[0]["status"] == "active"
        assert med_reqs[0]["intent"] == "order"
        assert med_reqs[0]["medicationCodeableConcept"]["text"] == "amlodipine"

    def test_provenance(self, exporter, sample_entities, sample_patient, sample_metadata):
        """Test Provenance resource for audit."""
        bundle = exporter.to_fhir_r4(
            text="Test",
            entities=sample_entities,
            patient=sample_patient,
            metadata=sample_metadata
        )

        prov_entry = next(
            e for e in bundle["entry"] if e["resource"]["resourceType"] == "Provenance"
        )
        prov = prov_entry["resource"]

        assert prov["activity"]["coding"][0]["code"] == "CREATE"
        assert prov["agent"][0]["type"]["coding"][0]["code"] == "assembler"

    def test_without_patient(self, exporter, sample_entities, sample_metadata):
        """Test export without patient info."""
        bundle = exporter.to_fhir_r4(
            text="Test text",
            entities=sample_entities,
            patient=None,
            metadata=sample_metadata
        )

        resource_types = [entry["resource"]["resourceType"] for entry in bundle["entry"]]
        assert "Patient" not in resource_types
        assert "Composition" in resource_types

    def test_without_metadata(self, exporter, sample_entities, sample_patient):
        """Test export without metadata."""
        bundle = exporter.to_fhir_r4(
            text="Test text",
            entities=sample_entities,
            patient=sample_patient,
            metadata=None
        )

        assert bundle["resourceType"] == "Bundle"
        assert len(bundle["entry"]) > 0

    def test_bundle_identifier(self, exporter, sample_entities, sample_patient, sample_metadata):
        """Test Bundle has identifier."""
        bundle = exporter.to_fhir_r4(
            text="Test",
            entities=sample_entities,
            patient=sample_patient,
            metadata=sample_metadata
        )

        assert "identifier" in bundle
        assert bundle["identifier"]["system"] == "https://omnimedical.local/bundle-id"

    def test_composition_type(self, exporter, sample_entities, sample_patient, sample_metadata):
        """Test Composition has correct LOINC type."""
        bundle = exporter.to_fhir_r4(
            text="Test",
            entities=sample_entities,
            patient=sample_patient,
            metadata=sample_metadata
        )

        comp = next(
            e["resource"] for e in bundle["entry"]
            if e["resource"]["resourceType"] == "Composition"
        )

        assert comp["type"]["coding"][0]["system"] == "http://loinc.org"
        assert comp["type"]["coding"][0]["code"] == "18842-5"  # Discharge summary


class TestHL7v2Export:
    """Test HL7 v2.5 message export."""

    def test_hl7_message_structure(self, exporter, sample_entities, sample_patient, sample_metadata):
        """Test HL7 message has correct segments."""
        msg = exporter.to_hl7_v2(
            text="Test text",
            entities=sample_entities,
            patient=sample_patient,
            metadata=sample_metadata
        )

        segments = msg.split("\r")

        assert segments[0].startswith("MSH")
        assert any(s.startswith("PID") for s in segments)
        assert any(s.startswith("OBR") for s in segments)
        assert any(s.startswith("OBX") for s in segments)
        assert any(s.startswith("NTE") for s in segments)

    def test_msh_segment(self, exporter, sample_entities, sample_patient, sample_metadata):
        """Test MSH segment content."""
        msg = exporter.to_hl7_v2(
            text="Test",
            entities=sample_entities,
            patient=sample_patient,
            metadata=sample_metadata
        )

        msh = msg.split("\r")[0]

        assert "OmniMedical" in msh
        assert "OmniMedicalSuite" in msh
        assert "ORU^R01" in msh
        assert "2.5" in msh

    def test_pid_segment(self, exporter, sample_entities, sample_patient, sample_metadata):
        """Test PID segment with patient data."""
        msg = exporter.to_hl7_v2(
            text="Test",
            entities=sample_entities,
            patient=sample_patient,
            metadata=sample_metadata
        )

        pid = next(s for s in msg.split("\r") if s.startswith("PID"))

        assert "MRN-2024-001" in pid
        assert "أحمد محمد" in pid
        assert "1985-03-15" in pid

    def test_obx_segments(self, exporter, sample_entities, sample_patient, sample_metadata):
        """Test OBX segments for entities."""
        msg = exporter.to_hl7_v2(
            text="Test",
            entities=sample_entities,
            patient=sample_patient,
            metadata=sample_metadata
        )

        obx_segments = [s for s in msg.split("\r") if s.startswith("OBX")]

        assert len(obx_segments) == 3  # One per entity

    def test_mdm_message_type(self, exporter, sample_entities, sample_patient, sample_metadata):
        """Test MDM^T02 message type."""
        msg = exporter.to_hl7_v2(
            text="Test",
            entities=sample_entities,
            patient=sample_patient,
            metadata=sample_metadata,
            message_type="MDM^T02"
        )

        msh = msg.split("\r")[0]
        assert "MDM^T02" in msh

    def test_without_patient(self, exporter, sample_entities, sample_metadata):
        """Test HL7 without patient info."""
        msg = exporter.to_hl7_v2(
            text="Test",
            entities=sample_entities,
            patient=None,
            metadata=sample_metadata
        )

        pid = next(s for s in msg.split("\r") if s.startswith("PID"))
        assert "PID|1||" in pid  # Empty patient ID


class TestJSONExport:
    """Test custom JSON export."""

    def test_json_structure(self, exporter, sample_entities, sample_patient, sample_metadata):
        """Test JSON export structure."""
        result = exporter.to_json(
            text="Test text",
            entities=sample_entities,
            patient=sample_patient,
            metadata=sample_metadata
        )

        assert result["format"] == "omnimedical_custom_v1"
        assert "document" in result
        assert "export_info" in result

    def test_json_integrity_hash(self, exporter, sample_entities):
        """Test integrity hash generation."""
        text = "Medical document text"
        result = exporter.to_json(
            text=text,
            entities=sample_entities,
            patient=None,
            metadata=None
        )

        expected_hash = hashlib.sha256(text.encode()).hexdigest()[:16]
        assert result["document"]["integrity_hash"] == expected_hash

    def test_json_entities(self, exporter, sample_entities):
        """Test entity serialization in JSON."""
        result = exporter.to_json(
            text="Test",
            entities=sample_entities,
            patient=None,
            metadata=None
        )

        assert len(result["document"]["entities"]) == 3
        assert result["document"]["entities"][0]["type"] == "diagnosis"

    def test_json_patient(self, exporter, sample_entities, sample_patient):
        """Test patient serialization in JSON."""
        result = exporter.to_json(
            text="Test",
            entities=sample_entities,
            patient=sample_patient,
            metadata=None
        )

        assert result["document"]["patient"]["name"] == "أحمد محمد"
        assert result["document"]["patient"]["mrn"] == "MRN-2024-001"


class TestUtilityFunctions:
    """Test helper methods."""

    def test_generate_id(self, exporter):
        """Test ID generation."""
        id1 = exporter._generate_id("test")
        id2 = exporter._generate_id("test")

        assert id1.startswith("test-")
        assert len(id1) > 10
        assert id1 != id2  # Should be unique

    def test_entity_to_dict(self, exporter, sample_entities):
        """Test entity serialization."""
        entity_dict = exporter._entity_to_dict(sample_entities[0])

        assert entity_dict["type"] == "diagnosis"
        assert entity_dict["text"] == "hypertension"
        assert entity_dict["code"] == "38341003"
        assert entity_dict["confidence"] == 0.92

    def test_patient_to_dict(self, exporter, sample_patient):
        """Test patient serialization."""
        patient_dict = exporter._patient_to_dict(sample_patient)

        assert patient_dict["name"] == "أحمد محمد"
        assert patient_dict["gender"] == "male"

    def test_metadata_to_dict(self, exporter, sample_metadata):
        """Test metadata serialization."""
        metadata_dict = exporter._metadata_to_dict(sample_metadata)

        assert metadata_dict["document_id"] == "doc-67890"
        assert metadata_dict["source_type"] == "discharge"
        assert metadata_dict["ocr_confidence"] == 0.94


class TestPrescriptionType:
    """Test prescription-specific export."""

    def test_prescription_loinc(self, exporter):
        """Test prescription uses correct LOINC code."""
        metadata = DocumentMetadata(
            document_id="rx-001",
            source_type="prescription",
            created_at="2026-05-27",
            processed_at="2026-05-27T15:00:00Z",
            ocr_confidence=0.95,
            validator_confidence=0.90,
            language="ar"
        )

        bundle = exporter.to_fhir_r4(
            text="Prescription text",
            entities=[],
            patient=None,
            metadata=metadata
        )

        comp = next(
            e["resource"] for e in bundle["entry"]
            if e["resource"]["resourceType"] == "Composition"
        )

        assert comp["type"]["coding"][0]["code"] == "57833-6"


class TestLabReportType:
    """Test lab report-specific export."""

    def test_lab_loinc(self, exporter):
        """Test lab report uses correct LOINC code."""
        metadata = DocumentMetadata(
            document_id="lab-001",
            source_type="lab",
            created_at="2026-05-27",
            processed_at="2026-05-27T15:00:00Z",
            ocr_confidence=0.92,
            validator_confidence=0.85,
            language="en"
        )

        bundle = exporter.to_fhir_r4(
            text="Lab results",
            entities=[],
            patient=None,
            metadata=metadata
        )

        comp = next(
            e["resource"] for e in bundle["entry"]
            if e["resource"]["resourceType"] == "Composition"
        )

        assert comp["type"]["coding"][0]["code"] == "11502-2"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
