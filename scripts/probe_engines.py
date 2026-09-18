#!/usr/bin/env python3
"""TASK 003 - engine availability probe.

Checks importability of every OCR engine known to the registry WITHOUT
loading model weights and WITHOUT network access. Emits a markdown
status table. Status vocabulary (plan §9): REGISTERED / WIRED / CALLED /
EXECUTED / TESTED / BENCHMARKED / PRODUCTION - plus UNVERIFIED for
anything this probe cannot prove.

NOTE: importability != runtime readiness. This probe never claims
EXECUTED. Engine execution requires the real environment (GPU/models).
"""
from __future__ import annotations

import importlib
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

# engine id (as registered in packages/core/engine_registry.py) -> python modules to probe
ENGINE_MODULES: dict[str, list[tuple[str, str]]] = {
    "Tesseract": [("pytesseract", "pytesseract"), ("tesseract-binary", "shutil.which")],
    "EasyOCR": [("easyocr", "easyocr")],
    "PaddleOCR": [("paddleocr", "paddleocr"), ("paddlepaddle", "paddle")],
    "TrOCR": [("transformers", "transformers"), ("torch", "torch")],
    "Surya": [("surya", "surya")],
    "Nougat": [("nougat", "nougat")],
    # Upstream repo documented as unavailable (REFERENCE_PROJECTS.md):
    "QARI": [("qari", "qari")],
}


def _probe_module(name: str) -> dict:
    if name == "tesseract-binary":
        import shutil

        path = shutil.which("tesseract")
        return {"probe": name, "found": bool(path), "detail": path or "binary not on PATH"}
    try:
        mod = importlib.import_module(name)
        version = getattr(mod, "__version__", "unknown")
        return {"probe": name, "found": True, "detail": f"version={version}"}
    except Exception as exc:  # noqa: BLE001 - probe must survive any import error
        return {"probe": name, "found": False, "detail": f"{type(exc).__name__}"}


def main() -> int:
    rows = []
    for engine, probes in ENGINE_MODULES.items():
        results = [_probe_module(n) for n, _ in probes]
        all_found = all(r["found"] for r in results)
        # Runtime status is UNVERIFIED unless the engine was actually executed
        # in a validated environment - an import proves nothing more.
        rows.append(
            {
                "engine": engine,
                "registered": True,  # all present in engine_router.py ids
                "imports_ok": all_found,
                "probes": results,
                "runtime_status": "UNVERIFIED",
            }
        )

    payload = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "gpu": "not audited in this environment",
        },
        "engines": rows,
        "disclaimer": (
            "IMPORT-ONLY probe. No engine was executed, no model loaded, "
            "no benchmark run. Every runtime_status stays UNVERIFIED "
            "until proven in a real environment."
        ),
    }

    out_dir = Path("docs/portfolio")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "ENGINE_STATUS.json").write_text(json.dumps(payload, indent=2))

    lines = [
        "# ENGINE STATUS - TASK 003 (PHASE 1)",
        "",
        f"Generated: {payload['generated_utc']} | python {payload['environment']['python']}",
        "",
        "| Engine | Registered (router ids) | Imports | Runtime status |",
        "|---|---|---|---|",
    ]
    for row in rows:
        imports = "; ".join(f"{r['probe']}: {'OK' if r['found'] else 'MISSING'} ({r['detail']})" for r in row["probes"])
        lines.append(f"| {row['engine']} | yes | {imports} | {row['runtime_status']} |")
    lines += ["", "## Disclaimer", "", payload["disclaimer"], "", "## LIMITS", "",
              "- No GPU / no model weights in this environment (BLOCKED).",
              "- QARI upstream repo documented unavailable (REFERENCE_PROJECTS.md) -> stays UNVERIFIED.",
              "- This table must NOT be read as EXECUTED/BENCHMARKED claims."]
    (out_dir / "ENGINE_STATUS.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
