# OmniMedical — Scanner Fixer (v2.1)

تطبيق تصحيح صور السكانر الطبية (PySide6 desktop + Gradio web + Python package).

## البنية

```
omni-medical-suite/
├── packages/
│   ├── scanner_fixer/                # Python package (src-layout)
│   │   ├── pyproject.toml
│   │   └── src/scanner_fixer/
│   │       ├── __init__.py
│   │       └── core.py               # fix_scanned_image, batch_fix_folder, ...
│   └── desktop/
│       └── medical_doc_gui_final_v2.py   # PySide6 GUI
├── app/
│   └── advanced_review_app.py        # Gradio 4.x web UI
├── tests/
│   └── test_scanner_fixer_smoke.py
└── README.md
```

## التشغيل على مانجارو

```bash
# المتطلبات
pip install opencv-python pillow pytesseract pyside6 gradio

# اختبار سريع
python tests/test_scanner_fixer_smoke.py

# واجهة سطح المكتب
python packages/desktop/medical_doc_gui_final_v2.py

# واجهة الويب
python app/advanced_review_app.py
```

## الميزات

- **Text-aware auto-crop** عبر Tesseract (مع fallback على كشف الحواف)
- **Hough deskew** عبر `cv2.minAreaRect`
- **CLAHE** contrast enhancement
- **fastNlMeans** denoising
- **Batch folder processing** + JSON report
- **ZIP export** للنتائج
- **PySide6 desktop GUI** (drag & drop + before/after preview)
- **Gradio 4.x web UI** (single + batch + random preview + ZIP)
