#!/usr/bin/env python3
"""
packages/medical/medical_dictionary_loader.py

محمّل القواميس الطبية الموحّد — يدمج مصادر متعددة في قاموس إنتاجي واحد
مع metadata كاملة + جدار حماية طبي يمنع التحويلات الخطرة.

المصادر المدعومة:
  1. data/arabic-medical-glossary/glossaries/final_unified_glossary.csv (124,756 زوج)
  2. malek_data TMX files (مستخرجة مسبقاً في /home/z/my-project/work/malek_terms_extracted.json)
  3. data/arabic_fixes.json (القاموس الإنتاجي الحالي - 180 إدخال)
  4. OCR_CORRECTIONS من hf-space/app_core.py (13 إدخال دوائي)

الاستخدام:
    from packages.medical.medical_dictionary_loader import MedicalDictionaryLoader
    loader = MedicalDictionaryLoader()
    glossary = loader.load_unified_glossary()
    corrections = loader.load_safe_ocr_corrections()
"""
from __future__ import annotations

import csv
import json
import logging
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── المسارات الافتراضية ─────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_GLOSSARY_CSV = PROJECT_ROOT / "data" / "arabic-medical-glossary" / "glossaries" / "final_unified_glossary.csv"
DEFAULT_MALEK_JSON = PROJECT_ROOT / "data" / "dictionaries" / "malek_data_terms.json"
DEFAULT_EXISTING_FIXES = PROJECT_ROOT / "data" / "arabic_fixes.json"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "dictionaries"

# ── أنماط الأمان الطبي ───────────────────────────────────────────────────────
# لا يجب أن تُطبَّق تصحيحات على هذه الأنماط (قد تُغيّر المعنى الطبي)

# الكلمات العربية النافية - إذا ظهرت كمفتاح، تجاوزها
ARABIC_NEGATION_PATTERNS = [
    r"^\s*لا\b",           # لا (بداية)
    r"^\s*ليس\b",
    r"^\s*لم\b",
    r"^\s*لن\b",
    r"^\s*غير\b",
    r"^\s*بدون\b",
    r"\bلا\s+يعطى\b",      # لا يعطى
    r"\bلا\s+يوجد\b",     # لا يوجد
    r"\bليس\s+لديه\b",     # ليس لديه
]

# الأرقام العشرية/الكسور - لا يجوز تصحيحها
DECIMAL_PATTERN = re.compile(r"\d+[.,]\d+")
# الجرعات الدوائية: رقم + وحدة (mg, ml, g, mcg, IU, etc.)
DRUG_DOSE_PATTERN = re.compile(
    r"\b\d+(\.\d+)?\s*(?:mg|ml|g|mcg|µg|ug|IU|units?|قطرات?|مل|جم|مجم)\b",
    re.IGNORECASE,
)
# التركيز الدوائي: نسبة مئوية + رقم
CONCENTRATION_PATTERN = re.compile(r"\b\d+(\.\d+)?\s*%")
# أرقام هندية عربية (٠٫٥, ١٫٢٥, ...)
ARABIC_INDIC_DIGITS = re.compile(r"[\u0660-\u0669\u06F0-\u06F9]")

# الكلمات الطبية الخطرة - يجب ألا تكون مفاتيح تصحيح
CRITICAL_MEDICAL_TERMS = {
    "ترامادول", "باراسيتامول", "باراسيتبمول", "ايبوبروفين", "ايبوروفين",
    "اموكسيسيلين", "ديكلوفيناك", "نابروكسين", "كوديين", "سالبوتامول",
    "لوراتادين", "سيتيريزين", "رانيتيدين", "فاموتيدين", "ميترونيدازول",
    "اوجمنتين", "اوجمينتين", "اوميبرازول", "ازيثرومايسين", "ازيثروميسين",
    "سيفترياكسون", "دوكسيسيكلين", "سيبروفلوكساسين", "لوفلوكساسين",
    "ميفيناميك", "بنادول", "ادفيل", "كاتافلام", "فولتارين",
    "مونتيلوكاست", "سودوافيدرين", "انديسيترون", "انالجين",
}


