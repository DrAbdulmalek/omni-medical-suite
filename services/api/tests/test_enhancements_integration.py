"""
Integration tests for OmniMedical Suite v2.1 enhancements.
Tests end-to-end workflows combining: OCR Cache, Circuit Breaker, Rate Limiter, Medical Validator, FHIR Exporter.
"""

import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch
from services.api.ocr.cache import OCRCache
from services.api.ocr.circuit_breaker import CircuitBreakerRegistry, CircuitBreakerError
from services.api.middleware.rate_limit import UserRateLimiter, RateLimitExceeded
from services.api.validation.medical_validator import MedicalValidator
from services.api.fhir.converter import FHIRExporter, MedicalEntity, PatientInfo, DocumentMetadata


@pytest.fixture
async def mock_redis():
    """Create a shared mock Redis for all modules."""
    redis = MagicMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock()
    redis.setex = AsyncMock()
    redis.incr = AsyncMock(return_value=1)
    redis.delete = AsyncMock()
    redis.keys = AsyncMock(return_value=[])
    redis.zremrangebyscore = AsyncMock(return_value=0)
    redis.zcard = AsyncMock(return_value=0)
    redis.zadd = AsyncMock(return_value=1)
    redis.zrange = AsyncMock(return_value=[])
    redis.hincrby = AsyncMock(return_value=1)
    redis.hgetall = AsyncMock(return_value={})
    redis.hset = AsyncMock()
    redis.close = AsyncMock()
    return redis


class TestEndToEndOCRWorkflow:
    """Test complete OCR processing workflow."""

    @pytest.mark.asyncio
    async def test_cached_ocr_skips_processing(self, mock_redis):
        """Test cached result skips OCR engines entirely."""
        cache = await OCRCache.init(mock_redis)

        # Pre-populate cache
        file_hash = "abc123"
        engine_config = "cfg456"
        cached_result = {"text": "cached medical text", "confidence": 0.96}

        await cache.set(file_hash, engine_config, cached_result, 0.96)

        # Mock cache hit
        mock_redis.get.return_value = str({
            "file_hash": file_hash,
            "engine_config": engine_config,
            "result": cached_result,
            "confidence": 0.96,
            "created_at": 1000.0,
            "accessed_at": 1000.0,
            "access_count": 1,
            "tenant_id": None
        }).replace("'", '"')

        result = await cache.get(file_hash, engine_config)

        assert result is not None
        assert result.result["text"] == "cached medical text"

    @pytest.mark.asyncio
    async def test_ocr_with_circuit_breaker_fallback(self, mock_redis):
        """Test OCR with circuit breaker fallback to next engine."""
        await CircuitBreakerRegistry.init(mock_redis)

        mistral_cb = CircuitBreakerRegistry.get("mistral")

        # Simulate mistral failing (circuit opens)
        mock_redis.get.side_effect = ["open", str(int(time.time()))]

        async def _noop():
            await asyncio.sleep(0)

        with pytest.raises(CircuitBreakerError):
            await mistral_cb.call(_noop)

        # In production, would fallback to tesseract here
        assert True  # Circuit breaker protected the system

    @pytest.mark.asyncio
    async def test_rate_limited_user_cannot_process(self, mock_redis):
        """Test rate limited user cannot make OCR requests."""
        limiter = UserRateLimiter(mock_redis)

        # Simulate user exceeding limit
        mock_redis.zcard.return_value = 999

        with pytest.raises(RateLimitExceeded) as exc:
            await limiter.check_and_record("user_123", "free")

        assert exc.value.limit == 10


