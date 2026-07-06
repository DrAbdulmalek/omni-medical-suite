# app.py
"""
Omni Medical OCR — Hugging Face Space
Complete Arabic Medical Text Extraction Pipeline.

Pipeline: Upload → Preprocess → OCR Ensemble → Auto-Correct → NER → Display/Export

Engines: PaddleOCR (primary) + Tesseract (secondary) + EasyOCR (optional)
"""
import json
import os
import re
import time
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
import gradio as gr
from PIL import Image

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────────────────────
ENABLE_LLM = os.getenv("ENABLE_LLM", "false").lower() == "true"
START_TIME = time.time()

# ── OCR Engines Initialization ──────────────────────────────────────────────
logger.info("Initializing OCR engines...")

# PaddleOCR (primary)
paddle_ocr = None
try:
    from paddleocr import PaddleOCR
    paddle_ocr = PaddleOCR(
        use_angle_cls=True,
        lang="ar",
        show_log=False,
        use_gpu=False,
        det_db_thresh=0.3,
        det_db_box_thresh=0.5,
        det_db_unclip_ratio=1.6,
        max_text_length=800,
        use_mp=True,
    )
    logger.info("PaddleOCR initialized successfully")
except Exception as e:
    logger.error(f"PaddleOCR init failed: {e}")

# Tesseract (secondary)
HAS_TESSERACT = False
try:
    import pytesseract
    pytesseract.get_tesseract_version()
    HAS_TESSERACT = True
    logger.info("Tesseract initialized successfully")
except Exception as e:
    logger.warning(f"Tesseract not available: {e}")

# ── Medical Dictionary ──────────────────────────────────────────────────────
MEDICAL_TERMS = {
    # أدوية (Medications)
    "باراسيتامول": "paracetamol", "ايبوبروفين": "ibuprofen", "اموكسيسيلين": "amoxicillin",
    "اموكسيل": "amoxil", "ازيثرومايسين": "azithromycin", "سيفالكسين": "cephalexin",
    "ميترونيدازول": "metronidazole", "اوجمنتين": "augmentin", "زيثروماكس": "zithromax",
    "بنادول": "panadol", "ادفيل": "advil", "بروفيند": "profen", "فلاميكس": "flamex",
    "نوفافين": "novafen", "كاتافلام": "cataflam", "فولتارين": "voltaren",
    "ديكلوفيناك": "diclofenac", "نابروكسين": "naproxen", "سيليبريكس": "celebrex",
    "ميفيناميك": "mefenamic", "اونديسيترون": "ondansetron", "ميتوكلوبراميد": "metoclopramide",
    "اوميبرازول": "omeprazole", "بانتوبرازول": "pantoprazole", "رانيتيدين": "ranitidine",
    "فاموتيدين": "famotidine", "انتاسيد": "antacid", "مالوكس": "maalox",
    "اموكسيسيللاف": "amoxiclav", "سيفترياكسون": "ceftriaxone", "سيفيكسيم": "cefixime",
    "دوكسيسيكلين": "doxycycline", "سيبروفلوكساسين": "ciprofloxacin",
    "لوفلوكساسين": "levofloxacin", "ازيثرومايسين": "azithromycin",
    "كلاريثرومايسين": "clarithromycin", "سالبوتامول": "salbutamol",
    "فلوتيكازون": "fluticasone", "بوديسونيد": "budesonide", "مونتيلوكاست": "montelukast",
    "لوراتادين": "loratadine", "سيتريزين": "cetirizine", "فيكسوفينادين": "fexofenadine",
    "انالجين": "analgin", "نوفالجين": "novalgin", "ديبيرون": "dipyrone",
    "ترامادول": "tramadol", "كوديين": "codeine", "مورفين": "morphine",
    "امبول": "ampoule", "كبسولة": "capsule", "قرص": "tablet", "ملعقة": "spoon",
    "مللي": "ml", "ملigram": "mg", "جرام": "gram",
    # أمراض (Diseases)
    "سكري": "diabetes", "ضغط": "hypertension", "ربو": "asthma",
    "التهاب": "inflammation", "حساسية": "allergy", "قرحة": "ulcer",
    "التهاب رئوي": "pneumonia", "التهاب شعبي": "bronchitis",
    "التهاب مفاصل": "arthritis", "التهاب جيوب": "sinusitis",
    "ارتفاع ضغط": "hypertension", "انخفاض ضغط": "hypotension",
    "سرطان": "cancer", "ورم": "tumor",
    # أعراض (Symptoms)
    "صداع": "headache", "حمى": "fever", "سعال": "cough",
    "الم": "pain", "غثيان": "nausea", "اقياء": "vomiting",
    "اسهال": "diarrhea", "امساك": "constipation", "دوار": "dizziness",
    "تعب": "fatigue", "ضيق تنفس": "shortness of breath",
    "الم بطن": "abdominal pain", "الم حلق": "sore throat",
    "الم ظهر": "back pain", "الم مفاصل": "joint pain",
    # أجسام وتحاليل (Body / Labs)
    "دم": "blood", "بول": "urine", "هيموغلوبين": "hemoglobin",
    "سكر الدم": "blood sugar", "ضغط الدم": "blood pressure",
    "معدل نبض": "heart rate", "درجة حرارة": "temperature",
    "كريات دم بيضاء": "WBC", "كريات دم حمراء": "RBC",
    "صفيحات": "platelets", "كرياتينين": "creatinine",
    "يوريا": "urea", "الكوليسترول": "cholesterol",
    "كولسترول": "cholesterol", "دهون ثلاثية": "triglycerides",
    "انزيمات كبد": "liver enzymes", "SGOT": "AST", "SGPT": "ALT",
    # أماكن الجسم
    "رأس": "head", "صدر": "chest", "بطن": "abdomen",
    "ظهر": "back", "رقبة": "neck", "كتف": "shoulder",
    "ركبة": "knee", "مفصل": "joint", "عضلة": "muscle",
    "حلق": "throat", "اذن": "ear", "عين": "eye",
    "جلد": "skin", "اسنان": "teeth",
}