@dataclass
class DictionaryEntry:
    """مدخل موحد في القاموس الطبي."""
    key: str                    # المفتاح الأصلي
    value: str                  # القيمة الأصلية
    normalized_key: str         # المفتاح بعد التطبيع (للمقارنة فقط)
    source: str                 # مصدر البيانات
    category: str = "general"   # فئة المحتوى
    confidence: str = "medium" # high/medium/low
    section: str = ""           # قسم النشرة (إن وجد)
    conflicts: List[Dict[str, str]] = field(default_factory=list)
    safety_flag: str = "safe"   # safe/quarantined/dangerous

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "value": self.value,
            "normalized_key": self.normalized_key,
            "source": self.source,
            "category": self.category,
            "confidence": self.confidence,
            "section": self.section,
            "conflicts": self.conflicts,
            "safety_flag": self.safety_flag,
        }


# ── أدوات التطبيع ───────────────────────────────────────────────────────────

def normalize_arabic_key(text: str) -> str:
    """
    تطبيع المفتاح العربي للمقارنة فقط.
    ⚠️ هذا التطبيع لا يُغيّر القيمة المعروضة للمستخدم - يُستخدم فقط لاكتشاف التكرار/التعارض.
    """
    if not text:
        return ""
    s = text.strip()
    # إزالة الحركات
    s = re.sub(r"[\u064B-\u0652\u0670]", "", s)
    # توحيد الألف: أ إ آ ← ا
    s = re.sub(r"[\u0622\u0623\u0625]", "\u0627", s)
    # توحيد الياء: ى ← ي (الألف المقصورة)
    s = s.replace("\u0649", "\u064A")
    # توحيد الكاف: ک (فارسية) ← ك
    s = s.replace("\u06A9", "\u0643")
    # توحيد الياء الفارسية ی ← ي
    s = s.replace("\u06CC", "\u064A")
    # توحيد الهاء: ہ ← ه
    s = s.replace("\u06C1", "\u0647")
    # توحيد التاء المربوطة: ة → ه (للمقارنة فقط)
    s = s.replace("\u0629", "\u0647")
    # إزالة مسافات زائدة
    s = re.sub(r"\s+", " ", s)
    # Lowercase للأحرف اللاتينية
    s = s.lower()
    return s


# ── فحوصات الأمان الطبي ─────────────────────────────────────────────────────

def is_dangerous_key(key: str) -> Tuple[bool, str]:
    """
    تحقق مما إذا كان المفتاح خطيرًا لتطبيق تصحيح عليه.
    
    Returns:
        (is_dangerous: bool, reason: str)
    """
    if not key or not key.strip():
        return True, "empty_key"
    
    key_stripped = key.strip()
    
    # 1. أرقام عشرية (جرعات)
    if DECIMAL_PATTERN.search(key_stripped):
        return True, "decimal_dose"
    
    # 2. أرقام هندية عربية (٠٫٥ الخ)
    if ARABIC_INDIC_DIGITS.search(key_stripped):
        return True, "arabic_indic_digits"
    
    # 3. جرعات دوائية مع وحدة (mg, ml, ...)
    if DRUG_DOSE_PATTERN.search(key_stripped):
        return True, "drug_dose_unit"
    
    # 4. تركيز دوائي (5% مثلاً)
    if CONCENTRATION_PATTERN.search(key_stripped):
        return True, "concentration_percent"
    
    # 5. كلمة نافية عربية في بداية المفتاح
    for pattern in ARABIC_NEGATION_PATTERNS:
        if re.search(pattern, key_stripped):
            return True, f"negation:{pattern}"
    
    # 6. مفتاح رقمي خالص
    if key_stripped.replace(".", "").replace(",", "").isdigit():
        return True, "numeric_only"
    
    # 7. مفتاح قصير جدًا (حرف أو حرفين - غالبًا خطأ مطبعي)
    if len(key_stripped) < 2:
        return True, "too_short"
    
    # 8. مفتاح يحتوي على مسافة زائدة في البداية/النهاية
    if key != key_stripped:
        return True, "whitespace_padding"
    
    return False, ""