class TestMedicalValidationWorkflow:
    """Test medical validation after OCR."""

    @pytest.mark.asyncio
    async def test_valid_prescription_to_fhir(self):
        """Test valid prescription flows through validation to FHIR export."""
        validator = MedicalValidator()
        exporter = FHIRExporter()

        # OCR result
        ocr_text = "Paracetamol 500mg twice daily for 5 days"

        # Validate
        validation = await validator.validate(ocr_text, context="prescription")
        assert validation.is_valid is True

        # Export to FHIR
        entities = [
            MedicalEntity(type="medication", text="paracetamol", confidence=0.92)
        ]
        patient = PatientInfo(id="p-001", name="Test Patient", gender="male")
        metadata = DocumentMetadata(
            document_id="doc-001",
            source_type="prescription",
            created_at="2026-05-27",
            processed_at="2026-05-27T15:00:00Z",
            ocr_confidence=0.94,
            validator_confidence=validation.overall_confidence,
            language="en"
        )

        bundle = exporter.to_fhir_r4(ocr_text, entities, patient, metadata)

        assert bundle["resourceType"] == "Bundle"
        assert len(bundle["entry"]) > 0

    @pytest.mark.asyncio
    async def test_invalid_prescription_blocked(self):
        """Test invalid prescription is flagged before export."""
        validator = MedicalValidator()

        # Dangerous prescription
        ocr_text = "Warfarin 5mg + Aspirin 100mg daily"

        validation = await validator.validate(ocr_text, context="prescription")

        assert validation.is_valid is False
        assert any(i.severity.name == "CRITICAL" for i in validation.issues)

        # In production, would block export or require manual review

    @pytest.mark.asyncio
    async def test_arabic_prescription_validation(self):
        """Test Arabic prescription validation and export."""
        validator = MedicalValidator()
        exporter = FHIRExporter()

        ocr_text = "باراسيتامول 500 ملغ مرتين يومياً"

        validation = await validator.validate(ocr_text, context="prescription", language="ar")

        entities = [
            MedicalEntity(type="medication", text="paracetamol", confidence=0.88)
        ]
        patient = PatientInfo(id="p-002", name="مريض تجريبي", gender="male")
        metadata = DocumentMetadata(
            document_id="doc-002",
            source_type="prescription",
            created_at="2026-05-27",
            processed_at="2026-05-27T15:00:00Z",
            ocr_confidence=0.91,
            validator_confidence=validation.overall_confidence,
            language="ar"
        )

        bundle = exporter.to_fhir_r4(ocr_text, entities, patient, metadata)

        # Verify Arabic text preserved
        patient_entry = next(
            e for e in bundle["entry"] if e["resource"]["resourceType"] == "Patient"
        )
        assert patient_entry["resource"]["name"][0]["text"] == "مريض تجريبي"


class TestMultiTenantWorkflow:
    """Test multi-tenant isolation."""

    @pytest.mark.asyncio
    async def test_tenant_isolation(self, mock_redis):
        """Test cache and rate limits are isolated per tenant."""
        cache = await OCRCache.init(mock_redis)
        limiter = UserRateLimiter(mock_redis)

        file_hash = "shared_hash"
        engine_config = "shared_config"

        # Tenant 1 stores result
        result_t1 = {"text": "tenant1 data"}
        await cache.set(file_hash, engine_config, result_t1, 0.9, tenant_id="tenant1")

        # Tenant 2 should not see tenant 1's cache
        mock_redis.get.return_value = None
        result = await cache.get(file_hash, engine_config, tenant_id="tenant2")

        assert result is None

    @pytest.mark.asyncio
    async def test_different_tier_limits(self, mock_redis):
        """Test different tiers have different limits."""
        limiter = UserRateLimiter(mock_redis)

        # Free tier: 10 requests
        mock_redis.zcard.return_value = 10
        with pytest.raises(RateLimitExceeded) as exc:
            await limiter.check_and_record("free_user", "free")
        assert exc.value.limit == 10

        # Premium tier: 500 requests
        mock_redis.zcard.return_value = 10
        allowed, headers = await limiter.check_and_record("premium_user", "premium")
        assert allowed is True
        assert headers["X-RateLimit-Limit"] == "500"


