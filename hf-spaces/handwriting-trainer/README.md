---
title: Handwriting OCR Trainer
emoji: ✍️
colorFrom: blue
colorTo: indigo
sdk: docker
sdk_version: "3.0.0"
app_port: 7860
pinned: false
license: mit
tags:
  - ocr
  - handwriting
  - arabic
  - active-learning
  - trocr
---

# ✍️ Handwriting OCR Trainer — Arabic / English / German

## ما هذا التطبيق؟

واجهة تفاعلية لتصحيح التعرف الضوئي على الحروف (OCR) للمستندات المكتوبة بخط اليد. تساعد في بناء بيانات تدريبية عالية الجودة لتحسين نماذج التعرف على الخط اليدوي.

## طريقة الاستخدام

1. **رفع ملف PDF** مسحوب بالماسح الضوئي (خط يد)
2. **اختيار اللغة**: عربي + إنجليزي / إنجليزي / ألماني
3. **معالجة الصفحات**: يقوم التطبيق بتقسيم كل صفحة إلى كلمات
4. **التصحيح**: لكل كلمة، يعرض التطبيق نص OCR المقترح والمستخدم يكتب النص الصحيح
5. **الحفظ والتصدير**: التصحيحات تُحفظ في قاعدة بيانات وتُصدّر بصيغة JSONL

## Features

- **Auto-rotation detection**: Corrects 180° rotated pages automatically
- **Word-level segmentation**: Uses OpenCV contours + Tesseract for accurate word boxes
- **Multi-language OCR**: Arabic (`ara`), English (`eng`), German (`deu`)
- **SQLite database**: Persistent storage with deduplication
- **JSONL export**: Ready for HuggingFace Datasets upload
- **Active Learning loop**: Feeds corrections back to improve future OCR

## Training Samples

This Space references training samples from the parent repository:
- `training-data/samples/medical/` — Arabic handwritten medical documents
- `training-data/samples/technical/` — English/German technical documents (includes 180° rotated pages)

## Export to HuggingFace

After collecting corrections, export and upload:

```python
from datasets import load_dataset
ds = load_dataset('json', data_files='corrections.jsonl')
ds.push_to_hub('DrAbdulmalek/handwriting-corrections-ar-en-de')
```

## Tech Stack

- **Gradio 5.x** — UI framework
- **Tesseract 5.x** — OCR engine
- **OpenCV** — Image processing & word segmentation
- **PyMuPDF** — PDF to image conversion
- **SQLite** — Corrections storage