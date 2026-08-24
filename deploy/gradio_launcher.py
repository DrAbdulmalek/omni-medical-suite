"""Production launcher for the Gradio OCR UI.

The application module defines the UI but historically launched without an
authentication boundary. This wrapper imports it without executing its
__main__ block and applies mandatory HTTP Basic authentication in production.

Until the medical-review workflow is wired into the application itself, this
launcher also disables persistence of corrected medical text in production.
That is deliberately fail-closed: an unreviewed correction must never reach
the HuggingFace dataset.
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import gradio as gr


APP_PATH = Path(__file__).resolve().parents[1] / "hf-space" / "app.py"

_original_button_click = gr.Button.click


def _guarded_button_click(self, fn=None, *args, **kwargs):
    if os.getenv("ENVIRONMENT", "production") == "production" and getattr(fn, "__name__", "") == "save_to_hf":
        def blocked_save(*_inputs, **_kwargs):
            return "BLOCKED: corrected medical text cannot be persisted until mandatory human approval is enforced."

        fn = blocked_save
    return _original_button_click(self, fn, *args, **kwargs)


g.Button.click = _guarded_button_click

spec = importlib.util.spec_from_file_location("omni_gradio_app", APP_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Cannot load Gradio application from {APP_PATH}")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


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
