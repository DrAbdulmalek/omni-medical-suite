# Architecture — omni-medical-suite

End-to-end medical document processing suite: scan → OCR ensemble →
spell-check → NER → structured output. Ships as AppImage + HF Space.

```
┌────────────────────────────────────────────────────────────────────┐
│                         INPUT IMAGES                                │
│  scanned PDF  •  phone photo  •  tablet capture  •  DICOM          │
└─────────────────────────────┬──────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────────┐
│  packages/scanner_fixer                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐ │
│  │ auto_detect  │→ │ find_page_   │→ │ smart_auto_crop          │ │
│  │   _skew      │  │   bounds     │  │ (unified entry point)    │ │
│  │ HoughLinesP  │  │ adaptiveTh.  │  │                          │ │
│  │ + median     │  │ + morpholog. │  │                          │ │
│  └──────────────┘  └──────────────┘  └──────────────────────────┘ │
└─────────────────────────────┬──────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────────┐
│  src/ocr/ensemble.py                                                 │
│  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐                    │
│  │Tesseract│  │ EasyOCR│  │ Paddle │  │  RTL   │  → composite      │
│  │ engine  │  │ engine │  │ engine │  │ engine │    score =        │
│  └────┬───┘  └────┬───┘  └────┬───┘  └────┬───┘    conf × len      │
│       │           │           │           │         × validity      │
│       └───────────┴───────────┴───────────┘                        │
│                          ▼                                          │
│                 best_text + best_engine                             │
│              (was: longest_text — buggy)                            │
└─────────────────────────────┬──────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────────┐
│  src/text_processing  +  src/spell_checker  +  src/ner_extractor   │
│  • Arabic normalization     • medical dictionary     • Rx doses    │
│  • BiDi reordering           • Levenshtein            • diseases   │
│  • tokenization              • phonetic matching      • drug names │
└─────────────────────────────┬──────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────────┐
│  OUTPUTS:  structured JSON  •  annotated PDF  •  training corpus   │
└────────────────────────────────────────────────────────────────────┘
```

## P1 fix: ensemble composite score

Previously, `get_ensemble_text()` picked the engine returning the longest
text — which could be garbage from a failing OCR engine. The fix replaces
this with a composite score:

```python
score = avg_confidence * clean_length * validity_ratio
if result.get("error"):
    score *= 0.1   # penalize failed engines
```

Where `validity_ratio` = (alpha + digit + Arabic-char count) / total length.
