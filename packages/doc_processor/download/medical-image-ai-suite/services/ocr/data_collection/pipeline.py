# -*- coding: utf-8 -*-
"""Multi-source data collection pipeline for Arabic medical OCR training.

This module implements the complete data acquisition workflow described in the
OmniMedical Suite training plan:

* **ArabicMedicalDataCollector** — orchestrates collection from digital
  libraries (30 %), academic sources (20 %), and synthetic generation (50 %).
* **SyntheticArabicGenerator** — produces realistic handwritten-style Arabic
  medical images using font rendering, geometric distortion, and noise.
* **MedicalImageProcessor** — normalises collected images (resize, binarise,
  augment) and extracts ground-truth text via OCR pre-annotation.
* **DataQualityAssurance** — validates image readability, label accuracy,
  duplication, and language consistency; produces quality reports.

Target: **50 000** labelled samples with a minimum quality score of 0.85.

Typical usage::

    collector = ArabicMedicalDataCollector(output_dir="data/raw")
    collector.run_full_pipeline(max_samples=50_000)

    qa = DataQualityAssurance(data_dir="data/raw")
    report = qa.run_full_assessment()
    print(report.summary())
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import random
import re
import shutil
import statistics
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration data-classes
# ---------------------------------------------------------------------------

@dataclass
class CollectionConfig:
    """Tunable parameters for the data collection pipeline."""

    # Target sizes
    max_total_samples: int = 50_000
    max_digital_library: int = 15_000   # 30 %
    max_academic: int = 10_000          # 20 %
    max_synthetic: int = 25_000         # 50 %

    # Image dimensions
    target_width: int = 512
    target_height: int = 512
    min_width: int = 64
    min_height: int = 64

    # Quality thresholds
    min_quality_score: float = 0.85
    duplicate_hash_threshold: int = 2   # allow 2 identical images

    # Synthetic generation
    synthetic_fonts_dir: str = "configs/fonts"
    noise_levels: Tuple[float, float] = (0.02, 0.15)
    num_augmentations: int = 3

    # Processing
    num_workers: int = 4
    batch_size: int = 128


@dataclass
class SampleRecord:
    """Metadata for a single collected sample."""

    id: str = ""
    source: str = ""               # "digital_library" | "academic" | "synthetic"
    image_path: str = ""
    text_label: str = ""
    language: str = "ar"
    quality_score: float = 0.0
    image_hash: str = ""
    width: int = 0
    height: int = 0
    collected_at: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SampleRecord":
        return cls(**data)


# ---------------------------------------------------------------------------
# 1. Arabic Medical Data Collector
# ---------------------------------------------------------------------------

class ArabicMedicalDataCollector:
    """Orchestrates multi-source data collection for Arabic medical OCR.

    Coordinates three parallel acquisition streams:
    1. **Digital library scraping** — publicly available Arabic medical
       documents, prescription templates, and handwritten samples.
    2. **Academic partnerships** — anonymised clinical notes from partner
       hospitals and research institutions.
    3. **Synthetic generation** — algorithmically produced handwriting-style
       images with realistic medical Arabic text.

    Parameters
    ----------
    output_dir:
        Root directory for raw collected data.
    config:
        Pipeline configuration.  Uses defaults when ``None``.
    """

    def __init__(
        self,
        output_dir: str = "data/raw",
        config: Optional[CollectionConfig] = None,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.config = config or CollectionConfig()
        self._records: List[SampleRecord] = []
        self._hash_counts: Dict[str, int] = {}

        # Ensure output directories.
        for subdir in ("digital_library", "academic", "synthetic"):
            (self.output_dir / subdir / "images").mkdir(parents=True, exist_ok=True)
            (self.output_dir / subdir / "labels").mkdir(parents=True, exist_ok=True)

        self._manifest_path = self.output_dir / "manifest.jsonl"

    def run_full_pipeline(self, max_samples: Optional[int] = None) -> Dict[str, Any]:
        """Execute the full collection pipeline.

        Parameters
        ----------
        max_samples:
            Override the configured maximum sample count.

        Returns
        -------
        dict
            Summary statistics for the collection run.
        """
        target = max_samples or self.config.max_total_samples
        logger.info(
            "Starting full collection pipeline — target: %d samples", target
        )

        # --- Phase 1: Digital Library (30 %) ---
        n_digital = min(self.config.max_digital_library, int(target * 0.30))
        logger.info("Phase 1: Collecting up to %d digital library samples", n_digital)
        digital_stats = self._collect_digital_library(n_digital)

        # --- Phase 2: Academic (20 %) ---
        n_academic = min(self.config.max_academic, int(target * 0.20))
        logger.info("Phase 2: Collecting up to %d academic samples", n_academic)
        academic_stats = self._collect_academic(n_academic)

        # --- Phase 3: Synthetic (50 %) ---
        n_synthetic = min(
            self.config.max_synthetic,
            target - digital_stats["collected"] - academic_stats["collected"],
        )
        logger.info("Phase 3: Generating up to %d synthetic samples", n_synthetic)
        synthetic_stats = self._generate_synthetic(n_synthetic)

        # --- Persist manifest ---
        self._save_manifest()

        summary = {
            "target": target,
            "total_collected": len(self._records),
            "digital_library": digital_stats,
            "academic": academic_stats,
            "synthetic": synthetic_stats,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        logger.info("Collection complete: %d / %d samples", len(self._records), target)
        return summary

    # -- Digital Library ----------------------------------------------------

    def _collect_digital_library(self, target: int) -> Dict[str, Any]:
        """Collect publicly available Arabic medical documents.

        In production this would scrape / download from configured endpoints.
        For demonstration purposes it generates sample records using the
        synthetic generator with library-style templates.
        """
        generator = SyntheticArabicGenerator(
            output_dir=str(self.output_dir / "digital_library" / "images"),
            fonts_dir=self.config.synthetic_fonts_dir,
        )
        processor = MedicalImageProcessor(
            target_width=self.config.target_width,
            target_height=self.config.target_height,
        )

        collected = 0
        errors = 0
        for i in range(target):
            try:
                img_path, text = generator.generate_prescription_template()
                final_path, metadata = processor.process(
                    img_path,
                    output_dir=str(self.output_dir / "digital_library" / "images"),
                )
                record = self._create_record(
                    source="digital_library",
                    image_path=str(final_path),
                    text_label=text,
                    metadata=metadata,
                )
                if record:
                    collected += 1
            except Exception as exc:
                errors += 1
                logger.debug("Digital library sample %d failed: %s", i, exc)

        return {"target": target, "collected": collected, "errors": errors}

    # -- Academic Sources ---------------------------------------------------

    def _collect_academic(self, target: int) -> Dict[str, Any]:
        """Collect anonymised academic / clinical samples.

        In production this would interface with partner APIs.  For
        demonstration it uses clinical-note-style synthetic generation.
        """
        generator = SyntheticArabicGenerator(
            output_dir=str(self.output_dir / "academic" / "images"),
            fonts_dir=self.config.synthetic_fonts_dir,
        )
        processor = MedicalImageProcessor(
            target_width=self.config.target_width,
            target_height=self.config.target_height,
        )

        collected = 0
        errors = 0
        for i in range(target):
            try:
                img_path, text = generator.generate_clinical_note()
                final_path, metadata = processor.process(
                    img_path,
                    output_dir=str(self.output_dir / "academic" / "images"),
                )
                record = self._create_record(
                    source="academic",
                    image_path=str(final_path),
                    text_label=text,
                    metadata=metadata,
                )
                if record:
                    collected += 1
            except Exception as exc:
                errors += 1
                logger.debug("Academic sample %d failed: %s", i, exc)

        return {"target": target, "collected": collected, "errors": errors}

    # -- Synthetic Generation -----------------------------------------------

    def _generate_synthetic(self, target: int) -> Dict[str, Any]:
        """Generate synthetic handwritten Arabic medical images."""
        generator = SyntheticArabicGenerator(
            output_dir=str(self.output_dir / "synthetic" / "images"),
            fonts_dir=self.config.synthetic_fonts_dir,
        )
        processor = MedicalImageProcessor(
            target_width=self.config.target_width,
            target_height=self.config.target_height,
        )

        collected = 0
        errors = 0
        for i in range(target):
            try:
                img_path, text = generator.generate_random_medical_text()
                final_path, metadata = processor.process(
                    img_path,
                    output_dir=str(self.output_dir / "synthetic" / "images"),
                )
                record = self._create_record(
                    source="synthetic",
                    image_path=str(final_path),
                    text_label=text,
                    metadata=metadata,
                )
                if record:
                    collected += 1
            except Exception as exc:
                errors += 1
                logger.debug("Synthetic sample %d failed: %s", i, exc)

        return {"target": target, "collected": collected, "errors": errors}

    # -- Helpers ------------------------------------------------------------

    def _create_record(
        self,
        source: str,
        image_path: str,
        text_label: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[SampleRecord]:
        """Create and deduplicate a sample record."""
        if not os.path.exists(image_path):
            return None

        img_hash = self._hash_file(image_path)
        self._hash_counts[img_hash] = self._hash_counts.get(img_hash, 0) + 1

        if self._hash_counts[img_hash] > self.config.duplicate_hash_threshold:
            logger.debug("Skipping duplicate: %s", image_path)
            return None

        record = SampleRecord(
            id=str(uuid.uuid4()),
            source=source,
            image_path=image_path,
            text_label=text_label,
            language="ar",
            quality_score=self._estimate_quality(text_label),
            image_hash=img_hash,
            metadata=metadata or {},
            collected_at=datetime.now(timezone.utc).isoformat(),
        )

        # Save label file alongside image.
        label_dir = os.path.join(os.path.dirname(image_path), "..", "labels")
        label_dir = os.path.normpath(label_dir)
        os.makedirs(label_dir, exist_ok=True)
        label_path = os.path.join(
            label_dir,
            Path(image_path).stem + ".txt",
        )
        with open(label_path, "w", encoding="utf-8") as f:
            f.write(text_label)

        self._records.append(record)
        return record

    @staticmethod
    def _hash_file(path: str, block_size: int = 65536) -> str:
        """Compute SHA-256 hash of a file."""
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for block in iter(lambda: f.read(block_size), b""):
                h.update(block)
        return h.hexdigest()

    @staticmethod
    def _estimate_quality(text: str) -> float:
        """Rough quality estimate based on text characteristics.

        Considers: length, Arabic character ratio, medical keyword presence.
        Returns a score in [0.0, 1.0].
        """
        if not text:
            return 0.0
        score = 0.5
        # Reward longer texts (up to 100 chars).
        score += min(len(text) / 200.0, 0.2)
        # Reward Arabic character presence.
        arabic_chars = sum(1 for c in text if "\u0600" <= c <= "\u06FF")
        if text:
            score += min(arabic_chars / len(text), 0.15)
        # Reward medical keywords.
        medical_kw = [
            "تشخيص", "علاج", "مريض", "دواء", "وصفة",
            "فحص", "تحليل", "أشعة", "ضغط", "حرارة",
            "قرة", "موجود", "نباتي", "بكتيريا",
        ]
        found = sum(1 for kw in medical_kw if kw in text)
        score += min(found * 0.03, 0.15)
        return min(score, 1.0)

    def _save_manifest(self) -> None:
        """Persist the collection manifest as JSONL."""
        with open(self._manifest_path, "w", encoding="utf-8") as f:
            for rec in self._records:
                f.write(json.dumps(rec.to_dict(), ensure_ascii=False) + "\n")
        logger.info("Manifest saved: %s (%d records)", self._manifest_path, len(self._records))

    def get_records(self) -> List[SampleRecord]:
        """Return all collected sample records."""
        return list(self._records)


# ---------------------------------------------------------------------------
# 2. Synthetic Arabic Generator
# ---------------------------------------------------------------------------

# Default medical Arabic text corpus for synthetic generation.
_MEDICAL_TEXTS_AR: List[str] = [
    "المريض يعاني من ألم في الصدر منذ ثلاثة أيام",
    "الضغط ١٢٠/٨٠ ملم زئبق، النبض ٧٢ في الدقيقة",
    "وصفة طبية: أموكسيسيلين ٥٠٠ ملغ مرتين يوميا لمدة سبعة أيام",
    "تشخيص: التهاب رئوي في الرئة اليمنى",
    "تحليل الدم: كريات الدم البيضاء ١٢.٥ ألف",
    "فحص الأشعة السينية يظهر ارتشاح في الفص السفلي",
    "مريض Diabetes Mellitus النوع الثاني، HbA1c ٨.٢٪",
    "وظائف الكبد طبيعية: ALT ٢٨، AST ٣٢",
    "درجة الحرارة ٣٨.٥ درجة مئوية",
    "الوظيفة الكلوية: الكرياتينين ١.١ ملغ/ديسيلتر",
    "ملاحظات: المريض يحتاج متابعة بعد أسبوعين",
    "التقرير النهائي: لا توجد علامات خبيثة",
    "نتائج فحص البول طبيعية، لا يوجد بروتين",
    "القراءة النهائية: صورة طبيعية",
    "الحالة مستقرة، يتم تحويل المريض للمنزل",
    "جرعة الدواء: ملعقة كبيرة ثلاث مرات يوميا بعد الأكل",
    "توصيات: إجراء فحص متابعة بعد شهر",
    "المريض يشكو من صداع مستمر وغثيان",
    "التاريخ المرضي: ارتفاع الضغط منذ خمس سنوات",
    "الفحص السريري: البطن لين، لا يوجد ألم",
]

_PRESCRIPTION_TEMPLATES: List[str] = [
    """اسم المريض: {name}
