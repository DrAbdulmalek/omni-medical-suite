# في train_trocr.py، استبدل دالة تحميل النموذج بهذا الكود:

def load_model_with_arabic_tokenizer(base_model_name="microsoft/trocr-base-handwritten",
                                      arabic_tokenizer_name="aubmindlab/bert-base-arabertv02"):
    """
    يحمّل TrOCR مع استبدال الـ decoder tokenizer بـ AraBERT العربي.
    """
    from transformers import VisionEncoderDecoderModel, AutoTokenizer
    from transformers import ViTImageProcessor
    
    # 1. تحميل النموذج الأساسي
    model = VisionEncoderDecoderModel.from_pretrained(base_model_name)
    
    # 2. تحميل image processor من النموذج الأساسي (يبقى كما هو)
    image_processor = ViTImageProcessor.from_pretrained(base_model_name)
    
    # 3. تحميل AraBERT tokenizer العربي
    tokenizer = AutoTokenizer.from_pretrained(arabic_tokenizer_name)
    
    # 4. استبدال الـ decoder tokenizer في النموذج
    model.decoder.resize_token_embeddings(len(tokenizer))
    model.config.vocab_size = len(tokenizer)
    model.config.decoder_start_token_id = tokenizer.cls_token_id
    model.config.eos_token_id = tokenizer.sep_token_id
    model.config.pad_token_id = tokenizer.pad_token_id
    
    # 5. إعادة تهيئة الطبقات الجديدة (Embedding و FC و Positional Encoding)
    # هذه الخطوة حاسمة لاستقرار التدريب[reference:4]
    import torch.nn as nn
    model.decoder.model.decoder.embed_tokens = nn.Embedding(
        len(tokenizer), model.config.decoder.hidden_size, padding_idx=tokenizer.pad_token_id
    )
    model.decoder.lm_head = nn.Linear(
        model.config.decoder.hidden_size, len(tokenizer), bias=False
    )
    # إعادة تهيئة positional embeddings
    model.decoder.model.decoder.embed_positions.weight.data.normal_(
        mean=0.0, std=model.config.decoder.init_std
    )
    
    # 6. إنشاء processor مخصص يجمع بين image_processor و tokenizer
    class ArabicTrOCRProcessor:
        def __init__(self, image_processor, tokenizer):
            self.image_processor = image_processor
            self.tokenizer = tokenizer
        
        def __call__(self, images=None, text=None, **kwargs):
            if images is not None:
                return self.image_processor(images=images, **kwargs)
            if text is not None:
                return self.tokenizer(text, **kwargs)
        
        def batch_decode(self, *args, **kwargs):
            return self.tokenizer.batch_decode(*args, **kwargs)
        
        def save_pretrained(self, path):
            self.image_processor.save_pretrained(path)
            self.tokenizer.save_pretrained(path)
        
        @classmethod
        def from_pretrained(cls, path):
            return cls(
                ViTImageProcessor.from_pretrained(path),
                AutoTokenizer.from_pretrained(path)
            )
    
    processor = ArabicTrOCRProcessor(image_processor, tokenizer)
    return model, processor