# OCR common misrecognition patterns for Arabic medical text
OCR_CORRECTIONS = {
    # PaddleOCR/Tesseract common errors in Arabic
    "باراسيتبمول": "باراسيتامول",
    "باراسيتامول ": "باراسيتامول",
    "ايبوروفين": "ايبوبروفين",
    "ايبورفين": "ايبوبروفين",
    "اموكسيستلين": "اموكسيسيلين",
    "اموكسيسلين": "اموكسيسيلين",
    "سيفالكسين ": "سيفالكسين",
    "ازيثروميسين": "ازيثرومايسين",
    "ازثيرومايسين": "ازيثرومايسين",
    "ميتروندازول": "ميترونيدازول",
    "ديكلوفيناك ": "ديكلوفيناك",
    "اوجمينتين": "اوجمنتين",
    "اوميبرازول ": "اوميبرازول",
    "فاموتيدين ": "فاموتيدين",
    "مونتيلوكاست ": "مونتيلوكاست",
    "لوراتادين ": "لوراتادين",
    "فيكسوفينادين ": "فيكسوفينادين",
    "سيليبريكس ": "سيليبريكس",
    "ترامادول ": "ترامادول",
    "ميفيناميك ": "ميفيناميك",
    "كاتافلام ": "كاتافلام",
    "نوفافين ": "نوفافين",
    "فلاميكس ": "فلاميكس",
    "بنادول ": "بنادول",
    "ادفيل ": "ادفيل",
    "كبسول ": "كبسولة",
    "كبسولة ": "كبسولة",
    "قرص ": "قرص",
    "ملعق ": "ملعقة",
    "ميغ": "ملigram",
    "مغ": "ملigram",
    "مليمتر": "مللي",
    "م.ل": "مللي",
    "حبوب": "حبوب",
    # Common number confusions
    "O": "0", "l": "1", "I": "1",
}

# ── Image Preprocessing ─────────────────────────────────────────────────────

