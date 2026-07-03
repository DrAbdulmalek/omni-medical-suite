# scripts/create_jais_prompt_dataset.py
"""
Create prompt-completion dataset for Jais NER fine-tuning.

Converts HITL corrections from HuggingFace into prompt-completion pairs
where:
  - prompt: structured instruction to extract entities
  - completion: expected entity output (placeholder or annotated)

The generated dataset is saved to disk and can be loaded by
src/ner/fine_tune_jais_ner.py for fine-tuning.

Usage:
    python scripts/create_jais_prompt_dataset.py
    python scripts/create_jais_prompt_dataset.py --output_dir jais_ner_data
"""
import argparse
import json
import logging
import re
from pathlib import Path

from datasets import Dataset, load_dataset

logger = logging.getLogger(__name__)


def create_prompt_completion(text: str) -> dict:
    """
    Create a prompt-completion pair for Jais NER training.

    The prompt instructs Jais to extract medical entities.
    The completion is a placeholder — replace with actual annotated data for best results.
    """
    # Basic normalization for the prompt
    normalized = re.sub(r'[إأٱآ]', 'ا', text)
    normalized = re.sub(r'ى', 'ي', normalized)
    normalized = re.sub(r'\s+', ' ', normalized).strip()

    prompt = (
        f"أنت مساعد طبي متخصص في استخراج الكيانات من النصوص العربية الطبية.\n\n"
        f"نص: {normalized}\n\n"
        f"استخرج الكيانات بالصيغة التالية فقط:\n"
        f"- دواء: [قائمة]\n"
        f"- مرض: [قائمة]\n"
        f"- عرض: [قائمة]\n"
        f"- جرعة: [قائمة]\n"
        f"- تاريخ: [قائمة]\n\n"
        f"الإجابة:"
    )

    completion = (
        "دواء: -\n"
        "مرض: -\n"
        "جرعة: -\n"
        "عرض: -\n"
        "تاريخ: -"
    )

    return {"prompt": prompt, "completion": completion}


def generate_jais_dataset(
    hf_dataset_name: str = "DrAbdulmalek/arabic-medical-ocr-corrections",
    output_dir: str = "jais_ner_data",
) -> Dataset:
    """
    Generate full prompt-completion dataset from HF corrections.

    Args:
        hf_dataset_name: HuggingFace dataset identifier.
        output_dir: Directory to save the dataset.

    Returns:
        HuggingFace Dataset with 'prompt' and 'completion' columns.
    """
    logger.info(f"Loading dataset: {hf_dataset_name}")
    df = load_dataset(hf_dataset_name, split="train").to_pandas()

    data: dict = {"prompt": [], "completion": []}

    for _, row in df.iterrows():
        text = str(row.get("correct_text", "") or row.get("incorrect_ocr_output", ""))
        if not text or len(text.strip()) < 5:
            continue

        pc = create_prompt_completion(text)
        data["prompt"].append(pc["prompt"])
        data["completion"].append(pc["completion"])

    # Save
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True, parents=True)

    dataset = Dataset.from_dict(data)
    dataset.save_to_disk(output_path)

    # Save sample for inspection
    sample = {
        "prompt": data["prompt"][:3],
        "completion": data["completion"][:3],
        "total_samples": len(data["prompt"]),
    }
    with open(output_path / "sample.json", "w", encoding="utf-8") as f:
        json.dump(sample, f, ensure_ascii=False, indent=2)

    logger.info(f"Created {len(dataset)} prompt-completion samples → {output_path}")
    return dataset


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("--output_dir", default="jais_ner_data")
    parser.add_argument("--dataset", default="DrAbdulmalek/arabic-medical-ocr-corrections")
    args = parser.parse_args()

    generate_jais_dataset(
        hf_dataset_name=args.dataset,
        output_dir=args.output_dir,
    )