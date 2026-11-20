"""Production-safe Gradio entrypoint for the standalone HF Space.

The implementation lives in ``app_core.py``.  Both the standalone Space
entrypoint and ``deploy/gradio_launcher.py`` use the same authenticated launch
contract: production requires credentials, and PaddleOCR confidence is
normalized to the canonical 0..100 percent representation.
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path

_CORE_PATH = Path(__file__).with_name("app_core.py")
_spec = importlib.util.spec_from_file_location("omni_gradio_app_core", _CORE_PATH)
if _spec is None or _spec.loader is None:
    raise RuntimeError(f"Cannot load Gradio application core from {_CORE_PATH}")

_core = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_core)

# Preserve the historical module API used by tests and integrations.
for _name in dir(_core):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_core, _name)


def install_production_confidence_contract() -> None:
    """Normalize PaddleOCR confidence to the shared 0..100 percentage unit."""
    original = globals().get("_run_paddle_ocr")
    if original is None or getattr(original, "_omni_confidence_normalized", False):
        return

    def _run_paddle_ocr_percent(image):
        text, details = original(image)
        normalized = []
        for detail in details:
            value = float(detail.get("confidence", 0.0))
            if 0.0 <= value <= 1.0:
                value *= 100.0
            value = max(0.0, min(100.0, value))
            normalized.append({**detail, "confidence": round(value, 2)})
        return text, normalized

    _run_paddle_ocr_percent._omni_confidence_normalized = True
    globals()["_run_paddle_ocr"] = _run_paddle_ocr_percent


def launch_production() -> None:
    """Launch the Gradio UI with the production authentication boundary."""
    install_production_confidence_contract()

    username = os.getenv("GRADIO_USERNAME")
    password = os.getenv("GRADIO_PASSWORD")
    environment = os.getenv("ENVIRONMENT", "production")

    if environment == "production" and (not username or not password):
        raise RuntimeError(
            "GRADIO_USERNAME and GRADIO_PASSWORD are required for production Gradio access"
        )

    auth = (username, password) if username and password else None
    demo.launch(server_name="0.0.0.0", server_port=7860, auth=auth)


if __name__ == "__main__":
    launch_production()

del _name, _core, _spec, _CORE_PATH
