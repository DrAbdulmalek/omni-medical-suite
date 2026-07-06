import gradio as gr
from src.core.ocr_processor import OCRProcessor
from pathlib import Path
import json

processor = OCRProcessor()

def process_image(image):
    if image is None:
        return "يرجى رفع صورة", "", ""
    
    # حفظ مؤقت
    temp_path = "temp_upload.jpg"
    image.save(temp_path)
    
    corrected, entities = processor.process(temp_path)
    
    return (
        corrected,
        json.dumps(entities, ensure_ascii=False, indent=2),
        "تم المعالجة بنجاح ✓"
    )

with gr.Blocks(title="Omni Medical OCR", theme=gr.themes.Soft()) as demo:
    gr.Markdown("# 🩺 Omni Medical OCR Pipeline")
    
    with gr.Row():
        with gr.Column():
            input_image = gr.Image(type="pil", label="رفع صورة وصفة طبية")
            btn = gr.Button("🚀 معالجة", variant="primary")
        
        with gr.Column():
            output_text = gr.Textbox(label="النص المصحح", lines=8)
            output_entities = gr.JSON(label="الكيانات الطبية")
            status = gr.Textbox(label="الحالة")
    
    btn.click(
        process_image,
        inputs=input_image,
        outputs=[output_text, output_entities, status]
    )

    gr.Markdown("### ملاحظات: يدعم الخط اليدوي العربي + التصحيح الطبي الذكي")

if __name__ == "__main__":
    demo.launch()