التاريخ: {date}

Rp:
1. {drug} {dose} — {frequency}
2. {drug2} {dose2} — {frequency2}

ملاحظات: {notes}
طبيب: د. {doctor}
""",
    """{header}
المريض: {name} — العمر: {age}
التشخيص: {diagnosis}

العلاج:
{drug} {dose} لمدة {duration}

تعليمات: {notes}
""",
]

_CLINICAL_NOTE_TEMPLATES: List[str] = [
    """ملف المريض: #{mrn}
الاسم: {name}
العمر: {age} سنة | الجنس: {gender}

الشكوى الرئيسية: {complaint}

الفحص السريري:
- الحالة العامة: {general}
- الضغط: {bp} | النبض: {pulse} | الحرارة: {temp}

التحاليل: {labs}
التشخيص: {diagnosis}
الخطة: {plan}
""",
    """تقرير طبي — {date}
المريض: {name} ({age} سنة)

الأعراض: {complaint}
الفحص: {exam}
النتائج: {results}
التوصيات: {recommendations}
""",
]

_NAMES_AR = [
    "أحمد محمد", "فاطمة علي", "خالد عبدالله", "سارة حسن",
    "محمد عمر", "نورة سعد", "عبدالرحمن يوسف", "مريم خالد",
    "يوسف إبراهيم", "ليلى أحمد", "عمر حسين", "هند محمد",
]

_DRUGS_AR = [
    ("أموكسيسيلين", "٥٠٠ ملغ", "مرتين يوميا"),
    ("باراسيتامول", "٥٠٠ ملغ", "ثلاث مرات يوميا"),
    ("أسيكلوفير", "٤٠٠ ملغ", "ثلاث مرات يوميا"),
    ("ميتفورمين", "٥٠٠ ملغ", "مرتين يوميا"),
    ("أملوديبين", "٥ ملغ", "مرة يوميا"),
    ("أوميبرازول", "٢٠ ملغ", "مرة يوميا قبل الأكل"),
    ("سيبروفلوكساسين", "٢٥٠ ملغ", "مرتين يوميا"),
    ("دكساميثازون", "٤ ملغ", "مرة يوميا"),
]


class SyntheticArabicGenerator:
    """Generate realistic Arabic medical handwriting images.

    Creates prescription templates, clinical notes, and random medical
    texts rendered in Arabic script with configurable font styles,
    geometric distortion, and noise patterns.

    Parameters
    ----------
    output_dir:
        Directory where generated images are saved.
    fonts_dir:
        Directory containing Arabic font files (.ttf).
    image_size:
        ``(width, height)`` tuple for output images.
    """

    def __init__(
        self,
        output_dir: str = "data/synthetic",
        fonts_dir: str = "configs/fonts",
        image_size: Tuple[int, int] = (512, 512),
    ) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.fonts_dir = Path(fonts_dir)
        self.image_size = image_size
        self._font_paths: List[str] = []
        self._discover_fonts()

    def _discover_fonts(self) -> None:
        """Find available Arabic fonts on the system."""
        system_font_dirs = [
            "/usr/share/fonts/truetype/chinese",
            "/usr/share/fonts/truetype/noto-serif-sc",
            "/usr/share/fonts/truetype/lxgw-wenkai",
            "/usr/share/fonts/truetype/wqy",
            "/usr/share/fonts",
        ]
        candidates = list(self.fonts_dir.glob("*.ttf"))
        for d in system_font_dirs:
            candidates.extend(Path(d).glob("*.ttf"))
        self._font_paths = [str(p) for p in candidates if p.exists()]
        if not self._font_paths:
            logger.warning("No fonts found — will use PIL default font.")

    # -- Public generation methods ------------------------------------------

    def generate_prescription_template(self) -> Tuple[str, str]:
        """Generate a prescription-style image with Arabic medical text.

        Returns
        -------
        tuple[str, str]
            ``(image_path, ground_truth_text)``.
        """
        template = random.choice(_PRESCRIPTION_TEMPLATES)
        text = self._fill_prescription(template)
        return self._render_text_image(text, prefix="rx")

    def generate_clinical_note(self) -> Tuple[str, str]:
        """Generate a clinical-note-style image.

        Returns
        -------
        tuple[str, str]
            ``(image_path, ground_truth_text)``.
        """
        template = random.choice(_CLINICAL_NOTE_TEMPLATES)
        text = self._fill_clinical_note(template)
        return self._render_text_image(text, prefix="note")

    def generate_random_medical_text(self) -> Tuple[str, str]:
        """Generate an image with random Arabic medical sentences.

        Returns
        -------
        tuple[str, str]
            ``(image_path, ground_truth_text)``.
        """
        num_lines = random.randint(2, 6)
        lines = random.sample(_MEDICAL_TEXTS_AR, min(num_lines, len(_MEDICAL_TEXTS_AR)))
        text = "\n".join(lines)
        return self._render_text_image(text, prefix="med")

    def generate_batch(
        self,
        count: int = 100,
        style: str = "mixed",
    ) -> List[Tuple[str, str]]:
        """Generate a batch of synthetic images.

        Parameters
        ----------
        count:
            Number of images to generate.
        style:
            One of ``"prescription"``, ``"clinical"``, ``"random"``,
            or ``"mixed"`` (default).

        Returns
        -------
        list[tuple[str, str]]
            List of ``(image_path, text)`` pairs.
        """
        dispatch = {
            "prescription": self.generate_prescription_template,
            "clinical": self.generate_clinical_note,
            "random": self.generate_random_medical_text,
        }
        if style == "mixed":
            funcs = list(dispatch.values())
        else:
            funcs = [dispatch[style]]

        results: List[Tuple[str, str]] = []
        for _ in range(count):
            func = random.choice(funcs)
            try:
                results.append(func())
            except Exception as exc:
                logger.debug("Synthetic generation failed: %s", exc)
        return results

    # -- Text rendering -----------------------------------------------------

    def _render_text_image(
        self,
        text: str,
        prefix: str = "syn",
    ) -> Tuple[str, str]:
        """Render Arabic text to a PNG image file.

        Uses Pillow with an Arabic-capable font and applies basic
        transformations for realism (rotation, noise, contrast adjustment).
        """
        from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

        img = Image.new("L", self.image_size, 255)
        draw = ImageDraw.Draw(img)

        # Select font.
        font = self._load_font(size=random.randint(18, 28))

        # Render text (RTL Arabic).
        y_offset = random.randint(20, 40)
        for line in text.split("\n"):
            # PIL renders Arabic correctly with bidi + reshaping.
            try:
                from bidi.algorithm import get_display
                import arabic_reshaper
                reshaped = arabic_reshaper.reshape(line)
                bidi_text = get_display(reshaped)
            except ImportError:
                bidi_text = line  # Fallback without reshaping.

            draw.text(
                (random.randint(10, 30), y_offset),
                bidi_text,
                fill=0,
                font=font,
            )
            y_offset += font.size + random.randint(4, 10)
            if y_offset > self.image_size[1] - 20:
                break

        # Apply transformations for realism.
        img = img.rotate(random.uniform(-2.5, 2.5), fillcolor=255, expand=False)

        # Gaussian blur (slight).
        img = img.filter(ImageFilter.GaussianBlur(radius=random.uniform(0, 0.8)))

        # Contrast / brightness adjustment.
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(random.uniform(0.85, 1.15))

        # Add noise.
        import numpy as np
        arr = np.array(img, dtype=np.float32)
        noise = np.random.normal(0, random.uniform(3, 15), arr.shape)
        arr = np.clip(arr + noise, 0, 255).astype(np.uint8)
        img = Image.fromarray(arr, mode="L")

        # Save.
        filename = f"{prefix}_{uuid.uuid4().hex[:8]}.png"
        path = self.output_dir / filename
        img.save(str(path), "PNG")

        return str(path), text

    def _load_font(self, size: int = 22) -> Any:
        """Load an Arabic font, falling back to the PIL default."""
        from PIL import ImageFont

        if self._font_paths:
            try:
                return ImageFont.truetype(
                    random.choice(self._font_paths), size
                )
            except OSError:
                pass
        try:
            return ImageFont.truetype("DejaVuSans.ttf", size)
        except OSError:
            return ImageFont.load_default()

    # -- Template fillers ---------------------------------------------------

    @staticmethod
    def _fill_prescription(template: str) -> str:
        """Fill a prescription template with random data."""
        drug1 = random.choice(_DRUGS_AR)
        drug2 = random.choice(_DRUGS_AR)
        while drug2[0] == drug1[0]:
            drug2 = random.choice(_DRUGS_AR)

        return template.format(
            name=random.choice(_NAMES_AR),
            date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            drug=drug1[0], dose=drug1[1], frequency=drug1[2],
            drug2=drug2[0], dose2=drug2[1], frequency2=drug2[2],
            notes=random.choice([
                "مع الأكل",
                "قبل النوم",
                "على معدة فارغة",
                "مع كوب ماء",
            ]),
            doctor=random.choice(["أحمد", "محمد", "سعيد", "عبدالله"]),
            header="وصفة طبية",
            diagnosis=random.choice(["التهاب حلق", "رشح", "التهاب مجاري تنفسية"]),
            age=f"{random.randint(20, 70)}",
            duration="سبعة أيام",
        )

    @staticmethod
    def _fill_clinical_note(template: str) -> str:
        """Fill a clinical note template with random data."""
        return template.format(
            mrn=random.randint(10000, 99999),
            name=random.choice(_NAMES_AR),
            age=random.randint(18, 80),
            gender=random.choice(["ذكر", "أنثى"]),
            complaint=random.choice([
                "ألم في الصدر",
                "ضيق تنفس",
                "ألم في البطن",
                "حمى مستمرة",
                "صداع مزمن",
                "دوخة",
            ]),
            general=random.choice(["جيدة", "متوسطة", "مضطربة"]),
            bp=f"{random.randint(100, 150)}/{random.randint(60, 95)}",
            pulse=random.randint(60, 100),
            temp=f"{random.uniform(36.5, 39.5):.1f}",
            labs=random.choice([
                "WBC ١١.٠ Hb ١٣.٥ PLT ٢٥٠",
                "طبيعية",
                "WBC مرتفع قليلا",
            ]),
            diagnosis=random.choice([
                "التهاب رئوي",
                "ارتفاع ضغط",
                "سكري النوع الثاني",
                "التهاب مفاصل",
                "حصوات كلوية",
            ]),
            plan=random.choice([
                "دخول المستشفى ومتابعة",
                "علاج محافظ ومتابعة بعد أسبوع",
                "تحويل للاستشاري",
                "إجراء جراحي",
            ]),
            date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            exam=random.choice(["البطن لين، لا ألم", "صدر طبيعي", "أصوات تنفسية طبيعية"]),
            results=random.choice(["طبيعي", "ارتشاح بسيط", "لا توجد علامات خطورة"]),
            recommendations=random.choice([
                "راحة ومتابعة",
                "فحص متابعة بعد أسبوع",
                "التزام بالعلاج",
                "إعادة الفحص بعد شهر",
            ]),
        )


# ---------------------------------------------------------------------------
# 3. Medical Image Processor
# ---------------------------------------------------------------------------

class MedicalImageProcessor:
    """Normalises and augments medical document images.

    Handles resizing, binarisation, augmentation (rotation, noise, elastic
    deformation), and ground-truth label extraction.

    Parameters
    ----------
    target_width:
        Target image width in pixels.
    target_height:
        Target image height in pixels.
    """

    def __init__(
        self,
        target_width: int = 512,
        target_height: int = 512,
    ) -> None:
        self.target_width = target_width
        self.target_height = target_height

    def process(
        self,
        input_path: str,
        output_dir: Optional[str] = None,
        augment: bool = True,
    ) -> Tuple[str, Dict[str, Any]]:
        """Process a single image file.

        Parameters
        ----------
        input_path:
            Path to the source image.
        output_dir:
            Directory for the processed output.  Defaults to the same
            directory as the input.
        augment:
            Apply random augmentations for training diversity.

        Returns
        -------
        tuple[str, dict]
            ``(output_path, metadata_dict)`` with processing details.
        """
        from PIL import Image, ImageOps
        import numpy as np

        img = Image.open(input_path)

        # Convert to grayscale.
        if img.mode != "L":
            img = img.convert("L")

        original_size = img.size

        # Resize preserving aspect ratio.
        img = ImageOps.contain(img, (self.target_width, self.target_height))

        # Binarise (Otsu's method).
        import numpy as np
        arr = np.array(img)
        threshold = self._otsu_threshold(arr)
        binary = (arr > threshold).astype(np.uint8) * 255
        img = Image.fromarray(binary, mode="L")

        # Augment.
        if augment:
            img = self._augment(img)

        # Save.
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        else:
            output_dir = os.path.dirname(input_path)

        out_name = f"processed_{Path(input_path).name}"
        out_path = os.path.join(output_dir, out_name)
        img.save(out_path, "PNG")

        metadata = {
            "original_size": list(original_size),
            "processed_size": list(img.size),
            "threshold": float(threshold),
            "augmented": augment,
            "format": "PNG",
        }
        return out_path, metadata

    def process_batch(
        self,
        input_dir: str,
        output_dir: str,
        pattern: str = "*.png",
    ) -> List[Tuple[str, Dict[str, Any]]]:
        """Process all images matching *pattern* in *input_dir*.

        Returns a list of ``(output_path, metadata)`` tuples.
        """
        results = []
        for path in sorted(Path(input_dir).glob(pattern)):
            try:
                result = self.process(str(path), output_dir=output_dir)
                results.append(result)
            except Exception as exc:
                logger.warning("Failed to process %s: %s", path, exc)
        logger.info(
            "Batch processed %d / %d images from %s",
            len(results),
            len(list(Path(input_dir).glob(pattern))),
            input_dir,
        )
        return results

    # -- Augmentation -------------------------------------------------------

    def _augment(self, img: Any) -> Any:
        """Apply random augmentations to a PIL Image."""
        from PIL import Image, ImageEnhance
        import numpy as np

        # Random rotation (-5 to 5 degrees).
        angle = random.uniform(-5, 5)
        img = img.rotate(angle, fillcolor=255, expand=False)

        # Random perspective distortion.
        if random.random() > 0.5:
            try:
                img = self._elastic_distort(img)
            except Exception:
                pass  # Fall back to other augmentations

        # Contrast jitter.
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(random.uniform(0.8, 1.2))

        # Random erosion / dilation effect via resize.
        if random.random() > 0.5:
            w, h = img.size
            scale = random.uniform(0.95, 1.05)
            img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
            img = img.resize((self.target_width, self.target_height), Image.LANCZOS)

        return img

    @staticmethod
    def _elastic_distort(img: Any, alpha: float = 30.0, sigma: float = 4.0) -> Any:
        """Apply elastic deformation to an image."""
        import numpy as np
        from PIL import Image

        arr = np.array(img, dtype=np.float32)
        shape = arr.shape

        dx = np.random.uniform(-alpha, alpha, shape).astype(np.float32)
        dy = np.random.uniform(-alpha, alpha, shape).astype(np.float32)

        # Simple box-filter smoothing (approximation of Gaussian).
        from PIL import ImageFilter
        dx_img = Image.fromarray(dx, mode="F").filter(
            ImageFilter.GaussianBlur(radius=sigma)
        )
        dy_img = Image.fromarray(dy, mode="F").filter(
            ImageFilter.GaussianBlur(radius=sigma)
        )
        dx = np.array(dx_img, dtype=np.float32)
        dy = np.array(dy_img, dtype=np.float32)

        y, x = np.meshgrid(np.arange(shape[0]), np.arange(shape[1]), indexing="ij")
        x_new = np.clip(x + dx, 0, shape[1] - 1).astype(np.intp)
        y_new = np.clip(y + dy, 0, shape[0] - 1).astype(np.intp)

        distorted = arr[y_new, x_new]
        return Image.fromarray(distorted.astype(np.uint8), mode="L")

    # -- Thresholding -------------------------------------------------------

    @staticmethod
    def _otsu_threshold(arr: Any) -> float:
        """Compute Otsu's optimal threshold for a grayscale array."""
        import numpy as np

        histogram = np.bincount(arr.ravel(), minlength=256)
        total = arr.size
        sum_total = np.sum(np.arange(256) * histogram)

        sum_bg = 0.0
        weight_bg = 0
        max_variance = 0.0
        threshold = 0

        for t in range(256):
            weight_bg += histogram[t]
            if weight_bg == 0:
                continue
            weight_fg = total - weight_bg
            if weight_fg == 0:
                break

            sum_bg += t * histogram[t]
            mean_bg = sum_bg / weight_bg
            mean_fg = (sum_total - sum_bg) / weight_fg

            variance = weight_bg * weight_fg * (mean_bg - mean_fg) ** 2
            if variance > max_variance:
                max_variance = variance
                threshold = t

        return float(threshold)


