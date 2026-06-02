---
title: Medical OCR Suite
emoji: 🏥
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
license: mit
---

# 🩺 Medical OCR Suite — منصة معالجة النصوص الطبية

> تجربة مباشرة لمكتبة تصحيح النصوص الطبية (Arabic/English)

## 🚀 الميزات

- **تصحيح نصوص OCR**: تدعم العربية والإنجليزية مع قاموس طبي يضم +921,000 مصطلح
- **حجب البيانات الصحية (PHI Masking)**: حجب تلقائي لأسماء المرضى والتواريخ والأرقام
- **معالجة مجمعة**: معالجة عدة ملفات في وقت واحد

## 🔗 نقاط الوصول (API)

| Endpoint | الوصف |
|----------|-------|
| `GET /` | حالة المنصة |
| `GET /docs` | وثائق API التفاعلية (Swagger) |
| `POST /correct` | تصحيح نص طبي |
| `POST /correct/batch` | تصحيح مجموعة نصوص |
| `POST /mask-phi` | حجب البيانات الصحية |
| `POST /health` | فحص حالة النظام |

## 📦 التكنولوجيا

- **FastAPI** — خادم API عالي الأداء
- **medical-ocr-postprocessor** — محرك التصحيح الأساسي
- **Docker** — حاوية معزولة وجاهزة للنشر

## 👨‍⚕️ المطور

Dr. Abdulmalek Tamer Al-husseini

## 📄 الترخيص

MIT License
