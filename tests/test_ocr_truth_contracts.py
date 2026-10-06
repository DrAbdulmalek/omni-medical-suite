from packages.ocr_contracts.confidence import ConfidenceEvidence, combine_calibrated
from packages.ocr_contracts.normalization import normalize_for_matching, preserve_reference
from packages.ocr_contracts.training import ReviewStatus, validate_training_sample


def test_reference_is_verbatim():
    ref = "صيدلية ة ١٢٠"
    assert preserve_reference(ref) == ref


def test_normalization_is_derived_view_only():
    raw = "صيدلية ١٢٠"
    view, policy = normalize_for_matching(raw)
    assert view == "صيدلية 120"
    assert raw == "صيدلية ١٢٠"
    assert policy["version"] == "normalize_v1/1.0.0"


def test_cross_engine_raw_confidence_is_not_aggregated():
    evidence = [
        ConfidenceEvidence("tesseract", .91, "native", "word", None),
        ConfidenceEvidence("surya", .87, "native", "token", None),
    ]
    assert combine_calibrated(evidence) is None


def test_calibrated_confidence_can_be_combined():
    evidence = [
        ConfidenceEvidence("tesseract", .91, "probability", "word", "cal-v1"),
        ConfidenceEvidence("surya", .87, "probability", "token", "cal-v1"),
    ]
    assert combine_calibrated(evidence) == .89


def test_approved_training_sample_requires_reviewer():
    row = {
        "incorrect_ocr_output": "المريض",
        "correct_text": "المريض",
        "category": "medical",
        "content_hash": "abc",
        "review_status": ReviewStatus.APPROVED.value,
        "provenance": {},
    }
    try:
        validate_training_sample(row)
    except ValueError as exc:
        assert "reviewer" in str(exc)
    else:
        raise AssertionError("approval without reviewer must fail")
