"""Golden Path UI — minimal Gradio skeleton (S2-T1/S2-T2).

Decision doc: marathon-suite/docs/plans/golden-path-ui-decision.md (Gradio, LOCAL_ONLY).
This is a REVERSIBLE SKELETON: three steps only — upload image → run OCR via
ocr-core → review/correct → save corrected text locally in the exact
``--- filename.jpg ---`` format that packages/vision/dataset_builder.py consumes.
No network calls; binds 127.0.0.1 only.

Status: PARTIALLY_PROVEN — never executed against a real PDF yet (S2-T2).
Rollback: close PR / revert commit — nothing else depends on this file.
"""
from __future__ import annotations

from pathlib import Path


def _load_gradio():
    """Lazy import so the dependency stays optional for CI and other consumers."""
    try:
        import gradio as gr  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover - environment-dependent
        raise SystemExit(
            "golden-path UI needs gradio: pip install 'gradio>=4.44,<5.0.0' "
            "(see tools/golden_path/README.md)"
        ) from exc
    return gr


class OCREngineAdapter:
    """Thin seam over ocr-core. Replace _run_engine with any engine later."""

    name = "ocr-core"

    def _run_engine(self, image_path: str) -> tuple[str, float]:
        """Returns (text, confidence). confidence 0.0 = unknown (never invented)."""
        try:
            from ocr_core import OCRProcessor  # noqa: PLC0415

            processor = OCRProcessor()
            result = processor.process_image(image_path)
            text = getattr(result, "text", "")
            confidence = getattr(result, "confidence", 0.0)
            return str(text), float(confidence or 0.0)
        except ImportError:
            return (
                "[engine not installed] pip install "
                "'marathon-ocr-core[tesseract] @ "
                "git+https://github.com/DrAbdulmalek/ocr-core.git' "
                "— then re-run. Image: " + image_path,
                0.0,
            )

    def process(self, image_path: str) -> tuple[str, float]:
        return self._run_engine(image_path)


def save_corrected(image_name: str, corrected_text: str, out_dir: str) -> str:
    """Write the correction file in the DatasetBuilder-expected format."""
    safe = Path(image_name).name or "page.jpg"
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    target = out / f"corrected_{Path(safe).stem}.txt"
    target.write_text(
        f"--- {safe} ---\n{corrected_text.strip()}\n", encoding="utf-8"
    )
    return str(target)


def build_app():  # pragma: no cover - UI wiring, exercised manually
    gr = _load_gradio()
    adapter = OCREngineAdapter()

    def on_upload(image_path):
        if not image_path:
            return "", 0.0
        text, conf = adapter.process(str(image_path))
        return text, conf

    with gr.Blocks(title="Golden Path — LOCAL_ONLY") as app:
        gr.Markdown("# المسار الذهبي — OCR ثم تصحيح بشري (محلي فقط)")
        with gr.Row():
            image_in = gr.Image(type="filepath", label="صورة الوصفة/التقرير")
            raw_out = gr.Textbox(label="نص OCR الخام", lines=12)
        conf_out = gr.Number(label="الثقة (0.0 = مجهولة)", interactive=False)
        corrected = gr.Textbox(label="النص المصحح بشريًا", lines=12)
        out_dir = gr.Textbox(
            value=str(Path.home() / "golden_path_corrections"),
            label="مجلد الحفظ المحلي",
        )
        saved_to = gr.Textbox(label="حُفظ في", interactive=False)
        image_in.change(on_upload, inputs=image_in, outputs=[raw_out, conf_out])
        corrected.change(lambda t: t, inputs=corrected, outputs=corrected)
        save_btn = gr.Button("احفظ التصحيح محليًا")
        save_btn.click(
            lambda img, txt, d: save_corrected(Path(str(img)).name, txt or "", d),
            inputs=[image_in, corrected, out_dir],
            outputs=saved_to,
        )
    return app


def main() -> None:  # pragma: no cover - entrypoint
    app = build_app()
    # LOCAL_ONLY by design: never bind 0.0.0.0, never expose publicly.
    app.launch(server_name="127.0.0.1", server_port=7861, share=False)


if __name__ == "__main__":
    main()
