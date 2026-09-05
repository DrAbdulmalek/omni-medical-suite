# src/processors/ocr_engine.py
"""Medical OCR with controlled EasyOCR loading and Tesseract fallback."""
from __future__ import annotations
from pathlib import Path
from typing import Iterable,Union
import numpy as np
class OCRError(RuntimeError): pass
class MedicalOCREngine:
    def __init__(self,languages:Iterable[str]=("ar","en"),use_easyocr:bool=True,tesseract_lang:str="ara+eng",psm:int=6,easyocr_model_storage_directory:str|None=None,allow_easyocr_download:bool=False)->None:
        self.languages=list(languages); self.use_easyocr=use_easyocr; self._easyocr_reader=None
        self.tesseract_lang=tesseract_lang; self.tesseract_config=f"--oem 3 --psm {psm}"
        self.easyocr_model_storage_directory=easyocr_model_storage_directory; self.allow_easyocr_download=allow_easyocr_download
    def _load_easyocr(self):
        if not self.use_easyocr:return None
        if self._easyocr_reader is None:
            try:
                import easyocr
                kwargs={"gpu":False,"download_enabled":self.allow_easyocr_download}
                if self.easyocr_model_storage_directory: kwargs["model_storage_directory"]=self.easyocr_model_storage_directory
                self._easyocr_reader=easyocr.Reader(self.languages,**kwargs)
            except Exception: self.use_easyocr=False; return None
        return self._easyocr_reader
    def _extract_with_easyocr(self,image:np.ndarray)->str:
        reader=self._load_easyocr()
        return " ".join(reader.readtext(image,detail=0)).strip() if reader else ""
    def _extract_with_tesseract(self,image:np.ndarray)->str:
        try: import pytesseract
        except Exception as e: raise OCRError("pytesseract is not installed.") from e
        return pytesseract.image_to_string(image,lang=self.tesseract_lang,config=self.tesseract_config).strip()
    def extract_text(self,image_input:Union[str,Path,np.ndarray])->str:
        image=image_input
        if isinstance(image_input,(str,Path)):
            import cv2; image=cv2.imread(str(image_input))
            if image is None: raise ValueError(f"Cannot read image: {image_input}")
        if self.use_easyocr:
            try:
                text=self._extract_with_easyocr(image)
                if text:return text
            except Exception: pass
        return self._extract_with_tesseract(image)
