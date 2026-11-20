## Description / الوصف

Please include a summary of the change and which component is affected.  
يرجى تضمين ملخص للتغيير والمكون المتأثر.

<!--
Example examples:
- TermExtractor: Add support for Egyptian dialect variant mapping
- SentenceAligner: Implement hybrid alignment with dictionary fallback
- Exporters: Add TMX 1.4b export with segmentation support
- Database: Add full-text search indexes for Arabic and English terms
-->

**Component**: [TermExtractor / SentenceAligner / WordAligner / Exporters / Database / Docs / Tests]

**Related Issue**: # [issue number]

---

## Type of Change / نوع التغيير

<!-- Check all that apply / ضع علامة على كل ما ينطبق -->

- [ ] Bug fix / إصلاح خطأ
- [ ] New feature / ميزة جديدة
- [ ] Breaking change / تغيير كبير
- [ ] Documentation update / تحديث التوثيق
- [ ] Refactoring / إعادة هيكلة
- [ ] Performance improvement / تحسين الأداء
- [ ] Test coverage / تغطية الاختبارات
- [ ] Database migration / ترحيل قاعدة البيانات

---

## Motivation and Context / الدافع والسياق

Why is this change needed? What problem does it solve?
لماذا هذا التغيير مطلوب؟ ما المشكلة التي يحلها؟

<!-- 
Provide context for the change. For medical domain changes, include:
- Which medical specialty is affected
- What terminology or alignment issues are addressed
- How this impacts corpus quality or researcher workflow

قم بتوفير سياق للتغيير. للتغييرات المتعلقة بالمجال الطبي، أضف:
- التخصص الطبي المتأثر
- مشاكل المصطلحات أو المحاذاة المعالجة
- تأثير ذلك على جودة Corpus أو سير عمل الباحث
-->

---

## Changes Made / التغييرات المنفذة

### Files Modified / الملفات المعدلة

<!-- List all files changed with brief description -->

| File | Change Description |
|------|-------------------|
| `path/to/file.py` | Brief description of change |
| `path/to/test_file.py` | Brief description of change |

### Code Changes / التغييرات البرمجية

<!-- 
Describe the implementation details. Include:
- New classes, functions, or methods added
- Algorithm changes or optimizations
- API changes (new parameters, return types)
- Database schema changes
-->

**New Classes/Functions:**

```python
# Example: New function signature
def new_function(param1: str, param2: int = 0) -> List[TermPair]:
    """
    Brief description of what this function does.
    وصف مختصر لوظيفة هذه الدالة.
    """
```

**Algorithm Changes:**

<!-- Describe any changes to extraction, alignment, or scoring algorithms -->

**API Changes:**

| Endpoint / Function | Before | After |
|---------------------|--------|-------|
| `extract_terms()` | Returns `List[TermPair]` | Returns `List[TermPair]` with new `source` field |

---

## Testing / الاختبارات

### Test Coverage / تغطية الاختبارات

<!-- 
Describe how the changes were tested. Include:
- Unit tests added or modified
- Integration tests
- Performance benchmarks
- Test data used (sample textbooks, specific medical domains)
-->

**Unit Tests:**

```bash
# Run unit tests
pytest tests/unit/test_component.py -v

# Expected output / الناتج المتوقع
# tests/unit/test_component.py::test_function PASSED
```

**Integration Tests:**

```bash
# Run integration tests
pytest tests/integration/ -v
```

**Test Data / بيانات الاختبار:**

<!-- 
Describe the test data used:
- Medical domain(s) tested
- Number of terms/sentences in test data
- Source of test data (synthetic, real textbook excerpt)
-->

### Manual Testing / الاختبار اليدوي

<!-- Steps performed for manual verification -->

1. Step 1: Load sample medical text
2. Step 2: Run extraction with configuration X
3. Step 3: Verify output matches expected results
4. Step 4: Export and validate file format

---

## Medical Domain Impact / التأثير على المجال الطبي

### Terminology Coverage / تغطية المصطلحات

