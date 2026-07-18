"""
packages/core/mobile/server.py — Flask server for mobile OCR review (unified).

This server is the **single canonical entry point** for the mobile PWA.
It is wired directly into the same ``app.services.*`` layer used by the
main Gradio HITL app (``app/gradio_full_hitl.py``), so that:

  - Image preprocessing, OCR ensemble, spell checking, and NER all run
    through the SAME code path regardless of whether the request comes
    from the web (Gradio) or the mobile (Flask/PWA).
  - User corrections submitted via ``POST /save`` are routed to
    ``packages.core.corrections_manager.CorrectionsDictManager`` and
    ``packages.ai.active_learning.ActiveLearner`` — feeding the live
    learning loop instead of being written to a dead JSON file.
  - A new ``GET /stats`` endpoint exposes how many corrections have been
    saved, when the model was last retrained, and the estimated accuracy
    improvement.

Run:
    python -m packages.core.mobile.server --host 0.0.0.0 --port 5000

Then open http://<device-ip>:5000 from a phone browser.
For remote access: ``ngrok http 5000``.

Environment:
    Set ``OMNI_MOBILE_DB_DIR`` to control where SQLite databases live
    (default: ``./data``).
"""

from __future__ import annotations

import argparse
import io
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from flask import (
    Flask,
    Response,
    jsonify,
    render_template,
    request,
    send_from_directory,
)

# ── Project path bootstrap ────────────────────────────────────────────────
# Resolve monorepo root from this file's location:
#   packages/core/mobile/server.py  →  parents[3] = monorepo root
MONOREPO_ROOT = Path(__file__).resolve().parents[3]
for p in (
    str(MONOREPO_ROOT),
    str(MONOREPO_ROOT / "packages"),
    str(MONOREPO_ROOT / "packages" / "core" / "mobile"),
):
    if p not in sys.path:
        sys.path.insert(0, p)

logger = logging.getLogger("mobile_review")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)

# ── App services (lazy import — fail soft if deps missing) ────────────────
# These match exactly what ``app/gradio_full_hitl.py`` imports, so any
# request that goes through this server takes the same code path as the
# Gradio app. This is the whole point of Task 2.
HAS_APP_SERVICES = False
_preprocess_image = None
_run_paddle_ocr = None
_run_tesseract = None
_auto_correct_ocr = None
spell_checker = None
_extract_ner = None

try:
    from app.services.ocr_service import (  # type: ignore
        _auto_correct_ocr,
        _preprocess_image,
        _run_paddle_ocr,
        _run_tesseract,
        spell_checker,
    )
    from app.services.review_service import _extract_ner  # type: ignore
    HAS_APP_SERVICES = True
    logger.info("app.services.* loaded — mobile server shares the live OCR pipeline")
except Exception as exc:
    logger.warning(
        "app.services.* unavailable (%s) — /process will return 503. "
        "Run from monorepo root with PYTHONPATH include '.'.",
        exc,
    )

# ── Learning loop (lazy import — fail soft) ──────────────────────────────
# This is the Task 3 wiring: every saved correction is fed to BOTH
# CorrectionsDictManager (for the JSON dictionary) AND ActiveLearner
# (for the SQLite-backed active learning DB that triggers retraining).
HAS_LEARNING = False
corrections_mgr = None
active_learner = None
word_trainer_db = None

DB_DIR = Path(os.getenv("OMNI_MOBILE_DB_DIR", MONOREPO_ROOT / "data"))
DB_DIR.mkdir(parents=True, exist_ok=True)

try:
    from packages.core.corrections_manager import CorrectionsDictManager  # type: ignore
    corrections_mgr = CorrectionsDictManager(
        corrections_path=str(DB_DIR / "correction_dict.json"),
        arabic_fixes_path=str(DB_DIR / "arabic_fixes.json"),
        backup_dir=str(DB_DIR / "backups"),
    )

    from packages.core.word_trainer import WordCorrectionDB  # type: ignore
    word_trainer_db = WordCorrectionDB(db_path=str(DB_DIR / "corrections.db"))

    from packages.ai.active_learning import ActiveLearner  # type: ignore
    active_learner = ActiveLearner(db_path=str(DB_DIR / "active_learning.db"))

    HAS_LEARNING = True
    logger.info("Learning loop wired: corrections_manager + word_trainer + active_learner")
