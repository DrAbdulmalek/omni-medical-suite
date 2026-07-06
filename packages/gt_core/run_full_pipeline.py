#!/usr/bin/env python3
"""
run_full_pipeline.py — Fully Automated Ground Truth + OCR Training Pipeline
=============================================================================
One-command pipeline that executes the complete workflow:
    Import GT (ABBYY/ReadIRIS/PDF) → Extract Fonts → Run OCR →
    Compare → Font Validate → Export → Report

Author: Dr. Abdulmalek
Version: 1.0.0
Date: 2026-06-04

Usage:
    # Full pipeline (recommended)
    python run_full_pipeline.py \
        --abbyy "page_588_abbyy.docx" \
        --readiris "page_588_readiris.rtf" \
        --pdf "page_588.pdf" \
        --image "Scanned Document-588.jpg" \
        --output-dir "pipeline_output_588"

    # Quick mode (ABBYY + Image only)
    python run_full_pipeline.py \
        --abbyy "abbyy.docx" \
        --image "document.jpg" \
        --quick

    # Skip OCR (use existing results)
    python run_full_pipeline.py \
        --abbyy "abbyy.docx" \
        --ocr "ocr_result.json" \
        --skip-ocr

    # With postprocessing patch
    python run_full_pipeline.py \
        --abbyy "abbyy.docx" \
        --image "doc.jpg" \
        --patch medical_doc_gui_patch.py \
        --dictionary arabic_medical_dict.json
"""

import json
import os
import sys
import time
import shutil
import argparse
import logging
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


# ============================================================
# Pipeline Step Results
# ============================================================

@dataclass
class StepResult:
    """Result of a single pipeline step."""
    step_name: str
    success: bool
    duration: float
    output_files: List[str]
    message: str
    metrics: Dict = None

    def to_dict(self) -> Dict:
        return asdict(self)


# ============================================================
# Main Pipeline Orchestrator
# ============================================================

