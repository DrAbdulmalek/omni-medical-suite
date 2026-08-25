"""Canonical production launcher for the Gradio OCR UI.

The standalone HF Space entrypoint owns the authentication and confidence
contract.  This launcher loads that same entrypoint without executing its
``__main__`` block and delegates to ``launch_production``.  Keeping one launch
contract prevents the production Docker path and the HF Space mirror from
drifting apart.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path


APP_PATH = Path(__file__).resolve().parents[1] / "hf-space" / "app.py"

spec = importlib.util.spec_from_file_location("omni_gradio_app_entrypoint", APP_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Cannot load Gradio entrypoint from {APP_PATH}")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def main() -> None:
    module.launch_production()


if __name__ == "__main__":
    main()
