import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT / "hf-space"))  # AHW-02G fix: append (not insert) — inserting hf-space first shadowed canonical packages.core with the hf-space copy (no router_executor) and would run E3 against the unpatched mistral_integration
import app_core

def test_tramadol_dose_separator_preserved():
    out, _ = app_core._auto_correct_ocr("ترامادول 0.5 mg")
    assert out == "ترامادول 0.5 mg"

def test_medical_negation_and_dose_preserved():
    text = "لا يعطى ترامادول 0.5 mg"
    out, _ = app_core._auto_correct_ocr(text)
    assert out == text

def test_decimals_preserved():
    for text in ["0.5", "1.25", "0.75", "٠٫٥", "١٫٢٥"]:
        out, _ = app_core._auto_correct_ocr(text)
        assert out == text

def test_negations_preserved():
    for text in ["لا", "ليس", "لم", "لن", "غير", "بدون", "لا يوجد سكري"]:
        out, _ = app_core._auto_correct_ocr(text)
        assert out == text

def test_intended_ocr_correction_remains():
    out, _ = app_core._auto_correct_ocr("باراسيتبمول 500 mg")
    assert out == "باراسيتامول 500 mg"
