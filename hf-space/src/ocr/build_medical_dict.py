# src/ocr/build_medical_dict.py
"""
Auto-build and expand medical dictionary from HITL corrections dataset.

Scans correct_text from HuggingFace dataset, extracts Arabic medical terms
by frequency, and merges with existing medical_terms.json.
Can be called manually or integrated into weekly_retrain pipeline.
"""
import json
import re
import logging
from pathlib import Path
from collections import Counter
from typing import Optional

logger = logging.getLogger(__name__)


def extract_medical_terms(text: str) -> list[str]:
    """
    Extract potential medical terms from text.
    Filters for Arabic words + numbers longer than 2 chars.
    """
    words = re.findall(r'\b[\w\u0600-\u06FF]+\b', text)
    return [w for w in words if len(w) > 2]


def build_and_expand_dict(
    dataset_name: str = "DrAbdulmalek/arabic-medical-ocr-corrections",
    min_freq: int = 3,
    output_path: str = None,
) -> dict:
    """
    Build/expand medical dictionary from HF dataset.

    Args:
        dataset_name: HuggingFace dataset identifier.
        min_freq: Minimum frequency threshold for terms.
        output_path: Path to save the dictionary JSON.
                    Defaults to <project_root>/medical_terms.json

    Returns:
        Updated medical dictionary.
    """
    from src.ocr.normalization import arabic_strong_normalize

    if output_path is None:
        output_path = str(Path(__file__).parent.parent.parent / "medical_terms.json")

    # 1. Load dataset
    logger.info(f"Loading dataset: {dataset_name}")
    from datasets import load_dataset
    df = load_dataset(dataset_name, split="train").to_pandas()

    # 2. Extract and normalize terms
    all_terms: list[str] = []
    text_col = "correct_text" if "correct_text" in df.columns else "text"
    for text in df[text_col].dropna():
        normalized = arabic_strong_normalize(str(text))
        terms = extract_medical_terms(normalized)
        all_terms.extend(terms)

    # 3. Frequency analysis
    freq = Counter(all_terms)
    medical_dict: dict[str, str] = {
        term: term for term, count in freq.items() if count >= min_freq
    }

    logger.info(f"Extracted {len(medical_dict)} terms (min_freq={min_freq})")
    logger.info(f"Top 10: {freq.most_common(10)}")

    # 4. Merge with existing dictionary
    output = Path(output_path)
    if output.exists():
        with open(output, encoding="utf-8") as f:
            existing = json.load(f)
        medical_dict.update(existing)
        logger.info(f"Merged with existing: {len(existing)} terms")

    # 5. Save
    output.parent.mkdir(exist_ok=True, parents=True)
    with open(output, "w", encoding="utf-8") as f:
        json.dump(medical_dict, f, ensure_ascii=False, indent=2)

    logger.info(f"Saved {len(medical_dict)} terms to {output_path}")
    return medical_dict


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    build_and_expand_dict(min_freq=2)