class FullPipeline:
    """
    Fully automated OCR Ground Truth + Training pipeline.

    Steps:
        1. Import Ground Truth (ABBYY .docx, ReadIRIS .rtf, PDF, or manual .txt)
        2. Extract Font Data (from PDF via PDF Grabber format)
        3. Run OCR (PaddleOCR / EasyOCR / Tesseract)
        4. Apply Postprocessor Patch (medical_doc_gui_patch)
        5. Compare OCR with GT (CER/WER/Medical Accuracy)
        6. Font Glyph Validation
        7. Export (merged dictionary + training pairs)
        8. Generate Final Report
    """

    def __init__(self, config: Dict):
        self.config = config
        self.output_dir = Path(config.get("output_dir", "pipeline_output"))
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.results: List[StepResult] = []
        self.start_time = time.time()
        self.log_lines: List[str] = []

        # File paths
        self.ground_truth_txt = self.output_dir / "ground_truth.txt"
        self.ground_truth_json = self.output_dir / "ground_truth.json"
        self.fonts_json = self.output_dir / "fonts.json"
        self.ocr_result_json = self.output_dir / "ocr_result.json"
        self.ocr_patched_json = self.output_dir / "ocr_result_patched.json"
        self.comparison_report = self.output_dir / "comparison_report.json"
        self.auto_dictionary = self.output_dir / "auto_dictionary.json"
        self.training_pairs = self.output_dir / "training_pairs.json"
        self.font_validated_txt = self.output_dir / "ocr_font_validated.txt"
        self.merged_dictionary = self.output_dir / "merged_dictionary.json"
        self.pipeline_report = self.output_dir / "PIPELINE_REPORT.json"
        self.pipeline_log = self.output_dir / "pipeline.log"

    def _log(self, message: str, level: str = "INFO"):
        """Log to both logger and file."""
        if level == "INFO":
            logger.info(message)
        elif level == "ERROR":
            logger.error(message)
        elif level == "WARNING":
            logger.warning(message)
        elif level == "SUCCESS":
            logger.info(f"  >> {message}")
        self.log_lines.append(f"[{datetime.now().strftime('%H:%M:%S')}] {level}: {message}")

    def run(self) -> Dict:
        """Execute the full pipeline."""
        self._log("=" * 70)
        self._log("FULL OCR GROUND TRUTH + TRAINING PIPELINE")
        self._log(f"Output: {self.output_dir}")
        self._log(f"Mode: {self.config.get('mode', 'full')}")
        self._log("=" * 70)

        # Step 1: Import Ground Truth
        self.step1_import_ground_truth()

        # Step 2: Extract Font Data (optional)
        if self.config.get("pdf"):
            self.step2_extract_fonts()

        # Step 3: Run OCR (unless skip-ocr)
        if not self.config.get("skip_ocr"):
            self.step3_run_ocr()
        else:
            self._log("Skipping OCR step (using existing results)")

        # Step 4: Apply Postprocessor Patch (optional)
        if self.config.get("patch"):
            self.step4_apply_patch()

        # Step 5: Compare with Ground Truth
        self.step5_compare()

        # Step 6: Font Glyph Validation (optional)
        if self.fonts_json.exists() and self.ocr_result_json.exists():
            self.step6_font_validate()

        # Step 7: Export
        self.step7_export()

        # Step 8: Generate Final Report
        self.step8_generate_report()

        # Save log
        with open(self.pipeline_log, 'w', encoding='utf-8') as f:
            f.write('\n'.join(self.log_lines))

        self._log("=" * 70)
        self._log("PIPELINE COMPLETE")
        self._log(f"Total time: {time.time() - self.start_time:.1f}s")
        self._log(f"All outputs in: {self.output_dir}")
        self._log("=" * 70)

        return self._get_summary()

    # -------------------------------------------------------
    # Step 1: Import Ground Truth
    # -------------------------------------------------------
    def step1_import_ground_truth(self):
        """Import ground truth from ABBYY, ReadIRIS, or manual file."""
        step_name = "Import Ground Truth"
        start = time.time()

        gt_sources = []

        # ABBYY (.docx)
        if self.config.get("abbyy"):
            gt_sources.append(("ABBYY (.docx)", self.config["abbyy"]))

        # ReadIRIS (.rtf)
        if self.config.get("readiris"):
            gt_sources.append(("ReadIRIS (.rtf)", self.config["readiris"]))

        # Manual (.txt)
        if self.config.get("manual_gt"):
            gt_sources.append(("Manual (.txt)", self.config["manual_gt"]))

        if not gt_sources:
            self._log("No GT sources provided. Skipping.", "WARNING")
            self.results.append(StepResult(
                step_name=step_name, success=True, duration=0,
                output_files=[], message="No GT sources provided"
            ))
            return

        self._log(f"Importing GT from {len(gt_sources)} source(s)...")

        # Try to use import_ground_truth.py
        importer_script = Path(__file__).parent / "import_ground_truth.py"

        all_entries = []

        for source_name, source_path in gt_sources:
            if not Path(source_path).exists():
                self._log(f"  Source not found: {source_path}", "WARNING")
                continue

            self._log(f"  Importing: {source_name} ({source_path})")

            if importer_script.exists():
                # Use the import script
                try:
                    cmd = [
                        sys.executable, str(importer_script),
                        source_path,
                        "--output", str(self.ground_truth_json),
                        "--format", "json"
                    ]
                    result = subprocess.run(
                        cmd, capture_output=True, text=True, timeout=60
                    )
                    if result.returncode == 0:
                        with open(self.ground_truth_json, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            entries = data.get("entries", [])
                            all_entries.extend(entries)
                        self._log(f"    Imported {len(entries)} entries via script")
                    else:
                        self._log(f"    Script failed: {result.stderr}", "ERROR")
                        # Fallback to manual import
                        entries = self._manual_import(source_path)
                        all_entries.extend(entries)
                except Exception as e:
                    self._log(f"    Script error: {e}. Trying manual import.", "WARNING")
                    entries = self._manual_import(source_path)
                    all_entries.extend(entries)
            else:
                # Manual import (no script available)
                entries = self._manual_import(source_path)
                all_entries.extend(entries)

        # Save combined GT
        if all_entries:
            # Save as text
            lines = [e.get("text", "") if isinstance(e, dict) else str(e)
                     for e in all_entries]
            lines = [l for l in lines if l.strip()]
            with open(self.ground_truth_txt, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines))

            # Save as JSON
            gt_data = {
                "source": "combined",
                "imported_at": datetime.now().isoformat(),
                "total_entries": len(all_entries),
                "sources": [s[0] for s in gt_sources],
                "entries": all_entries
            }
            with open(self.ground_truth_json, 'w', encoding='utf-8') as f:
                json.dump(gt_data, f, ensure_ascii=False, indent=2)

            self._log(f"  Total: {len(all_entries)} lines saved to ground_truth.txt", "SUCCESS")

        duration = time.time() - start
        self.results.append(StepResult(
            step_name=step_name, success=True, duration=duration,
            output_files=[str(self.ground_truth_txt), str(self.ground_truth_json)],
            message=f"Imported {len(all_entries)} lines from {len(gt_sources)} sources",
            metrics={"entries": len(all_entries), "sources": len(gt_sources)}
        ))

    def _manual_import(self, file_path: str) -> List[Dict]:
        """Manual import when the import script is not available."""
        entries = []
        path = Path(file_path)
        suffix = path.suffix.lower()

        try:
            if suffix == '.docx':
                try:
                    from docx import Document
                    doc = Document(str(path))
                    for i, para in enumerate(doc.paragraphs):
                        if para.text.strip():
                            entries.append({"text": para.text.strip(), "source": "abbyy",
                                          "line_number": i, "page_number": 1})
                except ImportError:
                    # Fallback: read as zip and extract text
                    import zipfile
                    with zipfile.ZipFile(str(path), 'r') as z:
                        for name in z.namelist():
                            if name.endswith('.xml') and 'word/document' in name:
                                content = z.read(name).decode('utf-8', errors='ignore')
                                # Simple XML text extraction
                                import re
                                texts = re.findall(r'<w:t[^>]*>([^<]+)</w:t>', content)
                                for i, t in enumerate(texts):
                                    if t.strip():
                                        entries.append({"text": t.strip(), "source": "abbyy",
                                                      "line_number": i, "page_number": 1})
                    self._log("    Used fallback zip extraction for .docx")

            elif suffix == '.rtf':
                content = path.read_text(encoding='utf-8', errors='ignore')
                # Strip RTF control words
                text = re.sub(r'[\\\{\}]', '', content)
                text = re.sub(r'\s+', ' ', text)
                lines = [l.strip() for l in text.split('\n') if l.strip()]
                for i, line in enumerate(lines):
                    entries.append({"text": line, "source": "readiris",
                                  "line_number": i, "page_number": 1})

            elif suffix == '.txt':
                with open(str(path), 'r', encoding='utf-8') as f:
                    for i, line in enumerate(f):
                        if line.strip():
                            entries.append({"text": line.strip(), "source": "manual",
                                          "line_number": i, "page_number": 1})

            elif suffix == '.pdf':
                try:
                    import fitz  # PyMuPDF
                    doc = fitz.open(str(path))
                    for page_num in range(len(doc)):
                        page = doc[page_num]
                        text_dict = page.get_text("dict")
                        for block in text_dict.get("blocks", []):
                            if "lines" in block:
                                for line in block["lines"]:
                                    line_text = "".join(
                                        span["text"] for span in line.get("spans", [])
                                    )
                                    if line_text.strip():
                                        entries.append({
                                            "text": line_text.strip(),
                                            "source": "pdf",
                                            "page_number": page_num + 1,
                                            "line_number": 0
                                        })
                    doc.close()
                except ImportError:
                    # Fallback: pdftotext or pdfplumber
                    try:
                        import pdfplumber
                        with pdfplumber.open(str(path)) as pdf:
                            for page_num, page in enumerate(pdf.pages):
                                text = page.extract_text()
                                if text:
                                    for i, line in enumerate(text.split('\n')):
                                        if line.strip():
                                            entries.append({
                                                "text": line.strip(),
                                                "source": "pdf",
                                                "page_number": page_num + 1,
                                                "line_number": i
                                            })
                    except ImportError:
                        self._log("    No PDF library available. Install PyMuPDF or pdfplumber.", "ERROR")

            self._log(f"    Manual import: {len(entries)} lines")

        except Exception as e:
            self._log(f"    Import error: {e}", "ERROR")

        return entries

    # -------------------------------------------------------
    # Step 2: Extract Font Data
    # -------------------------------------------------------
    def step2_extract_fonts(self):
        """Extract font and glyph data from PDF."""
        step_name = "Extract Font Data"
        start = time.time()

        pdf_path = self.config.get("pdf")
        if not pdf_path or not Path(pdf_path).exists():
            self._log(f"PDF not found: {pdf_path}", "WARNING")
            self.results.append(StepResult(
                step_name=step_name, success=False, duration=time.time() - start,
                output_files=[], message="PDF file not found"
            ))
            return

        self._log(f"Extracting fonts from: {pdf_path}")

        try:
            import fitz  # PyMuPDF
            doc = fitz.open(str(pdf_path))
            font_data = {
                "pdf_file": str(pdf_path),
                "extracted_at": datetime.now().isoformat(),
                "fonts": {},
                "glyphs": []
            }

            total_glyphs = 0
            for page_num in range(len(doc)):
                page = doc[page_num]
                page_fonts = page.get_fonts()

                for font in page_fonts:
                    font_name = font[3] if len(font) > 3 else "unknown"
                    font_type = font[2] if len(font) > 2 else "unknown"
                    if font_name not in font_data["fonts"]:
                        font_data["fonts"][font_name] = {
                            "type": font_type, "pages": []
                        }
                    font_data["fonts"][font_name]["pages"].append(page_num + 1)

                text_dict = page.get_text("dict")
                for block in text_dict.get("blocks", []):
                    if "lines" not in block:
                        continue
                    for line in block["lines"]:
                        for span in line.get("spans", []):
                            for char in span.get("chars", []):
                                font_data["glyphs"].append({
                                    "char": char["c"],
                                    "x": char["origin"][0],
                                    "y": char["origin"][1],
                                    "width": char["bbox"][2] - char["bbox"][0],
                                    "height": char["bbox"][3] - char["bbox"][1],
                                    "font": span["font"],
                                    "size": span["size"],
                                    "page": page_num + 1
                                })
                                total_glyphs += 1

            doc.close()

            with open(self.fonts_json, 'w', encoding='utf-8') as f:
                json.dump(font_data, f, ensure_ascii=False, indent=2)

            self._log(f"  Extracted {len(font_data['fonts'])} fonts, {total_glyphs} glyphs", "SUCCESS")

            self.results.append(StepResult(
                step_name=step_name, success=True, duration=time.time() - start,
                output_files=[str(self.fonts_json)],
                message=f"{len(font_data['fonts'])} fonts, {total_glyphs} glyphs",
                metrics={"fonts": len(font_data['fonts']), "glyphs": total_glyphs}
            ))

        except ImportError:
            self._log("PyMuPDF not installed. Skipping font extraction.", "WARNING")
            self.results.append(StepResult(
                step_name=step_name, success=False, duration=time.time() - start,
                output_files=[], message="PyMuPDF not installed"
            ))
        except Exception as e:
            self._log(f"Font extraction error: {e}", "ERROR")
            self.results.append(StepResult(
                step_name=step_name, success=False, duration=time.time() - start,
                output_files=[], message=str(e)
            ))

    # -------------------------------------------------------
    # Step 3: Run OCR
    # -------------------------------------------------------
    def step3_run_ocr(self):
        """Run OCR on the image with preferred engine."""
        step_name = "Run OCR"
        start = time.time()

        image_path = self.config.get("image")
        if not image_path or not Path(image_path).exists():
            self._log(f"Image not found: {image_path}", "WARNING")
            self.results.append(StepResult(
                step_name=step_name, success=False, duration=time.time() - start,
                output_files=[], message="Image file not found"
            ))
            return

        engine = self.config.get("ocr_engine", "auto")
        self._log(f"Running OCR: engine={engine}, image={image_path}")

        ocr_text = ""
        ocr_confidence = 0.0
        actual_engine = "none"
        ocr_boxes = []

        # Try engines in order of preference for Arabic
        engines_to_try = []
        if engine == "auto":
            engines_to_try = ["paddleocr", "easyocr", "tesseract"]
        else:
            engines_to_try = [engine]

        for eng in engines_to_try:
            try:
                if eng == "paddleocr":
                    ocr_text, ocr_confidence, ocr_boxes = self._run_paddleocr(image_path)
                    actual_engine = "paddleocr"
                    break
                elif eng == "easyocr":
                    ocr_text, ocr_confidence, ocr_boxes = self._run_easyocr(image_path)
                    actual_engine = "easyocr"
                    break
                elif eng == "tesseract":
                    ocr_text, ocr_confidence, ocr_boxes = self._run_tesseract(image_path)
                    actual_engine = "tesseract"
                    break
            except Exception as e:
                self._log(f"  {eng} failed: {e}", "WARNING")
                continue

        if ocr_text:
            # Save result
            ocr_data = {
                "raw_text": ocr_text,
                "language": "ar",
                "engine": actual_engine,
                "confidence": round(ocr_confidence, 4),
                "processing_time": round(time.time() - start, 2),
                "filename": Path(image_path).name,
                "timestamp": datetime.now().isoformat()
            }
            with open(self.ocr_result_json, 'w', encoding='utf-8') as f:
                json.dump(ocr_data, f, ensure_ascii=False, indent=2)

            self._log(f"  OCR complete: {len(ocr_text)} chars, conf={ocr_confidence:.2%}", "SUCCESS")
            self._log(f"  Engine used: {actual_engine}")

            self.results.append(StepResult(
                step_name=step_name, success=True, duration=time.time() - start,
                output_files=[str(self.ocr_result_json)],
                message=f"{len(ocr_text)} chars, {ocr_confidence:.1%} conf",
                metrics={"chars": len(ocr_text), "confidence": ocr_confidence,
                         "engine": actual_engine}
            ))
        else:
            self._log("  All OCR engines failed!", "ERROR")
            self.results.append(StepResult(
                step_name=step_name, success=False, duration=time.time() - start,
                output_files=[], message="All OCR engines failed"
            ))

    def _run_paddleocr(self, image_path: str):
        """Run PaddleOCR with Arabic support."""
        from paddleocr import PaddleOCR
        ocr = PaddleOCR(use_angle_cls=True, lang='ar', show_log=False)
        result = ocr.ocr(image_path, cls=True)

        texts, confidences, boxes = [], [], []
        if result and result[0]:
            for line in result[0]:
                bbox, (text, conf) = line
                texts.append(text)
                confidences.append(conf)
                boxes.append(bbox)

        full_text = '\n'.join(texts)
        avg_conf = sum(confidences) / len(confidences) if confidences else 0
        return full_text, avg_conf, boxes

    def _run_easyocr(self, image_path: str):
        """Run EasyOCR with Arabic support."""
        import easyocr
        reader = easyocr.Reader(['ar', 'en'], gpu=False)
        results = reader.readtext(image_path, detail=1)

        texts, confidences, boxes = [], [], []
        for (bbox, text, conf) in results:
            texts.append(text)
            confidences.append(conf)
            boxes.append(bbox)

        full_text = '\n'.join(texts)
        avg_conf = sum(confidences) / len(confidences) if confidences else 0
        return full_text, avg_conf, boxes

    def _run_tesseract(self, image_path: str):
        """Run Tesseract with Arabic support."""
        import pytesseract
        from PIL import Image

        img = Image.open(image_path)
        data = pytesseract.image_to_data(
            img, lang='ara+eng',
            output_type=pytesseract.Output.DICT
        )

        texts, confidences, boxes = [], [], []
        for i in range(len(data['text'])):
            if int(data['conf'][i]) > 0 and data['text'][i].strip():
                texts.append(data['text'][i].strip())
                confidences.append(int(data['conf'][i]) / 100)
                boxes.append((
                    data['left'][i], data['top'][i],
                    data['width'][i], data['height'][i]
                ))

        full_text = ' '.join(texts)
        avg_conf = sum(confidences) / len(confidences) if confidences else 0
        return full_text, avg_conf, boxes

    # -------------------------------------------------------
    # Step 4: Apply Postprocessor Patch
    # -------------------------------------------------------
    def step4_apply_patch(self):
        """Apply medical_doc_gui_patch.py to OCR results."""
        step_name = "Apply Postprocessor Patch"
        start = time.time()

        patch_path = self.config.get("patch")
        dict_path = self.config.get("dictionary")

        if not self.ocr_result_json.exists():
            self._log("No OCR result to patch. Skipping.", "WARNING")
            return

        self._log(f"Applying postprocessor patch: {patch_path}")

        try:
            # Import and apply patch
            patch_dir = Path(patch_path).parent
            if str(patch_dir) not in sys.path:
                sys.path.insert(0, str(patch_dir))

            # Dynamic import
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "medical_doc_gui_patch", str(patch_path)
            )
            patch_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(patch_module)

            # Load OCR result
            with open(self.ocr_result_json, 'r', encoding='utf-8') as f:
                ocr_data = json.load(f)

            # Apply patch
            patched = patch_module.patch_ocr_result(ocr_data, dictionary_path=dict_path)

            # Save patched result
            with open(self.ocr_patched_json, 'w', encoding='utf-8') as f:
                json.dump(patched, f, ensure_ascii=False, indent=2)

            corr_count = patched.get("correction_count", 0)
            new_conf = patched.get("confidence_post_corrected", 0)
            issues = patched.get("validation_issue_count", 0)

            self._log(f"  Applied {corr_count} corrections", "SUCCESS")
            self._log(f"  New confidence: {new_conf:.3f}")
            self._log(f"  Remaining issues: {issues}")

            # Copy patched as main result for subsequent steps
            shutil.copy2(str(self.ocr_patched_json), str(self.ocr_result_json))

            self.results.append(StepResult(
                step_name=step_name, success=True, duration=time.time() - start,
                output_files=[str(self.ocr_patched_json)],
                message=f"{corr_count} corrections, conf={new_conf:.3f}",
                metrics={"corrections": corr_count, "new_confidence": new_conf,
                         "issues": issues}
            ))

        except Exception as e:
            self._log(f"Patch failed: {e}", "ERROR")
            self.results.append(StepResult(
                step_name=step_name, success=False, duration=time.time() - start,
                output_files=[], message=str(e)
            ))

    # -------------------------------------------------------
    # Step 5: Compare OCR with Ground Truth
    # -------------------------------------------------------
    def step5_compare(self):
        """Compare OCR output with ground truth (CER/WER/Medical Accuracy)."""
        step_name = "Compare with GT"
        start = time.time()

        if not self.ground_truth_txt.exists():
            self._log("No ground truth file. Skipping comparison.", "WARNING")
            return

        if not self.ocr_result_json.exists():
            self._log("No OCR result file. Skipping comparison.", "WARNING")
            return

        self._log("Comparing OCR with Ground Truth...")

        # Load files
        with open(self.ground_truth_txt, 'r', encoding='utf-8') as f:
            gt_text = f.read()

        with open(self.ocr_result_json, 'r', encoding='utf-8') as f:
            ocr_data = json.load(f)

        # Determine which text to compare
        if ocr_data.get("corrected_text"):
            ocr_text = ocr_data["corrected_text"]
            label = "Corrected OCR"
        else:
            ocr_text = ocr_data.get("raw_text", "")
            label = "Raw OCR"

        # Use the comparison engine
        comparison_script = Path(__file__).parent / "gt_comparison_engine.py"

        if comparison_script.exists():
            try:
                # Write OCR text to temp file for comparison script
                ocr_txt_file = self.output_dir / "ocr_for_compare.txt"
                with open(ocr_txt_file, 'w', encoding='utf-8') as f:
                    f.write(ocr_text)

                cmd = [
                    sys.executable, str(comparison_script),
                    "--gt", str(self.ground_truth_txt),
                    "--ocr", str(ocr_txt_file),
                    "--output", str(self.comparison_report),
                    "--generate-dict",
                    "--generate-training"
                ]
                result = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=60
                )

                if result.returncode == 0:
                    self._log(f"  Comparison complete", "SUCCESS")
                    if result.stdout:
                        for line in result.stdout.strip().split('\n'):
                            if line.strip():
                                self._log(f"    {line}")
            except Exception as e:
                self._log(f"  Comparison script failed: {e}", "WARNING")
                # Fallback to inline comparison
                self._inline_comparison(gt_text, ocr_text)
        else:
            self._log("  Comparison script not found. Using inline comparison.", "WARNING")
            self._inline_comparison(gt_text, ocr_text)

        # Calculate metrics inline regardless
        cer, wer, med_acc = self._calculate_metrics(gt_text, ocr_text)

        self.results.append(StepResult(
            step_name=step_name, success=True, duration=time.time() - start,
            output_files=[str(self.comparison_report)],
            message=f"CER={cer:.1%}, WER={wer:.1%}, Medical={med_acc:.1%}",
            metrics={"cer": cer, "wer": wer, "medical_accuracy": med_acc}
        ))

    def _inline_comparison(self, gt_text: str, ocr_text: str):
        """Inline comparison when the comparison script is unavailable."""
        cer, wer, med_acc = self._calculate_metrics(gt_text, ocr_text)

        report = {
            "summary": {
                "avg_cer": cer, "avg_wer": wer,
                "medical_accuracy": med_acc,
                "lines_compared": 1
            },
            "inline": True
        }
        with open(self.comparison_report, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

    def _calculate_metrics(self, gt_text: str, ocr_text: str) -> tuple:
        """Calculate CER, WER, and medical accuracy."""
        import unicodedata

        def normalize(text):
            text = unicodedata.normalize('NFC', text)
            text = text.replace('أ', 'ا').replace('إ', 'ا').replace('آ', 'ا')
            text = text.replace('ى', 'ي').replace('ة', 'ه')
            for i in range(0x064B, 0x065F):
                text = text.replace(chr(i), '')
            return re.sub(r'\s+', ' ', text).strip()

        gt_norm = normalize(gt_text).replace(' ', '')
        ocr_norm = normalize(ocr_text).replace(' ', '')

        # CER (Levenshtein)
        def lev(s1, s2):
            if len(s1) < len(s2):
                return lev(s2, s1)
            if len(s2) == 0:
                return len(s1)
            prev = list(range(len(s2) + 1))
            for i, c1 in enumerate(s1):
                curr = [i + 1]
                for j, c2 in enumerate(s2):
                    curr.append(min(prev[j+1]+1, curr[j]+1, prev[j]+(c1!=c2)))
                prev = curr
            return prev[-1]

        cer_dist = lev(gt_norm, ocr_norm)
        cer = cer_dist / max(len(gt_norm), 1)

        # WER
        gt_words = normalize(gt_text).split()
        ocr_words = normalize(ocr_text).split()
        wer_dist = lev(gt_words, ocr_words)
        wer = wer_dist / max(len(gt_words), 1)

        # Medical accuracy
        med_patterns = [
            r'(?:ال)?(?:تهاب|خلع|متلازمة|داء|انزلاق|تشوه|شلل|قيلة|ورم|عسرة|حثول|ضفيرة|مفصل)\w*',
            r'(?:ال)?(?:مشاش|مثاش|فخذ|كتف|يد|قدم|دماغ|عمود)\w*',
            r'(?:ال)?(?:خلقي|عضلي|عظمي|سحائي|دماغي|قيحي|تطوري)\w*',
            r'Rickets', r'Perthes', r'Charcot',
        ]

        gt_terms = set()
        ocr_terms = set()
        for pat in med_patterns:
            for m in re.finditer(pat, normalize(gt_text), re.IGNORECASE):
                gt_terms.add(m.group())
            for m in re.finditer(pat, normalize(ocr_text), re.IGNORECASE):
                ocr_terms.add(m.group())

        found = len(gt_terms & ocr_terms)
        med_acc = found / max(len(gt_terms), 1)

        return cer, wer, med_acc

    # -------------------------------------------------------
    # Step 6: Font Glyph Validation
    # -------------------------------------------------------
    def step6_font_validate(self):
        """Validate OCR text against font glyph data."""
        step_name = "Font Glyph Validation"
        start = time.time()

        if not self.fonts_json.exists():
            self.results.append(StepResult(
                step_name=step_name, success=False, duration=time.time() - start,
                output_files=[], message="No font data available"
            ))
            return

        self._log("Validating OCR text against font glyphs...")

        try:
            with open(self.fonts_json, 'r', encoding='utf-8') as f:
                fonts_data = json.load(f)

            with open(self.ocr_result_json, 'r', encoding='utf-8') as f:
                ocr_data = json.load(f)

            ocr_text = ocr_data.get("corrected_text") or ocr_data.get("raw_text", "")

            # Build character set from fonts
            font_chars = set()
            for glyph in fonts_data.get("glyphs", []):
                font_chars.add(glyph.get("char", ""))

            validated = sum(1 for c in ocr_text if c in font_chars or c.isspace() or c.isdigit())
            total = len(ocr_text)
            rate = validated / max(total, 1)

            # Save validated text (no changes, just report)
            with open(self.font_validated_txt, 'w', encoding='utf-8') as f:
                f.write(ocr_text)

            self._log(f"  Font validation: {rate:.1%} chars in font set", "SUCCESS")

            self.results.append(StepResult(
                step_name=step_name, success=True, duration=time.time() - start,
                output_files=[str(self.font_validated_txt)],
                message=f"Validation rate: {rate:.1%}",
                metrics={"validation_rate": rate, "font_chars": len(font_chars)}
            ))

        except Exception as e:
            self._log(f"  Font validation error: {e}", "ERROR")
            self.results.append(StepResult(
                step_name=step_name, success=False, duration=time.time() - start,
                output_files=[], message=str(e)
            ))

    # -------------------------------------------------------
    # Step 7: Export
    # -------------------------------------------------------
    def step7_export(self):
        """Export merged dictionary and training data."""
        step_name = "Export"
        start = time.time()

        self._log("Exporting training data...")

        # Merge dictionaries
        merged = {}

        # Load auto-generated dictionary (if exists)
        if self.comparison_report.exists():
            try:
                with open(self.comparison_report, 'r', encoding='utf-8') as f:
                    report = json.load(f)
                # Auto dictionary would be saved by comparison engine
                auto_dict_path = self.output_dir / "report_dict.json"
                if not auto_dict_path.exists():
                    auto_dict_path = str(self.comparison_report).replace('.json', '_dict.json')
                if Path(auto_dict_path).exists():
                    with open(auto_dict_path, 'r', encoding='utf-8') as f:
                        merged["auto_generated"] = json.load(f)
            except Exception:
                pass

        # Load medical dictionary
        dict_path = self.config.get("dictionary")
        if dict_path and Path(dict_path).exists():
            try:
                with open(dict_path, 'r', encoding='utf-8') as f:
                    merged["medical"] = json.load(f)
                self._log(f"  Loaded medical dictionary: {dict_path}")
            except Exception as e:
                self._log(f"  Failed to load medical dictionary: {e}", "WARNING")

        # Collect training pairs
        training_pairs = []

        # From comparison engine output
        for pattern in [self.output_dir / "report_training.json",
                        str(self.comparison_report).replace('.json', '_training.json')]:
            if Path(pattern).exists():
                try:
                    with open(pattern, 'r', encoding='utf-8') as f:
                        pairs = json.load(f)
                        training_pairs.extend(pairs)
                except Exception:
                    pass

        # Deduplicate training pairs
        seen = set()
        unique_pairs = []
        for pair in training_pairs:
            key = f"{pair.get('input', '')}::{pair.get('target', '')}"
            if key not in seen:
                seen.add(key)
                unique_pairs.append(pair)

        # Save merged dictionary
        with open(self.merged_dictionary, 'w', encoding='utf-8') as f:
            json.dump(merged, f, ensure_ascii=False, indent=2)

        # Save training pairs
        with open(self.training_pairs, 'w', encoding='utf-8') as f:
            json.dump({
                "total_pairs": len(unique_pairs),
                "generated_at": datetime.now().isoformat(),
                "pairs": unique_pairs
            }, f, ensure_ascii=False, indent=2)

        self._log(f"  Merged dictionary: {self.merged_dictionary.name}", "SUCCESS")
        self._log(f"  Training pairs: {len(unique_pairs)}", "SUCCESS")

        self.results.append(StepResult(
            step_name=step_name, success=True, duration=time.time() - start,
            output_files=[str(self.merged_dictionary), str(self.training_pairs)],
            message=f"{len(unique_pairs)} training pairs",
            metrics={"training_pairs": len(unique_pairs),
                     "dictionary_sources": len(merged)}
        ))

    # -------------------------------------------------------
    # Step 8: Generate Final Report
    # -------------------------------------------------------
    def step8_generate_report(self):
        """Generate comprehensive pipeline report."""
        step_name = "Generate Report"
        start = time.time()

        total_time = time.time() - self.start_time

        # Find CER/WER from comparison step
        cer, wer, med_acc = 0, 0, 0
        for r in self.results:
            if r.metrics and "cer" in r.metrics:
                cer = r.metrics["cer"]
                wer = r.metrics["wer"]
                med_acc = r.metrics["medical_accuracy"]

        # Find corrections count from patch step
        corrections = 0
        for r in self.results:
            if r.metrics and "corrections" in r.metrics:
                corrections = r.metrics["corrections"]

        report = {
            "success": True,
            "output_dir": str(self.output_dir),
            "mode": self.config.get("mode", "full"),
            "timestamp": datetime.now().isoformat(),
            "execution_time": round(total_time, 2),
            "metrics": {
                "cer": round(cer, 4),
                "wer": round(wer, 4),
                "medical_accuracy": round(med_acc, 4),
                "corrections_generated": corrections,
                "training_pairs": 0  # Will be updated below
            },
            "steps": {
                r.step_name: {
                    "success": r.success,
                    "duration": round(r.duration, 2),
                    "message": r.message,
                    "metrics": r.metrics
                }
                for r in self.results
            }
        }

        # Update training pairs count
        if self.training_pairs.exists():
            try:
                with open(self.training_pairs, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    report["metrics"]["training_pairs"] = data.get("total_pairs", 0)
            except Exception:
                pass

        with open(self.pipeline_report, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        # Print summary
        self._log("")
        self._log("=" * 50)
        self._log("PIPELINE SUMMARY")
        self._log("=" * 50)
        self._log(f"  CER:              {cer:.2%}")
        self._log(f"  WER:              {wer:.2%}")
        self._log(f"  Medical Accuracy: {med_acc:.2%}")
        self._log(f"  Corrections:      {corrections}")
        self._log(f"  Training Pairs:   {report['metrics']['training_pairs']}")
        self._log(f"  Execution Time:   {total_time:.1f}s")
        self._log("=" * 50)

        self.results.append(StepResult(
            step_name=step_name, success=True, duration=time.time() - start,
            output_files=[str(self.pipeline_report), str(self.pipeline_log)],
            message=f"Total: {total_time:.1f}s, CER={cer:.1%}, WER={wer:.1%}",
            metrics={"cer": cer, "wer": wer, "medical_accuracy": med_acc,
                     "total_time": total_time}
        ))

    def _get_summary(self) -> Dict:
        """Get pipeline summary for return."""
        return {
            "success": all(r.success for r in self.results if r.step_name != "Font Glyph Validation"),
            "output_dir": str(self.output_dir),
            "steps_completed": len(self.results),
            "steps_failed": sum(1 for r in self.results if not r.success),
            "total_time": time.time() - self.start_time,
            "results": [r.to_dict() for r in self.results]
        }


# ============================================================
# CLI Entry Point
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Fully Automated Ground Truth + OCR Training Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Modes:
  Full:     ABBYY + ReadIRIS + PDF + Image + Patch (~2-3 min)
  Quick:    ABBYY + Image only (~1 min)
  Skip-OCR: GT + existing OCR results (~30 sec)

Examples:
  # Full pipeline
  python run_full_pipeline.py \\
      --abbyy "page_588_abbyy.docx" \\
      --readiris "page_588_readiris.rtf" \\
      --pdf "page_588.pdf" \\
      --image "Scanned Document-588.jpg" \\
      --output-dir "pipeline_output_588"

  # Quick mode
  python run_full_pipeline.py \\
      --abbyy "abbyy.docx" \\
      --image "document.jpg" \\
      --quick

  # With postprocessing
  python run_full_pipeline.py \\
      --abbyy "abbyy.docx" \\
      --image "doc.jpg" \\
      --patch medical_doc_gui_patch.py \\
      --dictionary arabic_medical_dict.json

  # Skip OCR (use existing)
  python run_full_pipeline.py \\
      --abbyy "abbyy.docx" \\
      --ocr "ocr_result.json" \\
      --skip-ocr
        """
    )

    # Input sources
    parser.add_argument("--abbyy", help="ABBYY FineReader .docx output")
    parser.add_argument("--readiris", help="ReadIRIS .rtf output")
    parser.add_argument("--pdf", help="PDF file (for font extraction)")
    parser.add_argument("--manual-gt", help="Manual ground truth .txt file")
    parser.add_argument("--image", help="Scanned document image (for OCR)")
    parser.add_argument("--ocr", help="Existing OCR result JSON (skip-ocr mode)")

    # Options
    parser.add_argument("--output-dir", default="pipeline_output",
                        help="Output directory (default: pipeline_output)")
    parser.add_argument("--ocr-engine", choices=["auto", "paddleocr", "easyocr", "tesseract"],
                        default="auto", help="OCR engine (default: auto)")
    parser.add_argument("--patch", help="Path to medical_doc_gui_patch.py")
    parser.add_argument("--dictionary", help="Path to arabic_medical_dict.json")

    # Modes
    parser.add_argument("--quick", action="store_true",
                        help="Quick mode: ABBYY + Image only")
    parser.add_argument("--skip-ocr", action="store_true",
                        help="Skip OCR step, use existing results")

    args = parser.parse_args()

    # Build config
    config = {
        "abbyy": args.abbyy,
        "readiris": args.readiris,
        "pdf": args.pdf,
        "manual_gt": args.manual_gt,
        "image": args.image,
        "ocr_engine": args.ocr_engine,
        "output_dir": args.output_dir,
        "patch": args.patch,
        "dictionary": args.dictionary,
        "skip_ocr": args.skip_ocr,
        "mode": "quick" if args.quick else "full"
    }

    if args.ocr:
        # Copy existing OCR result
        import shutil
        out_dir = Path(args.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(args.ocr, out_dir / "ocr_result.json")
        config["skip_ocr"] = True

    # Run pipeline
    pipeline = FullPipeline(config)
    summary = pipeline.run()

    # Exit code
    if summary["success"]:
        print(f"\n>> Pipeline completed successfully!")
        print(f">> Output: {summary['output_dir']}")
        sys.exit(0)
    else:
        print(f"\n>> Pipeline completed with {summary['steps_failed']} errors")
        sys.exit(1)


if __name__ == "__main__":
    main()