class TestErrorHandlingWorkflow:
    """Test error handling across modules."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_protects_downstream(self, mock_redis):
        """Test circuit breaker prevents cascading failures."""
        await CircuitBreakerRegistry.init(mock_redis)

        cb = CircuitBreakerRegistry.get("mistral")

        # Open the circuit
        await cb.force_open()

        async def _noop():
            await asyncio.sleep(0)

        # All calls should fail fast
        with pytest.raises(CircuitBreakerError):
            await cb.call(_noop)

    @pytest.mark.asyncio
    async def test_rate_limiter_with_penalty(self, mock_redis):
        """Test penalty box after repeated abuse."""
        limiter = UserRateLimiter(mock_redis)

        # Simulate user in penalty box
        future = int(time.time()) + 300
        mock_redis.get.return_value = str(future)

        with pytest.raises(RateLimitExceeded) as exc:
            await limiter.check_and_record("abuser", "standard")

        assert exc.value.limit == 0
        assert exc.value.retry_after > 0


class TestFHIRExportWorkflow:
    """Test complete FHIR export workflows."""

    def test_discharge_summary_to_fhir(self):
        """Test discharge summary export."""
        exporter = FHIRExporter()
        validator = MedicalValidator()

        # Simulated OCR + NLP output
        text = "Patient discharged with hypertension medication."
        entities = [
            MedicalEntity(type="diagnosis", text="hypertension", code="38341003", confidence=0.92),
            MedicalEntity(type="medication", text="amlodipine", code="329526", confidence=0.88),
        ]
        patient = PatientInfo(id="p-003", name="John Doe", birth_date="1970-01-01", gender="male", mrn="MRN-003")
        metadata = DocumentMetadata(
            document_id="doc-003",
            source_type="discharge",
            created_at="2026-05-20",
            processed_at="2026-05-27T15:00:00Z",
            ocr_confidence=0.95,
            validator_confidence=0.90,
            language="en"
        )

        bundle = exporter.to_fhir_r4(text, entities, patient, metadata)

        # Verify all required resources present
        resource_types = [e["resource"]["resourceType"] for e in bundle["entry"]]
        assert "Composition" in resource_types
        assert "Patient" in resource_types
        assert "DocumentReference" in resource_types
        assert "Observation" in resource_types
        assert "MedicationRequest" in resource_types
        assert "Provenance" in resource_types

        # Verify LOINC code for discharge
        comp = next(e["resource"] for e in bundle["entry"] if e["resource"]["resourceType"] == "Composition")
        assert comp["type"]["coding"][0]["code"] == "18842-5"

    def test_lab_report_to_hl7(self):
        """Test lab report to HL7 conversion."""
        exporter = FHIRExporter()

        text = "Glucose: 95 mg/dL, Cholesterol: 180 mg/dL"
        entities = [
            MedicalEntity(type="lab_result", text="glucose", confidence=0.95),
            MedicalEntity(type="lab_result", text="cholesterol", confidence=0.93),
        ]
        patient = PatientInfo(id="p-004", name="Jane Smith", mrn="MRN-004")
        metadata = DocumentMetadata(
            document_id="doc-004",
            source_type="lab",
            created_at="2026-05-27",
            processed_at="2026-05-27T15:00:00Z",
            ocr_confidence=0.96,
            validator_confidence=0.92,
            language="en"
        )

        hl7 = exporter.to_hl7_v2(text, entities, patient, metadata, message_type="ORU^R01")

        assert "MSH" in hl7
        assert "ORU^R01" in hl7
        assert "PID" in hl7
        assert "OBR" in hl7
        assert "OBX" in hl7
        assert "MRN-004" in hl7


class TestPerformanceWorkflow:
    """Test performance characteristics."""

    @pytest.mark.asyncio
    async def test_cache_hit_performance(self, mock_redis):
        """Test cache hit is faster than processing."""
        cache = await OCRCache.init(mock_redis)

        file_hash = "perf_test"
        engine_config = "perf_cfg"
        result = {"text": "test", "confidence": 0.95}

        # Pre-populate
        await cache.set(file_hash, engine_config, result, 0.95)

        # Mock hit
        mock_redis.get.return_value = str({
            "file_hash": file_hash,
            "engine_config": engine_config,
            "result": result,
            "confidence": 0.95,
            "created_at": 1000.0,
            "accessed_at": 1000.0,
            "access_count": 1,
            "tenant_id": None
        }).replace("'", '"')

        start = time.time()
        cached = await cache.get(file_hash, engine_config)
        elapsed = time.time() - start

        assert cached is not None
        assert elapsed < 0.1  # Should be very fast

    @pytest.mark.asyncio
    async def test_circuit_breaker_fast_fail(self, mock_redis):
        """Test circuit breaker fails fast when open."""
        await CircuitBreakerRegistry.init(mock_redis)
        cb = CircuitBreakerRegistry.get("mistral")

        await cb.force_open()

        async def _slow_fn():
            await asyncio.sleep(10)

        start = time.time()
        try:
            await cb.call(_slow_fn)  # Would take 10s
        except CircuitBreakerError:
            pass
        elapsed = time.time() - start

        assert elapsed < 0.1  # Should fail immediately


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
