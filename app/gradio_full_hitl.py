"""Compatibility shim for the previous Gradio entrypoint.

The canonical Gradio UI now lives in ``app/advanced_review_app.py`` with the
three review-oriented tabs requested in the July 2026 refactor.
"""

from app.advanced_review_app import demo


if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
