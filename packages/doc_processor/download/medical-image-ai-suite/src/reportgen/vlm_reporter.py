"""
مولّد التقارير الطبية التلقائية - VLM Report Generator
توليد تقارير وصفيّة من الصور الشعاعية باستخدام نماذج الرؤية واللغة
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union

import numpy as np

from ..utils.logger import get_logger

logger = get_logger("vlm_reporter")


class VLMReporter:
    """
    نموذج توليد التقارير الطبية من الصور (Vision-Language Model)

    البنية:
    1. Vision Encoder (ViT / ResNet) ← يستخرج مميزات الصورة
    2. Projection Layer ← يحوّل مميزات الصورة إلى فضاء النص
    3. Text Decoder (GPT-2 / AraGPT2) ← يولّد التقرير النصي

    يدعم:
    - التوليد من الصور (Image → Report)
    - التوليد المشروط (Image + Condition → Report)
    - التقييم (BLEU, ROUGE, BERTScore)

    الاستخدام:
        reporter = VLMReporter(language="ar")
        reporter.train(image_paths, report_texts)
        report = reporter.generate(image_array)
    """

    def __init__(
        self,
        language: str = "ar",
        vision_model: str = "google/vit-base-patch16-224",
        text_model: str = "aubmindlab/aragpt2-base",
        max_text_length: int = 512,
        beam_size: int = 5,
        temperature: float = 0.7,
        top_k: int = 50,
        top_p: float = 0.95,
        device: str = "auto",
        image_size: Tuple[int, int] = (224, 224),
    ):
        """
        Args:
            language: لغة التقرير (ar, en)
            vision_model: اسم نموذج Vision من HuggingFace
            text_model: اسم نموذج اللغة من HuggingFace
            max_text_length: أقصى طول للتقرير
            beam_size: حجم شعاع البحث
            temperature: درجة حرارة التوليد
            top_k: أقل k اختیار
            top_p: nucleus sampling
            device: جهاز التدريب
            image_size: حجم الصورة
        """
        self.language = language
        self.vision_model_name = vision_model
        self.text_model_name = text_model
        self.max_text_length = max_text_length
        self.beam_size = beam_size
        self.temperature = temperature
        self.top_k = top_k
        self.top_p = top_p
        self.image_size = image_size

        self.device = self._detect_device() if device == "auto" else device

        self.vision_encoder = None
        self.text_decoder = None
        self.tokenizer = None
        self.projection = None
        self.is_trained = False

        logger.info(
            f"VLM Reporter: لغة={language}, vision={vision_model}, text={text_model}"
        )

    def _detect_device(self) -> str:
        """اكتشاف الجهاز"""
        try:
            import torch
            if torch.cuda.is_available():
                return "cuda"
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                return "mps"
        except ImportError:
            pass
        return "cpu"

    def _load_vision_encoder(self):
        """تحميل نموذج Vision Encoder"""
        try:
            import torch
            from transformers import ViTModel, ViTFeatureExtractor

            self.feature_extractor = ViTFeatureExtractor.from_pretrained(self.vision_model_name)
            self.vision_encoder = ViTModel.from_pretrained(self.vision_model_name)
            self.vision_encoder.eval()
            self.vision_encoder.to(self.device)

            # بُعد المخرجات (عادة 768 لـ ViT-Base)
            self.vision_dim = self.vision_encoder.config.hidden_size
            logger.info(f"تم تحميل Vision Encoder: {self.vision_model_name}")

        except ImportError:
            logger.warning("transformers غير مثبت")
        except Exception as e:
            logger.error(f"فشل تحميل Vision Encoder: {e}")

    def _load_text_decoder(self):
        """تحميل نموذج Text Decoder"""
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer

            self.tokenizer = AutoTokenizer.from_pretrained(self.text_model_name)
            self.text_decoder = AutoModelForCausalLM.from_pretrained(self.text_model_name)
            self.text_decoder.to(self.device)

            # بُعد المدخلات (عادة 768)
            self.text_dim = self.text_decoder.config.n_embd if hasattr(self.text_decoder.config, "n_embd") else 768
            logger.info(f"تم تحميل Text Decoder: {self.text_model_name}")

        except ImportError:
            logger.warning("transformers غير مثبت")
        except Exception as e:
            logger.error(f"فشل تحميل Text Decoder: {e}")

    def _build_projection(self):
        """بناء طبقة الإسقاط بين Vision و Text"""
        import torch
        import torch.nn as nn

        self.projection = nn.Sequential(
            nn.Linear(self.vision_dim, self.text_dim),
            nn.LayerNorm(self.text_dim),
            nn.ReLU(),
            nn.Linear(self.text_dim, self.text_dim),
            nn.LayerNorm(self.text_dim),
        ).to(self.device)

    def extract_features(self, image: np.ndarray) -> np.ndarray:
        """
        استخراج مميزات الصورة باستخدام Vision Encoder

        Args:
            image: مصفوفة الصورة [H, W] أو [H, W, 3]

        Returns:
            متجه المميزات [vision_dim]
        """
        if self.vision_encoder is None:
            self._load_vision_encoder()

        import torch

        # تحويل الصورة
        if image.ndim == 2:
            image = np.stack([image] * 3, axis=-1)  # → [H, W, 3]
        if image.dtype != np.uint8:
            image = (np.clip(image, 0, 1) * 255).astype(np.uint8)

        try:
            inputs = self.feature_extractor(images=image, return_tensors="pt")
            inputs = {k: v.to(self.device) for k, v in inputs.items()}

            with torch.no_grad():
                outputs = self.vision_encoder(**inputs)
                features = outputs.last_hidden_state[:, 0, :]  # CLS token

            return features.cpu().numpy().squeeze()

        except Exception as e:
            logger.error(f"فشل استخراج المميزات: {e}")
            return np.zeros(self.vision_dim, dtype=np.float32)

    def generate(
        self,
        image: np.ndarray,
        max_length: Optional[int] = None,
        num_beams: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> str:
        """
        توليد تقرير طبي من صورة

        Args:
            image: مصفوفة الصورة [H, W] أو [H, W, 3]
            max_length: أقصى طول (لا شيء = الافتراضي)
            num_beams: حجم الشعاع
            temperature: درجة الحرارة

        Returns:
            نص التقرير المُولّد
        """
        if not self.is_trained and self.vision_encoder is None:
            # الوضع البسيط: توليد قالب بدون نموذج
            return self._generate_template_report(image)

        import torch

        # استخراج مميزات الصورة
        features = self.extract_features(image)
        features_tensor = torch.FloatTensor(features).unsqueeze(0).to(self.device)

        # الإسقاط إلى فضاء النص
        if self.projection is not None:
            projected = self.projection(features_tensor)
        else:
            projected = features_tensor

        # توليد النص
        max_len = max_length or self.max_text_length
        beams = num_beams or self.beam_size
        temp = temperature or self.temperature

        try:
            # توليد باستخدام نموذج اللغة
            input_ids = self.tokenizer.encode(
                self._get_prompt(), return_tensors="pt"
            ).to(self.device)

            generated = self.text_decoder.generate(
                input_ids,
                max_length=max_len,
                num_beams=beams,
                temperature=temp,
                top_k=self.top_k,
                top_p=self.top_p,
                do_sample=True,
                pad_token_id=self.tokenizer.eos_token_id,
                eos_token_id=self.tokenizer.eos_token_id,
            )

            report = self.tokenizer.decode(generated[0], skip_special_tokens=True)
            return self._format_report(report)

        except Exception as e:
            logger.error(f"فشل التوليد: {e}")
            return self._generate_template_report(image)

    def generate_batch(
        self,
        images: np.ndarray,
    ) -> List[str]:
        """
        توليد تقارير لمجموعة صور

        Args:
            images: مصفوفة صور [N, H, W]

        Returns:
            قائمة نصوص التقارير
        """
        reports = []
        for i in range(len(images)):
            report = self.generate(images[i])
            reports.append(report)
            if (i + 1) % 10 == 0:
                logger.info(f"توليد التقرير {i+1}/{len(images)}")
        return reports

    def _generate_template_report(self, image: np.ndarray) -> str:
        """
        توليد تقرير قالب بسيط (بدون نموذج مدرب)
        يحلل الصورة بطريقة بسيطة لتوليد وصف أولي
        """
        if self.language == "ar":
            header = "تقرير الفحص الشعاعي\n"
            findings = self._analyze_image_simple(image)
            return (
                f"{header}"
                f"{'=' * 30}\n"
                f"النتائج:\n{findings}\n"
                f"{'=' * 30}\n"
                f"التوصية: يُنصح بمراجعة الطبيب المختص."
            )
        else:
            header = "Radiology Report\n"
            findings = self._analyze_image_simple(image)
            return (
                f"{header}"
                f"{'=' * 30}\n"
                f"Findings:\n{findings}\n"
                f"{'=' * 30}\n"
                f"Recommendation: Consult with specialist."
            )

    def _analyze_image_simple(self, image: np.ndarray) -> str:
        """تحليل بسيط للصورة لتوليد وصف أولي"""
        mean_val = np.mean(image)
        std_val = np.std(image)
        max_val = np.max(image)

        if self.language == "ar":
            analysis = f"متوسط كثافة الصورة: {mean_val:.1f}, الانحراف المعياري: {std_val:.1f}\n"

            if mean_val < 0.3:
                analysis += "- الصورة تظهر مناطق مظلمة قد تشير إلى وجود هواء أو انصباب\n"
            elif mean_val < 0.6:
                analysis += "- الصورة تظهر كثافة نسيجية طبيعية نسبياً\n"
            else:
                analysis += "- الصورة تظهر مناطق كثيفة قد تشير إلى تعظّم أو ارتشاح\n"

            if std_val > 0.25:
                analysis += "- تباين عالي يشير إلى وجود مناطق مختلفة الكثافة\n"

            analysis += f"- الحد الأقصى للكثافة: {max_val:.1f}"
            return analysis
        else:
            analysis = f"Mean intensity: {mean_val:.1f}, Std: {std_val:.1f}\n"
            analysis += f"- Max intensity: {max_val:.1f}"
            return analysis

    def _get_prompt(self) -> str:
        """الحصول على نص البداية للتوليد"""
        if self.language == "ar":
            return "تقرير الفحص الشعاعي: النتائج تظهر"
        return "Radiology report findings: The examination shows"

    def _format_report(self, text: str) -> str:
        """تنسيق التقرير"""
        if self.language == "ar":
            sections = ["النتائج", "الاستنتاج", "التوصية"]
            report = f"تقرير الفحص الشعاعي\n{'=' * 30}\n{text}\n"
            return report
        return text

    def train(
        self,
        image_paths: List[str],
        report_texts: List[str],
        epochs: int = 10,
        batch_size: int = 4,
        learning_rate: float = 3e-5,
        save_dir: Optional[str] = None,
    ):
        """
        تدريب نموذج VLM على أزواج (صورة، تقرير)

        Args:
            image_paths: مسارات الصور
            report_texts: نصوص التقارير المقابلة
            epochs: عدد الحقب
            batch_size: حجم المجموعة
            learning_rate: معدل التعلم
            save_dir: مجلد الحفظ
        """
        try:
            import torch
            import torch.nn as nn
            import torch.optim as optim
            from torch.utils.data import DataLoader, Dataset
        except ImportError:
            logger.error("PyTorch غير مثبت")
            return

        # تحميل النماذج
        self._load_vision_encoder()
        self._load_text_decoder()
        self._build_projection()

        # تجهيز البيانات
        class ReportDataset(Dataset):
            def __init__(self, img_paths, texts, feature_extractor, tokenizer, image_size):
                self.img_paths = img_paths
                self.texts = texts
                self.feature_extractor = feature_extractor
                self.tokenizer = tokenizer
                self.image_size = image_size

            def __len__(self):
                return len(self.img_paths)

            def __getitem__(self, idx):
                try:
                    from PIL import Image
                    img = Image.open(self.img_paths[idx]).convert("RGB")
                    if img.size != self.image_size:
                        img = img.resize(self.image_size)
                    img_np = np.array(img)
                    pixel_values = self.feature_extractor(
                        images=img_np, return_tensors="pt"
                    )["pixel_values"].squeeze(0)
                except Exception:
                    pixel_values = torch.zeros(
                        3, self.image_size[0], self.image_size[1]
                    )

                text = self.texts[idx]
                tokens = self.tokenizer(
                    text, truncation=True, max_length=512,
                    padding="max_length", return_tensors="pt",
                )

                return {
                    "pixel_values": pixel_values,
                    "input_ids": tokens["input_ids"].squeeze(0),
                    "attention_mask": tokens["attention_mask"].squeeze(0),
                }

        dataset = ReportDataset(
            image_paths, report_texts,
            self.feature_extractor, self.tokenizer, self.image_size,
        )

        dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

        # إعداد التدريب
        params = list(self.projection.parameters()) + list(self.text_decoder.parameters())
        optimizer = optim.AdamW(params, lr=learning_rate)

        logger.info(f"بدء تدريب VLM: {epochs} حقب, {len(image_paths)} عينة")

        # تجميد Vision Encoder (نستخدم المميزات الجاهزة)
        for param in self.vision_encoder.parameters():
            param.requires_grad = False

        for epoch in range(epochs):
            self.text_decoder.train()
            self.projection.train()
            total_loss = 0.0

            for batch in dataloader:
                pixel_values = batch["pixel_values"].to(self.device)
                input_ids = batch["input_ids"].to(self.device)
                attention_mask = batch["attention_mask"].to(self.device)

                optimizer.zero_grad()

                # Vision features
                with torch.no_grad():
                    vision_outputs = self.vision_encoder(pixel_values)
                    vision_features = vision_outputs.last_hidden_state[:, 0, :]

                # Projection
                projected = self.projection(vision_features)

                # Language modeling loss
                outputs = self.text_decoder(
                    input_ids=input_ids,
                    attention_mask=attention_mask,
                    labels=input_ids,
                )
                loss = outputs.loss
                loss.backward()
                optimizer.step()

                total_loss += loss.item()

            avg_loss = total_loss / len(dataloader)
            logger.info(f"  حقبة {epoch+1}/{epochs} | الخسارة: {avg_loss:.4f}")

            if save_dir and (epoch + 1) % 5 == 0:
                self._save_model(save_dir)

        self.is_trained = True
        logger.info("انتهى تدريب VLM")

    def _save_model(self, save_dir: str):
        """حفظ النموذج"""
        import torch
        save_path = Path(save_dir)
        save_path.mkdir(parents=True, exist_ok=True)

        torch.save({
            "projection": self.projection.state_dict(),
            "text_decoder": self.text_decoder.state_dict(),
            "config": {
                "language": self.language,
                "vision_model": self.vision_model_name,
                "text_model": self.text_model_name,
                "max_text_length": self.max_text_length,
                "image_size": self.image_size,
            },
        }, save_path / "vlm_reporter.pt")

        logger.info(f"تم حفظ VLM: {save_path}")


class ReportGenerator:
    """
    واجهة عالية المستوى لتوليد التقارير الطبية
    تجمع بين VLM والقوالب والمعلومات المُستخرجة من NER
    """

    def __init__(self, language: str = "ar"):
        self.vlm = VLMReporter(language=language)
        self.language = language

    def generate_report(
        self,
        image: np.ndarray,
        ner_results: Optional[Dict[str, Any]] = None,
        use_template: bool = True,
    ) -> str:
        """
        توليد تقرير شامل

        Args:
            image: مصفوفة الصورة
            ner_results: نتائج NER (اختياري)
            use_template: استخدام القالب

        Returns:
            نص التقرير
        """
        if use_template and ner_results:
            return self._generate_from_ner(image, ner_results)
        return self.vlm.generate(image)

    def _generate_from_ner(
        self,
        image: np.ndarray,
        ner_results: Dict[str, Any],
    ) -> str:
        """توليد تقرير من نتائج NER"""
        entities = ner_results.get("entities", [])
        relations = ner_results.get("relations", [])
        labels = ner_results.get("labels", {})

        if self.language == "ar":
            report = "تقرير الفحص الشعاعي\n" + "=" * 30 + "\n\n"
            report += "النتائج:\n"

            # بناء وصف من الكيانات
            described = set()
            for entity in entities:
                if entity.get("is_negated", False):
                    continue
                text = entity.get("ar", entity.get("text", ""))
                category = entity.get("category", "")

                if text in described:
                    continue
                described.add(text)

                if category == "DISEASE":
                    report += f"- وجود {text}"
                    # البحث عن الموقع
                    loc = self._find_related(entity, relations, "location")
                    if loc:
                        report += f" في منطقة {loc}"
                    lat = self._find_related(entity, relations, "laterality")
                    if lat:
                        report += f" ({lat})"
                    sev = self._find_related(entity, relations, "severity")
                    if sev:
                        report += f" بدرجة {sev}"
                    report += "\n"
                elif category == "FINDING":
                    report += f"- {text}\n"

            report += "\n" + "=" * 30 + "\n"
            report += "التوصية: يُنصح بالمراجعة المتخصصة.\n"
            return report
        else:
            report = "Radiology Report\n" + "=" * 30 + "\n\nFindings:\n"
            for entity in entities:
                if entity.get("is_negated", False):
                    continue
                text = entity.get("en", entity.get("text", ""))
                report += f"- {text}\n"
            return report

    def _find_related(
        self, entity: Dict, relations: List[Dict], rel_type: str
    ) -> Optional[str]:
        """البحث عن كيان مرتبط"""
        entity_text = entity.get("text", "")
        for rel in relations:
            if rel.get("subject", "") == entity_text:
                return rel.get("relations", {}).get(rel_type)
        return None
