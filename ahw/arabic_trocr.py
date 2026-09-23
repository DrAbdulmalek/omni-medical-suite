"""ATR-F1 — TrOCR مع محوّل AraBERT للخط اليد العربي.

يعيد بناء رأس فك التشفير بمفردات عربية (AraBERT) بدل المفردات الإنجليزية
الأصلية، مع إعادة تهيئة الأوزان اللغوية (embeddings + lm_head + مواضع) كما
يقتضي الماستر برومبت — والإبقاء على الترميز البصري (TrOCR encoder) كما هو.

مواصفات ATR-F1 المنفَّذة:
    load_model_with_arabic_tokenizer(base="microsoft/trocr-base-handwritten",
        arabic="aubmindlab/bert-base-arabertv02", dry_run=False):
      - VisionEncoderDecoderModel + ViTImageProcessor من الأساس
      - AutoTokenizer من AraBERT؛ resize_token_embeddings(len(tokenizer))
      - decoder_start=cls، eos=sep، pad=pad
      - إعادة تهيئة embed_tokens + lm_head + embed_positions بـ std=init_std
      - ArabicTrOCRProcessor (image_processor + tokenizer) مع save/from_pretrained
      - dry_run=True: أوزان عشوائية صغيرة للتحقق من الأشكال فقط (بلا شبكة)

توافق الإصدار (موثق بالتنفيذ): أُنفّذ أصلًا على transformers==4.48.3 ثم قُيّد
على 5.12.1 (حدّ المستودع الموثق من binary-search لتوافق TrOCR+Trainer —
worklog TASK-02D). الفروق الموثقة:
  - ArabicTrOCRProcessor ترث TrOCRProcessor الجاهزة (إعادة استخدام بدل إعادة
    تنفيذ) — save/from_pretrained سليمة عبر ProcessorMixin.
  - 4.48: Trainer يمرر num_items_in_batch وViTModel.forward يرفضه — تدريب
    TrOCR عبر Trainer مكسور (مثبت تجريبيًا)؛ السبب في انتقال 5.x.
  - 4.48: VisionEncoderDecoderModel لا يعرّف get_input_embeddings ويرفض resize
    — النفاذ عبر model.decoder (الكود يحافظ على هذا المسار وهو متوافق مع 5.x).
  - 5.x: المفككات البطيئة أُزيلت — dry_run يبني WordPiece في الذاكرة عبر
    tokenizers + PreTrainedTokenizerFast (راجع _build_dry_run).
  - lm_head مربوط (tied) بـ embed_tokens؛ تتم إعادة التهيئة ثم فحص data_ptr
    — tied يُسجل ولا تُعاد التهيئة المزدوجة.
  - embed_positions يُكتشف عبر مسارات معروفة (TrOCR 5.x:
    model.decoder.embed_positions) مع تجاهل آمن إن غاب.

بلا شبكة في وضع dry_run تمامًا (مفردات مصغّرة مبنية في الذاكرة).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

import numpy as np
from transformers import TrOCRProcessor  # عمدًا على مستوى الوحدة (يرثه الصنف أدناه)

logger = logging.getLogger(__name__)

DEFAULT_BASE = "microsoft/trocr-base-handwritten"
DEFAULT_ARABIC = "aubmindlab/bert-base-arabertv02"


def _find_module(obj: Any, dotted: str) -> Any:
    """وصول آمن لمسار خاصية متداخل (يرجع None إن انقطع)."""
    cur = obj
    for part in dotted.split("."):
        cur = getattr(cur, part, None)
        if cur is None:
            return None
    return cur


def _reinit_decoder_weights(model, std: float, info: Dict[str, Any]) -> None:
    """إعادة تهيئة embed_tokens + lm_head + embed_positions بـ std=init_std."""
    import torch

    dec = model.decoder
    emb = dec.get_input_embeddings()
    head = dec.get_output_embeddings()
    with torch.no_grad():
        if emb is not None:
            emb.weight.normal_(mean=0.0, std=std)
            pad_idx = getattr(emb, "padding_idx", None)
            if pad_idx is not None:
                emb.weight[pad_idx].zero_()
        tied = (head is not None and emb is not None and
                head.weight.data_ptr() == emb.weight.data_ptr())
        if head is not None and not tied:
            head.weight.normal_(mean=0.0, std=std)
        # مواضع المفكك (متعلَّمة مطلقة). مسارات معروفة حسب صنف المفكك:
        #   BertLMHeadModel: bert.embed_positions | RobertaForCausalLM:
        #   roberta.embed_positions | TrOCRForCausalLM (4.48): model.decoder.embed_positions
        positions = (_find_module(dec, "bert.embed_positions")
                     or _find_module(dec, "roberta.embed_positions")
                     or _find_module(dec, "model.decoder.embed_positions")
                     or _find_module(dec, "model.roberta.embed_positions")
                     or _find_module(dec, "model.model.embed_positions")
                     or getattr(dec, "embed_positions", None))
        pos_w = getattr(positions, "weight", None)
        if pos_w is not None:
            pos_w.normal_(mean=0.0, std=std)
            pad_idx = getattr(positions, "padding_idx", None)
            if pad_idx is not None:
                pos_w[pad_idx].zero_()
    info["reinit"] = {
        "embed_tokens": emb is not None,
        "lm_head": ("tied-to-embed_tokens (skipped)" if tied
                    else ("reinitialized" if head is not None else "absent")),
        "embed_positions": ("reinitialized" if pos_w is not None else "absent"),
        "std": std,
    }


def _apply_arabic_decoder_vocab(model, tokenizer, info: Dict[str, Any]) -> None:
    """resize المفردات + ضبط decoder_start/eos/pad من AraBERT + إعادة التهيئة.

    توافق 4.48.3: VisionEncoderDecoderModel لا يعرّف get_input_embeddings
    ويرفض resize_token_embeddings صراحةً — تُنفَّذ على model.decoder مباشرة.
    """
    dec = model.decoder
    old_vocab = dec.get_input_embeddings().weight.shape[0]
    new_vocab = len(tokenizer)
    if old_vocab != new_vocab:
        dec.resize_token_embeddings(new_vocab)
    model.config.vocab_size = new_vocab
    if getattr(model.config, "decoder", None) is not None:
        model.config.decoder.vocab_size = new_vocab

    cls_id = tokenizer.cls_token_id
    sep_id = tokenizer.sep_token_id
    pad_id = tokenizer.pad_token_id
    model.config.decoder_start_token_id = cls_id
    model.config.eos_token_id = sep_id
    model.config.pad_token_id = pad_id
    if getattr(model.config, "decoder", None) is not None:
        model.config.decoder.bos_token_id = cls_id
        model.config.decoder.eos_token_id = sep_id
        model.config.decoder.pad_token_id = pad_id
    if getattr(model, "generation_config", None) is not None:
        model.generation_config.decoder_start_token_id = cls_id
        model.generation_config.eos_token_id = sep_id
        model.generation_config.pad_token_id = pad_id

    init_std = float(getattr(model.config.decoder, "init_std", 0.02))
    info["resized_from"] = int(old_vocab)
    info["special_tokens"] = {"decoder_start": "cls", "eos": "sep", "pad": "pad"}
    _reinit_decoder_weights(model, std=init_std, info=info)


def _build_dry_run(base: str, arabic: str) -> Tuple[Any, Any, Dict[str, Any]]:
    """نموذج صغير بأوزان عشوائية + مفردات مصغّرة في الذاكرة — بلا شبكة إطلاقًا.

    يمر عبر نفس مسار _apply_arabic_decoder_vocab (resize + special tokens +
    إعادة تهيئة) ليتحقق الاختبار من الأشكال الفعلية لا من وهمها.
    """
    from transformers import (BertConfig, PreTrainedTokenizerFast, ViTConfig,
                              ViTImageProcessor, VisionEncoderDecoderConfig,
                              VisionEncoderDecoderModel)
    from tokenizers import Tokenizer, models, pre_tokenizers

    base_chars = "ابجدهوزحطيكلمنسعفصقرشتثخذضظغءآأإئىة"
    vocab = {"[PAD]": 0, "[UNK]": 1, "[CLS]": 2, "[SEP]": 3, "[MASK]": 4}
    for ch in base_chars:
        vocab.setdefault(ch, len(vocab))
        vocab.setdefault("##" + ch, len(vocab))  # استمراريات WordPiece
    for w in ["الجراحة", "العظمية", "المريض", "ألم", "ضغط", "الدواء"]:
        vocab.setdefault(w, len(vocab))
    # توافق الإصدارات (موثق):
    #  - transformers 4.48.3: المفكك البطيء لـ BERT يقرأ vocab.txt حصرًا ولا
    #    يقبل قاموسًا في الذاكرة (from_pretrained(local_dir) يفشل: stat(None)).
    #  - transformers 5.x: المفككات البطيئة أُزيلت — vocab.txt يُقرأ جزئيًا
    #    (فشل IndexError في الـembedding مثبت). الحل المشترك للإصدارين:
    #    مفردات WordPiece مبنية في الذاكرة عبر tokenizers +
    #    PreTrainedTokenizerFast (بلا شبكة وبلا ملفات مؤقتة).
    wp = models.WordPiece(vocab=vocab, unk_token="[UNK]",
                          continuing_subword_prefix="##", max_input_chars_per_word=100)
    tk = Tokenizer(wp)
    tk.pre_tokenizer = pre_tokenizers.BertPreTokenizer()
    # ملاحظة مصالحة (ATR-04c, جلسة Qwen على transformers 4.57.6):
    # بلا post_processor تُرمَّز الكلمة المفردة إلى توكن واحد بلا [CLS]/[SEP]،
    # فينهار الإشراف في تدريب dry_run (loss=0 على 4.57.6؛ يعمل صدفةً على 5.12.1).
    # إضافة [CLS] $A [SEP] تجعل dry_run وفيًّا للـ AraBERT/TrOCR الحقيقي (الذي
    # يلفّ التسلسل دائمًا) وتُصلح الانهيار عبر الإصدارين 4.x و5.x معًا —
    # tokenizers.TemplateProcessing مستقر عبر الإصدارات. لا يكسر أي assertion
    # قائم (اختبار الأشكال يتطلب input_ids>=2 فقط).
    from tokenizers import processors as _procs
    tk.post_processor = _procs.TemplateProcessing(
        single="[CLS] $A [SEP]",
        pair="[CLS] $A [SEP] $B:1 [SEP]:1",
        special_tokens=[("[CLS]", vocab["[CLS]"]), ("[SEP]", vocab["[SEP]"])],
    )
    tokenizer = PreTrainedTokenizerFast(
        tokenizer_object=tk, do_lower_case=False, model_max_length=64,
        unk_token="[UNK]", pad_token="[PAD]", cls_token="[CLS]",
        sep_token="[SEP]", mask_token="[MASK]")

    encoder_cfg = ViTConfig(hidden_size=32, num_hidden_layers=1,
                            num_attention_heads=2, intermediate_size=64,
                            image_size=32, patch_size=16, num_channels=3)
    # مفردات المفكك تُبنى أصغر عمدًا ليمر الكود عبر resize_token_embeddings
    decoder_cfg = BertConfig(vocab_size=max(8, len(vocab) - 5), hidden_size=32,
                             num_hidden_layers=1, num_attention_heads=2,
                             intermediate_size=64, max_position_embeddings=64,
                             is_decoder=True, add_cross_attention=True,
                             pad_token_id=tokenizer.pad_token_id,
                             bos_token_id=tokenizer.cls_token_id,
                             eos_token_id=tokenizer.sep_token_id)
    # 4.48.3: VisionEncoderDecoderConfig يقبل encoder/decoder كقواميس (مع model_type)
    cfg = VisionEncoderDecoderConfig(encoder=encoder_cfg.to_dict(),
                                     decoder=decoder_cfg.to_dict())
    model = VisionEncoderDecoderModel(cfg)

    image_processor = ViTImageProcessor(size={"height": 32, "width": 32},
                                        patch_size=16)
    processor = ArabicTrOCRProcessor(image_processor=image_processor,
                                     tokenizer=tokenizer)

    info: Dict[str, Any] = {"dry_run": True, "base": base, "arabic": arabic,
                            "vocab_size": len(tokenizer)}
    _apply_arabic_decoder_vocab(model, tokenizer, info)
    model.eval()
    return model, processor, info


def load_model_with_arabic_tokenizer(
    base: str = DEFAULT_BASE,
    arabic: str = DEFAULT_ARABIC,
    dry_run: bool = False,
    cache_dir: Optional[str] = None,
) -> Tuple[Any, Any, Dict[str, Any]]:
    """تحميل TrOCR مع مفردات AraBERT — يعيد (model, processor, info).

    dry_run=True: نموذج صغير عشوائي بلا أي تنزيل (للتحقق من الأشكال).
    dry_run=False: تنزيل من HuggingFace (الترميز البصري كاملًا + مفردات
        AraBERT) — راجع scripts/atr_probe_models.py لسجل الأحجام والرخص.
    """
    if dry_run:
        return _build_dry_run(base, arabic)

    import transformers
    from transformers import (AutoTokenizer, ViTImageProcessor,
                              VisionEncoderDecoderModel)

    info: Dict[str, Any] = {"dry_run": False, "base": base, "arabic": arabic,
                            "transformers_version": transformers.__version__}
    model = VisionEncoderDecoderModel.from_pretrained(base, cache_dir=cache_dir)
    image_processor = ViTImageProcessor.from_pretrained(base, cache_dir=cache_dir)
    tokenizer = AutoTokenizer.from_pretrained(arabic, cache_dir=cache_dir)
    processor = ArabicTrOCRProcessor(image_processor=image_processor,
                                     tokenizer=tokenizer)
    info["vocab_size"] = len(tokenizer)
    _apply_arabic_decoder_vocab(model, tokenizer, info)
    model.eval()
    return model, processor, info


class ArabicTrOCRProcessor(TrOCRProcessor):
    """محوّل عربي: ViTImageProcessor + tokenizer عربي (AraBERT).

    يرث __call__ وsave/from_pretrained من TrOCRProcessor في transformers —
    نفس العقد المتوقع في ATR-F1 (image_processor + tokenizer معًا).
    """