def preprocess_image(image: np.ndarray) -> Tuple[np.ndarray, Dict[str, str]]:
    """
    Advanced medical document preprocessing pipeline.
    Returns: (processed_image, processing_log)
    """
    log = {}
    steps = []

    if image is None:
        return image, {"error": "No image provided"}

    try:
        # Convert to BGR if RGB
        if len(image.shape) == 3 and image.shape[2] == 3:
            img = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        else:
            img = image.copy()

        original_shape = img.shape
        steps.append(f"الأبعاد الأصلية: {original_shape[1]}×{original_shape[0]}")

        # 1. Convert to grayscale
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            gray = img.copy()

        # 2. Shadow removal using morphological operations
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
        shadow = cv2.morphologyEx(gray, cv2.MORPH_CLOSE, kernel)
        normalized = cv2.divide(gray, shadow, scale=255)
        steps.append("إزالة الظلال")

        # 3. Denoising
        denoised = cv2.fastNlMeansDenoising(normalized, h=10)
        steps.append("إزالة الضوضاء")

        # 4. CLAHE (Contrast Limited Adaptive Histogram Equalization)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(denoised)
        steps.append("تحسين التباين (CLAHE)")

        # 5. Adaptive binarization
        binary = cv2.adaptiveThreshold(
            enhanced, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            31, 10
        )
        steps.append("ثنائية الألوان")

        # 6. Deskew using Hough transform
        coords = np.column_stack(np.where(binary > 0))
        if len(coords) > 100:
            angle = cv2.minAreaRect(coords)[-1]
            if angle < -45:
                angle = -(90 + angle)
            else:
                angle = -angle
            if abs(angle) > 0.5:
                (h, w) = binary.shape
                center = (w // 2, h // 2)
                M = cv2.getRotationMatrix2D(center, angle, 1.0)
                binary = cv2.warpAffine(
                    binary, M, (w, h),
                    flags=cv2.INTER_CUBIC,
                    borderMode=cv2.BORDER_REPLICATE
                )
                steps.append(f"تصحيح الميل: {angle:.1f}°")

        # 7. Slight sharpening
        kernel_sharp = np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]])
        sharpened = cv2.filter2D(binary, -1, kernel_sharp)
        steps.append("الحدة")

        # Convert back to RGB for Gradio display
        result = cv2.cvtColor(sharpened, cv2.COLOR_GRAY2RGB)

        log["steps"] = steps
        log["steps_count"] = len(steps)
        log["status"] = "success"

        return result, log

    except Exception as e:
        logger.error(f"Preprocessing error: {e}", exc_info=True)
        log["error"] = str(e)
        log["status"] = "partial"
        return image, log


# ── OCR Engines ──────────────────────────────────────────────────────────────

def run_paddle_ocr(image: np.ndarray) -> Tuple[str, List[Dict]]:
    """Run PaddleOCR and return (text, detailed_results)."""
    if paddle_ocr is None:
        return "", []

    try:
        # Convert RGB to BGR for PaddleOCR
        if len(image.shape) == 3 and image.shape[2] == 3:
            img_bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        else:
            img_bgr = image

        result = paddle_ocr.ocr(img_bgr, cls=True)

        lines = []
        details = []

        if result and result[0]:
            for idx, line in enumerate(result[0]):
                box = line[0]
                text = line[1][0]
                confidence = line[1][1]

                # Clean text
                text = text.strip()
                if text:
                    lines.append(text)
                    details.append({
                        "line": idx + 1,
                        "text": text,
                        "confidence": round(float(confidence), 4),
                        "bbox": [[round(p[0], 1), round(p[1], 1)] for p in box]
                    })

        full_text = "\n".join(lines)
        return full_text, details

    except Exception as e:
        logger.error(f"PaddleOCR error: {e}")
        return f"[PaddleOCR Error: {str(e)}]", []


def run_tesseract(image: np.ndarray) -> Tuple[str, float]:
    """Run Tesseract OCR and return (text, avg_confidence)."""
    if not HAS_TESSERACT:
        return "", 0.0

    try:
        # Convert to grayscale for better results
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        else:
            gray = image

        # Run with Arabic + English
        text = pytesseract.image_to_string(gray, lang="ara+eng", config="--psm 6")

        # Get confidence data
        try:
            data = pytesseract.image_to_data(gray, lang="ara+eng", output_type=pytesseract.Output.DICT)
            confs = [int(c) for c in data["conf"] if int(c) > 0]
            avg_conf = sum(confs) / len(confs) if confs else 0.0
        except Exception:
            avg_conf = 0.0

        return text.strip(), round(avg_conf, 2)

    except Exception as e:
        logger.error(f"Tesseract error: {e}")
        return f"[Tesseract Error: {str(e)}]", 0.0


# ── Text Post-Processing ────────────────────────────────────────────────────