def is_critical_medical_term(text: str) -> bool:
    """تحقق مما إذا كان النص مصطلحًا طبيًا حرجًا (دواء مثلًا)."""
    if not text:
        return False
    text_lower = text.lower().strip()
    return text_lower in CRITICAL_MEDICAL_TERMS


# ── الفئة الرئيسية: MedicalDictionaryLoader ─────────────────────────────────

class MedicalDictionaryLoader:
    """
    محمّل القواميس الطبية الموحّد.
    
    يجمع البيانات من:
    - arabic-medical-glossary CSV (المصدر الموثوق الأساسي)
    - malek_data TMX (ذاكرة ترجمة طبية)
    - data/arabic_fixes.json (القاموس الإنتاجي الحالي)
    
    يطبّق:
    - جدار حماية طبي (لا تصحيحات على الجرعات/النفي/الأرقام)
    - إزالة التكرار عبر normalized_key
    - كشف التعارضات وحلها حسب أولوية المصدر
    - حفظ metadata كامل (source, original_key, normalized_key, confidence)
    """

    SOURCE_PRIORITY = [
        "production_arabic_fixes",    # أعلى أولوية - موجود في الإنتاج
        "arabic_medical_glossary",    # القاموس الطبي الموثوق (124K زوج)
        "malek_data_tmx",             # ذاكرة الترجمة من malek_data
        "ocr_corrections_hf_space",   # OCR_CORRECTIONS من hf-space
    ]

    def __init__(
        self,
        glossary_csv_path: Optional[Path] = None,
        malek_json_path: Optional[Path] = None,
        existing_fixes_path: Optional[Path] = None,
        output_dir: Optional[Path] = None,
    ):
        self.glossary_csv_path = glossary_csv_path or DEFAULT_GLOSSARY_CSV
        self.malek_json_path = malek_json_path or DEFAULT_MALEK_JSON
        self.existing_fixes_path = existing_fixes_path or DEFAULT_EXISTING_FIXES
        self.output_dir = output_dir or DEFAULT_OUTPUT_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ── قراءة arabic-medical-glossary CSV ─────────────────────────────────

    def load_arabic_medical_glossary(self) -> List[DictionaryEntry]:
        """قراءة القاموس الطبي الموحد من submodule."""
        if not self.glossary_csv_path.exists():
            logger.warning(f"arabic-medical-glossary CSV not found: {self.glossary_csv_path}")
            return []
        
        entries = []
        try:
            with open(self.glossary_csv_path, encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    en = (row.get("en") or "").strip()
                    ar = (row.get("ar") or "").strip()
                    if not en or not ar:
                        continue
                    source = (row.get("source") or "").strip()
                    entry_type = (row.get("type") or "term").strip()
                    section = (row.get("section") or "").strip()
                    confidence = (row.get("confidence") or "medium").strip().lower()
                    
                    # خذ اتجاه en→ar (للتحقق من التدقيق الإملائي الإنجليزي)
                    # لا حاجة لعكسه لأن الـspell_checker يعمل على العربية بشكل أساسي
                    entries.append(DictionaryEntry(
                        key=en,
                        value=ar,
                        normalized_key=normalize_arabic_key(en),
                        source=f"arabic_medical_glossary:{source}",
                        category=f"glossary_{entry_type}",
                        confidence=confidence,
                        section=section,
                        safety_flag="safe",
                    ))
        except Exception as e:
            logger.error(f"Failed to load arabic-medical-glossary: {e}")
        return entries

    # ── قراءة malek_data TMX terms ────────────────────────────────────────

    def load_malek_data_terms(self) -> List[DictionaryEntry]:
        """قراءة المصطلحات المستخرجة من malek_data TMX."""
        if not self.malek_json_path.exists():
            logger.warning(f"malek_data JSON not found: {self.malek_json_path}")
            return []
        
        entries = []
        try:
            with open(self.malek_json_path, encoding="utf-8") as f:
                data = json.load(f)
            
            excluded_files = {"التمويل الاصغر.tmx"}  # غير طبي
            
            for entry in data.get("entries", []):
                en = (entry.get("en") or "").strip()
                ar = (entry.get("ar") or "").strip()
                # الحصول على اسم الملف المصدر من field المخصص
                tuid = entry.get("tuid", "")
                source_file = "unknown"
                # محاولة استخراج اسم الملف من source field
                src_field = entry.get("source", "")
                if src_field:
                    source_file = src_field.split(":")[0][:60]
                
                if not en or not ar:
                    continue
                if any(x in entry.get("_file", "") for x in excluded_files):
                    continue
                
                entries.append(DictionaryEntry(
                    key=en,
                    value=ar,
                    normalized_key=normalize_arabic_key(en),
                    source=f"malek_data:{source_file}",
                    category="translation_memory",
                    confidence="medium",
                    section="",
                    safety_flag="safe",
                ))
        except Exception as e:
            logger.error(f"Failed to load malek_data: {e}")
        return entries

    # ── قراءة arabic_fixes.json الإنتاجي ──────────────────────────────────

    def load_existing_arabic_fixes(self) -> List[DictionaryEntry]:
        """قراءة قاموس arabic_fixes.json الحالي."""
        if not self.existing_fixes_path.exists():
            logger.warning(f"arabic_fixes.json not found: {self.existing_fixes_path}")
            return []
        
        entries = []
        try:
            with open(self.existing_fixes_path, encoding="utf-8") as f:
                data = json.load(f)
            for key, value in data.items():
                entries.append(DictionaryEntry(
                    key=key,
                    value=value,
                    normalized_key=normalize_arabic_key(key),
                    source="production_arabic_fixes",
                    category="ocr_correction",
                    confidence="high",
                    section="",
                    safety_flag="safe",
                ))
        except Exception as e:
            logger.error(f"Failed to load arabic_fixes.json: {e}")
        return entries

    # ── كشف وحل التعارضات ─────────────────────────────────────────────────

    def _source_priority(self, entry: DictionaryEntry) -> int:
        """الحصول على أولوية المصدر (0=أعلى، أكبر=أدنى)."""
        src_prefix = entry.source.split(":")[0]
        try:
            return self.SOURCE_PRIORITY.index(src_prefix)
        except ValueError:
            return len(self.SOURCE_PRIORITY)  # أدنى أولوية

    def detect_and_resolve_conflicts(
        self, entries: List[DictionaryEntry]
    ) -> Tuple[List[DictionaryEntry], List[Dict[str, Any]]]:
        """
        كشف التعارضات وحلها حسب أولوية المصدر.
        
        تعارض = نفس normalized_key مع قيم مختلفة.
        الحل = الاحتفاظ بالأعلى أولوية، تسجيل الباقي كـ conflicts.
        """
        by_key: Dict[str, List[DictionaryEntry]] = {}
        for e in entries:
            by_key.setdefault(e.normalized_key, []).append(e)
        
        conflicts: List[Dict[str, Any]] = []
        resolved: List[DictionaryEntry] = []
        
        for nkey, group in by_key.items():
            if len(group) == 1:
                resolved.append(group[0])
                continue
            
            # تحقق من وجود قيم مختلفة
            values = set(e.value for e in group)
            if len(values) == 1:
                # كلها متفقون - خذ واحدًا واحفظ الباقي في conflicts metadata
                winner = max(group, key=lambda e: self._source_priority(e))
                winner.conflicts = [
                    {"source": e.source, "value": e.value, "decision": "duplicate_same_value"}
                    for e in group if e is not winner
                ]
                resolved.append(winner)
            else:
                # تعارض حقيقي - اختر حسب الأولوية
                sorted_group = sorted(group, key=self._source_priority)
                winner = sorted_group[0]
                loser_conflicts = [
                    {
                        "source": e.source,
                        "value": e.value,
                        "decision": f"lost_to:{winner.source}",
                    }
                    for e in sorted_group[1:]
                ]
                winner.conflicts = loser_conflicts
                resolved.append(winner)
                
                conflicts.append({
                    "normalized_key": nkey,
                    "winner_source": winner.source,
                    "winner_value": winner.value,
                    "losers": loser_conflicts,
                })
        
        return resolved, conflicts

    # ── تطبيق جدار الحماية الطبي ──────────────────────────────────────────

    def apply_medical_safety_firewall(
        self, entries: List[DictionaryEntry]
    ) -> Tuple[List[DictionaryEntry], List[DictionaryEntry]]:
        """
        تطبيق جدار الحماية الطبي - عزل المدخلات الخطرة.
        
        Returns:
            (safe_entries, quarantined_entries)
        """
        safe = []
        quarantined = []
        for entry in entries:
            # فحص المفتاح
            dangerous, reason = is_dangerous_key(entry.key)
            if dangerous:
                entry.safety_flag = f"quarantined:{reason}"
                quarantined.append(entry)
                continue
            
            # فحص القيمة - لا يجب أن تكون القيمة فارغة أو مطابقة للمفتاح كثيرًا
            if not entry.value.strip():
                entry.safety_flag = "quarantined:empty_value"
                quarantined.append(entry)
                continue
            
            # إذا كان المفتاح مصطلحًا طبيًا حرجًا (دواء)، تأكد أن القيمة هي نفسها
            # لا نريد إضافة "ترامادول" → شيء آخر كقاموس تصحيح
            if is_critical_medical_term(entry.key):
                # هذا المصطلح الطبي يجب أن لا يكون مفتاح تصحيح إملائي
                # (يحمي من استبدال اسم دواء في نتيجة التصحيح)
                entry.safety_flag = "quarantined:critical_medical_term_as_key"
                quarantined.append(entry)
                continue
            
            safe.append(entry)
        
        return safe, quarantined

    # ── واجهة التحميل الموحدة ─────────────────────────────────────────────

    def load_unified_glossary(
        self, apply_safety: bool = True
    ) -> Dict[str, Any]:
        """
        تحميل القاموس الطبي الموحد من جميع المصادر.
        
        Returns dict with:
            - 'entries': قائمة DictionaryEntry.to_dict()
            - 'conflicts': قائمة التعارضات
            - 'quarantined': قائمة المدخلات المعزولة
            - 'stats': إحصائيات
            - 'sources': قائمة المصادر المستخدمة
        """
        all_entries: List[DictionaryEntry] = []
        sources_used = []
        
        # 1. القاموس الإنتاجي الحالي (أعلى أولوية)
        existing = self.load_existing_arabic_fixes()
        if existing:
            all_entries.extend(existing)
            sources_used.append({
                "name": "production_arabic_fixes",
                "path": str(self.existing_fixes_path),
                "entries_loaded": len(existing),
            })
        
        # 2. arabic-medical-glossary (المصدر الطبي الموثوق)
        amg = self.load_arabic_medical_glossary()
        if amg:
            all_entries.extend(amg)
            sources_used.append({
                "name": "arabic_medical_glossary",
                "path": str(self.glossary_csv_path),
                "entries_loaded": len(amg),
            })
        
        # 3. malek_data TMX (ذاكرة الترجمة)
        malek = self.load_malek_data_terms()
        if malek:
            all_entries.extend(malek)
            sources_used.append({
                "name": "malek_data_tmx",
                "path": str(self.malek_json_path),
                "entries_loaded": len(malek),
            })
        
        # تطبيق جدار الحماية الطبي
        if apply_safety:
            safe_entries, quarantined = self.apply_medical_safety_firewall(all_entries)
        else:
            safe_entries = all_entries
            quarantined = []
        
        # كشف وحل التعارضات
        resolved, conflicts = self.detect_and_resolve_conflicts(safe_entries)
        
        # إحصائيات
        stats = {
            "total_loaded": len(all_entries),
            "safe_after_firewall": len(safe_entries),
            "quarantined": len(quarantined),
            "after_dedup_and_conflict_resolution": len(resolved),
            "conflicts_detected": len(conflicts),
            "by_source": {},
            "by_category": {},
            "by_confidence": {},
        }
        for e in resolved:
            src_prefix = e.source.split(":")[0]
            stats["by_source"][src_prefix] = stats["by_source"].get(src_prefix, 0) + 1
            stats["by_category"][e.category] = stats["by_category"].get(e.category, 0) + 1
            stats["by_confidence"][e.confidence] = stats["by_confidence"].get(e.confidence, 0) + 1
        
        return {
            "entries": [e.to_dict() for e in resolved],
            "conflicts": conflicts,
            "quarantined": [e.to_dict() for e in quarantined],
            "stats": stats,
            "sources": sources_used,
        }

    # ── تصدير ──────────────────────────────────────────────────────────────

    def export_to_json(self, data: Dict[str, Any], path: Path) -> None:
        """تصدير القاموس الموحد إلى JSON."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"Exported unified glossary to {path}")

    def export_safe_ocr_corrections(self, data: Dict[str, Any], path: Path) -> None:
        """
        تصدير قاموس تصحيحات OCR الآمن فقط (key → value) بدون metadata.
        مناسب للاستخدام المباشر في HybridSpellChecker._arabic_fixes.
        """
        corrections = {}
        for entry in data["entries"]:
            # فقط المدخلات من نوع ocr_correction (وليس glossary_term)
            if entry.get("category") == "ocr_correction" or "fixes" in entry.get("source", ""):
                corrections[entry["key"]] = entry["value"]
        
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(corrections, f, ensure_ascii=False, indent=2)
        logger.info(f"Exported {len(corrections)} safe OCR corrections to {path}")


# ── نقطة دخول CLI ───────────────────────────────────────────────────────────

def main():
    """CLI entry point for testing the loader."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    
    loader = MedicalDictionaryLoader()
    print(f"Project root: {PROJECT_ROOT}")
    print(f"Glossary CSV: {loader.glossary_csv_path} ({'EXISTS' if loader.glossary_csv_path.exists() else 'MISSING'})")
    print(f"Malek JSON:   {loader.malek_json_path} ({'EXISTS' if loader.malek_json_path.exists() else 'MISSING'})")
    print(f"Existing fixes: {loader.existing_fixes_path} ({'EXISTS' if loader.existing_fixes_path.exists() else 'MISSING'})")
    print(f"Output dir:   {loader.output_dir}")
    print()
    
    result = loader.load_unified_glossary(apply_safety=True)
    
    stats = result["stats"]
    print("=== Unified Glossary Statistics ===")
    for k, v in stats.items():
        if isinstance(v, dict):
            print(f"  {k}:")
            for sk, sv in sorted(v.items(), key=lambda x: -x[1] if isinstance(x[1], int) else 0)[:10]:
                print(f"    {sk}: {sv}")
        else:
            print(f"  {k}: {v}")
    
    print(f"\n=== Sources used ({len(result['sources'])}) ===")
    for s in result["sources"]:
        print(f"  {s['name']}: {s['entries_loaded']} entries from {s['path']}")
    
    print(f"\n=== Conflicts ({len(result['conflicts'])}) ===")
    for c in result["conflicts"][:5]:
        print(f"  key={c['normalized_key']!r}")
        print(f"    winner: {c['winner_source']} → {c['winner_value']!r}")
        for l in c["losers"]:
            print(f"    loser:  {l['source']} → {l['value']!r}")
    
    print(f"\n=== Quarantined entries ({len(result['quarantined'])}) ===")
    by_reason = {}
    for q in result["quarantined"]:
        reason = q.get("safety_flag", "unknown")
        by_reason[reason] = by_reason.get(reason, 0) + 1
    for reason, cnt in sorted(by_reason.items(), key=lambda x: -x[1])[:10]:
        print(f"  {reason}: {cnt}")


if __name__ == "__main__":
    main()
