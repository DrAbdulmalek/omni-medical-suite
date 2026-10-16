"""ATR-F1 tests — dry_run يبني نموذجًا، الأشكال صحيحة، save/from_pretrained.

اصطناعية بالكامل وبلا شبكة (dry_run) — صفر PHI، صفر تنزيل.
"""
from __future__ import annotations

import pytest

# حراس CI (ATR-04d): هذه الوحدة تتطلب torch+transformers (requirements-atr.txt).
# في البيئات التي لا تتضمنها (مثل CI "Unit Tests" job) تُتخطى الوحدة نظيفًا بدل
# خطأ تجميع (collection error) يكسر المجموعة. عند توفر التبعيات تعمل كل
# الـassertions كاملة دون إضعاف (38/38 مثبتة محليًا على 4.57.6 و5.12.1).
pytest.importorskip("torch", reason="ATR-F1 requires torch (requirements-atr.txt)")
pytest.importorskip("transformers",
                    reason="ATR-F1 requires transformers (requirements-atr.txt)")

import numpy as np  # noqa: E402
import torch  # noqa: E402
from transformers import VisionEncoderDecoderModel  # noqa: E402

from ahw.arabic_trocr import (DEFAULT_ARABIC, DEFAULT_BASE,  # noqa: E402
                              ArabicTrOCRProcessor,
                              load_model_with_arabic_tokenizer)


@pytest.fixture(scope="module")
def dry_components():
    return load_model_with_arabic_tokenizer(base=DEFAULT_BASE, arabic=DEFAULT_ARABIC,
                                            dry_run=True)


def test_dry_run_builds_model_with_correct_special_tokens(dry_components):
    model, processor, info = dry_components
    assert info["dry_run"] is True
    tok = processor.tokenizer
    vocab = len(tok)
    assert vocab > 8
    assert model.config.vocab_size == vocab
    assert model.get_output_embeddings().weight.shape[0] == vocab
    assert model.decoder.get_input_embeddings().weight.shape[0] == vocab
    # decoder_start=cls، eos=sep، pad=pad (متطلب ATR-F1)
    assert model.config.decoder_start_token_id == tok.cls_token_id
    assert model.config.eos_token_id == tok.sep_token_id
    assert model.config.pad_token_id == tok.pad_token_id
    assert model.generation_config.decoder_start_token_id == tok.cls_token_id
    # 4.48.3: الـwrapper لا يعرّف get_input_embeddings — التحقق عبر المفكك
    assert model.decoder.get_input_embeddings().weight.shape[0] == vocab


def test_dry_run_resize_and_reinit_exercised(dry_components):
    """dry_run يبني المفكك بمفردات أصغر عمدًا — مسار resize_token_embeddings
    وإعادة التهيئة (embed_tokens/lm_head/embed_positions) يُمارس فعليًا."""
    model, processor, info = dry_components
    assert info["resized_from"] < model.config.vocab_size
    assert info["reinit"]["embed_tokens"] is True
    assert info["reinit"]["lm_head"] in ("tied-to-embed_tokens (skipped)",
                                         "reinitialized")
    assert info["reinit"]["std"] == pytest.approx(0.02)


def test_dry_run_forward_shapes(dry_components):
    model, processor, info = dry_components
    model.eval()
    tok = processor.tokenizer
    img_size = model.config.encoder.image_size
    pixel_values = torch.randn(2, 3, img_size, img_size)
    ids = torch.tensor([
        [tok.cls_token_id, 5, tok.sep_token_id],
        [tok.cls_token_id, 6, tok.sep_token_id],
    ])
    with torch.no_grad():
        out = model(pixel_values=pixel_values, decoder_input_ids=ids)
    assert out.logits.shape == (2, 3, model.config.vocab_size)
    assert torch.isfinite(out.logits).all()

    # المعالج: صورة -> pixel_values بالأبعاد الصحيحة، نص -> input_ids
    img = (np.random.rand(48, 48, 3) * 255).astype(np.uint8)
    enc = processor(images=[img], return_tensors="pt")
    assert tuple(enc["pixel_values"].shape) == (1, 3, img_size, img_size)
    enc2 = processor(text=["الجراحة العظمية"], return_tensors="pt")
    assert enc2["input_ids"].shape[0] == 1 and enc2["input_ids"].shape[1] >= 2


def test_dry_run_save_from_pretrained_roundtrip(dry_components, tmp_path):
    model, processor, info = dry_components
    d = tmp_path / "atr_model"
    model.save_pretrained(str(d))
    processor.save_pretrained(str(d))

    model2 = VisionEncoderDecoderModel.from_pretrained(str(d))
    proc2 = ArabicTrOCRProcessor.from_pretrained(str(d))
    assert model2.config.vocab_size == model.config.vocab_size
    assert len(proc2.tokenizer) == len(processor.tokenizer)
    assert model2.config.decoder_start_token_id == processor.tokenizer.cls_token_id
    assert model2.config.eos_token_id == processor.tokenizer.sep_token_id
    assert model2.config.pad_token_id == processor.tokenizer.pad_token_id
