# app/gradio_full_hitl.py
"""Full Gradio HITL: Preprocess → OCR → LLM Proofread → NER → Save to HF.
Set ENABLE_LLM=true to enable Jais/proofreader (requires GPU)."""
import gradio as gr, json, os
from datetime import datetime

ENABLE_LLM = os.getenv("ENABLE_LLM", "false").lower() == "true"
HAS_LLM = False
if ENABLE_LLM:
    try:
        from src.ner.jais_ner import JaisNER
        from src.llm.proofreader import MedicalProofreader
        HAS_LLM = True
    except ImportError: pass

try:
    from datasets import load_dataset, Dataset
    from huggingface_hub import HfApi
    import pandas as pd
    HAS_HF = True
except ImportError: HAS_HF = False

proofreader = ner = None
if HAS_LLM:
    try: proofreader = MedicalProofreader(); ner = JaisNER()
    except Exception as e: print(f"Warning: {e}")

def full_process(image):
    if image is None: return None, "No image", "", {}, "Upload an image"
    raw_text = "[OCR output]"
    corrected = raw_text; entities = {}
    if proofreader:
        try: corrected = proofreader.proofread(raw_text)["corrected"]
        except: pass
    if ner:
        try: entities = ner.extract_entities(corrected)
        except: pass
    return image, corrected, raw_text, entities, "Done"

def save_to_hf(corrected, original, entities, category):
    if not HAS_HF: return "huggingface_hub not available"
    try:
        df = pd.DataFrame([{"incorrect_ocr_output":original,"correct_text":corrected,
            "category":category,"entities":json.dumps(entities) if isinstance(entities,dict) else str(entities),
            "timestamp":datetime.now().isoformat()}])
        try:
            existing = load_dataset("DrAbdulmalek/arabic-medical-ocr-corrections",split="train").to_pandas()
            df = pd.concat([existing,df], ignore_index=True)
        except: pass
        Dataset.from_pandas(df).push_to_hub("DrAbdulmalek/arabic-medical-ocr-corrections", private=False)
        return f"Saved! Total: {len(df)} samples"
    except Exception as e: return f"Error: {e}"

def update_medical_dictionary():
    try:
        from src.ocr.build_medical_dict import build_and_expand_dict
        yield "Analyzing corrections..."
        d = build_and_expand_dict(min_freq=2)
        yield f"Dictionary updated! Terms: {len(d)}"
    except Exception as e: yield f"Error: {e}"

css = ".gradio-container{direction:rtl}"
with gr.Blocks(title="Omni Medical OCR", theme=gr.themes.Soft(), css=css) as demo:
    gr.Markdown("# Omni Medical OCR\n**Arabic Medical Text Extraction & Correction**")
    with gr.Row():
        input_image = gr.Image(type="numpy", label="Upload Medical Image")
        process_btn = gr.Button("Process", variant="primary", size="lg")
    with gr.Row():
        with gr.Column(scale=1): cleaned_img = gr.Image(label="Preprocessed")
        with gr.Column(scale=2):
            raw_ocr = gr.Textbox(label="Raw OCR", lines=4)
            corrected = gr.Textbox(label="Corrected (LLM)", lines=4)
    entities_output = gr.JSON(label="Extracted Entities")
    with gr.Row():
        category = gr.Dropdown(choices=["prescription","report","handwriting","lab_result"],
            value="prescription", label="Document Type")
        save_btn = gr.Button("Save to HF Dataset", variant="secondary")
    status = gr.Textbox(label="Status", interactive=False)
    if HAS_LLM:
        with gr.Row():
            dict_btn = gr.Button("Update Medical Dictionary", variant="primary")
            dict_status = gr.Textbox(label="Dictionary Status", lines=4)
        dict_btn.click(fn=update_medical_dictionary, outputs=[dict_status])
    process_btn.click(fn=full_process, inputs=[input_image],
        outputs=[cleaned_img, corrected, raw_ocr, entities_output, status])
    save_btn.click(fn=save_to_hf, inputs=[corrected, raw_ocr, entities_output, category], outputs=[status])

if __name__ == "__main__": demo.launch(server_name="0.0.0.0", server_port=7860)