# scripts/generate_ner_data.py
"""Generate NER training data from HITL corrections."""
import json, re
from pathlib import Path
from datasets import load_dataset, Dataset

DRUG_KW = ["أموكسيسيلين","باراسيتامول","إيبوبروفين","مضاد","حبوب","كبسولة","شراب","حقن","فيتامين"]
DISEASE_KW = ["التهاب","ارتفاع","سكر","ضغط","سرطان","حساسية","ربو","سكري","قلب","كلى","كبد"]
SYMPTOM_KW = ["ألم","حمى","سعال","صداع","دوار","غثيان","إسهال"]
DOSAGE_KW = ["ملغ","جرعة","قرص","حبة","كبسولة","مرتين","ثلاث"]

def simple_ner_annotate(text):
    tokens = re.findall(r'\b[\w\u0600-\u06FF]+\b', text)
    tags = [0]*len(tokens)
    for i, tok in enumerate(tokens):
        low = tok.lower()
        if any(k in low for k in DRUG_KW): tags[i]=1
        elif any(k in low for k in DISEASE_KW): tags[i]=3
        elif any(k in low for k in SYMPTOM_KW): tags[i]=5
        elif any(k in low for k in DOSAGE_KW): tags[i]=7
    return tokens, tags

def generate_ner_dataset(hf_dataset_name="DrAbdulmalek/arabic-medical-ocr-corrections", output_dir="ner_data"):
    print("Loading dataset...")
    df = load_dataset(hf_dataset_name, split="train").to_pandas()
    data = {"tokens":[], "ner_tags":[]}
    for _, row in df.iterrows():
        correct = str(row.get("correct_text",""))
        if not correct: continue
        normalized = re.sub(r'[إأٱآ]','ا',correct); normalized = re.sub(r'ى','ي',normalized); normalized = re.sub(r'ة','ه',normalized)
        tokens, tags = simple_ner_annotate(normalized)
        if tokens: data["tokens"].append(tokens); data["ner_tags"].append(tags)
    out = Path(output_dir); out.mkdir(exist_ok=True)
    ds = Dataset.from_dict(data); ds.save_to_disk(out/"ner_dataset")
    with open(out/"sample.json","w",encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Generated {len(ds)} NER samples → {out}")
    return ds

if __name__ == "__main__": generate_ner_dataset()