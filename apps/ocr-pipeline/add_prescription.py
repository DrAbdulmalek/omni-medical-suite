from src.core.ocr_processor import OCRProcessor
from pathlib import Path
import shutil

def add_prescription(image_path, ground_truth=None):
    processor = OCRProcessor()
    dest = Path("samples") / Path(image_path).name
    shutil.copy(image_path, dest)
    
    text, entities = processor.process(str(dest))
    print("✅ تمت المعالجة:")
    print(text)
    print(entities)
    return text

if __name__ == "__main__":
    add_prescription("1000899617.jpg", "النص الصحيح...")