except Exception as exc:
    logger.warning(
        "Learning modules unavailable (%s) — /save will store JSON only, "
        "no active learning will occur.",
        exc,
    )

# ── Flask app ────────────────────────────────────────────────────────────
app = Flask(__name__, template_folder="templates")

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
STATIC_DIR.mkdir(exist_ok=True)
IMAGE_FOLDER = DB_DIR / "mobile_images"
IMAGE_FOLDER.mkdir(parents=True, exist_ok=True)

# Default OCR result file (for the simple /load endpoint, kept for backwards
# compatibility with the old JSON-only workflow).
DATA_FILE = DB_DIR / "ocr_result.json"
CORRECTED_FILE = DB_DIR / "ocr_corrected.json"


def _load_json(path: Path) -> Any:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _detect_lang(text: str) -> str:
    """Quick language detection: 'ar' if Arabic chars dominate, else 'en'."""
    if not text:
        return "ar"
    arabic = sum(1 for c in text if "\u0600" <= c <= "\u06ff")
    latin = sum(1 for c in text if "a" <= c.lower() <= "z")
    return "ar" if arabic >= latin else "en"


# ── Routes: PWA static assets ────────────────────────────────────────────
@app.route("/")
def index() -> Response:
    """Serve the PWA shell. Tries the templated review page first; falls
    back to the standalone ocr-review.html if no OCR data exists yet."""
    data = _load_json(DATA_FILE) if DATA_FILE.exists() else {}
    return render_template("review.html", data=data)


@app.route("/manifest.json")
def manifest() -> Response:
    """Serve the PWA manifest from the canonical mobile/ location."""
    return send_from_directory(BASE_DIR, "manifest.json", mimetype="application/manifest+json")


@app.route("/service-worker.js")
def service_worker() -> Response:
    """Serve the PWA service worker (created in Task 4)."""
    sw_path = STATIC_DIR / "service-worker.js"
    if not sw_path.exists():
        return Response("// service worker not available", status=404, mimetype="application/javascript")
    return send_from_directory(STATIC_DIR, "service-worker.js", mimetype="application/javascript")


@app.route("/static/<path:filename>")
def serve_static(filename: str) -> Response:
    return send_from_directory(STATIC_DIR, filename)


@app.route("/mobile/ocr-review.html")
def pwa_shell() -> Response:
    """Standalone PWA shell (used as ``start_url`` in manifest.json)."""
    return send_from_directory(BASE_DIR, "ocr-review.html", mimetype="text/html")


@app.route("/images/<path:filename>")
def serve_image(filename: str) -> Response:
    """Serve original images referenced in OCR results."""
    return send_from_directory(IMAGE_FOLDER, filename)


# ── Routes: live OCR processing (shares app.services.*) ───────────────────
@app.route("/process", methods=["POST"])
def process_image() -> Response:
    """Process an uploaded image through the SAME pipeline as the Gradio app.

    Accepts multipart/form-data with an ``image`` file field.
    Returns JSON with: text, corrected, raw_text, entities, steps, elapsed.
    """
    if not HAS_APP_SERVICES:
        return jsonify({
            "status": "error",
            "message": "app.services.* not loaded — run from monorepo root",
        }), 503

    if "image" not in request.files:
        return jsonify({"status": "error", "message": "no image field in request"}), 400

    file = request.files["image"]
    if not file.filename:
        return jsonify({"status": "error", "message": "empty filename"}), 400

    try:
        import numpy as np
        from PIL import Image

        # Read into numpy RGB (matches what app.services expects)
        pil = Image.open(file.stream).convert("RGB")
        image = np.array(pil)

        t0 = time.time()

        # 1. Preprocess
        cleaned, prep_steps = _preprocess_image(image)

        # 2. OCR ensemble
        paddle_text, paddle_details = _run_paddle_ocr(cleaned)
        tesseract_text, tess_conf = _run_tesseract(cleaned)

        # 3. Pick primary
        raw_text = paddle_text if (paddle_text and len(paddle_text.strip()) > 5) else tesseract_text
        if not raw_text.strip():
            raw_text = paddle_text or tesseract_text or ""

        # 4. Auto-correct OCR artifacts
        corrected, corrections = _auto_correct_ocr(raw_text)

        # 5. Spell check
        if spell_checker is not None:
            try:
                corrected = spell_checker.correct_text(corrected)
            except Exception as exc:
                logger.warning("Spell check failed: %s", exc)

        # 6. NER
        entities = _extract_ner(corrected) if _extract_ner else {}

        elapsed = round(time.time() - t0, 2)

        # Persist OCR result so /load and the templated review page can show it
        result_payload = {
            "raw_text": raw_text,
            "corrected_text": corrected,
            "entities": entities,
            "engine_info": {
                "paddle": {"lines": len(paddle_details)} if paddle_text else None,
                "tesseract": {"confidence": tess_conf} if tesseract_text else None,
            },
            "corrections": corrections,
            "preprocessing_steps": prep_steps,
            "processing_time_seconds": elapsed,
            "timestamp": datetime.now().isoformat(),
        }
        _save_json(DATA_FILE, result_payload)

        return jsonify({
            "status": "success",
            "result": result_payload,
        })

    except Exception as exc:
        logger.exception("process_image failed")
        return jsonify({"status": "error", "message": str(exc)}), 500


