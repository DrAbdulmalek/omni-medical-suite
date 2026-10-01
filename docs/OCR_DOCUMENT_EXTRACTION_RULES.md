# OCR / Document Extraction — Visual Evidence and Error-Aware Rules

**Status:** Normative OCR/document-extraction guidance  
**Scope:** PDF, EPUB, scanned documents, page images, screenshots, OCR/HTR output, document conversion, medical-translation extraction  
**Primary principle:** OCR extracts what is visible; it does not automatically determine what is true.

## 1. Purpose

When processing PDF, EPUB, scanned pages, screenshots, or images, extracted text MUST NOT automatically be treated as factual ground truth.

The OCR/document-extraction pipeline MUST distinguish between:

- source text that appears to be authoritative;
- educational examples;
- intentionally incorrect examples;
- corrected text;
- uncertain text;
- visual evidence such as ✓, ✔, ✗, ✘, X, arrows, strike-through, underlining, layout, and color.

Visual semantics MUST be preserved when they carry meaning.

## 2. Telegram → PDF/EPUB → TXT/Markdown

When a PDF or EPUB is obtained from a Telegram channel:

1. Preserve the original file unchanged.
2. Preserve the original extension.
3. Record available provenance such as source/channel identifier and processing date.
4. Compute SHA-256 when the pipeline supports it.
5. Do not treat the filename, caption, or post description as proof of document content.
6. Prefer local/offline processing when practical.

Convert:

- PDF → TXT and/or Markdown
- EPUB → TXT and/or Markdown

The conversion SHOULD preserve:

- headings;
- paragraphs;
- page/section order;
- tables;
- rows and columns;
- lists;
- footnotes;
- page numbers or location markers when useful;
- relationships between text, images, captions, and annotations.

## 3. Table Preservation

Do not flatten a table into an unordered text stream when that would destroy cell relationships.

Markdown is preferred when the table structure can be represented reliably:

| Correct translation | Incorrect translation |
|---|---|
| Correct example | Incorrect example |

Preserve the original column order.

If the table structure cannot be determined reliably, mark the structure as uncertain rather than inventing columns or moving values between cells.

## 4. Images Are Not Automatically Ground Truth

Text inside an image is not necessarily correct.

An image may be:

- an educational example;
- an example of an error;
- a comparison of correct and incorrect translations;
- a screenshot of a bad OCR result;
- a visual explanation of a problem;
- training material containing corrections;
- evidence that a particular extraction is wrong.

The model MUST inspect visual context and surrounding text before treating image content as authoritative.

## 5. Sentences or Translations Inside Images

When an image contains sentences or translations, inspect for evidence that identifies correctness.

Relevant indicators include:

- ✓ / ✔
- ✗ / ✘
- X
- correction marks;
- arrows;
- strike-through;
- underlining;
- color;
- labels such as `correct`, `incorrect`, `wrong`, `right`, `correction`, `error`, `suggested translation`, `original`, or `revised`.

Do not discard these indicators during OCR. They may carry more semantic information than the extracted sentence itself.

## 6. ✓ / ✗ / X Semantics

When the image clearly uses a marker to classify a sentence:

- ✓ / ✔ → visually marked as correct.
- ✗ / ✘ / X → visually marked as incorrect.

Preserve the relationship between marker and text.

Example:

| Status | Text |
|---|---|
| Correct ✓ | Correct translation |
| Incorrect ✗ | Incorrect translation |

### Context requirement

Do not interpret every `X` as an error marker automatically. It may be a normal character, medical symbol, multiplication sign, or unrelated annotation.

Interpret `X` as a correctness marker only when the visual/layout context supports that interpretation.

## 7. Color Semantics

If color is used to distinguish translation correctness, preserve the color-derived semantic information.

For the project convention:

- **red text = incorrect translation**
- **green text = correct translation**

Convert color-only meaning into explicit structured meaning rather than relying on color in the final text.

Example:

| Status | Translation |
|---|---|
| Incorrect — red | Incorrect translation |
| Correct — green | Correct translation |

### Color safety rule

Do not assume that red always means incorrect and green always means correct in every source.

If the image contains a legend, caption, or explicit instruction defining the colors, follow that source-specific definition.

If the color meaning is not established, mark:

`COLOR_SEMANTICS_UNCERTAIN`

Do not invent a classification.

## 8. Correct vs. Incorrect Translations

When an image contains multiple translations/sentences and visual evidence distinguishes correct from incorrect versions, keep them explicitly separated.

Preferred representation:

| Correct translation | Incorrect translation |
|---|---|
| Correct medical translation | Incorrect medical translation |
| Correct example | Wrong example |

Never:

- combine both into one unlabelled cell;
- swap the columns;
- remove the markers that establish correctness;
- assume the first sentence is correct merely because it appears first;
- assume one sentence is correct merely because it differs from another.

