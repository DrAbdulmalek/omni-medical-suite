"""
groundtruth_builder.py
Orchestrates the full workflow:
  1. Read searchable PDFs from ABBYY / Readiris (and optionally your own
     engines' output as plain text)
  2. Extract text (+ optionally word boxes from ABBYY/Readiris PDF since
     they share the same source image)
  3. Merge/align all sources into a ground-truth candidate
  4. Write a JSON ground-truth record per document, ready to feed into
     your training/benchmark datasets (same schema family used in
     omni-medical-ocr-dataset-v1)
"""

import json
from pathlib import Path
from typing import Dict, Optional, Union, List
from datetime import datetime, timezone

from .pdf_extractor import extract_pdf_text, extract_pdf_words, is_text_layer_present
from .alignment import merge_multi_source, compute_similarity_ratio


def build_ground_truth_record(
    image_id: str,
    abbyy_pdf: Optional[Union[str, Path]] = None,
    readiris_pdf: Optional[Union[str, Path]] = None,
    extra_sources: Optional[Dict[str, str]] = None,
    primary_source: str = "abbyy",
) -> Dict:
    """
    Builds a single ground-truth record for one document/page by merging
    available OCR sources.

    Args:
        image_id: Identifier for this document (used in the dataset)
        abbyy_pdf: Path to ABBYY-exported searchable PDF (optional)
        readiris_pdf: Path to Readiris-exported searchable PDF (optional)
        extra_sources: dict of {name: text} for additional sources
            (e.g. your own Tesseract/EasyOCR output as plain strings)
        primary_source: which source name to align against
            (defaults to "abbyy" if available, else first available)

    Returns:
        Ground-truth record dict (see schema in module docstring below)
    """
    sources: Dict[str, str] = {}
    source_files: Dict[str, str] = {}

    if abbyy_pdf:
        abbyy_pdf = Path(abbyy_pdf)
        if not is_text_layer_present(abbyy_pdf):
            raise ValueError(
                f"No text layer found in {abbyy_pdf} — was OCR actually run "
                f"before exporting to PDF in ABBYY?"
            )
        sources["abbyy"] = extract_pdf_text(abbyy_pdf)
        source_files["abbyy"] = str(abbyy_pdf)

    if readiris_pdf:
        readiris_pdf = Path(readiris_pdf)
        if not is_text_layer_present(readiris_pdf):
            raise ValueError(
                f"No text layer found in {readiris_pdf} — was OCR actually run "
                f"before exporting to PDF in Readiris?"
            )
        sources["readiris"] = extract_pdf_text(readiris_pdf)
        source_files["readiris"] = str(readiris_pdf)

    if extra_sources:
        sources.update(extra_sources)

    if not sources:
        raise ValueError("At least one OCR source (ABBYY, Readiris, or extra_sources) is required")

    # Pick a valid primary source
    if primary_source not in sources:
        primary_source = list(sources.keys())[0]

    merged = merge_multi_source(sources, primary_source=primary_source)

    # Pairwise similarity (useful diagnostic — e.g. ABBYY vs Readiris agreement)
    pairwise_similarity = {}
    names = list(sources.keys())
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = names[i], names[j]
            key = f"{a}_vs_{b}"
            pairwise_similarity[key] = compute_similarity_ratio(sources[a], sources[b])

    record = {
        "image_id": image_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "sources_used": list(sources.keys()),
        "source_files": source_files,
        "primary_source": primary_source,
        "raw_texts": sources,
        "merged_text": merged["merged_text"],
        "word_results": merged["word_results"],
        "stats": merged["stats"],
        "pairwise_similarity": pairwise_similarity,
        "review_needed": merged["stats"]["conflicts"] > 0,
    }

    return record


def build_dataset_from_folder(
    abbyy_dir: Optional[Union[str, Path]] = None,
    readiris_dir: Optional[Union[str, Path]] = None,
    output_dir: Union[str, Path] = "./ground_truth_output",
    extra_source_dirs: Optional[Dict[str, Union[str, Path]]] = None,
    extra_source_ext: str = ".txt",
) -> List[Dict]:
    """
    Batch-builds ground-truth records by matching files with the same
    stem (filename without extension) across the ABBYY / Readiris /
    extra source folders.

    Expects:
        abbyy_dir/0001.pdf
        readiris_dir/0001.pdf
        extra_source_dirs["tesseract"]/0001.txt
    All matched by stem "0001".

    Args:
        abbyy_dir: Folder containing ABBYY-exported searchable PDFs
        readiris_dir: Folder containing Readiris-exported searchable PDFs
        output_dir: Where to write the JSON ground-truth records
        extra_source_dirs: dict of {source_name: folder_path} for
            additional plain-text OCR outputs (e.g. your own engines)
        extra_source_ext: file extension to look for in extra_source_dirs

    Returns:
        List of ground-truth records (also written to output_dir as JSON)
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Collect all available document stems across every source
    stems = set()

    abbyy_files = {}
    if abbyy_dir:
        abbyy_dir = Path(abbyy_dir)
        for f in abbyy_dir.glob("*.pdf"):
            abbyy_files[f.stem] = f
            stems.add(f.stem)

    readiris_files = {}
    if readiris_dir:
        readiris_dir = Path(readiris_dir)
        for f in readiris_dir.glob("*.pdf"):
            readiris_files[f.stem] = f
            stems.add(f.stem)

    extra_files: Dict[str, Dict[str, Path]] = {}
    if extra_source_dirs:
        for source_name, folder in extra_source_dirs.items():
            folder = Path(folder)
            extra_files[source_name] = {}
            for f in folder.glob(f"*{extra_source_ext}"):
                extra_files[source_name][f.stem] = f
                stems.add(f.stem)

    if not stems:
        print("No matching files found in any source directory.")
        return []

    results = []
    for stem in sorted(stems):
        extra_sources = {}
        for source_name, files in extra_files.items():
            if stem in files:
                extra_sources[source_name] = files[stem].read_text(encoding="utf-8")

        try:
            record = build_ground_truth_record(
                image_id=stem,
                abbyy_pdf=abbyy_files.get(stem),
                readiris_pdf=readiris_files.get(stem),
                extra_sources=extra_sources or None,
            )
            status = "ok"
        except Exception as e:
            record = {"image_id": stem, "error": str(e)}
            status = "error"

        out_path = output_dir / f"{stem}.json"
        out_path.write_text(
            json.dumps(record, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        results.append(record)
        agreement = record.get("stats", {}).get("agreement_rate", "—")
        print(f"[{status.upper()}] {stem} → agreement_rate={agreement}")

    # Write a summary report
    summary = {
        "total_documents": len(results),
        "successful": sum(1 for r in results if "error" not in r),
        "errors": sum(1 for r in results if "error" in r),
        "needs_review": sum(1 for r in results if r.get("review_needed")),
        "average_agreement_rate": round(
            sum(r.get("stats", {}).get("agreement_rate", 0) for r in results if "error" not in r)
            / max(1, sum(1 for r in results if "error" not in r)),
            3
        ),
    }
    (output_dir / "_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(f"\nSummary: {summary}")

    return results