def correct_ocr_text(text: str) -> Tuple[str, List[Dict]]:
    """
    Auto-correct OCR output using medical dictionary + pattern rules.
    Returns: (corrected_text, list_of_corrections)
    """
    if not text or not text.strip():
        return text, []

    corrections = []
    corrected = text

    # 1. Apply OCR misrecognition corrections
    for wrong, right in OCR_CORRECTIONS.items():
        if wrong in corrected:
            count = corrected.count(wrong)
            corrected = corrected.replace(wrong, right)
            corrections.append({
                "type": "ocr_correction",
                "from": wrong,
                "to": right,
                "count": count
            })

    # 2. Normalize whitespace
    original = corrected
    corrected = re.sub(r'[ \t]+', ' ', corrected)
    corrected = re.sub(r'\n{3,}', '\n\n', corrected)
    corrected = corrected.strip()
    if original != corrected:
        corrections.append({
            "type": "whitespace",
            "description": "تطبيع المسافات والأسطر الفارغة"
        })

    # 3. Remove non-Arabic/non-useful characters artifacts
    original = corrected
    corrected = re.sub(r'[_]{3,}', '', corrected)
    corrected = re.sub(r'[.]{5,}', '...', corrected)
    if original != corrected:
        corrections.append({
            "type": "artifact_removal",
            "description": "إزالة الرموز الزائدة"
        })

    return corrected, corrections


def extract_ner_entities(text: str) -> Dict[str, List[str]]:
    """
    Extract medical named entities from text using dictionary matching.
    Categories: medications, diseases, symptoms, body_parts, lab_tests
    """
    if not text or not text.strip():
        return {}

    entities = {
        "medications": [],
        "diseases": [],
        "symptoms": [],
        "body_parts": [],
        "lab_tests": [],
        "dosages": [],
    }

    # Dosage pattern: number + unit
    dosage_patterns = [
        r'(\d+(?:\.\d+)?)\s*(?:ملigram|mg|مغ|مللي|مل|جرام|g|حبة|كبسولة|قرص|ملعقة|amp|امبول)',
        r'(\d+(?:\.\d+)?)\s*(?:×|x)\s*(?:يومي|daily|daily|أسبوعي|week)',
    ]
    for pattern in dosage_patterns:
        matches = re.findall(pattern, text)
        entities["dosages"].extend(matches)

    # Dictionary-based entity matching
    for term_ar, term_en in MEDICAL_TERMS.items():
        if term_ar in text:
            # Categorize
            term_lower = term_en.lower()
            if any(kw in term_lower for kw in ["paracetamol", "ibuprofen", "amoxicillin",
                    "cephalexin", "metronidazole", "augmentin", "panadol", "advil",
                    "diclofenac", "naproxen", "celebrex", "omeprazole", "pantoprazole",
                    "ranitidine", "famotidine", "tramadol", "codeine", "morphine",
                    "salbutamol", "fluticasone", "budesonide", "montelukast",
                    "loratadine", "cetirizine", "fexofenadine", "doxycycline",
                    "ciprofloxacin", "levofloxacin", "azithromycin", "clarithromycin",
                    "analgin", "novalgin", "dipyrone", "ondansetron", "metoclopramide",
                    "ceftriaxone", "cefixime", "amoxil", "zithromax", "profen",
                    "flamex", "novafen", "cataflam", "voltaren", "antacid", "maalox",
                    "amoxiclav"]):
                entities["medications"].append(f"{term_ar} ({term_en})")
            elif any(kw in term_lower for kw in ["diabetes", "hypertension", "asthma",
                    "inflammation", "allergy", "ulcer", "pneumonia", "bronchitis",
                    "arthritis", "sinusitis", "cancer", "tumor"]):
                entities["diseases"].append(f"{term_ar} ({term_en})")
            elif any(kw in term_lower for kw in ["headache", "fever", "cough", "pain",
                    "nausea", "vomiting", "diarrhea", "constipation", "dizziness",
                    "fatigue", "shortness", "abdominal", "sore", "back", "joint"]):
                entities["symptoms"].append(f"{term_ar} ({term_en})")
            elif any(kw in term_lower for kw in ["blood", "urine", "hemoglobin",
                    "sugar", "pressure", "heart", "temperature", "wbc", "rbc",
                    "platelets", "creatinine", "urea", "cholesterol", "triglycerides",
                    "liver", "ast", "alt"]):
                entities["lab_tests"].append(f"{term_ar} ({term_en})")
            elif any(kw in term_lower for kw in ["head", "chest", "abdomen", "back",
                    "neck", "shoulder", "knee", "joint", "muscle", "throat", "ear",
                    "eye", "skin", "teeth"]):
                entities["body_parts"].append(f"{term_ar} ({term_en})")

    # Remove duplicates
    for key in entities:
        entities[key] = list(dict.fromkeys(entities[key]))

    # Remove empty categories
    return {k: v for k, v in entities.items() if v}


