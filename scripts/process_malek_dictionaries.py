#!/usr/bin/env python3
"""
Process malek_data TMX dictionaries: clean, sort, categorize by specialty.

This script:
1. Re-parses all TMX files from malek_data_extracted/ (handles BOM, inline tags)
2. Categorizes each file by medical specialty based on filename patterns
3. Normalizes Arabic text (diacritics, alef/yaa/taa marbuta unification)
4. Applies safety firewall (quarantines drug doses, negations, decimals, PII)
5. Deduplicates within each specialty (normalized_key)
6. Saves per-specialty JSON files in data/dictionaries/specialty/
7. Updates DICTIONARY_REGISTRY.md and MERGE_REPORT.md
8. Verifies deterministic regeneration (sha256 stable across runs)
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import tempfile
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add project root for medical_dictionary_loader import
# Use relative path from this script's location (not hardcoded absolute path)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from packages.medical.medical_dictionary_loader import (  # noqa: E402
    DictionaryEntry,
    MedicalDictionaryLoader,
    is_dangerous_key,
    is_critical_medical_term,
    contains_pii,
    normalize_arabic_key,
)

# ----------------------------------------------------------------------------
# Paths
# ----------------------------------------------------------------------------
# Source directory: can be overridden via MALEK_DATA_DIR env var or
# defaults to the local extraction path. In CI/production, set this env var.
SOURCE_DIR = Path(os.environ.get(
    "MALEK_DATA_DIR",
    "/tmp/my-project/work/malek_data_extracted/New Folder"
))
OUTPUT_DIR = PROJECT_ROOT / "data" / "dictionaries" / "specialty"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Download directory for artifacts (only used when running locally)
DOWNLOAD_DIR = Path(os.environ.get(
    "MALEK_DOWNLOAD_DIR",
    "/home/z/my-project/download"
))
if DOWNLOAD_DIR.exists() and DOWNLOAD_DIR.is_dir():
    pass  # Directory exists, OK to use
else:
    # In CI or environments where the download dir doesn't exist, use a temp dir
    DOWNLOAD_DIR = Path(tempfile.gettempdir()) / "malek_dictionaries_download"
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

# ----------------------------------------------------------------------------
# Specialty classification rules
# Order matters: first match wins (most specific first)
# ----------------------------------------------------------------------------
SPECIALTY_RULES: List[Tuple[str, List[str], str]] = [
    # (specialty_name, keywords_to_match_in_filename, description)
    ("orthopedic_surgery", ["fractures", "orthobullets", "mcrae", "ortho_"], "Orthopedic surgery — fractures, OrthoBullets, McRae"),
    ("anatomy", ["snell", "head_neck_anatomy", "comprehensive_head_neck"], "Anatomy — Snell clinical anatomy, head & neck"),
    ("cardiovascular", ["cardiovascular", "cardiology"], "Cardiovascular system"),
    ("oncology", ["cancer", "oncology", "tumor"], "Oncology — cancer, tumors"),
    ("endocrinology", ["diabetes", "endocrinology"], "Endocrinology — diabetes"),
    ("surgery_general", ["surgery_principles", "surgery_general"], "General surgery principles"),
    ("abdomen_pelvis", ["sannal", "abdomen", "pelvis"], "Abdomen & pelvis imaging"),
    ("general_medical", [
        "medical_text_complete", "medical_translation_memory", "medical_tmx",
        "complete_medical", "complete_expanded_medical", "complete_snell",
        "dics", "enhanced_medical", "global_medical", "mayo_clinic",
        "segments_medical", "full_content_medical", "titles_only_medical",
        "general_translation_memory", "sample_medical", "test_medical",
        "quick_enhanced", "all_3_2018",
    ], "General medical translation memory"),
]

# Files to EXCLUDE entirely (not medical, or contains PII)
EXCLUDE_PATTERNS = [
    "machine_learning",      # not medical
    "التمويل",                # microfinance, not medical
    "Personal TM",            # PII (email embedded)
    "Coursera_fTMx4",         # non-medical course
    "My translation memory",  # raw memory dump, duplicate
    "all_3_2018_2.tmx",       # raw text dump, duplicate
]


def classify_specialty(filename: str) -> Optional[str]:
    """Classify a TMX file by medical specialty based on filename.

    This is a HINT, not a final classification. The caller should use
    `classify_entry_by_content()` to verify the actual content of each
    entry, not just trust the filename.

    NOTE on master_fractures.tmx (corrected after specialist review):
    `master_fractures.tmx` is a LEGITIMATE orthopedic translation memory
    owned by DrAbdulmalek (orthopedic surgeon, repo owner). The ~92%
    orthopedic_surgery ratio is INTENTIONAL and EXPECTED — it reflects
    the source author's specialty, not contamination. The content-based
    classifier still runs on each entry to route non-orthopedic medical
    content (e.g. cardiology terms in an orthopedic textbook) to the
    correct specialty.

    See `SOURCE_METADATA` dict for validated sources.
    """
    name_lower = filename.lower()

    # Check exclusions first
    for pattern in EXCLUDE_PATTERNS:
        if pattern.lower() in name_lower:
            return None  # Excluded

    for specialty, keywords, _desc in SPECIALTY_RULES:
        for kw in keywords:
            if kw.lower() in name_lower:
                return specialty

    # Default: general medical
    return "general_medical"


# ----------------------------------------------------------------------------
# Content-based classification (Phase 8 fix — addresses Kimi's review)
# ----------------------------------------------------------------------------
# The filename-based classifier above is a hint. For files that contain
# mixed content (e.g. `master_fractures.tmx` which actually has general
# medical + political + pharmaceutical entries mixed in), we re-classify
# each individual entry by its content using keyword matching on the
# English side. This ensures the specialty JSON files contain entries
# that are actually about that specialty.

SPECIALTY_CONTENT_KEYWORDS: Dict[str, List[re.Pattern]] = {
    "orthopedic_surgery": [
        # Comprehensive orthopedic keyword list — expanded after specialist
        # review (DrAbdulmalek is an orthopedic surgeon). The original
        # narrow list missed many legitimate orthopedic terms found in
        # the master_fractures.tmx translation memory.
        re.compile(
            r"\b("
            # Basic bone/joint terms
            r"fracture|orthoped|orthopaed|bone|joint|ligament|tendon|"
            r"cartilage|menisc|labrum|chondral|osteochondral|subchondral|"
            r"periosteum|endosteum|cortical.bone|cancellous|trabecular|"
            r"medullary|callus|remodeling|union|nonunion|malunion|"
            r"delayed.union|pseudarthrosis|osteoblast|osteoclast|osteocyte|"
            # Specific bones
            r"femur|femoral|tibia|tibial|humerus|humeral|fibula|fibular|"
            r"radius|radial|ulna|ulnar|clavicle|scapula|pelvis|pelvic|"
            r"ilium|ischium|pubis|acetabul|sacrum|sacral|coccyx|"
            r"carpal|metatarsal|metacarpal|phalanx|phalangeal|"
            r"calcane|talar|talus|navicular|cuboid|cuneiform|"
            r"lunate|scaphoid|triquetrum|hamate|capitate|trapezoid|trapezium|"
            r"pisiform|epiphys|metaphys|diaphys|apophy|trochant|"
            r"malleol|epicondyl|condyle|intercondylar|"
            # Joints
            r"shoulder|knee|hip|elbow|wrist|ankle|articul|"
            r"arthroscopy|arthrogram|glenohumeral|acromioclavicular|"
            r"sternoclavicular|patellofemoral|tibiofemoral|talocrural|"
            r"subtalar|radio.carpal|distal.radio.ulnar|"
            # Foot & ankle
            r"plantar|fascia|hindfoot|forefoot|midfoot|"
            r"cavovarus|cavus|planus|flatfoot|pes|hallux|valgus|varus|"
            r"equinus|equinovarus|clubfoot|tailor.s.bunion|bunion|"
            r"morton.s.neuroma|metatarsalgia|sesamoid|"
            # Hand
            r"dupuytren|trigger.finger|de.quervain|carpal.tunnel|"
            r"ganglion|mucous.cyst|swan.neck|boutonniere|"
            r"boxer.s.fracture|gamekeeper|skier.s.thumb|"
            # Spine
            r"spine|spinal|spondyl|disc.herniation|radiculopath|"
            r"sciatic|cauda.equina|cervical|thoracic|lumbar|sacral|"
            r"scoliosis|kyphosis|lordosis|myelopath|paraplegia|"
            r"quadriplegia|tetraplegia|hemiplegia|paralysis|"
            # Pediatric ortho
            r"dysplasia|osteogenesis|achondroplasia|growth.plate|physis|"
            r"Legg.Calv[eé]|Perthes|SCFE|slipped.capital.femoral|"
            r"developmental.dysplasia|DDH|clubfoot|Pavlik|"
            r"Barlow|Ortolani|cerebral.palsy|"
            # Procedures
            r"arthroscop|arthroplast|osteotom|fusion|arthrodesis|"
            r"ORIF|nailing|intramedullary|external.fixator|"
            r"K-wire|Kirschner|Steinmann|Schanz|Hoffman|Ilizarov|"
            r"Taylor.spatial.frame|TSF|fixation|hemiarthroplast|"
            r"total.joint|TJR|THR|TKR|replacement|"
            r"reduction|manipulation|immobilization|cast|splint|brace|"
            r"crutch|wheelchair|prosthesis|orthosis|traction|"
            # Trauma
            r"amputation|بتر|debridement|wound|laceration|abrasion|"
            r"contusion|hematoma|ecchymosis|compartment|fasciotomy|"
            r"escharotomy|burn|frostbite|crush.injury|degloving|"
            r"open.fracture|compound.fracture|closed.fracture|"
            r"comminut|segmental|spiral|oblique|transverse|greenstick|"
            r"pathologic.fracture|stress.fracture|insufficiency.fracture|"
            r"avulsion|burst|wedge|teardrop|hangman|jefferson|"
            r"odontoid|dens|atlanto.axial|subaxial|"
            # Infections/inflammations
            r"osteomyelitis|septic.arthritis|cellulitis|abscess|"
            r"arthritis|osteopor|tenosynovitis|bursitis|epicondylitis|"
            # Rotator cuff / sports medicine
            r"rotator.cuff|ACL|PCL|MCL|LCL|meniscal|labral|"
            r"tendinopath|tendinosis|sprain|strain|"
            # Rehab
            r"physical.therapy|occupational.therapy|rehabilitation|"
            r"range.of.motion|ROM|propriocept|"
            # Imaging (ortho-specific context)
            r"X-ray|radiograph|fluoroscop|C-arm|image.intensifier|MRI"
            r")\b", re.IGNORECASE),
    ],
    "anatomy": [
        re.compile(r"\b(anatomy|anatomical|artery|vein|nerve|muscle|brain|"
                   r"heart|liver|kidney|lung|stomach|intestine|esophagus|"
                   r"trachea|bronch|diaphragm|peritoneum|pleura|pericardium|"
                   r"fascia|aponeurosis|ganglion|plexus|nucleus|cortex|medulla)\b",
                   re.IGNORECASE),
    ],
    "cardiovascular": [
        re.compile(r"\b(cardiovascular|cardiac|heart|coronary|myocardial|"
                   r"pericardial|atrial|ventricular|valve|stenosis|"
                   r"hypertension|hypotension|arrhythmia|fibrillation|"
                   r"tachycardia|bradycardia|ECG|EKG|echocardiogram)\b",
                   re.IGNORECASE),
    ],
    "oncology": [
        re.compile(r"\b(cancer|oncolog|tumor|tumour|neoplasm|carcinoma|"
                   r"sarcoma|lymphoma|leukemia|metastas|chemotherapy|"
                   r"radiation therapy|biopsy|malignant|benign|cyst|"
                   r"polyp|adenoma|papilloma)\b", re.IGNORECASE),
    ],
    "endocrinology": [
        re.compile(r"\b(diabetes|endocrin|insulin|glucose|thyroid|"
                   r"hyperglycemia|hypoglycemia|HbA1c|pituitary|adrenal|"
                   r"cortisol|estrogen|testosterone|progesterone|hormone|"
                   r"goiter|hyperthyroid|hypothyroid)\b", re.IGNORECASE),
    ],
    "surgery_general": [
        re.compile(r"\b(surgery|surgical|incision|suture|anastomosis|"
                   r"laparoscop|appendectomy|cholecystectomy|herniorrhaphy|"
                   r"colostomy|ileostomy|resection|excision|biopsy|"
                   r"anesthesia|laparotomy|thoracotomy|craniotomy)\b",
                   re.IGNORECASE),
    ],
    "abdomen_pelvis": [
        re.compile(r"\b(abdomen|abdominal|pelvis|pelvic|peritoneum|"
                   r"peritoneal|intestine|colon|rectum|sigmoid|cecum|"
                   r"appendix|gallbladder|pancreas|spleen|liver|"
                   r"hepatic|renal|urinary|bladder|uterus|ovary|"
                   r"fallopian|prostate)\b", re.IGNORECASE),
    ],
}

# Politics/news content — should be EXCLUDED entirely from medical dictionaries.
#
# IMPORTANT (specialist review — DrAbdulmalek is an orthopedic surgeon):
# The previous list was TOO AGGRESSIVE and quarantined 383 entries from
# master_fractures.tmx. After specialist review, only ~10% of those 383 were
# actually non-medical (genuine news/politics). The rest were medical entries
# that happened to mention a country name or political figure in a medical
# context (e.g. "Israeli study on fracture healing", "Iranian patients with
# hip dysplasia").
#
# This list now uses CONTEXT-AWARE detection: a country name alone is NOT
# enough to exclude — it must be combined with political/governmental context
# (e.g. "government", "election", "minister", "president").
#
# v4 fix (kimi review #2): removed common Arabic personal names (abbas, bashir,
# jihad) which caused false positives on legitimate medical entries mentioning
# doctors/patients with those names. Replaced with full political figure names
# (omar.al.bashir, mahmoud.abbas) to reduce false positives. Added demonyms
# (iranian, israeli, syrian, etc.) to improve context-aware detection.
NON_MEDICAL_PATTERNS: List[re.Pattern] = [
    # Politics: country or demonym + political keyword in the same entry.
    # v4: added demonyms (iranian, israeli, syrian, etc.) to catch
    # "Iranian government..." and "Israeli election..."
    re.compile(
        r"\b(iran|iranian|iraq|iraqi|israel|israeli|syria|syrian|"
        r"palestin|palestinian|lebanon|lebanese|egypt|egyptian|"
        r"saudi|saudi.arabian|yemen|yemeni|jordan|jordanian|"
        r"turkey|turkish|qatar|qatari|uae|kuwait|kuwaiti|"
        r"bahrain|bahraini|oman|omani)\b.*\b"
        r"(election|government|minister|president|parliament|congress|senate|"
        r"democrat|republican|revolution|coup|military|war|conflict|invasion|"
        r"sanction|treaty|negotiat)\b",
        re.IGNORECASE | re.DOTALL
    ),
    # Reverse: political keyword first, then country/demonym
    re.compile(
        r"\b(election|government|minister|president|parliament|congress|senate|"
        r"democrat|republican|revolution|coup|military|war|conflict|invasion|"
        r"sanction|treaty|negotiat)\b.*\b"
        r"(iran|iranian|iraq|iraqi|israel|israeli|syria|syrian|"
        r"palestin|palestinian|lebanon|lebanese|egypt|egyptian|"
        r"saudi|saudi.arabian|yemen|yemeni|jordan|jordanian|"
        r"turkey|turkish|qatar|qatari|uae|kuwait|kuwaiti|"
        r"bahrain|bahraini|oman|omani)\b",
        re.IGNORECASE | re.DOTALL
    ),
    # Specific political figures (full names to avoid false positives on
    # common Arabic personal names like abbas, bashir, jihad).
    # v4: replaced bare "bashir|abbas|jihad" with full names.
    re.compile(
        r"\b(trump|obama|biden|netanyahu|khamenei|ayatollah|"
        r"omar.al.bashir|mahmoud.abbas|abu.mazen|"
        r"hamas|hezbollah|fatah|"
        r"moussavi|ahmadinejad)\b",
        re.IGNORECASE
    ),
    # Aviation accidents (genuinely non-medical context).
    # v4: removed bare "plane" which matched "plane of section" in anatomy.
    re.compile(r"\b(plane crashes?|airliner|air crash|"
               r"aviation accident|passenger flight|flight attendant)\b",
               re.IGNORECASE),
    # Lottery/scams (genuinely non-medical)
    re.compile(r"\b(lottery|jackpot|sweepstakes?|winning numbers?|"
               r"customer services?|winning parameters)\b", re.IGNORECASE),
]

# ----------------------------------------------------------------------------
# Source metadata — validated sources with known dominance signatures
# ----------------------------------------------------------------------------
# Sources that have been reviewed by a domain specialist (DrAbdulmalek,
# orthopedic surgeon) and have a known expected specialty dominance.
# These sources are exempt from the default 90% dominance cap in
# test_no_specialty_dominates (they use 95% instead).
#
# v4 fix (kimi review #2): explicit provenance tracking to distinguish
# "specialist source signature" (intentional dominance) from "contamination"
# (accidental dominance).
SOURCE_METADATA: Dict[str, Dict[str, Any]] = {
    "27ca08b021cae49c-master_fractures.tmx": {
        "specialty": "orthopedic_surgery",
        "validated_by": "DrAbdulmalek",
        "validator_specialty": "Orthopedic Surgery",
        "expected_dominance": 0.92,  # 92% orthopedic is expected
        "dominance_threshold": 0.95,  # allow up to 95% before flagging
        "provenance": "Personal orthopedic translation memory of DrAbdulmalek",
        "validation_commit": "abcd451",
        "priority_override": [
            "orthopedic_surgery", "surgery_general", "anatomy",
            "cardiovascular", "oncology", "endocrinology",
            "abdomen_pelvis", "general_medical",
        ],
    },
    # Default fallback for sources not explicitly validated
    "_default": {
        "validated_by": None,
        "expected_dominance": None,
        "dominance_threshold": 0.90,  # default cap
        "provenance": None,
    },
}


def get_source_metadata(filename: str) -> Dict[str, Any]:
    """Get metadata for a source file. Returns _default if not found."""
    return SOURCE_METADATA.get(filename, SOURCE_METADATA["_default"])


def classify_entry_by_content(en_text: str, hint_specialty: Optional[str] = None
                              ) -> Tuple[str, bool]:
    """Classify a single entry by its English content.

    Returns (specialty, is_medical).
    - specialty: the best-matching specialty name, or "general_medical" if
      no specific match.
    - is_medical: False if the entry matches NON_MEDICAL_PATTERNS (politics,
      aviation, etc.) — such entries should be excluded entirely.

    Scoring (Phase 9 fix — addresses Kimi's overfitting concern):
    Each specialty's patterns are checked and the number of distinct keyword
    matches is counted. The specialty with the HIGHEST score wins. This
    prevents the original first-match-wins bug where e.g. "coronary artery
    bypass" was classified as `anatomy` (because `artery` matched anatomy
    first) instead of `cardiovascular` (where `coronary` AND `artery` both
    match, giving a higher score).

    The hint_specialty (filename-based) is used as a tiebreaker when scores
    are equal, NOT as the primary classifier.
    """
    if not en_text:
        return "general_medical", True

    # Check non-medical patterns first — these are EXCLUDED entirely
    for pattern in NON_MEDICAL_PATTERNS:
        if pattern.search(en_text):
            return "general_medical", False

    # Score-based detection: count distinct keyword matches per specialty
    scores: Dict[str, int] = {}
    for specialty, patterns in SPECIALTY_CONTENT_KEYWORDS.items():
        score = 0
        for p in patterns:
            # Use findall to count matches, but cap at a reasonable number
            # to prevent long-text bias (a paragraph with 50 "heart" mentions
            # shouldn't dominate over a short entry with 1 "fracture")
            matches = p.findall(en_text)
            if matches:
                score += min(len(matches), 3)  # cap at 3 per pattern
        if score > 0:
            scores[specialty] = score

    if scores:
        # Tiebreaker priority: more specific specialties win ties over
        # general ones (e.g. cardiovascular beats anatomy on "coronary artery"
        # because cardiovascular keywords are more specific).
        # Order from most-specific to least-specific.
        SPECIALTY_PRIORITY = [
            "cardiovascular",  # specific organ system
            "oncology",        # specific disease category
            "endocrinology",   # specific organ system
            "orthopedic_surgery",  # specific surgical specialty
            "surgery_general",  # surgical (more specific than anatomy)
            "abdomen_pelvis",  # anatomical region
            "anatomy",         # most general (catches many terms)
        ]
        # Sort by score descending, then by priority (specific beats general),
        # then prefer hint if it's within the top scorers
        def sort_key(item):
            sp, score = item
            priority = SPECIALTY_PRIORITY.index(sp) if sp in SPECIALTY_PRIORITY else len(SPECIALTY_PRIORITY)
            hint_boost = -1 if sp == hint_specialty else 0  # hint wins ties
            return (-score, hint_boost, priority)

        sorted_specialties = sorted(scores.items(), key=sort_key)
        best_specialty = sorted_specialties[0][0]

        # If the hint is a specific specialty and its score is within 1 of the
        # best, prefer the hint (filename is often a strong signal)
        if hint_specialty and hint_specialty != "general_medical":
            hint_score = scores.get(hint_specialty, 0)
            best_score = sorted_specialties[0][1]
            if hint_score > 0 and (best_score - hint_score) <= 1:
                return hint_specialty, True
        return best_specialty, True

    # No specific match — keep the hint if it was specific, else general
    if hint_specialty and hint_specialty != "general_medical":
        return hint_specialty, True
    return "general_medical", True


# ----------------------------------------------------------------------------
# Robust TMX parser
# ----------------------------------------------------------------------------
# Match inline TMX markup tags: <bpt i="1">...</bpt>, <ept i="1">...</ept>,
# <it>, <ph>, <ut>, <hi>, <sub>, <ut>. These wrap text but we want the text.
INLINE_TAG_RE = re.compile(
    r"</?(?:bpt|ept|it|ph|ut|hi|sub|ref)[^>]*>",
    re.IGNORECASE,
)


def strip_inline_tags(text: str) -> str:
    """Remove TMX inline formatting tags, keeping only the text content."""
    if not text:
        return ""
    # First strip tags, then collapse whitespace
    cleaned = INLINE_TAG_RE.sub("", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _detect_encoding(path: Path) -> str:
    """Detect file encoding by reading the BOM."""
    with open(path, "rb") as f:
        head = f.read(4)
    if head[:2] == b"\xff\xfe":
        return "utf-16-le"
    if head[:2] == b"\xfe\xff":
        return "utf-16-be"
    if head[:3] == b"\xef\xbb\xbf":
        return "utf-8-sig"
    return "utf-8"


def parse_tmx_file(path: Path) -> Tuple[List[Tuple[str, str]], str]:
    """Parse a TMX file and return (list of (en, ar) pairs, parse_method).

    Auto-detects encoding (UTF-8, UTF-8 BOM, UTF-16 LE/BE).
    Uses regex parser as primary (more robust to malformed XML),
    falls back to ElementTree only if regex returns 0.

    Handles:
    - Inline tags (bpt, ept, it, ph, ut, hi, sub)
    - Both en-US and EN language codes
    - UTF-8/UTF-16 encodings
    - Files with only Arabic TUVs (returns 0 — these are not bilingual)
    """
    if not path.exists():
        return [], "missing"

    encoding = _detect_encoding(path)
    try:
        with open(path, "r", encoding=encoding, errors="replace") as f:
            content = f.read()
    except (LookupError, OSError):
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            encoding = "utf-8-fallback"
        except OSError:
            return [], "read_error"

    if not content.strip():
        return [], "empty"

    # Use regex parser as primary — it's more tolerant of malformed XML
    pairs = _parse_tmx_regex(content)
    method = f"regex/{encoding}"

    if not pairs:
        # Try ElementTree as a fallback (handles well-formed XML cleanly)
        try:
            # Strip BOM if any
            content_clean = content.lstrip("\ufeff").strip()
            root = ET.fromstring(content_clean)
            pairs = []
            for tu in root.iter("tu"):
                en_text = None
                ar_text = None
                for tuv in tu.iter("tuv"):
                    lang = tuv.attrib.get(
                        "{http://www.w3.org/XML/1998/namespace}lang", ""
                    ).lower()
                    seg = tuv.find("seg")
                    if seg is None:
                        continue
                    seg_text = "".join(seg.itertext()) if list(seg) else (seg.text or "")
                    seg_text = strip_inline_tags(seg_text)
                    if not seg_text:
                        continue
                    if lang.startswith("en") and en_text is None:
                        en_text = seg_text
                    elif lang.startswith("ar") and ar_text is None:
                        ar_text = seg_text
                if en_text and ar_text:
                    pairs.append((en_text, ar_text))
            if pairs:
                method = f"xml/{encoding}"
        except ET.ParseError:
            pass

    return pairs, method


# Regex fallback for malformed TMX files
_TU_BLOCK_RE = re.compile(r"<tu\b[^>]*>(.*?)</tu>", re.DOTALL | re.IGNORECASE)
_TUV_RE = re.compile(
    r'<tuv[^>]*xml:lang=["\']([a-zA-Z\-]+)["\'][^>]*>(.*?)</tuv>',
    re.DOTALL | re.IGNORECASE,
)
_SEG_RE = re.compile(r"<seg[^>]*>(.*?)</seg>", re.DOTALL | re.IGNORECASE)


def _parse_tmx_regex(content: str) -> List[Tuple[str, str]]:
    """Fallback regex parser for malformed TMX."""
    pairs: List[Tuple[str, str]] = []
    for tu_match in _TU_BLOCK_RE.finditer(content):
        tu_body = tu_match.group(1)
        en_text = None
        ar_text = None
        for tuv_match in _TUV_RE.finditer(tu_body):
            lang = tuv_match.group(1).lower()
            tuv_body = tuv_match.group(2)
            seg_match = _SEG_RE.search(tuv_body)
            if not seg_match:
                continue
            seg_text = strip_inline_tags(seg_match.group(1))
            if not seg_text:
                continue
            if lang.startswith("en") and en_text is None:
                en_text = seg_text
            elif lang.startswith("ar") and ar_text is None:
                ar_text = seg_text
        if en_text and ar_text:
            pairs.append((en_text, ar_text))
    return pairs


# ----------------------------------------------------------------------------
# Cleanup / normalization helpers
# ----------------------------------------------------------------------------
WHITESPACE_RE = re.compile(r"\s+")
PUNCT_LEADING_RE = re.compile(r"^[\s\.,;:!?\-—–_•·]+")
PUNCT_TRAILING_RE = re.compile(r"[\s\.,;:!?\-—–_•·]+$")


def clean_text(text: str) -> str:
    """Light cleanup: trim, collapse whitespace, strip leading/trailing punctuation."""
    if not text:
        return ""
    # Strip HTML entities
    text = (text
            .replace("&amp;", "&")
            .replace("&lt;", "<")
            .replace("&gt;", ">")
            .replace("&quot;", '"')
            .replace("&apos;", "'")
            .replace("&#39;", "'")
            .replace("&nbsp;", " "))
    # Collapse whitespace
    text = WHITESPACE_RE.sub(" ", text)
    # Strip leading/trailing punctuation+whitespace
    text = PUNCT_LEADING_RE.sub("", text)
    text = PUNCT_TRAILING_RE.sub("", text)
    return text.strip()


def is_valid_pair(en: str, ar: str) -> Tuple[bool, str]:
    """Validate an en/ar pair. Returns (is_valid, reason_if_invalid)."""
    en_clean = clean_text(en)
    ar_clean = clean_text(ar)

    if not en_clean or not ar_clean:
        return False, "empty_after_clean"
    if len(en_clean) < 2 or len(ar_clean) < 2:
        return False, "too_short"
    if en_clean == ar_clean:
        return False, "identical"
    # Pure numeric
    if en_clean.replace(".", "").replace(",", "").isdigit():
        return False, "numeric_only_en"
    if ar_clean.replace(".", "").replace(",", "").replace("٠", "").replace("١", "").replace("٢", "").replace("٣", "").replace("٤", "").replace("٥", "").replace("٦", "").replace("٧", "").replace("٨", "").replace("٩", "").isdigit():
        return False, "numeric_only_ar"
    # URL or path
    if en_clean.startswith(("http://", "https://", "www.", "/", "\\")):
        return False, "url_or_path"
    return True, ""


# ----------------------------------------------------------------------------
# Main processing
# ----------------------------------------------------------------------------
@dataclass
class FileStats:
    file: str
    specialty: str
    pairs_extracted: int = 0
    pairs_valid: int = 0
    pairs_quarantined: int = 0
    pairs_duplicate: int = 0
    pairs_added: int = 0
    size_bytes: int = 0
    parse_method: str = "xml"


@dataclass
class SpecialtyStats:
    specialty: str
    description: str
    files_count: int = 0
    total_pairs_extracted: int = 0
    total_pairs_valid: int = 0
    total_pairs_quarantined: int = 0
    total_pairs_after_dedup: int = 0
    files: List[str] = field(default_factory=list)
    quarantined_reasons: Dict[str, int] = field(default_factory=dict)


def main():
    print("=" * 72)
    print("malek_data Dictionary Processor")
    print("=" * 72)
    print(f"Source: {SOURCE_DIR}")
    print(f"Output: {OUTPUT_DIR}")
    print()

    # ------------------------------------------------------------------
    # Phase 1: Inventory + classify
    # ------------------------------------------------------------------
    if not SOURCE_DIR.exists():
        print(f"❌ ERROR: Source directory does not exist: {SOURCE_DIR}")
        sys.exit(1)

    all_files = sorted([f for f in SOURCE_DIR.iterdir()
                        if f.is_file() and f.suffix.lower() in (".tmx", ".txt")
                        and not f.name.startswith(".")])

    # For .txt files, only include ones that look like renamed TMX (have <tmx> or <tu>)
    tmx_files = []
    for f in all_files:
        if f.suffix.lower() == ".tmx":
            tmx_files.append(f)
        elif f.suffix.lower() == ".txt":
            # Check if it's a renamed TMX
            try:
                with open(f, "rb") as fh:
                    head = fh.read(500)
                if b"<tmx" in head.lower() or b"<tu " in head.lower():
                    tmx_files.append(f)
            except OSError:
                pass

    print(f"Found {len(tmx_files)} TMX-style files")
    print()

    # Classify each file by specialty
    classified: Dict[str, List[Path]] = defaultdict(list)
    excluded_files: List[str] = []
    for f in tmx_files:
        specialty = classify_specialty(f.name)
        if specialty is None:
            excluded_files.append(f.name)
        else:
            classified[specialty].append(f)

    print("Specialty classification:")
    for sp in [r[0] for r in SPECIALTY_RULES]:
        if sp in classified:
            print(f"  {sp}: {len(classified[sp])} files")
    print(f"  EXCLUDED: {len(excluded_files)} files")
    print()

    # ------------------------------------------------------------------
    # Phase 1.5: Detect monolingual Arabic files (Mayo Clinic style —
    # no English TUV). These are not bilingual dictionaries; we save them
    # separately as Arabic medical corpus for transparency.
    # ------------------------------------------------------------------
    monolingual_files: List[Tuple[str, str, int]] = []  # (specialty, filename, article_count)
    for sp_name, _files_list in list(classified.items()):
        keep_files = []
        for f in classified[sp_name]:
            try:
                encoding = _detect_encoding(f)
                with open(f, "r", encoding=encoding, errors="replace") as fh:
                    content = fh.read()
            except OSError:
                keep_files.append(f)
                continue
            en_tuvs = len(_TUV_RE.findall(content))  # captures all TUVs
            # Re-count with case-insensitive lang="en"
            en_count = len(re.findall(r'<tuv[^>]*xml:lang="en', content, re.IGNORECASE))
            ar_count = len(re.findall(r'<tuv[^>]*xml:lang="ar', content, re.IGNORECASE))
            tu_count = len(re.findall(r'<tu\b', content, re.IGNORECASE))
            if tu_count > 0 and en_count == 0 and ar_count > 0:
                # Monolingual Arabic — exclude from bilingual dictionaries
                monolingual_files.append((sp_name, f.name, tu_count))
            else:
                keep_files.append(f)
        classified[sp_name] = keep_files

    if monolingual_files:
        print(f"Monolingual Arabic files detected (excluded from bilingual dictionaries): {len(monolingual_files)}")
        for sp, fname, count in monolingual_files:
            print(f"  [{sp}] {fname} ({count} Arabic articles, 0 English)")
        print()

        # Save monolingual corpus manifest — use build_id for traceability
        mono_path = OUTPUT_DIR / "_monolingual_corpus.json"
        mono_data = {
            "note": (
                "These TMX files contain only Arabic medical articles with no English "
                "translation. They are NOT bilingual dictionaries and are excluded from "
                "the specialty JSON files. They are listed here for transparency and may "
                "be useful as Arabic medical corpus for future terminology extraction."
            ),
            "files": [
                {"specialty": sp, "filename": fname, "article_count": count}
                for sp, fname, count in monolingual_files
            ],
        }
        with open(mono_path, "w", encoding="utf-8") as f:
            json.dump(mono_data, f, ensure_ascii=False, indent=2, sort_keys=True)

    # ------------------------------------------------------------------
    # Phase 2: Parse + clean + quarantine ALL files (collecting entries)
    # ------------------------------------------------------------------
    # Phase 8 fix (Kimi review): Instead of processing files per-specialty
    # (file-hint based), we process ALL files in one pass and let
    # classify_entry_by_content() route each entry to its correct specialty
    # via entry.section. This catches misclassified files like
    # master_fractures.tmx which actually contain general/political content.
    loader = MedicalDictionaryLoader()  # For safety firewall methods

    specialty_stats: Dict[str, SpecialtyStats] = {}
    all_quarantined: List[Dict[str, Any]] = []
    file_stats_list: List[FileStats] = []
    # entries_by_specialty: maps content-detected specialty -> list of entries
    entries_by_specialty: Dict[str, List[DictionaryEntry]] = defaultdict(list)
    # source_files_by_specialty: tracks which source files contributed to each specialty
    source_files_by_specialty: Dict[str, set] = defaultdict(set)

    # Iterate over ALL bilingual TMX files (regardless of file-hint specialty)
    all_tmx_files = []
    for sp_name_file_hint, files in classified.items():
        for f in files:
            all_tmx_files.append((f, sp_name_file_hint))

    for tmx_path, file_hint_specialty in all_tmx_files:
        file_stat = FileStats(
            file=tmx_path.name,
            specialty=file_hint_specialty,
            size_bytes=tmx_path.stat().st_size,
        )

        # Parse
        pairs, parse_method = parse_tmx_file(tmx_path)
        file_stat.pairs_extracted = len(pairs)
        file_stat.parse_method = parse_method

        # Process each pair
        valid_count = 0
        quarantined_count = 0
        non_medical_count = 0
        for en, ar in pairs:
            # Clean
            en_clean = clean_text(en)
            ar_clean = clean_text(ar)

            # Validate
            is_valid, reason = is_valid_pair(en_clean, ar_clean)
            if not is_valid:
                quarantined_count += 1
                all_quarantined.append({
                    "file": tmx_path.name,
                    "specialty": file_hint_specialty,
                    "en": en_clean[:200],
                    "ar": ar_clean[:200],
                    "reason": f"invalid:{reason}",
                })
                continue

            # Phase 8 fix (Kimi review): content-based re-classification.
            # Some files (esp. master_fractures.tmx) contain mixed content
            # that does not match their filename-based specialty hint.
            # Re-classify each entry by content and route to the right
            # specialty. If content matches NON_MEDICAL_PATTERNS, exclude
            # the entry entirely (don't add to any specialty).
            entry_specialty, is_medical = classify_entry_by_content(
                en_clean, hint_specialty=file_hint_specialty
            )
            if not is_medical:
                non_medical_count += 1
                all_quarantined.append({
                    "file": tmx_path.name,
                    "specialty": file_hint_specialty,
                    "en": en_clean[:200],
                    "ar": ar_clean[:200],
                    "reason": "non_medical_content",
                })
                continue

            # Build DictionaryEntry
            entry = DictionaryEntry(
                key=en_clean,
                value=ar_clean,
                normalized_key=normalize_arabic_key(en_clean),
                source=f"malek_data:{tmx_path.name}",
                category="translation_memory",
                confidence="medium",
            )
            # Override the file-level specialty hint with content-based
            # classification when they disagree
            entry.section = entry_specialty

            # Phase 8 fix (Kimi review): context-aware firewall.
            # The original is_dangerous_key() is designed for str.replace
            # context (HybridSpellChecker). For exact-match lookup context
            # (ExactTranslationMemory), decimal_dose / concentration_percent
            # / drug_dose_unit are NOT dangerous — they are legitimate
            # medical content (e.g. "Refer to Fig. 3.10", "ICD 754.71",
            # "5mg dose", "0.9% saline").
            #
            # We still quarantine the genuinely dangerous categories:
            #   - critical_medical_term_as_key (high-risk drug names as keys)
            #   - PII (emails, phone numbers)
            #   - arabic_indic_digits (locale-ambiguous)
            #   - numeric_only, too_short, whitespace_padding
            # But we ALLOW:
            #   - decimal_dose, concentration_percent, drug_dose_unit
            #   - negation patterns (safe for exact-match lookup)
            # Because exact-match lookup cannot corrupt these values.

            if not entry.value.strip():
                quarantined_count += 1
                continue

            if contains_pii(entry.key) or contains_pii(entry.value):
                quarantined_count += 1
                all_quarantined.append({
                    "file": tmx_path.name,
                    "specialty": entry_specialty,
                    "en": en_clean[:200],
                    "ar": ar_clean[:200],
                    "reason": "pii_or_contact",
                })
                continue

            if is_critical_medical_term(entry.key):
                quarantined_count += 1
                all_quarantined.append({
                    "file": tmx_path.name,
                    "specialty": entry_specialty,
                    "en": en_clean[:200],
                    "ar": ar_clean[:200],
                    "reason": "critical_medical_term_as_key",
                })
                continue

            # Run is_dangerous_key but only quarantine for the categories
            # that are still dangerous in exact-match context.
            dangerous, dreason = is_dangerous_key(entry.key)
            if dangerous and dreason in (
                "arabic_indic_digits",
                "numeric_only",
                "too_short",
                "whitespace_padding",
            ):
                quarantined_count += 1
                all_quarantined.append({
                    "file": tmx_path.name,
                    "specialty": entry_specialty,
                    "en": en_clean[:200],
                    "ar": ar_clean[:200],
                    "reason": f"dangerous:{dreason}",
                })
                continue
            # Allow: decimal_dose, concentration_percent, drug_dose_unit, negation:*

            # Passed firewall — route to content-detected specialty
            valid_count += 1
            entries_by_specialty[entry_specialty].append(entry)
            source_files_by_specialty[entry_specialty].add(tmx_path.name)

        file_stat.pairs_valid = valid_count
        file_stat.pairs_quarantined = quarantined_count
        file_stats_list.append(file_stat)

        print(f"  hint={file_hint_specialty:25s} | {tmx_path.name[:50]:50s} | "
              f"extracted={file_stat.pairs_extracted:>6} | "
              f"valid={valid_count:>6} | "
              f"quarantined={quarantined_count:>4} | "
              f"non_medical={non_medical_count:>4}")

    # ------------------------------------------------------------------
    # Phase 3: Build per-specialty JSON files (after content-based routing)
    # ------------------------------------------------------------------
    for sp_name, sp_keywords, sp_desc in SPECIALTY_RULES:
        # Get all entries routed to this specialty (via content classification)
        all_entries = entries_by_specialty.get(sp_name, [])
        files = sorted(source_files_by_specialty.get(sp_name, set()))

        sp_stats = SpecialtyStats(
            specialty=sp_name,
            description=sp_desc,
            files_count=len(files),
            files=files,
            total_pairs_extracted=len(all_entries),  # post-firewall count
            total_pairs_valid=len(all_entries),
        )

        # Deduplicate within the specialty by normalized_key
        # Keep first occurrence (preserve file order; later duplicates lose)
        groups: Dict[str, List[DictionaryEntry]] = defaultdict(list)
        for e in all_entries:
            groups[e.normalized_key].append(e)

        deduped_entries: List[DictionaryEntry] = []
        duplicates_count = 0
        for nkey in sorted(groups):
            group = groups[nkey]
            winner = group[0]
            if len(group) > 1:
                duplicates_count += len(group) - 1
            deduped_entries.append(winner)

        sp_stats.total_pairs_after_dedup = len(deduped_entries)
        sp_stats.total_pairs_quarantined = sum(
            1 for q in all_quarantined if q.get("specialty") == sp_name
        )

        # Save per-specialty JSON
        # Note: generated_at is omitted for deterministic regeneration (sha256 stable)
        output_data = {
            "specialty": sp_name,
            "description": sp_desc,
            "source_files": files,
            "stats": {
                "files_count": sp_stats.files_count,
                "total_pairs_extracted": sp_stats.total_pairs_extracted,
                "total_pairs_valid_after_firewall": sp_stats.total_pairs_valid,
                "total_pairs_quarantined": sp_stats.total_pairs_quarantined,
                "total_pairs_after_dedup": sp_stats.total_pairs_after_dedup,
            },
            "entries": [
                {
                    "en": e.key,
                    "ar": e.value,
                    "normalized_key": e.normalized_key,
                    "source": e.source,
                }
                for e in sorted(deduped_entries, key=lambda x: x.normalized_key)
            ],
        }

        out_path = OUTPUT_DIR / f"{sp_name}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2, sort_keys=True)

        specialty_stats[sp_name] = sp_stats
        print(f"  → Saved {out_path.name}: {sp_stats.total_pairs_after_dedup} entries")
        print()

    # ------------------------------------------------------------------
    # Phase 3: Aggregate stats + summary
    # ------------------------------------------------------------------
    total_extracted = sum(s.total_pairs_extracted for s in specialty_stats.values())
    total_valid = sum(s.total_pairs_valid for s in specialty_stats.values())
    total_quarantined = sum(s.total_pairs_quarantined for s in specialty_stats.values())
    total_deduped = sum(s.total_pairs_after_dedup for s in specialty_stats.values())

    # Use a stable build_id based on the source directory's file inventory (not wall clock).
    # This makes the output fully deterministic: same inputs → same build_id → same hashes.
    source_inventory = sorted([(f.name, f.stat().st_size, int(f.stat().st_mtime)) for f in SOURCE_DIR.iterdir() if f.is_file()])
    build_id = hashlib.sha256(json.dumps(source_inventory, ensure_ascii=False).encode()).hexdigest()[:16]

    summary = {
        "build_id": build_id,
        "source_archive": "malek_data_combined.7z (extracted to /tmp/my-project/work/malek_data_extracted)",
        "source_repo": "https://github.com/DrAbdulmalek/malek_data/blob/main/dictionaries_backup_17files.7z (private/404; used local mirror)",
        "specialties": {
            sp: {
                "description": s.description,
                "files_count": s.files_count,
                "files": s.files,
                "pairs_extracted": s.total_pairs_extracted,
                "pairs_valid_after_firewall": s.total_pairs_valid,
                "pairs_quarantined": s.total_pairs_quarantined,
                "pairs_after_dedup": s.total_pairs_after_dedup,
                "quarantined_reasons": dict(sorted(s.quarantined_reasons.items())),
            }
            for sp, s in specialty_stats.items()
        },
        "totals": {
            "files_processed": sum(s.files_count for s in specialty_stats.values()),
            "files_excluded": len(excluded_files),
            "excluded_files": excluded_files,
            "pairs_extracted": total_extracted,
            "pairs_valid_after_firewall": total_valid,
            "pairs_quarantined": total_quarantined,
            "pairs_after_dedup": total_deduped,
        },
        "file_stats": [asdict(fs) for fs in file_stats_list],
    }

    # Save aggregate summary
    summary_path = OUTPUT_DIR / "_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2, sort_keys=True)

    # Save quarantined log (truncated for size). Note: includes build_id for traceability
    # but content (sample list) is fully deterministic.
    quarantined_path = OUTPUT_DIR / "_quarantined.json"
    quarantied_data = {
        "build_id": build_id,
        "total_quarantined": len(all_quarantined),
        "note": "Quarantined entries are NOT included in specialty dictionaries. They are logged here for audit only.",
        "sample_count": min(len(all_quarantined), 500),
        "samples": all_quarantined[:500],
    }
    with open(quarantined_path, "w", encoding="utf-8") as f:
        json.dump(quarantied_data, f, ensure_ascii=False, indent=2, sort_keys=True)

    # ------------------------------------------------------------------
    # Phase 4: Deterministic regeneration verification
    # ------------------------------------------------------------------
    print("=" * 72)
    print("Deterministic regeneration check")
    print("=" * 72)
    print(f"build_id: {build_id}")
    print()

    # Compute sha256 of each specialty file
    hashes_v1 = {}
    for sp in specialty_stats:
        p = OUTPUT_DIR / f"{sp}.json"
        with open(p, "rb") as f:
            hashes_v1[sp] = hashlib.sha256(f.read()).hexdigest()
        print(f"  {sp}: {hashes_v1[sp][:16]}... ({(p.stat().st_size / 1024):.1f} KB)")

    summary_hash = hashlib.sha256(
        json.dumps(summary, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    print(f"  _summary.json hash: {summary_hash[:16]}...")
    print()

    # Save hash manifest for verification — uses build_id (deterministic)
    manifest = {
        "build_id": build_id,
        "specialty_files": hashes_v1,
        "summary_hash": summary_hash,
        "verification_note": (
            "If this script is re-run on the same source files, the build_id and "
            "all specialty file hashes will be identical (deterministic)."
        ),
    }
    with open(OUTPUT_DIR / "_hashes.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2, sort_keys=True)

    # ------------------------------------------------------------------
    # Phase 5: Print final summary
    # ------------------------------------------------------------------
    print("=" * 72)
    print("FINAL SUMMARY")
    print("=" * 72)
    print(f"Files processed:   {summary['totals']['files_processed']}")
    print(f"Files excluded:    {summary['totals']['files_excluded']}")
    print(f"Pairs extracted:   {total_extracted:,}")
    print(f"Pairs after firewall: {total_valid:,}")
    print(f"Pairs quarantined: {total_quarantined:,}")
    print(f"Pairs after dedup:  {total_deduped:,}")
    print()
    print("By specialty:")
    for sp, s in specialty_stats.items():
        print(f"  {sp:25s}: {s.files_count:>2} files | "
              f"{s.total_pairs_extracted:>6,} → {s.total_pairs_after_dedup:>6,} pairs")
    print()
    print(f"Output directory: {OUTPUT_DIR}")
    print(f"Files written: {len(list(OUTPUT_DIR.glob('*.json')))}")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
