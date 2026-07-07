<!-- ARCHIVE BANNER - AUTO-GENERATED -->
<div align="center">

# ⚠️ This repository has been archived

**Document processor merged into omni-medical-suite/backend/parsers/**

This project has been consolidated into the unified **[omni-medical-suite](https://github.com/DrAbdulmalek/omni-medical-suite)** monorepo.

All active development, bug fixes, and new features continue there.

</div>

---

> **Archived on: 2026-06-28** | **Active project:** [omni-medical-suite](https://github.com/DrAbdulmalek/omni-medical-suite)

---

> **⚠️ LEGACY**: This repo is being merged into [omni-medical-suite](https://github.com/DrAbdulmalek/omni-medical-suite).  
> See [LEGACY_NOTICE.md](./LEGACY_NOTICE.md) for migration details.

---

# 🏥 Medical Document Suite | معالج المستندات الطبية

> A comprehensive medical document processing platform that combines image processing, OCR, handwriting recognition, and AI-powered quality assessment into a unified monorepo.

> منصة شاملة لمعالجة المستندات الطبية تجمع بين معالجة الصور والتعرف على النصوص وتدريب خط اليد وتقييم الجودة بالذكاء الاصطناعي في مستودع موحّد.

---

## ✨ Features | الميزات

### 🖼️ Image Processing | معالجة الصور
- **Smart Auto-Crop** — Intelligent page boundary detection and cropping
- **Auto Deskew** — Automatic skew angle detection and correction
- **Gray Border Removal** — Removes scanner artifacts and gray borders
- **Quality Assessment** — Blur detection before and after processing
- **Batch Processing** — Process multiple images with progress tracking

### ✍️ Handwriting Training | تدريب خط اليد
- **OCR Integration** — Tesseract-based text recognition
- **Word Segmentation** — Automatic word and line detection
- **Manual Correction** — Interactive correction interface
- **Training Data Management** — Store and manage training samples
- **Confidence Scoring** — Real-time confidence metrics

### 🤖 AI Capabilities | الذكاء الاصطناعي
- **Chat Assistant** — AI-powered processing assistant (Arabic)
- **Auto-Suggestions** — Smart parameter recommendations
- **Quality Prediction** — ML-based quality assessment
- **Settings Parsing** — Natural language settings configuration

### 🧠 KNN Learning | KNN التعلّم
- **Training Data** — Curated training dataset management
- **Prediction** — KNN-based word prediction
- **Model Management** — Train, evaluate, and manage models
- **Performance Metrics** — Accuracy and confidence tracking

### 💻 Desktop App | تطبيق سطح المكتب
- **Electron Wrapper** — Desktop application with native feel
- **Python Core** — Backend processing engine
- **Auto-Update** — Built-in update mechanism

---

## 🚀 Quick Start | البدء السريع

### Prerequisites | المتطلبات

- **Node.js** >= 18.x
- **pnpm** >= 8.x (or **bun** >= 1.x)
- **Python** >= 3.9 (for core algorithms)
- **Tesseract OCR** installed on the system

### Installation | التثبيت

```bash
# Clone the repository
git clone https://github.com/DrAbdulmalek/medical-doc-processor.git
cd medical-doc-processor

# Install dependencies
bun install

# Set up the database
bun run db:push

# Start the development server
bun run dev
```

### Environment Setup | إعداد البيئة

```bash
# Copy environment template
cp .env.example .env.local

# Install Tesseract OCR (Ubuntu/Debian)
sudo apt install tesseract-ocr tesseract-ocr-arab

# Install Tesseract OCR (macOS)
brew install tesseract tesseract-lang
```

---

## 📁 Monorepo Structure | هيكل المستودع

```
medical-doc-suite/
├── packages/
│   ├── web/          # Next.js 16 web application
│   ├── desktop/      # Electron desktop application
│   ├── core/         # Shared processing engine (Python)
│   ├── mobile/       # React Native mobile app
│   └── shared/       # Shared types, utils, components
├── turbo.json        # Turborepo configuration
├── pnpm-workspace.yaml
├── package.json
└── README.md
```

### Source Projects | المشاريع المصدرية

| Project | Description | Status |
|---------|-------------|--------|
| `medical-doc-processor` | Main web + desktop app (Next.js + Electron) | ✅ Active |
| `medical-document-scanner` | Desktop scanner app (PyQt5) | 🔄 Merging |
| `medical-doc-webapp` | Mobile-first web app (React) | 🔄 Merging |

---

## 📜 Available Scripts | الأوامر المتاحة

### Development | التطوير

| Command | Description |
|---------|-------------|
| `bun run dev` | Start development server on port 3000 |
| `bun run lint` | Run ESLint for code quality |
| `bun run db:push` | Push Prisma schema to database |
| `bun run db:studio` | Open Prisma Studio (database GUI) |

### Testing | الاختبار

| Command | Description |
|---------|-------------|
| `python test_core.py` | Run core algorithm tests |
| `python -m pytest` | Run all Python tests with pytest |

### Build | البناء

| Command | Description |
|---------|-------------|
| `bun run build` | Create production build |
| `bun run start` | Start production server |

---

## ⌨️ Keyboard Shortcuts | اختصارات لوحة المفاتيح

| Shortcut | Action | الوظيفة |
|----------|--------|---------|
| `Ctrl + U` | Upload images | رفع الصور |
| `Ctrl + Enter` | Start processing | بدء المعالجة |
| `Ctrl + S` | Save settings | حفظ الإعدادات |
| `Ctrl + ,` | Open settings | فتح الإعدادات |
| `Ctrl + B` | Toggle sidebar | تبديل الشريط الجانبي |
| `Esc` | Close dialogs | إغلاق النوافذ |

---

## 🛠️ Tech Stack | التقنيات المستخدمة

### Frontend | الواجهة الأمامية
- **Framework**: Next.js 16 (App Router) + TypeScript
- **Styling**: Tailwind CSS 4 + shadcn/ui
- **State**: Zustand + TanStack Query
- **Icons**: Lucide React
- **Charts**: Recharts
- **Animation**: Framer Motion

### Backend | الخادم
- **Runtime**: Node.js (Bun)
- **Database**: SQLite + Prisma ORM
- **AI**: z-ai-web-dev-sdk
- **Auth**: NextAuth.js v4

### Processing Engine | محرك المعالجة
- **Image Processing**: Sharp (Node.js) + OpenCV (Python)
- **OCR**: Tesseract.js + Tesseract (Python)
- **ML**: scikit-learn (KNN classifier)
- **Desktop**: Electron + Python bridge

---

## 🔧 Troubleshooting | حل المشاكل

### Common Issues | مشاكل شائعة

<details>
<summary><strong>OCR not working / التعرف على النصوص لا يعمل</strong></summary>

Make sure Tesseract is installed and the Arabic language pack is available:
```bash
tesseract --list-langs
```
If Arabic (`ara`) is not listed:
```bash
sudo apt install tesseract-ocr-arab
```
</details>

<details>
<summary><strong>Images not processing / الصور لا تُعالَج</strong></summary>

- Ensure images are in supported formats (JPEG, PNG, WebP, TIFF)
- Check file permissions
- Verify sufficient disk space for temporary files
</details>

<details>
<summary><strong>Database errors / أخطاء قاعدة البيانات</strong></summary>

```bash
# Reset the database
rm -f db/dev.db
bun run db:push
```
</details>

<details>
<summary><strong>Port 3000 already in use / المنفذ 3000 مستخدم</strong></summary>

```bash
# Kill the process on port 3000
lsof -ti:3000 | xargs kill -9
# Then restart
bun run dev
```
</details>

<details>
<summary><strong>Blur values seem incorrect / قيم الضبابية تبدو غير صحيحة</strong></summary>

The blur detection uses the Laplacian variance method. Very high-quality or very low-quality images may show unexpected values. Adjust `minConfidence` in settings for better filtering.
</details>

---

## 📄 License | الترخيص

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

---

<div align="center">

**معالج المستندات الطبية v3.0** | Medical Document Suite

Built with ❤️ by [Dr. Abdulmalek](https://github.com/DrAbdulmalek)

</div>


---

## Repository Status

| Field | Value |
|-------|-------|
| **Role** | Desktop/Web Review App (Image Quality) |
| **Status** | Legacy / Migrating to omni-medical-suite |
| **Layer** | Applications (Product) |
| **Priority** | Medium |
| **Migration Target** | [omni-medical-suite](https://github.com/DrAbdulmalek/omni-medical-suite) |

## Migration Notice

> This repository is in the process of being integrated into [omni-medical-suite](https://github.com/DrAbdulmalek/omni-medical-suite).
> For new features and the unified platform, please use omni-medical-suite.

## Who Should Use This (Current)

- Users specifically needing the **PyQt5 desktop image processing** capabilities
- Teams focused on **document scanning and quality checking** workflows
- Developers maintaining existing integrations with this codebase

## When to Use This vs omni-medical-suite

| Need | Repository |
|------|-----------|
| Full unified medical document processing | [omni-medical-suite](https://github.com/DrAbdulmalek/omni-medical-suite) |
| Desktop image scanning & quality check | **This repo** (medical-doc-processor) |
| OCR correction engine | [medical-ocr-postprocessor](https://github.com/DrAbdulmalek/medical-ocr-postprocessor) |
| Production handwriting OCR | [medical-handwriting-ocr](https://github.com/DrAbdulmalek/medical-handwriting-ocr) |

## Migration Path

```
medical-doc-processor
├── packages/core/     → omni-medical-suite/packages/medical
├── packages/web/      → omni-medical-suite/apps/web
├── packages/desktop/  → Legacy (standalone)
└── packages/mobile/   → omni-medical-suite/apps/mobile
```

## Related Repositories

| Repo | Role | Status |
|------|------|--------|
| [omni-medical-suite](https://github.com/DrAbdulmalek/omni-medical-suite) | Main Platform (Migration Target) | Active |
| [medical-ocr-postprocessor](https://github.com/DrAbdulmalek/medical-ocr-postprocessor) | Core Correction Engine | Active |
| [medical-handwriting-ocr](https://github.com/DrAbdulmalek/medical-handwriting-ocr) | Production OCR | Active |

**License: MIT** — Dr. Abdulmalek Tamer Al-husseini
