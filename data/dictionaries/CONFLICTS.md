# CONFLICTS.md — Translation Conflict Log

Generated: 2026-08-25 23:48:43 UTC

**Total conflicts detected:** 27,742

## Conflict Resolution Policy

When the same `normalized_key` (after Arabic normalization) appears in multiple sources
with **different** values, the source with higher priority wins.

Source priority (highest → lowest):
1. `production_arabic_fixes` (existing production dictionary)
2. `arabic_medical_glossary` (verified submodule, 124K pairs)
3. `malek_data_tmx` (translation memory)
4. `ocr_corrections_hf_space` (hardcoded in hf-space/app_core.py)

## Conflict Statistics

| Winner Source | Conflicts Won |
|---------------|---------------|
| `arabic_medical_glossary` | 22,896 |
| `malek_data` | 4,846 |

## Notable Conflicts (top 30 by loser count)

| Key | Winner Source → Value | Losers |
|-----|------------------------|--------|
| `ar` | `arabic_medical_glossary:dictionary_combined` → 'ؠا' | 9683 alternatives |
| `physical exam` | `malek_data:unknown` → 'الفحص السريري' | 197 alternatives |
| `treatment` | `arabic_medical_glossary:hama_tyeb_glossary` → 'علاج' | 193 alternatives |
| `differential diagnosis` | `arabic_medical_glossary:medical_dictionary` → 'التشخيص الفارق - التشخيص بالت... | 176 alternatives |
| `physical therapy` | `arabic_medical_glossary:hama_tyeb_glossary` → 'العلاج الطبيعي' | 166 alternatives |
| `associated conditions` | `malek_data:unknown` → 'الحالات المرافقة' | 133 alternatives |
| `lab` | `arabic_medical_glossary:medical_dictionary` → 'إنفحة' | 106 alternatives |
| `history` | `arabic_medical_glossary:medical_dictionary` → 'تاريخ - سيرة' | 90 alternatives |
| `suffer` | `arabic_medical_glossary:medical_dictionary` → 'يعاني - يقاسي' | 46 alternatives |
| `sustain` | `arabic_medical_glossary:corpus_unl_omw_arabic_wordnet` → 'أثار' | 46 alternatives |
| `bear` | `arabic_medical_glossary:medical_dictionary` → 'الدب' | 45 alternatives |
| `have` | `arabic_medical_glossary:corpus_unl_omw_arabic_wordnet` → 'أثار' | 44 alternatives |
| `get` | `arabic_medical_glossary:corpus_unl_omw_arabic_wordnet` → 'أثار' | 44 alternatives |
| `expect` | `arabic_medical_glossary:corpus_unl_omw_arabic_wordnet` → 'أطاق' | 44 alternatives |
| `carry` | `arabic_medical_glossary:corpus_unl_omw_arabic_wordnet` → 'أطاق' | 43 alternatives |
| `gestate` | `arabic_medical_glossary:corpus_unl_omw_arabic_wordnet` → 'أطاق' | 43 alternatives |
| `median nerve` | `arabic_medical_glossary:medical_dictionary` → 'العصب الوسيط' | 38 alternatives |
| `fix` | `arabic_medical_glossary:medical_dictionary` → 'يثبت' | 35 alternatives |
| `doctor` | `arabic_medical_glossary:medical_dictionary` → 'دكتور - طبيب' | 33 alternatives |
| `repair` | `arabic_medical_glossary:medical_dictionary` → 'تصليح - إصلاح - ترميم. يصلح' | 32 alternatives |
| `restore` | `arabic_medical_glossary:medical_dictionary` → 'يعيد (الصحة أو الوعي)' | 30 alternatives |
| `axillary nerve` | `malek_data:unknown` → 'العصب الإبطي' | 30 alternatives |
| `branches (fig` | `malek_data:unknown` → 'فروع جلدية: يعصب العصب الساعدي الجلدي الوحشي جلد' | 29 alternatives |
| `sciatic nerve` | `arabic_medical_glossary:medical_dictionary` → 'العصب الوركي (عرق النسا)' | 28 alternatives |
| `mend` | `arabic_medical_glossary:corpus_unl_omw_arabic_wordnet` → 'أحيا' | 28 alternatives |
| `bushel` | `arabic_medical_glossary:corpus_unl_omw_arabic_wordnet` → 'أحيا' | 28 alternatives |
| `furbish up` | `arabic_medical_glossary:corpus_unl_omw_arabic_wordnet` → 'أحيا' | 28 alternatives |
| `touch on` | `arabic_medical_glossary:corpus_unl_omw_arabic_wordnet` → 'أحيا' | 28 alternatives |
| `saphenous nerve` | `arabic_medical_glossary:medical_dictionary` → 'العصب الصافن' | 26 alternatives |
| `pectoralis major` | `malek_data:unknown` → 'الصدرية الكبيرة' | 24 alternatives |