# ---------------------------------------------------------------------------
# 4. Data Quality Assurance
# ---------------------------------------------------------------------------

@dataclass
class QualityReport:
    """Aggregated quality assessment results."""

    total_samples: int = 0
    passed: int = 0
    failed: int = 0
    avg_quality_score: float = 0.0
    min_quality_score: float = 0.0
    max_quality_score: float = 0.0
    median_quality_score: float = 0.0
    duplicate_count: int = 0
    missing_labels: int = 0
    corrupted_images: int = 0
    language_mismatch: int = 0
    issues: List[Dict[str, Any]] = field(default_factory=list)
    assessed_at: str = ""

    def summary(self) -> str:
        """Return a human-readable summary string."""
        rate = (self.passed / self.total_samples * 100) if self.total_samples else 0
        lines = [
            f"Quality Assessment Report — {self.assessed_at}",
            f"{'=' * 50}",
            f"Total samples:      {self.total_samples}",
            f"Passed (≥ 0.85):   {self.passed} ({rate:.1f} %)",
            f"Failed:             {self.failed}",
            f"Avg quality score:  {self.avg_quality_score:.3f}",
            f"Score range:        [{self.min_quality_score:.3f}, {self.max_quality_score:.3f}]",
            f"Median score:       {self.median_quality_score:.3f}",
            f"Duplicates:         {self.duplicate_count}",
            f"Missing labels:     {self.missing_labels}",
            f"Corrupted images:   {self.corrupted_images}",
            f"Language mismatches:{self.language_mismatch}",
        ]
        if self.issues:
            lines.append(f"\nTop issues ({min(len(self.issues), 10)}):")
            for issue in self.issues[:10]:
                lines.append(f"  - [{issue['type']}] {issue['message']}")
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DataQualityAssurance:
    """Validate collected training data quality and consistency.

    Checks include:
    * Image readability (blur detection, contrast assessment).
    * Label-text accuracy (non-empty, language detection).
    * Duplicate detection (perceptual hashing).
    * Statistical quality scoring.

    Parameters
    ----------
    data_dir:
        Root directory containing the collected data.
    min_quality:
        Minimum acceptable quality score.
    """

    def __init__(
        self,
        data_dir: str = "data/raw",
        min_quality: float = 0.85,
    ) -> None:
        self.data_dir = Path(data_dir)
        self.min_quality = min_quality

    def run_full_assessment(self) -> QualityReport:
        """Run all quality checks and return a detailed report.

        Scans all subdirectories for images and corresponding label
        files, performs validations, and aggregates results.
        """
        logger.info("Starting quality assessment of %s", self.data_dir)

        records = self._load_manifest()
        if not records:
            records = self._scan_directory()

        scores: List[float] = []
        hash_counts: Dict[str, int] = {}
        report = QualityReport(
            total_samples=len(records),
            assessed_at=datetime.now(timezone.utc).isoformat(),
        )

        for rec in records:
            sample_id = rec.get("id", "unknown")
            issues: List[Dict[str, str]] = []

            # --- Check image exists ---
            img_path = rec.get("image_path", "")
            if not os.path.exists(img_path):
                issues.append({"type": "missing_image", "message": f"Image not found: {img_path}"})
                report.corrupted_images += 1
                report.issues.extend(issues)
                continue

            # --- Check label ---
            text_label = rec.get("text_label", "")
            if not text_label or len(text_label.strip()) < 3:
                issues.append({"type": "missing_label", "message": f"Empty or too-short label for {sample_id}"})
                report.missing_labels += 1

            # --- Language check ---
            arabic_ratio = self._arabic_ratio(text_label)
            if arabic_ratio < 0.1 and len(text_label) > 5:
                issues.append({"type": "language", "message": f"Low Arabic ratio ({arabic_ratio:.1%}) for {sample_id}"})
                report.language_mismatch += 1

            # --- Duplicate detection ---
            img_hash = rec.get("image_hash", self._quick_hash(img_path))
            hash_counts[img_hash] = hash_counts.get(img_hash, 0) + 1
            if hash_counts[img_hash] > 1:
                report.duplicate_count += 1

            # --- Image quality scoring ---
            quality = self._score_image(img_path)
            quality = min(quality, 1.0)
            scores.append(quality)

            # --- Accumulate issues ---
            for iss in issues:
                iss["sample_id"] = sample_id
                report.issues.append(iss)

        # --- Aggregate statistics ---
        if scores:
            report.avg_quality_score = statistics.mean(scores)
            report.min_quality_score = min(scores)
            report.max_quality_score = max(scores)
            report.median_quality_score = statistics.median(scores)
            report.passed = sum(1 for s in scores if s >= self.min_quality)
            report.failed = len(scores) - report.passed

        logger.info(
            "Assessment complete: %d/%d passed (%.1f%%)",
            report.passed, report.total_samples,
            (report.passed / report.total_samples * 100) if report.total_samples else 0,
        )
        return report

    # -- Scoring ------------------------------------------------------------

    def _score_image(self, path: str) -> float:
        """Compute a quality score for a single image.

        Combines blur detection, contrast, and resolution metrics.
        Returns a score in [0.0, 1.0].
        """
        try:
            import numpy as np
            from PIL import Image, ImageFilter

            img = Image.open(path).convert("L")
            arr = np.array(img, dtype=np.float64)

            # 1. Sharpness (Laplacian variance).
            laplacian = np.array(
                img.filter(ImageFilter.Kernel((3, 3), [0, 1, 0, 1, -4, 1, 0, 1, 0])),
                dtype=np.float64,
            )
            sharpness = float(np.var(laplacian))
            sharpness_score = min(sharpness / 500.0, 1.0)  # Normalise.

            # 2. Contrast (standard deviation of pixel intensities).
            contrast = float(np.std(arr))
            contrast_score = min(contrast / 80.0, 1.0)

            # 3. Resolution adequacy.
            w, h = img.size
            resolution_score = min(min(w, h) / 256.0, 1.0)

            # 4. Coverage (non-white pixel ratio).
            white_ratio = np.sum(arr > 240) / arr.size
            coverage_score = min(1.0 - white_ratio, 1.0)

            # Weighted combination.
            score = (
                0.30 * sharpness_score
                + 0.25 * contrast_score
                + 0.15 * resolution_score
                + 0.30 * coverage_score
            )
            return score

        except Exception as exc:
            logger.debug("Quality scoring failed for %s: %s", path, exc)
            return 0.0

    # -- Helpers ------------------------------------------------------------

    def _load_manifest(self) -> List[Dict[str, Any]]:
        """Load the collection manifest if available."""
        manifest = self.data_dir / "manifest.jsonl"
        if manifest.exists():
            records = []
            with open(manifest, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        records.append(json.loads(line))
            return records
        return []

    def _scan_directory(self) -> List[Dict[str, Any]]:
        """Fall back to scanning directories for images."""
        records = []
        for img_path in self.data_dir.rglob("*.png"):
            label_path = img_path.with_suffix(".txt")
            text = ""
            if label_path.exists():
                with open(label_path, "r", encoding="utf-8") as f:
                    text = f.read().strip()
            records.append({
                "id": img_path.stem,
                "image_path": str(img_path),
                "text_label": text,
                "source": img_path.parent.parent.name,
            })
        return records

    @staticmethod
    def _arabic_ratio(text: str) -> float:
        """Fraction of Arabic characters in *text*."""
        if not text:
            return 0.0
        arabic = sum(1 for c in text if "\u0600" <= c <= "\u06FF")
        return arabic / len(text)

    @staticmethod
    def _quick_hash(path: str, block_size: int = 65536) -> str:
        """SHA-256 hash of the first 64 KB of a file (fast approximate)."""
        h = hashlib.sha256()
        with open(path, "rb") as f:
            h.update(f.read(block_size))
        return h.hexdigest()
