# BilingualExtractor Documentation / توثيق BilingualExtractor

## Arabic-English Medical Parallel Corpus Extraction System
### نظام استخراج Corpus موازٍ طبي عربي-إنجليزي

---

**Version:** 1.0.0
**License:** MIT
**Author:** BilingualExtractor Team

---

## Table of Contents / فهرس المحتويات

1. [Introduction / مقدمة](#1-introduction--مقدمة)
2. [System Architecture / بنية النظام](#2-system-architecture--بنية-النظام)
3. [Installation & Setup / التثبيت والإعداد](#3-installation--setup--التثبيت-والإعداد)
4. [TermExtractor Module / وحدة استخراج المصطلحات](#4-termextractor-module--وحدة-استخراج-المصطلحات)
5. [SentenceAligner Module / وحدة محاذاة الجمل](#5-sentencealigner-module--وحدة-محاذاة-الجمل)
6. [WordAligner Module / وحدة محاذاة الكلمات](#6-wordaligner-module--وحدة-محاذاة-الكلمات)
7. [Export Formats / صيغ التصدير](#7-export-formats--صيغ-التصدير)
8. [Database Schema / مخطط قاعدة البيانات](#8-database-schema--مخطط-قاعدة-البيانات)
9. [API Reference / مرجع API](#9-api-reference--مرجع-api)
10. [Configuration / الإعدادات](#10-configuration--الإعدادات)
11. [Challenges & Solutions / التحديات والحلول](#11-challenges--solutions--التحديات-والحلول)
12. [Development Roadmap / خارطة الطريق](#12-development-roadmap--خارطة-الطريق)

---

## 1. Introduction / مقدمة

### English

BilingualExtractor is an open-source system designed to build a large-scale Arabic-English medical parallel corpus from bilingual textbooks. The system addresses a critical gap in Natural Language Processing (NLP) resources for the Arabic-English language pair in the medical domain. By combining pattern-based term extraction, vector-based sentence alignment, and statistical word alignment techniques, BilingualExtractor enables researchers, translators, and medical professionals to create structured, high-quality bilingual corpora suitable for machine translation training, terminology management, and clinical research applications.

The system is designed with modularity in mind, consisting of four primary components: TermExtractor for identifying and categorizing medical terms, SentenceAligner for aligning parallel sentences, WordAligner for fine-grained word-level alignment, and a comprehensive Export module supporting multiple industry-standard formats including CSV, TSV, JSON, TMX, and Excel. Each component can be used independently or as part of a complete pipeline, making the system adaptable to various research workflows and production environments.

### العربية

BilingualExtractor هو نظام مفتوح المصدر مصمم لبناء corpus موازٍ طبي عربي-إنجليزي ضخم من الكتب المدرسية ثنائية اللغة. يعالج النظام فجوة حرجة في موارد معالجة اللغات الطبيعية (NLP) للزوج اللغوي العربي-الإنجليزي في المجال الطبي. من خلال الجمع بين استخراج المصطلحات القائم على الأنماط، ومحاذاة الجمل القائمة على المتجهات، وتقنيات محاذاة الكلمات الإحصائية، يُمكّن BilingualExtractor الباحثين والمترجمين والمتخصصين الطبيين من إنشاء corpora ثنائية اللغة منظمة وعالية الجودة مناسبة لتدريب الترجمة الآلية وإدارة المصطلحات والتطبيقات البحثية السريرية.

تم تصميم النظام مع مراعاة التركيبية، ويتكون من أربعة مكونات رئيسية: TermExtractor لتحديد وتصنيف المصطلحات الطبية، وSentenceAligner لمحاذاة الجمل الموازية، وWordAligner لمحاذاة الكلمات بدقة، ووحدة تصدير شاملة تدعم صيغاً متعددة معتمدة في الصناعة بما في ذلك CSV وTSV وJSON وTMX وExcel. كل مكون يمكن استخدامه بشكل مستقل أو كجزء من مسار عمل متكامل.

---

## 2. System Architecture / بنية النظام

### English

The BilingualExtractor system follows a modular pipeline architecture where each component processes data independently and can be chained together. The pipeline consists of the following stages:

1. **Input Processing**: Text is loaded from files, directories, or parallel document pairs. A text preprocessor normalizes Arabic text (removing diacritics, normalizing alef variants, handling tatweel) and cleans common OCR errors encountered in scanned medical textbooks.

2. **Term Extraction**: Using regex-based pattern matching and morphological analysis, bilingual term pairs are extracted from the preprocessed text. Terms are categorized into medical domains (orthopedics, cardiology, neurology, etc.) and ranked by confidence scores that consider frequency, co-occurrence strength, and medical domain relevance.

3. **Sentence Alignment**: Parallel sentences are aligned using vector-based similarity (sentence-transformers), with fallback to length-based and dictionary-based methods for cases where vector similarity is below threshold. Supports 1:1, 1:N, and N:1 alignment types.

4. **Word Alignment**: Fine-grained word alignment using Awesome-Align models, with NER-aware alignment for medical named entities such as drug names, anatomical terms, and disease names.

5. **Quality Assessment**: Automated quality scoring evaluates fluency, adequacy, and terminology accuracy for all extracted and aligned content. A human review workflow supports manual verification and correction.

6. **Export**: Results are exported in multiple formats including CSV/TSV for data analysis, TMX for translation memory systems, JSON for programmatic access, and Excel for spreadsheet-based review.

```
Input Text → Preprocessor → TermExtractor → SentenceAligner → WordAligner → Quality Scorer → Exporter
                                ↓                    ↓                 ↓
                           term_pairs.csv      sentences.tsv      word_alignments.json
```

### العربية

يتبع نظام BilingualExtractor بنية مسار عمل تركيبي حيث يعالج كل مكون البيانات بشكل مستقل ويمكن تسلسله مع المكونات الأخرى. يتكون المسار من المراحل التالية:

1. **معالجة المدخلات**: يتم تحميل النص من ملفات أو مجلدات أو أزواج مستندات موازية. يقوم معالج النص بتطبيع النص العربي (إزالة التشكيل، توحيد متغيرات الألف، معالجة التطويل) وتنظيف أخطاء OCR الشائعة في الكتب الطبية الممسوحة ضوئياً.

2. **استخراج المصطلحات**: باستخدام مطابقة الأنماط القائمة على التعابير النمطية والتحليل المورفولوجي، يتم استخراج أزواج المصطلحات ثنائية اللغة من النص المعالج مسبقاً. تُصنف المصطلحات إلى مجالات طبية (جراحة العظام، أمراض القلب، الأعصاب، إلخ) وتُرتّب حسب درجات الثقة التي تأخذ في الاعتبار التكرار وقوة التواجد المشترك والصلة بالمجال الطبي.

3. **محاذاة الجمل**: تتم محاذاة الجمل الموازية باستخدام التشابه القائم على المتجهات (sentence-transformers)، مع الرجوع إلى الطرق القائمة على الطول والقاموس للحالات التي يكون فيها التشابه أقل من العتبة. يدعم أنواع محاذاة 1:1 و1:N وN:1.

4. **محاذاة الكلمات**: محاذاة دقيقة للكلمات باستخدام نماذج Awesome-Align، مع محاذاة واعية للكيانات المسماة الطبية مثل أسماء الأدوية والمصطلحات التشريحية وأسماء الأمراض.

5. **تقييم الجودة**: تقييم الجودة الآلي يقيّم الطلاقة والملاءمة ودقة المصطلحات لجميع المحتوى المستخرج والمحاذى. يدعم سير عمل المراجعة البشرية التحقق اليدوي والتصحيح.

6. **التصدير**: تُصدَّر النتائج بصيغ متعددة تشمل CSV/TSV للتحليل البياني، TMX لأنظمة ذاكرة الترجمة، JSON للوصول البرمجي، وExcel للمراجعة القائمة على الجداول.

---

## 3. Installation & Setup / التثبيت والإعداد

### English

#### Prerequisites

- Python 3.8 or higher
- pip package manager
- 4GB+ RAM (8GB recommended for sentence alignment)
- Optional: CUDA-capable GPU for accelerated sentence alignment

#### Installation

```bash
# Clone the repository
git clone https://github.com/your-org/bilingual-extractor.git
cd bilingual-extractor

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# Install core dependencies
pip install -r requirements.txt

# Optional: Install GPU support for sentence alignment
pip install sentence-transformers  # CPU version
pip install sentence-transformers --extra-index-url https://download.pytorch.org/whl/cu118  # GPU version

# Install development dependencies
pip install -r requirements-dev.txt
```

#### Project Structure

```
bilingual-extractor/
├── term_extractor/          # Term extraction module
│   ├── term_extractor.py    # Main extractor class
│   ├── patterns.py           # Regex patterns library
│   └── medical_resources.py  # Medical dictionaries
├── sentence_aligner/         # Sentence alignment module
│   ├── aligner.py            # Vector-based aligner
│   └── fallback.py           # Length/dictionary fallbacks
├── word_aligner/             # Word alignment module
│   ├── awesome_align.py      # Awesome-Align wrapper
│   └── ner_align.py          # NER-aware alignment
├── exporters/                # Export functionality
│   ├── csv_exporter.py
│   ├── tmx_exporter.py
│   ├── json_exporter.py
│   └── excel_exporter.py
├── database/                 # Database schema & migrations
│   ├── schema.sql
│   └── migrations/
├── notebooks/                # Jupyter notebooks
│   └── bilingual_extractor_demo.ipynb
├── docs/                     # Documentation
├── templates/                # PR & issue templates
├── tests/                    # Test suite
├── requirements.txt
└── setup.py
```

### العربية

#### المتطلبات الأساسية

- Python 3.8 أو أعلى
- مدير حزم pip
- 4GB+ ذاكرة RAM (8GB موصى بها لمحاذاة الجمل)
- اختياري: GPU يدعم CUDA لتسريع محاذاة الجمل

#### التثبيت

```bash
# استنساخ المستودع
git clone https://github.com/your-org/bilingual-extractor.git
cd bilingual-extractor

# إنشاء بيئة افتراضية (موصى بها)
python -m venv venv
source venv/bin/activate  # Linux/Mac

# تثبيت التبعيات الأساسية
pip install -r requirements.txt

# اختياري: تثبيت دعم GPU لمحاذاة الجمل
pip install sentence-transformers  # نسخة CPU
pip install sentence-transformers --extra-index-url https://download.pytorch.org/whl/cu118  # نسخة GPU

# تثبيت تبعيات التطوير
pip install -r requirements-dev.txt
```

#### هيكل المشروع

```
bilingual-extractor/
├── term_extractor/          # وحدة استخراج المصطلحات
│   ├── term_extractor.py    # صنف المستخرج الرئيسي
│   ├── patterns.py           # مكتبة الأنماط النمطية
│   └── medical_resources.py  # القواميس الطبية
├── sentence_aligner/         # وحدة محاذاة الجمل
├── word_aligner/             # وحدة محاذاة الكلمات
├── exporters/                # وظائف التصدير
├── database/                 # مخطط قاعدة البيانات
├── notebooks/                # Jupyter notebooks
├── docs/                     # التوثيق
├── templates/                # قوالب PR والقضايا
├── tests/                    # مجموعة الاختبارات
└── requirements.txt
```

---

## 4. TermExtractor Module / وحدة استخراج المصطلحات

### English

The TermExtractor module is the core component responsible for identifying and extracting bilingual medical term pairs from parallel Arabic-English text. It employs a multi-layered approach combining regex pattern matching, morphological analysis, and statistical filtering to achieve high precision and recall.

#### Key Classes

- **`TermExtractor`**: Main entry point. Orchestrates the extraction pipeline.
- **`TextPreprocessor`**: Normalizes Arabic/English text, fixes OCR errors, detects language.
- **`PatternExtractor`**: Regex-based extraction of Arabic terms, English terms, and bilingual pairs.
- **`MorphologicalAnalyzer`**: Categorizes terms into medical domains, finds dialectal variants, tracks historical terminology evolution.
- **`StatisticalFilter`**: Deduplicates terms using fuzzy matching, calculates confidence scores, ranks results.

#### Quick Start

```python
from term_extractor.term_extractor import TermExtractor, ExtractionConfig

# Create extractor with custom configuration
config = ExtractionConfig(
    min_confidence=0.4,
    min_frequency=2,
    deduplication_threshold=0.85
)

extractor = TermExtractor(config)

# Load text from file
extractor.load_text_file("path/to/textbook.txt")

# Extract terms
terms = extractor.extract_terms()

# Display results
for term in terms[:10]:
    print(f"{term.arabic_term} → {term.english_term} "
          f"(confidence: {term.confidence:.2f}, category: {term.category})")

# Export to CSV
extractor.export_to_csv("output/terms.csv")

# Export to JSON with full metadata
extractor.export_to_json("output/terms.json")

# Export to Excel with formatted sheets
extractor.export_to_excel("output/terms.xlsx")
```

#### CLI Usage

```bash
# Extract from a single file
python -m term_extractor.term_extractor --file textbook.txt --output terms.csv

# Extract from a directory of files
python -m term_extractor.term_extractor --dir ./books/ --output all_terms.json --format json

# Run demo with sample text
python -m term_extractor.term_extractor --demo

# Extract with custom thresholds
python -m term_extractor.term_extractor --file textbook.txt --min-confidence 0.5 --min-frequency 3
```

### العربية

وحدة TermExtractor هي المكون الأساسي المسؤول عن تحديد واستخراج أزواج المصطلحات الطبية ثنائية اللغة من النص الموازي العربي-الإنجليزي. تستخدم نهجاً متعدد الطبقات يجمع بين مطابقة الأنماط النمطية والتحليل المورفولوجي والتصفية الإحصائية لتحقيق دقة واستدعاء عاليين.

#### الأصناف الرئيسية

- **`TermExtractor`**: نقطة الدخول الرئيسية. ينسق مسار الاستخراج.
- **`TextPreprocessor`**: يطبع النص العربي/الإنجليزي، يصلح أخطاء OCR، يكتشف اللغة.
- **`PatternExtractor`**: استخراج قائم على التعابير النمطية للمصطلحات العربية والإنجليزية والأزواج ثنائية اللغة.
- **`MorphologicalAnalyzer`**: يصنف المصطلحات إلى مجالات طبية، يجد المتغيرات اللهجية، يتطور تتبع المصطلحات التاريخي.
- **`StatisticalFilter`**: يزيل المكرر باستخدام المطابقة الضبابية، يحسب درجات الثقة، يرتّب النتائج.

#### البدء السريع

```python
from term_extractor.term_extractor import TermExtractor, ExtractionConfig

# إنشاء المستخرج بإعدادات مخصصة
config = ExtractionConfig(
    min_confidence=0.4,
    min_frequency=2,
    deduplication_threshold=0.85
)

extractor = TermExtractor(config)

# تحميل النص من ملف
extractor.load_text_file("path/to/textbook.txt")

# استخراج المصطلحات
terms = extractor.extract_terms()

# عرض النتائج
for term in terms[:10]:
    print(f"{term.arabic_term} → {term.english_term} "
          f"(ثقة: {term.confidence:.2f}, تصنيف: {term.category})")

# التصدير إلى CSV
extractor.export_to_csv("output/terms.csv")
```

---

## 5. SentenceAligner Module / وحدة محاذاة الجمل

### English

The SentenceAligner module aligns parallel Arabic and English sentences using vector-based similarity computed via multilingual sentence transformers. It supports multiple alignment strategies and can handle complex alignment patterns including 1:N and N:1 mappings where a single sentence in one language corresponds to multiple sentences in the other.

#### Alignment Methods

1. **Vector-Based (Primary)**: Uses sentence-transformers (e.g., `paraphrase-multilingual-MiniLM-L12-v2`) to compute cosine similarity between sentence embeddings. This method captures semantic similarity even when sentences have different structures or use different vocabulary.

2. **Length-Based (Fallback)**: When vector similarity is below threshold, falls back to character length ratio comparison. Arabic sentences tend to be shorter than their English equivalents, and this method uses empirically calibrated ratio thresholds.

3. **Dictionary-Based (Fallback)**: Cross-references known term pairs from the TermExtractor to compute a dictionary-based alignment score, useful when sentences share medical terminology but have otherwise different structures.

4. **Hybrid**: Combines scores from all three methods using weighted averaging, with the weight of each method determined by the quality of its individual score.

#### Usage Example

```python
from sentence_aligner.aligner import SentenceAligner

aligner = SentenceAligner(
    model_name="paraphrase-multilingual-MiniLM-L12-v2",
    min_confidence=0.8,
    alignment_type="1:1"  # or "flexible" for 1:N, N:1
)

# Align parallel sentences
alignments = aligner.align(
    arabic_sentences=["الكسر هو انقطاع في استمرارية العظم.", "يتم علاج الكسر بالجبيرة."],
    english_sentences=["A fracture is a break in bone continuity.", "Fractures are treated with casts."]
)

for alignment in alignments:
    print(f"[{alignment.confidence:.2f}] {alignment.sentence_ar[:50]}... ↔ {alignment.sentence_en[:50]}...")
```

### العربية

وحدة SentenceAligner تحاذي الجمل العربية والإنجليزية الموازية باستخدام التشابه القائم على المتجهات المحسوب عبر محولات الجمل متعددة اللغات. تدعم استراتيجيات محاذاة متعددة ويمكنها التعامل مع أنماط محاذاة معقدة بما في ذلك التعيينات 1:N وN:1 حيث تتوافق جملة واحدة في لغة واحدة مع جمل متعددة في اللغة الأخرى.

---

## 6. WordAligner Module / وحدة محاذاة الكلمات

### English

The WordAligner module performs fine-grained word-level alignment within already-aligned sentence pairs. It uses Awesome-Align (an unsupervised word alignment model based on mBERT) with specialized handling for medical named entities. The module recognizes that medical terms often have different morphological structures across Arabic and English, and applies domain-specific alignment heuristics.

#### Key Features

- **NER-Aware Alignment**: Uses BiLSTM-CRF or transformer-based NER models to identify medical entities (diseases, drugs, anatomical terms) before alignment, ensuring these critical terms receive higher alignment priority and accuracy.
- **Morphological Matching**: Handles Arabic morphological complexity by considering stem-level matching alongside surface-form matching.
- **Confidence Scoring**: Each word alignment is assigned a confidence score based on the model's alignment probability, contextual similarity, and NER agreement.

### العربية

وحدة WordAligner تؤدي محاذاة دقيقة على مستوى الكلمات داخل أزواج الجمل المحاذاة مسبقاً. تستخدم Awesome-Align (نموذج محاذاة كلمات غير خاضع للإشراف قائم على mBERT) مع معالجة متخصصة للكيانات المسماة الطبية.

---

## 7. Export Formats / صيغ التصدير

### English

BilingualExtractor supports multiple export formats to accommodate different use cases:

| Format | Extension | Use Case | Module |
|--------|-----------|----------|--------|
| CSV | `.csv` | Data analysis, spreadsheet import | CSVExporter |
| TSV | `.tsv` | Parallel corpus standard format | TSVExporter |
| JSON | `.json` | Programmatic API access, web apps | JSONExporter |
| TMX | `.tmx` | Translation memory systems (SDL Trados, memoQ) | TMXExporter |
| Excel | `.xlsx` | Human review, formatted reports | ExcelExporter |
| SQLite | `.db` | Local database storage | DatabaseExporter |

#### TMX Export Details

The TMX (Translation Memory eXchange) format is the industry standard for translation memory interchange. BilingualExtractor generates TMX 1.4b compliant files with the following structure:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE tmx SYSTEM "tmx14.dtd">
<tmx version="1.4b">
  <header creationtool="BilingualExtractor" creationtoolversion="1.0.0"
          datatype="plaintext" segtype="sentence" adminlang="en-US"
          o-tmf="BilingualExtractor"/>
  <body>
    <tu>
      <tuv xml:lang="ar">
        <seg>الكسر هو انقطاع في استمرارية العظم</seg>
      </tuv>
      <tuv xml:lang="en">
        <seg>A fracture is a break in bone continuity</seg>
      </tuv>
    </tu>
  </body>
</tmx>
```

### العربية

يدعم BilingualExtractor صيغ تصدير متعددة لاستيعاب حالات الاستخدام المختلفة:

| الصيغة | الامتداد | حالة الاستخدام |
|--------|---------|----------------|
| CSV | `.csv` | تحليل البيانات، استيراد الجداول |
| TSV | `.tsv` | صيغة corpus الموازي القياسية |
| JSON | `.json` | الوصول البرمجي عبر API، تطبيقات الويب |
| TMX | `.tmx` | أنظمة ذاكرة الترجمة (SDL Trados, memoQ) |
| Excel | `.xlsx` | المراجعة البشرية، التقارير المنسقة |

---

## 8. Database Schema / مخطط قاعدة البيانات

### English

The database schema supports the full lifecycle of the corpus building process, from source document management to export tracking. The schema uses PostgreSQL as the primary database engine with support for JSONB columns for flexible metadata storage. Key tables include:

- **`medical_domains`**: Hierarchical categorization of medical specialties
- **`source_documents`**: Metadata for input textbooks (author, publisher, OCR quality)
- **`document_pages`**: Individual page content with character/word counts
- **`arabic_terms` / `english_terms`**: Normalized term storage with frequency data
- **`term_pairs`**: Bilingual term mappings with confidence scores
- **`sentence_alignments`**: Aligned sentence pairs with quality metrics
- **`word_alignments`**: Fine-grained word-level alignments with NER annotations
- **`quality_assessments`**: Automated quality scores and human review records
- **`export_jobs`**: Export history and configuration tracking

The schema includes performance-optimized indexes, views for common queries, and trigger functions for automatic timestamp and count updates. See `database/schema.sql` for the complete DDL.

### العربية

يدعم مخطط قاعدة البيانات دورة حياة كاملة لعملية بناء Corpus، من إدارة المستندات المصدرية إلى تتبع التصدير. يستخدم المخطط PostgreSQL كمحرك قاعدة بيانات أساسي مع دعم أعمدة JSONB لتخزين البيانات الوصفية المرنة.

---

## 9. API Reference / مرجع API

### English

#### TermExtractor Class

```python
class TermExtractor:
    """Main bilingual medical term extractor."""

    def __init__(self, config: Optional[ExtractionConfig] = None) -> None:
        """Initialize with optional configuration."""

    def load_text(self, text: str) -> 'TermExtractor':
        """Load raw text string for extraction. Returns self for chaining."""

    def load_text_file(self, file_path: str, encoding: str = 'utf-8') -> 'TermExtractor':
        """Load text from a file. Returns self for chaining."""

    def load_directory(self, dir_path: str, extensions: List[str] = None) -> 'TermExtractor':
        """Load all text files from a directory. Returns self for chaining."""

    def load_parallel_files(self, ar_file: str, en_file: str) -> 'TermExtractor':
        """Load parallel Arabic and English files. Returns self for chaining."""

    def extract_terms(self) -> List[TermPair]:
        """Execute extraction pipeline. Returns list of TermPair sorted by confidence."""

    def get_stats(self) -> Dict:
        """Return extraction statistics dictionary."""

    def get_terms_by_category(self, category: str) -> List[TermPair]:
        """Filter terms by medical category."""

    def get_high_confidence_terms(self, threshold: float = 0.7) -> List[TermPair]:
        """Get terms above confidence threshold."""

    def export_to_csv(self, output_path: str, include_variants: bool = False) -> str:
        """Export to CSV format. Returns saved file path."""

    def export_to_json(self, output_path: str) -> str:
        """Export to JSON format. Returns saved file path."""

    def export_to_excel(self, output_path: str) -> str:
        """Export to Excel format. Returns saved file path."""
```

#### TermPair Data Class

```python
@dataclass
class TermPair:
    arabic_term: str          # Arabic term text
    english_term: str         # English term text
    frequency: int = 1        # Occurrence count
    confidence: float = 0.0   # Confidence score (0.0 - 1.0)
    source_page: int = -1     # Source page number
    category: str = "general" # Medical category
    context_ar: str = ""      # Arabic context sentence
    context_en: str = ""      # English context sentence
    variants_ar: List[str]    # Arabic dialectal variants
    variants_en: List[str]    # English variants
```

### العربية

#### صنف TermExtractor

```python
class TermExtractor:
    """مستخرج المصطلحات الطبية ثنائي اللغة الرئيسي."""

    def load_text(self, text: str) -> 'TermExtractor':
        """تحميل نص خام للاستخراج. يعيد الذات للتسلسل."""

    def extract_terms(self) -> List[TermPair]:
        """تنفيذ مسار الاستخراج. يعيد قائمة TermPair مرتبة حسب الثقة."""

    def export_to_csv(self, output_path: str) -> str:
        """التصدير بصيغة CSV. يعيد مسار الملف المحفوظ."""
```

---

## 10. Configuration / الإعدادات

### English

The extraction process is fully configurable through the `ExtractionConfig` data class. Below are all configurable parameters with their default values and descriptions:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `min_term_length_ar` | int | 2 | Minimum Arabic term length in characters |
| `min_term_length_en` | int | 2 | Minimum English term length in characters |
| `max_term_length_ar` | int | 6 | Maximum Arabic term length in words |
| `max_term_length_en` | int | 5 | Maximum English term length in words |
| `min_frequency` | int | 1 | Minimum term occurrence frequency |
| `min_confidence` | float | 0.3 | Minimum confidence threshold for inclusion |
| `regex_patterns` | bool | True | Enable regex-based pattern extraction |
| `morphological_analysis` | bool | True | Enable morphological categorization |
| `statistical_filtering` | bool | True | Enable statistical deduplication |
| `deduplication_threshold` | float | 0.85 | Fuzzy match threshold for deduplication |
| `include_context` | bool | True | Include surrounding context for terms |
| `max_context_length` | int | 200 | Maximum context character length |

### العربية

عملية الاستخراج قابلة للتكوين بالكامل عبر صنف `ExtractionConfig`. أدناه جميع المعاملات القابلة للتكوين مع قيمها الافتراضية وأوصافها:

| المعامل | النوع | الافتراضي | الوصف |
|---------|-------|-----------|-------|
| `min_term_length_ar` | int | 2 | الحد الأدنى لطول المصطلح العربي بالحروف |
| `min_term_length_en` | int | 2 | الحد الأدنى لطول المصطلح الإنجليزي بالحروف |
| `min_confidence` | float | 0.3 | عتبة الثقة الدنيا للضم |
| `deduplication_threshold` | float | 0.85 | عتبة المطابقة الضبابية لإزالة التكرار |
| `include_context` | bool | True | تضمين السياق المحيط بالمصطلحات |

---

## 11. Challenges & Solutions / التحديات والحلول

### English

#### OCR Errors in Mixed-Script Text

**Challenge**: Medical textbooks scanned from bilingual Arabic-English sources often contain OCR errors including misrecognized Arabic characters, garbled mixed-script passages, and incorrect number recognition.

**Solution**: The `TextPreprocessor` class implements a multi-stage OCR error correction pipeline. First, common character-level substitutions are corrected (e.g., Arabic digit misrecognition, tatweel removal). Second, spacing issues around mixed-script boundaries are resolved using language-specific regex patterns. Third, a post-processing validation step flags low-confidence text regions for manual review. The system also supports an active learning loop where corrected OCR errors are fed back to improve future processing.

#### Dialectal Terminology Variations

**Challenge**: Arabic medical terminology varies significantly across regional dialects. For example, "fracture" may be referred to as "الكُسر" in Egypt, "الكَسر" in the Levant, and "الانكسار" in Gulf countries.

**Solution**: The `MorphologicalAnalyzer` maintains a comprehensive dialect mapping dictionary that normalizes dialectal variants to their Modern Standard Arabic (MSA) equivalents. Each term pair includes a `variants_ar` field listing known dialectal forms. The synonym mapping is extensible and can be enhanced with crowd-sourced contributions from medical professionals across different Arab regions.

#### Historical Terminology Evolution

**Challenge**: Older medical texts use historical terminology that differs from modern usage. For instance, "الفالج" (an older term for stroke/paralysis) has been largely replaced by "الشلل" in contemporary Arabic medical literature.

**Solution**: The `TerminologyEvolution` tracker maps historical terms to their modern equivalents, maintaining both forms in the database with cross-references. This enables researchers to build diachronic corpora that track how medical terminology has evolved, while ensuring modern applications use current terminology.

#### 1:N and N:1 Sentence Alignments

**Challenge**: Parallel texts frequently contain structural divergences where a single Arabic sentence corresponds to multiple English sentences or vice versa, making simple 1:1 alignment insufficient.

**Solution**: The `SentenceAligner` implements a dynamic programming algorithm that evaluates multiple alignment hypotheses using combined vector similarity, length ratio, and dictionary overlap scores. The algorithm supports 1:1, 1:N, N:1, and N:M alignment types with configurable thresholds for each type.

### العربية

#### أخطاء OCR في النصوص المختلطة

**التحدي**: الكتب الطبية الممسوحة ضوئياً من مصادر ثنائية اللغة غالباً ما تحتوي على أخطاء OCR تشمل إساءة التعرف على الحروف العربية والمقاطع المختلطة المشوشة وإساءة التعرف على الأرقام.

**الحل**: ينفذ صنف `TextPreprocessor` مسار تصحيح أخطاء OCR متعدد المراحل. أولاً، تُصلح الاستبدالات الشائعة على مستوى الحرف. ثانياً، تُحل مشكلات المسافات حول حدود النص المختلط. ثالثاً، تُحدد مناطق النص منخفضة الثقة للمراجعة اليدوية.

#### تباينات المصطلحات اللهجية

**التحدي**: تتباين المصطلحات الطبية العربية بشكل كبير عبر اللهجات الإقليمية. على سبيل المثال، "الكسر" قد يُشار إليه بـ "الكُسر" في مصر و"الكَسر" في الشام و"الانكسار" في دول الخليج.

**الحل**: يحافظ `MorphologicalAnalyzer` على قاموس شامل لربط اللهجات يطبع المتغيرات اللهجية إلى ما يعادلها بالعربية الفصحى الحديثة. كل زوج مصطلحات يتضمن حقل `variants_ar` يعرض الأشكال اللهجية المعروفة.

#### تطور المصطلحات التاريخي

**التحدي**: النصوص الطبية القديمة تستخدم مصطلحات تاريخية تختلف عن الاستخدام الحديث. على سبيل المثال، "الفالج" (مصطلح قديم للسكتة الدماغية/الشلل) تم استبداله إلى حد كبير بـ "الشلل" في الأدبيات الطبية العربية المعاصرة.

**الحل**: يتتبع `TerminologyEvolution` المصطلحات التاريخية ويربطها بما يعادلها الحديث، مع الحفاظ على كلا الشكلين في قاعدة البيانات مع مراجع متبادلة.

---

## 12. Development Roadmap / خارطة الطريق

### English

#### Sprint 1-2 (Weeks 1-2): MVP TermExtractor

- Core TermExtractor with pattern-based extraction
- CSV/TSV export functionality
- Basic web interface for term browsing
- Target: Extract 100+ terms from a single medical textbook
- Deliverable: Working demo with exportable results

#### Sprint 3-4 (Weeks 3-4): Sentence Alignment

- Vector-based SentenceAligner implementation
- 1:1 alignment with confidence scoring
- TSV export for aligned sentences
- Web interface for sentence comparison
- Target: Align 50+ sentences with >80% confidence

#### Sprint 5-6 (Weeks 5-6): Word Alignment + Quality

- Awesome-Align integration for word alignment
- Quality scoring module (fluency, adequacy, terminology)
- TMX export for translation memory systems
- Statistical reports and corpus analytics
- Target: Accurate word alignments with automated quality assessment

#### Future Enhancements

- Deep learning-based term extraction (BiLSTM-CRF)
- Active learning for OCR error correction
- RESTful API for programmatic access
- Docker containerization for easy deployment
- Integration with major CAT tools (SDL Trados, memoQ, OmegaT)
- Mobile application for field terminology collection

### العربية

#### Sprint 1-2 (الأسبوعان 1-2): MVP لمستخرج المصطلحات

- TermExtractor أساسي مع استخراج قائم على الأنماط
- وظيفة تصدير CSV/TSV
- واجهة ويب بسيطة لتصفح المصطلحات
- الهدف: استخراج 100+ مصطلح من كتاب طبي واحد

#### Sprint 3-4 (الأسبوعان 3-4): محاذاة الجمل

- تطبيق SentenceAligner القائم على المتجهات
- محاذاة 1:1 مع تسجيل الثقة
- تصدير TSV للجمل المحاذاة
- واجهة ويب لمقارنة الجمل
- الهدف: محاذاة 50+ جملة بثقة تتجاوز 80%

#### Sprint 5-6 (الأسبوعان 5-6): محاذاة الكلمات + الجودة

- تكامل Awesome-Align لمحاذاة الكلمات
- وحدة تسجيل الجودة (الطلاقة، الملاءمة، المصطلحات)
- تصدير TMX لأنظمة ذاكرة الترجمة
- تقارير إحصائية وتحليلات Corpus

#### التحسينات المستقبلية

- استخراج مصطلحات قائم على التعلم العميق (BiLSTM-CRF)
- التعلم النشط لتصحيح أخطاء OCR
- API RESTful للوصول البرمجي
- حاوية Docker للنشر السهل
- التكامل مع أدوات CAT الرئيسية (SDL Trados, memoQ, OmegaT)

---

## Contributing / المساهمة

We welcome contributions from researchers, developers, and medical professionals. Please see `CONTRIBUTING.md` for guidelines and use the PR template in `templates/PR_TEMPLATE.md` when submitting pull requests.

نرحب بالمساهمات من الباحثين والمطورين والمتخصصين الطبيين. يرجى مراجعة `CONTRIBUTING.md` للإرشادات واستخدام قالب PR في `templates/PR_TEMPLATE.md` عند تقديم طلبات السحب.

---

## License / الترخيص

This project is licensed under the MIT License. See `LICENSE` for details.

هذا المشروع مرخص بموجب ترخيص MIT. راجع `LICENSE` للتفاصيل.
