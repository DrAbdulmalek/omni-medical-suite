# ENGINE STATUS - TASK 003 (PHASE 1)

Generated: 2026-09-18T14:59:03.711700+00:00 | python 3.12.3

| Engine | Registered (router ids) | Imports | Runtime status |
|---|---|---|---|
| Tesseract | yes | pytesseract: OK (version=0.3.13); tesseract-binary: OK (/usr/bin/tesseract) | UNVERIFIED |
| EasyOCR | yes | easyocr: MISSING (ModuleNotFoundError) | UNVERIFIED |
| PaddleOCR | yes | paddleocr: MISSING (ModuleNotFoundError); paddlepaddle: MISSING (ModuleNotFoundError) | UNVERIFIED |
| TrOCR | yes | transformers: MISSING (ModuleNotFoundError); torch: MISSING (ModuleNotFoundError) | UNVERIFIED |
| Surya | yes | surya: MISSING (ModuleNotFoundError) | UNVERIFIED |
| Nougat | yes | nougat: MISSING (ModuleNotFoundError) | UNVERIFIED |
| QARI | yes | qari: MISSING (ModuleNotFoundError) | UNVERIFIED |

## Disclaimer

IMPORT-ONLY probe. No engine was executed, no model loaded, no benchmark run. Every runtime_status stays UNVERIFIED until proven in a real environment.

## LIMITS

- No GPU / no model weights in this environment (BLOCKED).
- QARI upstream repo documented unavailable (REFERENCE_PROJECTS.md) -> stays UNVERIFIED.
- This table must NOT be read as EXECUTED/BENCHMARKED claims.