# ── Ensemble Logic ───────────────────────────────────────────────────────────

def ensemble_vote(paddle_text: str, tesseract_text: str) -> Tuple[str, Dict]:
    """
    Combine results from multiple OCR engines using voting/selection logic.
    Strategy: Prefer PaddleOCR (better for Arabic), use Tesseract as supplement.
    """
    scores = {}

    # Score PaddleOCR
    paddle_score = 0
    if paddle_text and not paddle_text.startswith("["):
        paddle_score = len(paddle_text.strip()) * 2  # Longer text = more content
        scores["PaddleOCR"] = paddle_score

    # Score Tesseract
    tess_score = 0
    if tesseract_text and not tesseract_text.startswith("["):
        tess_score = len(tesseract_text.strip())
        scores["Tesseract"] = tess_score

    if not scores:
        return "", {"strategy": "none", "scores": {}, "winner": "none"}

    # Strategy: PaddleOCR is primary (better Arabic support)
    winner = max(scores, key=scores.get) if scores else "none"

    if winner == "PaddleOCR" and paddle_text:
        final_text = paddle_text
    elif winner == "Tesseract" and tesseract_text:
        final_text = tesseract_text
    else:
        final_text = paddle_text or tesseract_text

    return final_text, {
        "strategy": "PaddleOCR-primary with Tesseract fallback",
        "scores": {k: round(v, 1) for k, v in scores.items()},
        "winner": winner
    }


# ── Main Processing Pipeline ────────────────────────────────────────────────

def process_medical_image(image, enable_preprocess):
    """
    Complete processing pipeline.
    Returns: (cleaned_img, raw_text, corrected_text, ner_json, status)
    """
    if image is None:
        return None, "يرجى رفع صورة طبية أولاً", "", "{}", "⚠️ لم يتم رفع صورة"

    t_start = time.time()
    status_parts = []

    try:
        # Step 1: Preprocessing
        if enable_preprocess:
            cleaned, prep_log = preprocess_image(image)
            status_parts.append(f"✅ المعالجة المسبقة: {prep_log.get('steps_count', 0)} خطوة")
        else:
            cleaned = image
            status_parts.append("⏭️ المعالجة المسبقة: معطلة")

        # Step 2: OCR — run engines in sequence
        paddle_text, paddle_details = run_paddle_ocr(cleaned)
        status_parts.append(f"✅ PaddleOCR: {len(paddle_details)} سطر")

        tesseract_text, tess_conf = run_tesseract(cleaned)
        status_parts.append(f"✅ Tesseract: ثقة {tess_conf:.0f}%")

        # Step 3: Ensemble
        raw_text, vote_info = ensemble_vote(paddle_text, tesseract_text)
        status_parts.append(f"✅ التصويت: الفائز = {vote_info.get('winner', 'N/A')}")

        # Step 4: Auto-correction
        corrected_text, corrections = correct_ocr_text(raw_text)
        status_parts.append(f"✅ التصحيح: {len(corrections)} تعديل")

        # Step 5: NER
        ner_entities = extract_ner_entities(corrected_text)
        entity_count = sum(len(v) for v in ner_entities.values())
        status_parts.append(f"✅ الكيانات: {entity_count} كيان")

        # Timing
        elapsed = time.time() - t_start
        status_parts.append(f"⏱️ الوقت: {elapsed:.1f} ثانية")

        # Build engine comparison
        engine_comparison = {
            "paddleocr": {
                "text_preview": paddle_text[:200] + ("..." if len(paddle_text) > 200 else ""),
                "lines_detected": len(paddle_details),
                "details": paddle_details[:20]
            },
            "tesseract": {
                "text_preview": tesseract_text[:200] + ("..." if len(tesseract_text) > 200 else ""),
                "avg_confidence": tess_conf
            },
            "ensemble": vote_info
        }

        # Build full report
        full_report = {
            "status": "success",
            "preprocessing": {
                "enabled": enable_preprocess,
                "steps": prep_log.get("steps", []) if enable_preprocess else []
            },
            "ocr_engines": engine_comparison,
            "corrections": corrections,
            "ner_entities": ner_entities,
            "statistics": {
                "raw_text_length": len(raw_text),
                "corrected_text_length": len(corrected_text),
                "corrections_count": len(corrections),
                "entity_count": entity_count,
                "processing_time_seconds": round(elapsed, 2)
            }
        }

        status = "\n".join(status_parts)
        return cleaned, raw_text, corrected_text, json.dumps(full_report, ensure_ascii=False, indent=2), status

    except Exception as e:
        logger.error(f"Pipeline error: {e}", exc_info=True)
        return None, f"خطأ: {str(e)}", "", "{}", f"❌ حدث خطأ: {str(e)}"


