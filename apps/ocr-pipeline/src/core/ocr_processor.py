# src/core/ocr_processor.py

import cv2
import easyocr
import pytesseract
from PIL import Image
from transformers import TrOCRProcessor, VisionEncoderDecoderModel

from src.core.jais_proofreader import JaisProofreader
from src.spellcheck.hybrid_spell_checker import HybridSpellChecker


class OCRProcessor:
    def __init__(self, use_trocr=True):
        self.reader = easyocr.Reader(['ar', 'en'], gpu=False)
        self.spell = HybridSpellChecker()
        self.use_trocr = use_trocr
        self.trocr_model = None
        self.trocr_processor = None
        self.jais = None

        if use_trocr:
            try:
                self.trocr_processor = TrOCRProcessor.from_pretrained("./trocr_medical_arabic")
                self.trocr_model = VisionEncoderDecoderModel.from_pretrained("./trocr_medical_arabic")
                self.trocr_model.eval()
            except:
                self.use_trocr = False

    def enhanced_ocr(self, image_path: str):
        img = cv2.imread(image_path)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)

        # EasyOCR + Tesseract
        easy_text = "\n".join(self.reader.readtext(gray, paragraph=True, detail=0))
        tess_text = pytesseract.image_to_string(gray, lang='ara', config='--psm 6')

        combined = (easy_text + "\n" + tess_text).strip()

        if self.use_trocr and self.trocr_model:
            pil_img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
            pixel_values = self.trocr_processor(pil_img, return_tensors="pt").pixel_values
            generated = self.trocr_model.generate(pixel_values)
            trocr_text = self.trocr_processor.decode(generated[0], skip_special_tokens=True)
            combined = trocr_text if len(trocr_text) > len(combined) else combined

        return combined

    def process(self, image_path: str):
        raw = self.enhanced_ocr(image_path)
        corrected = self.spell.auto_correct(raw)

        jais = self.get_jais()
        if jais:
            final, entities = jais.proofread(corrected)
            return final, entities
        return corrected, {}

    def get_jais(self):
        if not self.jais:
            try:
                self.jais = JaisProofreader()
            except:
                self.jais = None
        return self.jais
