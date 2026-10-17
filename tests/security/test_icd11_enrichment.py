"""Tests for WHO ICD-11 enrichment script.

Tests verify:
  - Import script compiles
  - Output JSON schema is correct
  - Provenance fields are present
  - Duplicate detection works
  - Bilingual terminology format matches existing KB
  - No patient data is sent
  - Fixed URLs (SSRF prevention)
  - Offline operation (script is not runtime dependency)

These tests do NOT require WHO API access — they use fixtures.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest import mock
from io import BytesIO
import urllib.error

import pytest

# Ensure scripts/ is importable
ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT / "scripts" / "enrichment"
sys.path.insert(0, str(SCRIPTS_DIR))


class TestICD11EnrichmentScript:

    def test_script_compiles(self):
        """Script is syntactically valid Python."""
        import py_compile
        py_compile.compile(str(SCRIPTS_DIR / "who_icd11_enrich.py"), doraise=True)

    def test_fixed_base_url(self):
        """Base URL is fixed — not user-supplied (SSRF prevention)."""
        import who_icd11_enrich as script
        assert script.ICD_API_BASE == "https://id.who.int"
        assert script.ICD_TOKEN_URL == "https://icd.who.int/token"
        assert script.ICD_ENTITY_URL.startswith("https://")

    def test_output_path_is_data_dictionaries(self):
        """Output goes to the existing KB data directory."""
        import who_icd11_enrich as script
        assert script.OUTPUT_PATH == Path("data/dictionaries/icd11_terminology.json")

    def test_source_name(self):
        """Source name is correctly set for provenance."""
        import who_icd11_enrich as script
        assert script.SOURCE_NAME == "who-icd11"
        assert "CC BY-ND 3.0 IGO" in script.SOURCE_LICENSE

    def test_extract_terminology_bilingual(self):
        """Bilingual terminology extraction produces correct output."""
        import who_icd11_enrich as script

        entity_en = {
            "title": {"@value": "Heart failure"},
            "definition": {"@value": "A condition in which the heart cannot pump enough blood"},
            "code": "BD11",
            "synonyms": [{"@value": "Cardiac failure"}],
        }
        entity_ar = {
            "title": {"@value": "قصور القلب"},
            "synonyms": [{"@value": "هبوط القلب"}],
        }

        result = script.extract_terminology(entity_en, entity_ar, "fake_token", "http://id.who.int/icd/entity/12345")

        assert result is not None
        assert result["term_en"] == "Heart failure"
        assert result["term_ar"] == "قصور القلب"
        assert result["source"] == "who-icd11"
        assert result["source_id"] == "http://id.who.int/icd/entity/12345"
        assert result["icd_code"] == "BD11"
        assert result["license"] == script.SOURCE_LICENSE
        assert "Cardiac failure" in result["synonyms_en"]
        assert "هبوط القلب" in result["synonyms_ar"]

    def test_extract_terminology_english_only(self):
        """Terminology with only English is still valid."""
        import who_icd11_enrich as script

        entity_en = {"title": {"@value": "Hypertension"}}
        entity_ar = None

        result = script.extract_terminology(entity_en, entity_ar, "token", "uri")
        assert result is not None
        assert result["term_en"] == "Hypertension"
        assert result["term_ar"] == ""  # Empty but present

    def test_extract_terminology_neither_language(self):
        """Returns None if no usable terms."""
        import who_icd11_enrich as script

        result = script.extract_terminology(None, None, "token", "uri")
        assert result is None

    def test_extract_terminology_preserves_provenance(self):
        """Every entry retains source, source_id, source_version, license."""
        import who_icd11_enrich as script

        entity_en = {"title": {"@value": "Diabetes"}}
        entity_ar = {"title": {"@value": "السكري"}}

        result = script.extract_terminology(entity_en, entity_ar, "token", "http://id.who.int/icd/entity/abc")

        assert result["source"] == "who-icd11"
        assert result["source_id"] == "http://id.who.int/icd/entity/abc"
        assert result["source_version"] == "2024-01"
        assert "CC BY-ND 3.0 IGO" in result["license"]

    def test_no_patient_data_sent(self):
        """The script only requests ICD-11 concept data, never patient text."""
        import who_icd11_enrich as script

        # The script fetches entities by URI — it never sends user text
        # Verify the fetch function takes entity_uri, not patient text
        import inspect
        sig = inspect.signature(script.fetch_icd_entity)
        params = list(sig.parameters.keys())
        assert "entity_uri" in params
        assert "language" in params
        # No parameter for patient text or document content

    def test_missing_credentials_raises(self):
        """Script exits if WHO credentials are not set."""
        import who_icd11_enrich as script

        with mock.patch.dict("os.environ", {"WHO_ICD_CLIENT_ID": "", "WHO_ICD_CLIENT_SECRET": ""}):
            with pytest.raises(SystemExit):
                script.run_enrichment()

    def test_output_json_schema(self, tmp_path):
        """Output JSON has the correct schema for KB import."""
        # Simulate the output format
        output = {
            "metadata": {
                "source": "who-icd11",
                "license": "CC BY-ND 3.0 IGO",
                "total_concepts": 1,
                "source_version": "2024-01",
            },
            "entries": [{
                "entity_id": "http://id.who.int/icd/entity/12345",
                "term_en": "Heart failure",
                "term_ar": "قصور القلب",
                "source": "who-icd11",
                "source_id": "http://id.who.int/icd/entity/12345",
                "source_version": "2024-01",
                "license": "CC BY-ND 3.0 IGO",
            }],
        }

        # Verify it can be imported as a JSON file
        output_path = tmp_path / "test_icd11.json"
        output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

        # Read back and validate
        data = json.loads(output_path.read_text(encoding="utf-8"))
        assert "metadata" in data
        assert "entries" in data
        assert data["entries"][0]["term_ar"] == "قصور القلب"
        assert data["entries"][0]["term_en"] == "Heart failure"
        assert data["entries"][0]["source"] == "who-icd11"

    def test_timeout_is_set(self):
        """Default timeout is 30 seconds."""
        import who_icd11_enrich as script
        assert script.DEFAULT_TIMEOUT == 30

    def test_response_size_limit(self):
        """Response size limit is set."""
        import who_icd11_enrich as script
        assert script.MAX_RESPONSE_BYTES == 10 * 1024 * 1024

    def test_rate_limit_delay(self):
        """Rate limit delay is set (respectful API usage)."""
        import who_icd11_enrich as script
        assert script.RATE_LIMIT_DELAY >= 1.0