def export_as_json(raw_text, corrected_text, ner_json):
    """Export results as JSON file."""
    try:
        ner_data = json.loads(ner_json) if ner_json else {}
        export = {
            "timestamp": datetime.now().isoformat(),
            "raw_ocr_text": raw_text,
            "corrected_text": corrected_text,
            "ner_entities": ner_data.get("ner_entities", {}),
            "statistics": ner_data.get("statistics", {})
        }
        output_path = "/tmp/ocr_result.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(export, f, ensure_ascii=False, indent=2)
        return output_path
    except Exception as e:
        logger.error(f"Export error: {e}")
        return None


def export_as_txt(corrected_text):
    """Export corrected text as TXT file."""
    try:
        output_path = "/tmp/ocr_result.txt"
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(corrected_text or "")
        return output_path
    except Exception as e:
        logger.error(f"Export error: {e}")
        return None


def get_system_info():
    """Return system status information."""
    uptime = time.time() - START_TIME
    engines = {
        "PaddleOCR": paddle_ocr is not None,
        "Tesseract": HAS_TESSERACT,
        "LLM (Jais)": ENABLE_LLM and False,  # Not implemented in basic mode
    }
    active = sum(1 for v in engines.values() if v)
    return (
        f"**المحركات النشطة**: {active}/{len(engines)}\n\n"
        f"| المحرك | الحالة |\n|--------|--------|\n"
        + "\n".join(f"| {k} | {'✅ يعمل' if v else '❌ غير متاح'} |" for k, v in engines.items())
        + f"\n\n**وقت التشغيل**: {uptime:.0f} ثانية\n"
        f"**الوضع**: {'GPU (LLM مفعّل)' if ENABLE_LLM else 'CPU (أساسي)'}"
    )


# ── Gradio UI ───────────────────────────────────────────────────────────────

# RTL + Arabic-friendly CSS
custom_css = """
/* RTL Layout */
.gradio-container {
    direction: rtl;
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
}

/* Arabic text display */
.output-text, .output-text textarea {
    direction: rtl;
    text-align: right;
    font-size: 16px !important;
    line-height: 2.2 !important;
    letter-spacing: 0.3px;
}

/* Header styling */
.main-header {
    text-align: center;
    padding: 20px;
    background: linear-gradient(135deg, #1e3a5f 0%, #2d5986 100%);
    color: white;
    border-radius: 12px;
    margin-bottom: 20px;
}

.main-header h1 {
    font-size: 2em;
    margin-bottom: 8px;
}

.main-header p {
    font-size: 1.1em;
    opacity: 0.9;
}

/* Section cards */
.section-card {
    border: 1px solid #e0e0e0;
    border-radius: 8px;
    padding: 16px;
    margin-bottom: 16px;
    background: #fafafa;
}

/* Entity chips */
.entity-chip {
    display: inline-block;
    padding: 4px 12px;
    margin: 3px;
    border-radius: 16px;
    font-size: 13px;
    background: #e8f4fd;
    color: #1565c0;
    border: 1px solid #90caf9;
}

/* Status bar */
.status-bar {
    padding: 12px 16px;
    border-radius: 8px;
    font-size: 14px;
    line-height: 1.8;
    background: #f5f5f5;
    border-right: 4px solid #1565c0;
}

/* Hide Gradio footer */
footer {
    display: none !important;
}

/* Button styles */
.gr-button-primary {
    background: linear-gradient(135deg, #1565c0, #0d47a1) !important;
    border: none !important;
    font-size: 16px !important;
    padding: 12px 32px !important;
}

/* Tab styling */
.tab-nav button {
    font-size: 15px !important;
    padding: 10px 20px !important;
}

/* Code/JSON display */
.json-output pre {
    direction: ltr;
    text-align: left;
    font-size: 12px;
    background: #1e1e1e;
    color: #d4d4d4;
    padding: 16px;
    border-radius: 8px;
    max-height: 500px;
    overflow: auto;
}
"""

