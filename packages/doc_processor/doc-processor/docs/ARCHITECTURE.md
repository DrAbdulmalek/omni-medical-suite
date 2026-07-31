# هيكلية النظام
# System Architecture

## Architecture Overview

Medical Doc Suite follows a **hybrid monorepo** architecture combining a Next.js 16 web application with a PyQt5 desktop application, sharing core image processing algorithms.

## Component Diagram

```
┌──────────────────────────────────────────────────────────────┐
│                    Medical Doc Suite                         │
├──────────────────────────┬───────────────────────────────────┤
│   Web Application        │   Desktop Application            │
│   (Next.js 16)           │   (PyQt5)                        │
│                          │                                   │
│   ┌──────────────┐       │   ┌──────────────┐                │
│   │  React UI    │       │   │  PyQt5 UI    │                │
│   │  shadcn/ui   │       │   │  RTL Arabic  │                │
│   └──────┬───────┘       │   └──────┬───────┘                │
│          │               │          │                         │
│   ┌──────┴───────┐       │   ┌──────┴───────┐                │
│   │  API Routes  │       │   │ Core Module  │                │
│   │  /api/*      │       │   │              │                │
│   └──────┬───────┘       │   └──────┬───────┘                │
│          │               │          │                         │
│   ┌──────┴───────┐       │   ┌──────┴───────┐                │
│   │   Sharp      │       │   │   OpenCV     │                │
│   │ Tesseract.js │       │   │ Tesseract    │                │
│   └──────────────┘       │   └──────────────┘                │
├──────────────────────────┴───────────────────────────────────┤
│                    Shared Layer                              │
│   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│   │  Algorithms  │  │  Database    │  │  Training    │      │
│   │  (Core)      │  │  (Prisma)    │  │  (KNN/JSONL) │      │
│   └──────────────┘  └──────────────┘  └──────────────┘      │
└──────────────────────────────────────────────────────────────┘
```

## Web Application Architecture

### Frontend (React + Next.js 16)
- **Framework**: Next.js 16 with App Router
- **UI Library**: shadcn/ui (New York style)
- **State Management**: Zustand (client), TanStack Query (server)
- **Styling**: Tailwind CSS 4
- **Direction**: RTL (Right-to-Left) for Arabic

### Backend (API Routes)
```
/api/
├── images/            # Image CRUD operations
├── process/[id]/      # Image processing pipeline
├── process-batch/     # Batch processing
├── pdf-pages/         # PDF page rendering & segmentation
├── word-correction/   # Handwriting correction API
├── training-words/    # Training data management
├── ai-chat/           # AI assistant (z-ai-web-dev-sdk)
├── extract-page-number/ # OCR page number extraction
├── export-training/   # Training data export
├── settings/          # Application settings
└── stats/             # Dashboard statistics
```

### Database Schema (Prisma + SQLite)
- **ProcessedImage**: Stores processed image metadata
- **ProcessingLog**: Processing history and quality logs
- **TrainingRecord**: KNN training data for adaptive processing
- **AppSettings**: User preferences and thresholds
- **TrainingWord**: Handwriting training samples

## Desktop Application Architecture

### Core Modules
```
desktop/medical_doc_gui_final.py
├── Core Algorithms
│   ├── find_page_bounds()    # Median-only page detection
│   ├── auto_detect_skew()    # Projection-based skew detection
│   ├── smart_auto_crop()     # Two-stage content cropping
│   ├── calc_blur()           # Laplacian variance blur score
│   └── assess_image_quality() # 6-metric quality assessment
├── Learning System
│   ├── AdaptiveLearner       # Feature-based suggestion engine
│   ├── ImageFeatureExtractor # 30-feature extraction pipeline
│   └── TrainingDataCollector # KNN prediction (top-3 weighted)
├── Worker Threads
│   ├── SkewWorker            # Non-blocking skew detection
│   └── ThumbnailWorker       # Background thumbnail generation
└── UI Components
    ├── MedicalDocApp         # Main window
    ├── CompareDialog         # Before/after comparison
    ├── ThumbButton           # Custom thumbnail widget
    └── LazyImage             # Memory-efficient image loader
```

## Shared Algorithms

### Image Processing Pipeline
```
Input Image
    │
    ├── [1] find_page_bounds() ─── Detect gray borders
    │       └── Median-based column/row analysis
    │
    ├── [2] auto_detect_skew() ─── Detect page tilt
    │       └── Projection profile variance optimization
    │       └── 5% improvement threshold verification
    │
    ├── [3] smart_auto_crop() ─── Remove borders + detect content
    │       ├── Stage 1: Page bounds removal
    │       └── Stage 2: Content region detection
    │
    ├── [4] apply_processing() ─── Apply all transformations
    │       ├── Rotation (0°/90°/180°/270°)
    │       ├── Crop (4-side margins)
    │       ├── Deskew (angle correction)
    │       ├── Horizontal flip
    │       ├── Sharpen (USM)
    │       └── Shadow removal (morphological)
    │
    └── [5] Quality Assessment
            ├── Blur score (Laplacian variance)
            ├── Edge density
            ├── Contrast
            ├── Content ratio
            └── Overall weighted score
```

### KNN Learning Pipeline
```
Training Phase:
    Image → ImageFeatureExtractor.extract() → 30 features
    User adjusts params → Final params saved
    Record: {features, initial_params, final_params, quality}

Prediction Phase:
    New Image → Extract features → Find K=3 nearest neighbors
    → Weighted average of params → Suggested settings
    → Apply if similarity > 0.80 threshold
```

## Data Flow

### Handwriting Training Flow
```
PDF Upload → Client-side rendering (pdf.js)
    → Send page images to /api/pdf-pages
    → Server: segmentPage() → Line detection → Word segmentation
    → Tesseract.js OCR per word → Save to DB
    → User reviews & corrects via UI
    → Corrected data saved as training samples
```

## Technology Stack

| Layer | Web | Desktop |
|-------|-----|---------|
| Runtime | Node.js (Bun) | Python 3.11+ |
| Framework | Next.js 16 | PyQt5 |
| Styling | Tailwind CSS 4 | Qt Stylesheets |
| Image Processing | Sharp | OpenCV + NumPy |
| OCR | Tesseract.js | Tesseract |
| Database | Prisma + SQLite | JSONL files |
| AI | z-ai-web-dev-sdk | - |