| Domain / المجال | Terms Before | Terms After | Change |
|----------------|-------------|------------|--------|
| Orthopedics / جراحة العظام | N/A | [count] | +[count] |
| Cardiology / أمراض القلب | N/A | [count] | +[count] |

### Dialectal Support / دعم اللهجات

<!-- 
List any new dialectal variants or mappings added:
- [ ] Egyptian Arabic / العربية المصرية
- [ ] Levantine Arabic / العربية الشامية
- [ ] Gulf Arabic / العربية الخليجية
- [ ] Maghrebi Arabic / العربية المغاربية
- [ ] Modern Standard Arabic / العربية الفصحى
-->

### Historical Terminology / المصطلحات التاريخية

<!-- List any new historical-to-modern term mappings added -->

---

## Performance Impact / تأثير الأداء

### Benchmarks / مقاييس الأداء

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Terms extracted per second | X.XX | X.XX | +/-XX% |
| Sentence alignment accuracy | X.XX% | X.XX% | +/-XX% |
| Word alignment precision | X.XX% | X.XX% | +/-XX% |
| Memory usage (peak) | XXX MB | XXX MB | +/-XX% |
| Processing time (100 pages) | XX.Xs | XX.Xs | +/-XX% |

### Scalability / قابلية التوسع

<!-- Describe how changes affect processing of large corpora (10,000+ pages) -->

---

## Database Changes / تغييرات قاعدة البيانات

### Schema Migrations / ترحيلات المخطط

```sql
-- List any new tables, columns, or indexes
-- ادرج أي جداول أو أعمدة أو فهارس جديدة

-- Example:
-- ALTER TABLE arabic_terms ADD COLUMN phonetic_transcription VARCHAR(200);
-- CREATE INDEX idx_ar_terms_phonetic ON arabic_terms(phonetic_transcription);
```

### Data Migration / ترحيل البيانات

<!-- 
Describe any data transformation needed:
- Backfilling new columns
- Re-categorization of terms
- Re-scoring of confidence values
-->

---

## Documentation / التوثيق

<!-- Check all documentation updated -->

- [ ] Code comments added/updated / تمت إضافة/تحديث تعليقات الكود
- [ ] README.md updated / تم تحديث README.md
- [ ] API reference updated / تم تحديث مرجع API
- [ ] Bilingual docs (AR+EN) updated / تم تحديث التوثيق ثنائي اللغة
- [ ] CHANGELOG.md updated / تم تحديث سجل التغييرات
- [ ] Jupyter notebook updated / تم تحديث Jupyter notebook

---

## Reviewer Checklist / قائمة مراجعة المراجع

<!-- For reviewers to check before approving -->

- [ ] Code follows project style guidelines / الكود يتبع إرشادات أسلوب المشروع
- [ ] No breaking changes without migration plan / لا تغييرات كبيرة بدون خطة ترحيل
- [ ] Tests pass with adequate coverage / الاختبارات تجتاز بتغطية كافية
- [ ] Medical terminology is accurate / المصطلحات الطبية دقيقة
- [ ] Arabic text is properly normalized / النص العربي مطبع بشكل صحيح
- [ ] English translations are correct / الترجمات الإنجليزية صحيحة
- [ ] Performance impact is acceptable / تأثير الأداء مقبول
- [ ] Documentation is updated / التوثيق محدث
- [ ] No sensitive data exposed / لا بيانات حساسة مكشوفة
- [ ] Export formats are valid / صيغ التصدير صالحة

---

## Screenshots / لقطات الشاشة

<!-- 
If applicable, add screenshots or output samples:
- Terminal output of extraction results
- CSV/TSV output samples
- Web interface screenshots
- Before/after comparison of aligned sentences
-->

```
Sample output:
========================================
  BilingualExtractor - Extraction Results
========================================
Total pairs found: 42
High confidence (>= 0.7): 15
Medium confidence (0.4-0.7): 18
Low confidence (< 0.4): 9

Top terms:
1. الكسر (Fracture) - confidence: 0.85 - category: orthopedics
2. التهاب المفاصل (Arthritis) - confidence: 0.82 - category: orthopedics
3. ...
```

---

## Additional Notes / ملاحظات إضافية

<!-- Any additional information for reviewers -->