# ── Routes: corrections save / load (Task 3 — learning loop) ──────────────
@app.route("/save", methods=["POST"])
def save_corrections() -> Response:
    """Save user corrections and feed them into the live learning loop.

    Accepts JSON in either of two shapes:

    Shape A (legacy / templated review page):
        [
            {"id": "blk-1", "original_text": "...", "corrected_text": "...", "bbox": [...]},
            ...
        ]

    Shape B (per-word corrections from the PWA):
        {
            "items": [
                {"predicted": "...", "corrected": "...", "lang": "ar", "confidence": 0.72},
                ...
            ],
            "source": "mobile-pwa",
            "image_hash": "<optional>"
        }

    Both shapes are normalised into a single internal representation and
    routed to:
      1. ``CorrectionsDictManager.add()`` — JSON dictionary, used by
         HybridSpellChecker via arabic_fixes.json
      2. ``WordCorrectionDB.save_batch()`` — SQLite, used by
         HybridSpellChecker for per-word best-correction lookup
      3. ``ActiveLearner.log_correction()`` — SQLite, used for triggering
         model retraining when the correction threshold is reached
    """
    payload = request.get_json(silent=True)
    if payload is None:
        return jsonify({"status": "error", "message": "invalid JSON body"}), 400

    # Normalise to a list of correction items
    if isinstance(payload, list):
        items = payload
        source = "mobile-pwa-legacy"
        image_hash = ""
    elif isinstance(payload, dict):
        items = payload.get("items", [])
        if not isinstance(items, list):
            items = []
        source = payload.get("source", "mobile-pwa")
        image_hash = payload.get("image_hash", "")
    else:
        return jsonify({"status": "error", "message": "payload must be list or object"}), 400

    if not items:
        return jsonify({"status": "error", "message": "no correction items provided"}), 400

    # Always persist a raw JSON copy (for /load and for forensic recovery)
    _save_json(CORRECTED_FILE, payload)

    saved_count = 0
    learning_count = 0
    word_db_count = 0
    errors: list[str] = []

    for item in items:
        if not isinstance(item, dict):
            continue

        # Extract fields from either shape
        predicted = (
            item.get("predicted")
            or item.get("original_text")
            or ""
        ).strip()
        corrected = (
            item.get("corrected")
            or item.get("corrected_text")
            or ""
        ).strip()

        if not predicted or not corrected or predicted == corrected:
            continue

        lang = item.get("lang") or _detect_lang(predicted)
        confidence = float(item.get("confidence", 0.0) or 0.0)

        # 1. CorrectionsDictManager (JSON dictionary)
        if corrections_mgr is not None:
            try:
                corrections_mgr.add(predicted, corrected)
                saved_count += 1
            except Exception as exc:
                errors.append(f"corrections_mgr: {exc}")

        # 2. WordCorrectionDB (SQLite — used by HybridSpellChecker)
        if word_trainer_db is not None:
            try:
                word_trainer_db.save_batch(
                    items=[{
                        "idx": int(item.get("idx", 0) or 0),
                        "predicted": predicted,
                        "corrected": corrected,
                        "lang": lang,
                        "confidence": confidence,
                    }],
                    image_hash=image_hash,
                )
                word_db_count += 1
            except Exception as exc:
                errors.append(f"word_trainer: {exc}")

        # 3. ActiveLearner (SQLite — triggers retraining when threshold met)
        if active_learner is not None:
            try:
                active_learner.log_correction(
                    original_text=predicted,
                    corrected_text=corrected,
                    language=lang,
                    confidence=confidence,
                    source=source,
                )
                learning_count += 1
            except Exception as exc:
                errors.append(f"active_learner: {exc}")

    return jsonify({
        "status": "success",
        "saved_to": str(CORRECTED_FILE),
        "items_received": len(items),
        "corrections_dict_added": saved_count,
        "word_trainer_added": word_db_count,
        "active_learning_added": learning_count,
        "errors": errors[:5],  # cap error list
    })


