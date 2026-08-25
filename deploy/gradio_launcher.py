"""Production launcher for the Gradio OCR UI.

The application module defines the UI but historically launched without an
authentication boundary. This wrapper imports it without executing its
__main__ block and applies mandatory HTTP Basic authentication in production.
Medical persistence is enforced by ``save_to_hf`` itself: explicit human
approval and the confidence threshold are required before any dataset write.

The launcher also establishes the production confidence contract: all OCR
confidence values exposed by the application are percentages in the range
0..100. PaddleOCR reports confidence as a fraction in 0..1, while Tesseract
already reports percentages, so Paddle values are normalized here before the
shared pipeline consumes them.
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import gradio as gr


APP_PATH = Path(__file__).resolve().parents[1] / "hf-space" / "app.py"

spec = importlib.util.spec_from_file_location("omni_gradio_app", APP_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Cannot load Gradio application from {APP_PATH}")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


# Production confidence contract: the shared ``confidence`` field is always
# expressed as a percentage (0..100). PaddleOCR returns 0..1 fractions.
_original_run_paddle_ocr = module._run_paddle_ocr


def _run_paddle_ocr_percent(image):
    text, details = _original_run_paddle_ocr(image)
    normalized = []
    for detail in details:
        value = float(detail.get("confidence", 0.0))
        if 0.0 <= value <= 1.0:
            value *= 100.0
        value = max(0.0, min(100.0, value))
        normalized.append({**detail, "confidence": round(value, 2)})
    return text, normalized


module._run_paddle_ocr = _run_paddle_ocr_percent


def main() -> None:
    username = os.getenv("GRADIO_USERNAME")
    password = os.getenv("GRADIO_PASSWORD")
    environment = os.getenv("ENVIRONMENT", "production")

    if environment == "production" and (not username or not password):
        raise RuntimeError(
            "GRADIO_USERNAME and GRADIO_PASSWORD are required for production Gradio access"
        )

    auth = (username, password) if username and password else None
    module.demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        auth=auth,
    )


if __name__ == "__main__":
    main()