## Manual Review Recommendations

The following conflicts involve **medical terminology** and warrant human review:

Found **46** conflicts involving medical section headers or critical terms.

### `composition & excipients`

**Winner:** `arabic_medical_glossary:ABESTOL` → `التركيب والسواغات`

**Alternatives:**

- `arabic_medical_glossary:ABESTOL` → `التركيب`

### `composition`

**Winner:** `arabic_medical_glossary:ABESTOL` → `التركيب`

**Alternatives:**

- `arabic_medical_glossary:medical_dictionary` → `تركيب. مركب`
- `arabic_medical_glossary:medical_dictionary` → `تركيب – مركب (من مجموعة عناصر) – مجمع`
- `arabic_medical_glossary:corpus_unl_omw_arabic_wordnet` → `مُركّب`
- `malek_data:unknown` → `تركيب`
- `malek_data:unknown` → `انشاء`

### `indications`

**Winner:** `arabic_medical_glossary:ABESTOL` → `الاستطبابات`

**Alternatives:**

- `arabic_medical_glossary:medical_dictionary` → `دواعي الاستعمال - استطبابات`
- `arabic_medical_glossary:medical_dictionary` → `دواعي الاستعمال`
- `arabic_medical_glossary:comprehensive_glossary` → `استطبابات`
- `malek_data:unknown` → `استطبابات`
- `malek_data:unknown` → `الاستطبابات`
- `malek_data:unknown` → `الاستطبابات`
- `malek_data:unknown` → `الاستطبابات`

### `contraindications`

**Winner:** `arabic_medical_glossary:pricksage_gemini` → `مضادات الاستطبابات`

**Alternatives:**

- `arabic_medical_glossary:ABESTOL` → `مضادات`
- `arabic_medical_glossary:ALOGLIPTIN` → `مضادات الاستطباب`
- `arabic_medical_glossary:medical_dictionary` → `النواهي - موانع الاستعمال`
- `arabic_medical_glossary:medical_dictionary` → `موانع الاستعمال`
- `malek_data:unknown` → `مضادات الاستطباب`

### `dosage and administration`

**Winner:** `arabic_medical_glossary:ABESTOL` → `الجرعة وطريقة الاستعمال`

**Alternatives:**

- `arabic_medical_glossary:ABESTOL` → `الجرعة`

### `dosage`

**Winner:** `arabic_medical_glossary:ABESTOL` → `الجرعة`

**Alternatives:**

- `arabic_medical_glossary:medical_dictionary` → `معايرة الجرعات - تقدير الجرعات`
- `arabic_medical_glossary:medical_dictionary` → `معايرة ـ تقدير`
- `arabic_medical_glossary:medical_dictionary` → `تقدير الجرعات`
- `arabic_medical_glossary:medical_dictionary` → `الجرعة الدوائية`
- `arabic_medical_glossary:common_pharmaceutical` → `جرعة`

### `side effects`

**Winner:** `arabic_medical_glossary:ABESTOL` → `الآثار الجانبية`

**Alternatives:**

- `arabic_medical_glossary:ABESTOL` → `الآثار`
- `arabic_medical_glossary:core_medical_vocabulary` → `التأثيرات الجانبية`
- `arabic_medical_glossary:hama_tyeb_glossary` → `الأعراض الجانبية`

### `interactions`

