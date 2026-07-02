# src/ocr/build_medical_dict.py
"""Auto-build medical dictionary from HITL corrections dataset."""
import json
from pathlib import Path
import re
from collections import Counter
from datasets import load_dataset

def build_and_expand_dict(dataset_name="DrAbdulmalek/arabic-medical-ocr-corrections",
                         min_freq=3, output_path="medical_terms.json"):
    print("Loading dataset...")
    df = load_dataset(dataset_name, split="train").to_pandas()
    all_terms = []
    for text in df["correct_text"].dropna():
        normalized = re.sub(r'[إأٱآ]', 'ا', str(text))
        terms = re.findall(r'\b[\w\u0600-\u06FF]+\b', normalized)
        all_terms.extend([t for t in terms if len(t) > 2])
    freq = Counter(all_terms)
    medical_dict = {term: term for term, count in freq.items() if count >= min_freq}
    output = Path(output_path)
    if output.exists():
        with open(output, encoding="utf-8") as f:
            medical_dict.update(json.load(f))
    output.parent.mkdir(exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        json.dump(medical_dict, f, ensure_ascii=False, indent=2)
    print(f"Built dictionary: {len(medical_dict)} terms")
    return medical_dict

if __name__ == "__main__":
    build_and_expand_dict()