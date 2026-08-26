#!/usr/bin/env python3
"""
scripts/setup_medical_dictionaries.py — Regenerate the unified medical dictionary.

Usage:
    python3 scripts/setup_medical_dictionaries.py

This script:
1. Extracts medical term pairs from malek_data TMX archive (if not already extracted).
2. Runs the MedicalDictionaryLoader to merge all sources with safety firewall.
3. Generates data/dictionaries/medical_glossary_merged.json (large, git-ignored).
4. Generates data/dictionaries/medical_glossary_merged.csv.
5. Generates data/dictionaries/ocr_corrections_safe.json (small, committed).
6. Generates data/dictionaries/quarantined_entries.json + conflicts.json.
7. Updates SOURCES.md, MERGE_REPORT.md, CONFLICTS.md.

Requirements:
- The malek_data 7z archive must be at /home/z/my-project/repos/malek_data/New Folder.7z.*
- The arabic-medical-glossary submodule must be initialized.
"""
from __future__ import annotations
import logging
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def extract_malek_data_archive(malek_repo: Path, dest: Path) -> Path:
    """Extract malek_data 7z archive to dest/. Returns path to extracted 'New Folder'."""
    parts = sorted(malek_repo.glob("New Folder.7z.*"))
    if not parts:
        raise FileNotFoundError(f"malek_data 7z parts not found in {malek_repo}")
    
    combined = dest / "malek_data_combined.7z"
    if not combined.exists() or combined.stat().st_size == 0:
        logger.info(f"Concatenating {len(parts)} 7z parts into {combined}")
        combined.parent.mkdir(parents=True, exist_ok=True)
        with open(combined, "wb") as out:
            for p in parts:
                with open(p, "rb") as f:
                    while True:
                        chunk = f.read(1024 * 1024)
                        if not chunk:
                            break
                        out.write(chunk)
    
    extracted_root = dest / "malek_data_extracted" / "New Folder"
    if not extracted_root.exists():
        logger.info(f"Extracting {combined} → {dest}/malek_data_extracted/")
        import py7zr
        with py7zr.SevenZipFile(str(combined), mode="r") as z:
            z.extractall(path=dest / "malek_data_extracted")
    
    return extracted_root


def extract_tmx_terms(malek_extracted: Path, output_json: Path) -> int:
    """Extract medical term pairs from malek_data TMX files."""
    if output_json.exists():
        logger.info(f"TMX terms already extracted at {output_json} ({output_json.stat().st_size:,} bytes)")
        return 0
    
    extractor_script = Path("/home/z/my-project/scripts/extract_malek_tmx_terms.py")
    if extractor_script.exists():
        logger.info(f"Running TMX extractor: {extractor_script}")
        # Patch the source dir
        env = os.environ.copy()
        env["MALEK_DIR"] = str(malek_extracted)
        env["OUT"] = str(output_json)
        result = subprocess.run([sys.executable, str(extractor_script)], env=env, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"TMX extractor failed: {result.stderr[-500:]}")
            return 1
        logger.info(f"TMX extraction completed: {output_json.stat().st_size:,} bytes")
        return 0
    else:
        logger.warning(f"Extractor script not found: {extractor_script}")
        return 1


def main():
    logger.info("=" * 60)
    logger.info("Setting up medical dictionaries")
    logger.info("=" * 60)
    
    # Step 1: extract malek_data 7z if available
    malek_repo = PROJECT_ROOT.parent / "malek_data"
    if malek_repo.exists():
        work_dir = PROJECT_ROOT / "work"
        work_dir.mkdir(parents=True, exist_ok=True)
        try:
            malek_extracted = extract_malek_data_archive(malek_repo, work_dir)
            logger.info(f"malek_data extracted to: {malek_extracted}")
        except FileNotFoundError as e:
            logger.warning(f"malek_data archive not found: {e}")
            malek_extracted = None
    else:
        logger.warning(f"malek_data repo not found at {malek_repo}")
        malek_extracted = None
    
    # Step 2: extract TMX terms if malek_data is available
    malek_terms_json = PROJECT_ROOT / "data" / "dictionaries" / "malek_data_terms.json"
    if malek_extracted and not malek_terms_json.exists():
        extract_tmx_terms(malek_extracted, malek_terms_json)
    
    # Step 3: run the export script
    export_script = Path("/home/z/my-project/scripts/export_unified_glossary.py")
    if export_script.exists():
        logger.info(f"Running export script: {export_script}")
        result = subprocess.run([sys.executable, str(export_script)], capture_output=True, text=True)
        if result.returncode == 0:
            print(result.stdout[-2000:])
            logger.info("✓ Medical dictionaries setup complete")
        else:
            logger.error(f"Export failed: {result.stderr[-500:]}")
            return 1
    else:
        logger.error(f"Export script not found: {export_script}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