**Winner:** `arabic_medical_glossary:ABESTOL` → `التداخلات`

**Alternatives:**

- `arabic_medical_glossary:hama_vitorex` → `التداخلات الدوائية`

### `storage`

**Winner:** `arabic_medical_glossary:ABESTOL` → `التخزين`

**Alternatives:**

- `arabic_medical_glossary:core_medical_vocabulary` → `شروط الحفظ`

### `pregnancy`

**Winner:** `arabic_medical_glossary:ABESTOL` → `الحمل`

**Alternatives:**

- `arabic_medical_glossary:hama_tyeb_glossary` → `حمل`
- `arabic_medical_glossary:medical_dictionary` → `حبل`
- `arabic_medical_glossary:medical_dictionary` → `الحبل - الحمل`
- `arabic_medical_glossary:medical_dictionary` → `حمل (بالعامية: حبل)`
- `arabic_medical_glossary:medical_dictionary` → `حمل - حبل`
- `malek_data:unknown` → `الحمل`

### `overdose`

**Winner:** `arabic_medical_glossary:ABESTOL` → `فرط الجرعة`

**Alternatives:**

- `arabic_medical_glossary:medical_dictionary` → `جرعة مفرطة`

### `overdosage`

**Winner:** `arabic_medical_glossary:ABESTOL` → `فرط`

**Alternatives:**

- `arabic_medical_glossary:AGILOMOX` → `فرط الجرعة`
- `arabic_medical_glossary:dictionaries_master` → `تَعَاطِي جُرْعَةٍ مُفْرِطَة`

### `mechanism of action`

**Winner:** `arabic_medical_glossary:pricksage_gemini` → `آلية التأثير`

**Alternatives:**

- `arabic_medical_glossary:ALOGLIPTIN` → `آلية`

### `pharmacokinetics`

**Winner:** `arabic_medical_glossary:pricksage_gemini` → `الحرائك الدوائية`

**Alternatives:**

- `arabic_medical_glossary:ALOGLIPTIN` → `الحرائك`
- `arabic_medical_glossary:core_medical_vocabulary` → `الحركية الدوائية`
- `arabic_medical_glossary:medical_dictionary` → `حركيات الدواء - حرائك العقار`
- `arabic_medical_glossary:medical_dictionary` → `حرائك الدواء`
- `arabic_medical_glossary:medical_dictionary` → `حركة الدواء في الجسم`

### `overdosage/toxicity`

**Winner:** `arabic_medical_glossary:PRICKSAGE` → `فرط الجرعة/السمية`

**Alternatives:**

- `arabic_medical_glossary:pricksage_gemini` → `فرط الجرعة / السمية`

### `warnings and precautions`

**Winner:** `arabic_medical_glossary:hama_alogliptin` → `التحذيرات والاحتياطات`

**Alternatives:**

- `arabic_medical_glossary:comprehensive_glossary` → `تحذيرات واحتياطات`

### `ablactation`

**Winner:** `arabic_medical_glossary:medical_dictionary` → `فطم. فطام`

**Alternatives:**

- `arabic_medical_glossary:medical_dictionary` → `1. فطام2. انقطاع اللبن`
- `arabic_medical_glossary:medical_dictionary` → `فطام`

### `lactation amenorrhea`

**Winner:** `arabic_medical_glossary:medical_dictionary` → `ضهي الإرضاع`

**Alternatives:**

- `arabic_medical_glossary:medical_dictionary` → `ضهى الإرضاع`

### `decomposition`

**Winner:** `arabic_medical_glossary:medical_dictionary` → `إزالة - نزع`

**Alternatives:**

- `arabic_medical_glossary:medical_dictionary` → `تحلل - تحليل - انحلال - تفكك`
- `arabic_medical_glossary:medical_dictionary` → `تفسخ ـ تحلل`
- `arabic_medical_glossary:medical_dictionary` → `تفكك`

### `decomposition of proteins`

**Winner:** `arabic_medical_glossary:medical_dictionary` → `تفكك البروتينات`

**Alternatives:**

- `arabic_medical_glossary:medical_dictionary` → `تفسخ البروتينات`