## 9. Images That Demonstrate Errors

If context indicates that an image is intended to demonstrate an OCR, translation, formatting, or extraction error, do NOT silently convert the displayed error into ground truth.

Use explicit status such as:

- `EXAMPLE_OF_ERROR`
- `INCORRECT_EXAMPLE`
- `VISUAL_CORRECTION_EXAMPLE`

Example:

| Type | Text |
|---|---|
| Incorrect | First translation |
| Correct | Corrected translation |

The source representation should remain recoverable.

## 10. Low-Confidence or Unconvincing Visual Evidence

If the model cannot confidently determine whether image content is correct or incorrect, it MUST NOT invent a decision.

Use:

- `VISUAL_CONFIDENCE_LOW`
- `VISUAL_INTERPRETATION_UNCERTAIN`

Record the reason when possible:

- marker is unclear;
- color is ambiguous;
- image resolution is insufficient;
- text is cropped;
- relationship between marker and text is unclear;
- table column assignment is unclear;
- image may be an example rather than a reference;
- source context is insufficient.

An uncertain visual interpretation MUST NOT be promoted to verified ground truth.

## 11. No Silent Correction

If the source contains an intentional error for educational or comparative purposes, preserve the original text.

Do not replace it silently with the corrected version.

Preferred representation:

~~~text
SOURCE_TEXT:
text exactly as represented in the source

STATUS:
INCORRECT_EXAMPLE

CORRECTION:
corrected text as explicitly indicated by the source
~~~

If the correction is inferred rather than explicitly indicated, label it as an inference and keep it separate from source truth.

## 12. Evidence and Provenance Metadata

When supported by the pipeline, preserve structured evidence:

~~~text
source_type: pdf | epub | image | telegram
page: <page number or null>
image_index: <index or null>
ocr_text: <extracted text>
visual_status: correct | incorrect | uncertain | neutral
visual_marker: check | x | none | other
color_status: green | red | other | uncertain
confidence: high | medium | low
~~~

Additional provenance SHOULD identify the source document and location sufficiently to allow human re-checking.

## 13. Evidence Precedence

When OCR text, visual layout, markers, colors, and surrounding context appear to conflict:

1. Preserve the original source.
2. Preserve relevant visual structure.
3. Preserve correctness markers.
4. Preserve color semantics when established.
5. Preserve surrounding textual context.
6. Extract the text.
7. Normalize/correct only when the applicable rule explicitly permits it and evidence supports it.

Do not force conflicting evidence into a single answer.

## 14. Medical Translation Safety

For medical content, keep these categories separate:

- original/source text;
- source language;
- translation;
- incorrect translation;
- correct translation;
- explicit correction;
- proposed correction;
- educational note.

An educational example of an incorrect medical translation MUST NOT be stored as a correct target.

## 15. Training Data / Translation Memory

When extracted material is later used for a dataset or Translation Memory:

- incorrect translations MUST NOT become the default correct target;
- incorrect examples MAY be retained as `negative_example`;
- correct translations MAY be stored as `positive_example` only when sufficient evidence supports that classification;
- uncertain examples MUST remain `uncertain` until reviewed.

Preferred conceptual structure:

~~~json
{
  "source": "original sentence",
  "correct_translation": "correct translation",
  "incorrect_translation": "incorrect translation",
  "evidence": {
    "marker": "check/x",
    "color": "green/red",
    "confidence": "high"
  }
}
~~~

Do not reverse the relationship between source, correct target, and negative example.

## 16. Markdown as Structured Output

Markdown SHOULD be preferred when table and document structure must survive conversion.

If Markdown cannot faithfully represent the source structure:

1. retain a raw extraction;
2. retain the structured Markdown representation;
3. explicitly identify structure that was lost or uncertain;
4. do not claim visual fidelity when it was not achieved.

## 17. Final OCR Verification Gate

Before declaring document extraction complete, check:

- tables preserved;
- column order preserved;
- important images detected;
- ✓ / ✔ / ✗ / ✘ / X handled;
- color semantics preserved or marked uncertain;
- correct and incorrect examples separated;
- error-demonstration images identified;
- uncertain regions explicitly marked;
- no unsupported correction introduced;
- training-data suitability assessed;
- source page/image location remains traceable.

Suggested final states:

- `PASS`
- `PARTIAL`
- `UNCERTAIN`
- `FAILED`

Important: a document MUST NOT be labelled `VERIFIED` when material visual evidence remains unresolved.

## 18. Core Rule

> **OCR extracts what is visible; it does not automatically determine what is true.**

The system must preserve the distinction between:

1. what the source displays;
2. what the source visually marks as correct or incorrect;
3. what the extraction system can verify;
4. what remains uncertain.

When evidence is insufficient, preserve the uncertainty instead of manufacturing certainty.
