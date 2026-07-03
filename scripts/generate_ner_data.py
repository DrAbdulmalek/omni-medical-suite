# scripts/generate_ner_data.py
"""
Generate NER training data from HITL corrections dataset.

Converts correct_text from HuggingFace dataset into (tokens, ner_tags) format
ready for MedicalNER training.

Supports two annotation modes:
  1. Rule-based (default): keyword matching for drugs, diseases, symptoms, dosages.
  2. LLM-based: uses LLMNERAnnotator or JaisNER for smarter annotation.

Usage:
    python scripts/generate_ner_data.py                        # Rule-based
    python scripts/generate_ner_data.py --method llm           # LLM-based
    python scripts/generate_ner_data.py --method jais          # Jais-based
"""
import argparse
import json
import logging
import re
from pathlib import Path

from datasets import Dataset, load_dataset

logger = logging.getLogger(__name__)

# ── Label IDs (matching src/ner/medical_ner.py LABEL_LIST) ────────────────
LABEL_O = 0
LABEL_B_DRUG = 1
LABEL_B_DISEASE = 3
LABEL_B_SYMPTOM = 5
LABEL_B_DOSAGE = 7

# ── Keyword lists for rule-based annotation ────────────────────────────────
DRUG_KEYWORDS = [
    "أموكسيسيلين", "باراسيتامول", "إيبوبروفين", "مضاد", "حبوب", "كبسولة",
    "شراب", "حقن", "فيتامين", "سلفاتيلين", "أزيثرومايسين", "ميترونيدازول",
    "أوميبرازول", "لوسارتان", "فولتارين", "ترامادول", "كوديين", "لوراتادين",
    "سيرترالين", "أنسولين", "ميتفورمين", "ديازيبام", "لورازيبام",
    "سيتيريزين", "رانيتيدين", "أسبرين", "ديكلوفيناك", "سودوإيفيدرين",
]

DISEASE_KEYWORDS = [
    "التهاب", "ارتفاع", "سكر", "ضغط", "سرطان", "حساسية", "ربو", "سكري",
    "قلب", "كلى", "كبد", "قرحة", "هشاشة", "روماتيزم", "ربو", "تهيج",
]

SYMPTOM_KEYWORDS = [
    "ألم", "حمى", "سعال", "صداع", "دوار", "غثيان", "إسهال", "إمساك",
    "تعب", "ضعف", "ضيق", "طفح", "حكة", "احتقان", "آلام",
]

DOSAGE_KEYWORDS = [
    "ملغ", "جرعة", "قرص", "حبة", "كبسولة", "مرتين", "ثلاث", "يوميا",
    "صباحا", "مساء", "أسبوع", "شه", "مم", "مل", "وحدة",
]


def simple_ner_annotate(text: str) -> tuple:
    """
    Rule-based NER annotation using keyword matching.

    Returns:
        (tokens, ner_tags) where ner_tags use LABEL_LIST IDs.
    """
    tokens = re.findall(r'\b[\w\u0600-\u06FF]+\b', text)
    ner_tags = [LABEL_O] * len(tokens)

    for i, token in enumerate(tokens):
        lower = token.lower()

        # Drug (highest priority — medical context)
        if any(kw in lower for kw in DRUG_KEYWORDS):
            ner_tags[i] = LABEL_B_DRUG
        # Disease
        elif any(kw in lower for kw in DISEASE_KEYWORDS):
            ner_tags[i] = LABEL_B_DISEASE
        # Symptom
        elif any(kw in lower for kw in SYMPTOM_KEYWORDS):
            ner_tags[i] = LABEL_B_SYMPTOM
        # Dosage
        elif any(kw in lower for kw in DOSAGE_KEYWORDS):
            ner_tags[i] = LABEL_B_DOSAGE

    return tokens, ner_tags


def llm_ner_annotate(text: str, annotator) -> tuple:
    """Use LLMNERAnnotator for annotation."""
    return annotator.annotate(text)


def jais_ner_annotate(text: str, annotator) -> tuple:
    """Use JaisNER for annotation."""
    return annotator.annotate_tokens(text)


def generate_ner_dataset(
    hf_dataset_name: str = "DrAbdulmalek/arabic-medical-ocr-corrections",
    output_dir: str = "ner_data",
    method: str = "rule",
) -> Dataset:
    """
    Generate NER training data from HITL corrections.

    Args:
        hf_dataset_name: HuggingFace dataset identifier.
        output_dir: Where to save the dataset.
        method: Annotation method: 'rule', 'llm', or 'jais'.

    Returns:
        HuggingFace Dataset with 'tokens' and 'ner_tags' columns.
    """
    from src.ocr.normalization import arabic_strong_normalize

    logger.info(f"Loading dataset: {hf_dataset_name}")
    df = load_dataset(hf_dataset_name, split="train").to_pandas()

    # Initialize annotator if needed
    annotator = None
    if method == "llm":
        from src.ner.llm_ner_annotator import LLMNERAnnotator
        annotator = LLMNERAnnotator()
    elif method == "jais":
        from src.ner.jais_ner import JaisNER
        annotator = JaisNER()

    data: dict = {"tokens": [], "ner_tags": []}

    for _, row in df.iterrows():
        correct = str(row.get("correct_text", ""))
        if not correct or len(correct.strip()) < 5:
            continue

        normalized = arabic_strong_normalize(correct)

        if method == "rule":
            tokens, ner_tags = simple_ner_annotate(normalized)
        elif method == "llm" and annotator:
            tokens, ner_tags = llm_ner_annotate(normalized, annotator)
        elif method == "jais" and annotator:
            tokens, ner_tags = jais_ner_annotate(normalized, annotator)
        else:
            tokens, ner_tags = simple_ner_annotate(normalized)

        if tokens:
            data["tokens"].append(tokens)
            data["ner_tags"].append(ner_tags)

    # Save
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True, parents=True)

    dataset = Dataset.from_dict(data)
    dataset.save_to_disk(output_path / "ner_dataset")

    # Save JSON sample for inspection
    sample = {
        "tokens": data["tokens"][:5],
        "ner_tags": data["ner_tags"][:5],
        "total_samples": len(data["tokens"]),
        "method": method,
    }
    with open(output_path / "sample.json", "w", encoding="utf-8") as f:
        json.dump(sample, f, ensure_ascii=False, indent=2)

    logger.info(f"Generated {len(dataset)} NER samples ({method}) → {output_path}")
    return dataset


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--method", choices=["rule", "llm", "jais"], default="rule")
    parser.add_argument("--output_dir", default="ner_data")
    parser.add_argument("--dataset", default="DrAbdulmalek/arabic-medical-ocr-corrections")
    args = parser.parse_args()

    generate_ner_dataset(
        hf_dataset_name=args.dataset,
        output_dir=args.output_dir,
        method=args.method,
    )