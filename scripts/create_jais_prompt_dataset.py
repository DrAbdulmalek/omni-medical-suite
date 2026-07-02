# scripts/create_jais_prompt_dataset.py
"""Create prompt-completion dataset for Jais NER fine-tuning from HITL corrections."""
import json, re
from pathlib import Path
from datasets import load_dataset, Dataset

def create_prompt_completion(text):
    normalized = re.sub(r'[إأٱآ]','ا',text); normalized = re.sub(r'ى','ي',normalized)
    prompt = f"""أنت مساعد طبي. استخرج الكيانات من النص:
نص: {normalized}
استخرج: دواء: [] مرض: [] عرض: [] جرعة: [] تاريخ: []
الإجابة:"""
    return {"prompt": prompt, "completion": "دواء: -\nمرض: -\nجرعة: -\nعرض: -\nتاريخ: -"}

def generate_jais_dataset(hf_dataset_name="DrAbdulmalek/arabic-medical-ocr-corrections", output_dir="jais_ner_data"):
    print("Loading dataset...")
    df = load_dataset(hf_dataset_name, split="train").to_pandas()
    data = {"prompt":[], "completion":[]}
    for _, row in df.iterrows():
        text = str(row.get("correct_text","") or row.get("incorrect_ocr_output",""))
        if not text: continue
        pc = create_prompt_completion(text)
        data["prompt"].append(pc["prompt"]); data["completion"].append(pc["completion"])
    out = Path(output_dir); out.mkdir(exist_ok=True)
    ds = Dataset.from_dict(data); ds.save_to_disk(out)
    with open(out/"sample.json","w",encoding="utf-8") as f:
        json.dump({"prompt":data["prompt"][:3], "completion":data["completion"][:3]}, f, ensure_ascii=False, indent=2)
    print(f"Created {len(ds)} prompt-completion samples → {out}")
    return ds

if __name__ == "__main__": generate_jais_dataset()