@app.route("/load", methods=["GET"])
def load_corrections() -> Response:
    """Load previously-saved corrections (for resuming a review session)."""
    if CORRECTED_FILE.exists():
        return jsonify(_load_json(CORRECTED_FILE))
    return jsonify({})


# ── Routes: learning-loop stats (Task 3) ──────────────────────────────────
@app.route("/stats", methods=["GET"])
def stats() -> Response:
    """Return learning-loop stats for the user / admin dashboard.

    Response shape:
        {
            "status": "success",
            "corrections_dict": {"count": int, "arabic_count": int, ...},
            "word_trainer": {"total": int, "improved": int, "accuracy_pct": float, ...},
            "active_learning": {"total_corrections": int, "by_language": {...}},
            "last_updated": ISO timestamp
        }
    """
    if not HAS_LEARNING:
        return jsonify({
            "status": "error",
            "message": "learning modules not loaded",
        }), 503

    out: dict[str, Any] = {"status": "success", "last_updated": datetime.now().isoformat()}

    # 1. CorrectionsDictManager stats
    try:
        out["corrections_dict"] = corrections_mgr.stats(top_n=10)
    except Exception as exc:
        out["corrections_dict"] = {"error": str(exc)}

    # 2. WordCorrectionDB stats
    try:
        out["word_trainer"] = word_trainer_db.stats()
    except Exception as exc:
        out["word_trainer"] = {"error": str(exc)}

    # 3. ActiveLearner stats
    try:
        al_stats = active_learner.get_training_stats(language="ar")
        out["active_learning"] = {
            "training_stats_ar": al_stats,
            "retrain_threshold": "see packages.ai.active_learning defaults",
        }
    except Exception as exc:
        out["active_learning"] = {"error": str(exc)}

    return jsonify(out)


# ── Routes: healthcheck ──────────────────────────────────────────────────
@app.route("/health")
def health() -> Response:
    """Simple healthcheck for Docker / load balancer probes."""
    return jsonify({
        "status": "ok",
        "app_services_loaded": HAS_APP_SERVICES,
        "learning_loop_loaded": HAS_LEARNING,
        "db_dir": str(DB_DIR),
        "version": "2.0",
    })


# ── CLI ──────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(
        description="OmniFile Mobile Review Server (unified with app.services)",
    )
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    print("=" * 60)
    print("  OmniFile Mobile Review Server (unified)")
    print("=" * 60)
    print(f"  Listening:     http://{args.host}:{args.port}")
    print(f"  Monorepo root: {MONOREPO_ROOT}")
    print(f"  DB dir:        {DB_DIR}")
    print(f"  app.services:  {'LOADED' if HAS_APP_SERVICES else 'NOT LOADED'}")
    print(f"  learning loop: {'LOADED' if HAS_LEARNING else 'NOT LOADED'}")
    print()
    print("  Endpoints:")
    print("    GET  /                 — PWA shell (review.html)")
    print("    GET  /manifest.json    — PWA manifest")
    print("    GET  /service-worker.js — PWA offline cache")
    print("    GET  /mobile/ocr-review.html — standalone PWA shell")
    print("    POST /process          — upload image → OCR pipeline")
    print("    POST /save             — save user corrections → learning loop")
    print("    GET  /load             — reload saved corrections")
    print("    GET  /stats            — learning-loop stats dashboard")
    print("    GET  /health           — healthcheck for Docker probes")
    print("=" * 60)

    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
