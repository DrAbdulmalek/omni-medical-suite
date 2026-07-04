# scripts/create_jais_prompt_dataset.py
"""
Create prompt-completion dataset for Jais NER fine-tuning.

Converts HITL corrections from HuggingFace into prompt-completion pairs
where:
  - prompt: structured instruction to extract entities from medical text
  - completion: entities extracted via dictionary matching (NO static placeholders)

v2.0 — CRITICAL FIX:
  Previous version used a static completion ("دواء: -\nمرض: -\n...") for EVERY
  sample, which would train Jais to ALWAYS output "-" for every field regardless
  of input. This version generates actual entity extractions from the text.

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
from typing import Dict, List

from datasets import load_dataset, Dataset

logger = logging.getLogger(__name__)

# ── Medical Entity Dictionary ────────────────────────────────────────────────
# Used for rule-based NER to generate training completions.
# Must be kept in sync with the Gradio NER and postprocessor dictionaries.
_MEDICATIONS = [
    "باراسيتامول", "ايبوبروفين", "اموكسيسيلين", "ازيثرومايسين",
    "سيفالكسين", "ميترونيدازول", "اوجمنتين", "اوميبرازول",
    "ديكلوفيناك", "نابروكسين", "ترامادول", "كوديين",
    "سالبوتامول", "لوراتادين", "سيتيريزين", "رانيتيدين",
    "فاموتيدين", "انالجين", "بنادول", "ادفيل",
    "كاتافلام", "فولتارين", "مونتيلوكاست", "سودوافيدرين",
    "سيفترياكسون", "دوكسيسيكلين", "سيبروفلوكساسين",
    "لوفلوكساسين", "ميفيناميك", "انديسيترون", "ميتوكلوبراميد",
    "سلفاتيلين", "كلافولانات", "لوسارتان", "اميلوديبين",
    "انالجين", "فولتارين", "نوفالجين", "بروجستيرون",
    "اسبرين", "كلوبريدوجريل", "اتورفاستاتين", "ميتفورمين",
    "انسولين", "جليمبريد", "كاربامازيبين", "فينيتوين",
    "فالبرويك", "سيرتالين", "فلوكسيتين", "لورازيبام",
    "ديازيبام", "سيتامول", "بوديسونيد", "فلوتيكازون",
    "اموكسيل", "اموكسيسلاف", "اموكلاف", "زيثروماكس",
    "كاربامازيبين", "فينيتوين", "فالبرويك", "اوجمنتين",
]

_DISEASES = [
    "سكري", "ضغط", "ربو", "التهاب", "حساسية", "قرحة",
    "التهاب رئوي", "التهاب شعبي", "التهاب مفاصل", "التهاب جيوب",
    "ارتفاع ضغط", "انخفاض ضغط", "سرطان", "ورم",
    "التهاب اللوزتين", "التهاب المعدة", "التهاب الجيوب الأنفية",
]

_SYMPTOMS = [
    "صداع", "حمى", "سعال", "الم", "غثيان", "اقياء",
    "اسهال", "امساك", "دوار", "تعب", "ضيق تنفس",
    "الم بطن", "الم حلق", "الم ظهر", "الم مفاصل",
    "الم صدر", "الم رأس", "ارتفاع حرارة",
]

_DOSAGE_RE = re.compile(r'(\d+(?:\.\d+)?)\s*(?:ملغ|mg|مغ|مللي|مل|حبة|كبسولة|قرص|امبول|مرتين|يومي|صباحا|مساء)')


def extract_entities(text: str) -> Dict[str, List[str]]:
    """
    Rule-based NER using medical dictionary.
    Returns dict with categories as keys and matched terms as values.
    """
    entities = {"medications": [], "diseases": [], "symptoms": [], "dosages": []}

    for med in _MEDICATIONS:
        if med in text and med not in entities["medications"]:
            entities["medications"].append(med)

    for dis in _DISEASES:
        if dis in text and dis not in entities["diseases"]:
            entities["diseases"].append(dis)

    for sym in _SYMPTOMS:
        if sym in text and sym not in entities["symptoms"]:
            entities["symptoms"].append(sym)

    for m in _DOSAGE_RE.findall(text):
        if m not in entities["dosages"]:
            entities["dosages"].append(m)

    return entities


def _entities_to_completion(entities: Dict[str, List[str]]) -> str:
    """Convert extracted entities to Jais completion format."""
    meds = ", ".join(entities["medications"]) if entities["medications"] else "-"
    dis = ", ".join(entities["diseases"]) if entities["diseases"] else "-"
    syms = ", ".join(entities["symptoms"]) if entities["symptoms"] else "-"
    doses = ", ".join(entities["dosages"]) if entities["dosages"] else "-"
    # التاريخ غير مدعوم بقاموس حالياً
    return (
        f"دواء: {meds}\n"
        f"مرض: {dis}\n"
        f"جرعة: {doses}\n"
        f"عرض: {syms}\n"
        f"تاريخ: -"
    )


def create_prompt_completion(text: str) -> dict:
    """
    Create a prompt-completion pair for Jais NER training.

    v2.0: completion is now generated from actual text content via
    dictionary-based NER, NOT a static placeholder.

    IMPORTANT: For production training, replace this with human-annotated
    completions. Dictionary matching is a starting point, not ground truth.
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

    # v2.0: استخراج فعلي بدل placeholder ثابت
    entities = extract_entities(text)
    completion = _entities_to_completion(entities)

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

    # ⚠️ تحقق أمان: لا تنشئ dataset فارغ أو بـ 0% entities
    empty_count = 0
    for comp in data["completion"]:
        if comp.count("-") >= 4:  # كل الحقول "-"
            empty_count += 1

    if len(data["prompt"]) == 0:
        logger.error("No valid samples found. Dataset NOT created.")
        raise ValueError(
            "Dataset is empty — cannot train on 0 samples. "
            "Ensure the HF dataset has 'correct_text' or 'incorrect_ocr_output' columns."
        )

    empty_ratio = empty_count / len(data["completion"]) if data["completion"] else 1.0
    if empty_ratio > 0.9:
        logger.warning(
            f"⚠️ {empty_ratio:.0%} of completions have NO extracted entities "
            f"(all fields are '-'). Training on this will teach the model to "
            f"always output '-'. Add more annotated medical texts to the dataset."
        )

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