with gr.Blocks(
    title="Omni Medical OCR — نظام استخراج النصوص الطبية العربية",
    theme=gr.themes.Soft(
        primary_hue="indigo",
        secondary_hue="blue",
        neutral_hue="slate",
        font=gr.themes.GoogleFont("Cairo"),
    ),
    css=custom_css,
) as demo:

    # ── Header ───────────────────────────────────────────────────────────
    gr.HTML("""
    <div class="main-header">
        <h1>🏥 Omni Medical OCR</h1>
        <p>نظام متكامل لاستخراج وتصحيح النصوص الطبية العربية باستخدام الذكاء الاصطناعي</p>
        <p style="font-size: 0.85em; opacity: 0.8; margin-top: 8px;">
            رفع صورة ← تنظيف ← OCR متعدد المحركات ← تصحيح ← استخراج كيانات ← تصدير
        </p>
    </div>
    """)

    # ── Input Section ────────────────────────────────────────────────────
    with gr.Row():
        with gr.Column(scale=3):
            input_image = gr.Image(
                type="numpy",
                label="📤 رفع صورة طبية (وصفة طبية، تقرير مخبري، تقرير طبي)",
                height=350,
            )
        with gr.Column(scale=1):
            enable_preprocess = gr.Checkbox(
                label="🔧 تفعيل المعالجة المسبقة (تنظيف + تحسين)",
                value=True,
            )
            process_btn = gr.Button(
                "🚀 معالجة كاملة",
                variant="primary",
                size="lg",
            )
            sys_info_btn = gr.Button("ℹ️ معلومات النظام", variant="secondary")

    # ── Results Tabs ────────────────────────────────────────────────────
    with gr.Tabs():
        # Tab 1: Main Results
        with gr.Tab("📋 النتائج الرئيسية"):
            with gr.Row():
                with gr.Column(scale=1):
                    cleaned_img = gr.Image(label="🖼️ الصورة بعد المعالجة", height=350)
                with gr.Column(scale=2):
                    raw_ocr = gr.Textbox(
                        label="📝 النص الخام من OCR",
                        lines=6,
                        show_copy_button=True,
                        elem_classes=["output-text"],
                    )
                    corrected_text = gr.Textbox(
                        label="✅ النص المصحح",
                        lines=6,
                        show_copy_button=True,
                        elem_classes=["output-text"],
                    )

        # Tab 2: NER Entities
        with gr.Tab("🔍 الكيانات الطبية (NER)"):
            ner_display = gr.JSON(label="الكيانات المستخرجة")

        # Tab 3: Technical Report
        with gr.Tab("📊 التقرير التقني"):
            full_report = gr.Code(
                label="التقرير الكامل (JSON)",
                language="json",
                interactive=False,
            )

    # ── Status Bar ──────────────────────────────────────────────────────
    status_output = gr.Textbox(
        label="📈 سجل المعالجة",
        lines=4,
        interactive=False,
        elem_classes=["status-bar"],
    )

    # ── Export Section ──────────────────────────────────────────────────
    with gr.Row():
        export_json_btn = gr.Button("📄 تصدير JSON", variant="secondary")
        export_txt_btn = gr.Button("📝 تصدير TXT", variant="secondary")
        json_file = gr.File(label="ملف JSON", visible=True)
        txt_file = gr.File(label="ملف TXT", visible=True)

    # ── System Info Modal ───────────────────────────────────────────────
    sys_info_output = gr.Textbox(
        label="معلومات النظام",
        visible=False,
        interactive=False,
    )

    # ── Events ──────────────────────────────────────────────────────────
    process_btn.click(
        fn=process_medical_image,
        inputs=[input_image, enable_preprocess],
        outputs=[cleaned_img, raw_ocr, corrected_text, full_report, status_output],
    )

    sys_info_btn.click(
        fn=get_system_info,
        outputs=[sys_info_output],
    )

    export_json_btn.click(
        fn=export_as_json,
        inputs=[raw_ocr, corrected_text, full_report],
        outputs=[json_file],
    )

    export_txt_btn.click(
        fn=export_as_txt,
        inputs=[corrected_text],
        outputs=[txt_file],
    )


# ── Launch ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logger.info("Starting Omni Medical OCR Space on port 7860")
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        show_error=True,
    )