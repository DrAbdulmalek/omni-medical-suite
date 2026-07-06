"""
مستخرج الإشارات الضعيفة - Weak Label Extractor
استخراج إشارات تدريب ضعيفة من التقارير الطبية لتدريب النماذج بصورة شبه خاضعة للإشراف
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union

import numpy as np

from ..ner.arabic_ner import ArabicMedicalNER
from ..preprocessing.text_handler import TextHandler
from ..utils.logger import get_logger

logger = get_logger("weak_labels")


class BinaryLabelExtractor:
    """
    مستخرج الإشارات الثنائية من التقارير

    يحوّل التقرير النصي إلى تصنيف ثنائي (موجود/غير موجود) لكل مرض/حالة

    مثال:
        "يوجد التهاب رئوي في الرئة اليمنى" → {"pneumonia": 1.0, "right_lung": 1.0}
        "لا يوجد انصباب جنبي" → {"pleural_effusion": 0.0}
    """

    def __init__(self, ner: Optional[ArabicMedicalNER] = None):
        self.ner = ner or ArabicMedicalNER()
        self.text_handler = TextHandler()

    def extract(self, report_text: str) -> Dict[str, float]:
        """
        استخراج إشارات ثنائية من تقرير واحد

        Args:
            report_text: نص التقرير

        Returns:
            قاموس {اسم_الفئة: ثقة (0.0 أو 1.0)}
        """
        # تنظيف النص أولاً
        cleaned = self.text_handler.clean(report_text)

        # استخراج الكيانات مع كشف النفي
        results = self.ner.extract(cleaned)

        # تحويل إلى إشارات ثنائية
        labels = {}
        for label_name, confidence in results.get("labels", {}).items():
            # الإشارة السالبة = لا يوجد المرض
            if confidence < 0:
                labels[label_name] = 0.0
            # الإشارة الموجبة = يوجد المرض
            elif confidence >= 0.5:
                labels[label_name] = 1.0
            # الضبابية = 0.5
            else:
                labels[label_name] = 0.5

        return labels

    def extract_batch(
        self,
        reports: List[str],
        min_frequency: int = 2,
    ) -> Tuple[np.ndarray, List[str], Dict[str, Any]]:
        """
        استخراج إشارات ثنائية من مجموعة تقارير

        Args:
            reports: قائمة نصوص التقارير
            min_frequency: أقل تكرر مطلوب لفئة لتضمينها

        Returns:
            tuple: (مصفوفة_الإشارات [N, C], قائمة_أسماء_الفئات, إحصائيات)
        """
        all_labels = []
        label_counts = {}

        logger.info(f"استخراج إشارات ضعيفة من {len(reports)} تقرير")

        for i, report in enumerate(reports):
            if not report or len(report.strip()) < 10:
                continue

            labels = self.extract(report)
            all_labels.append(labels)

            # حساب التكرارات
            for label_name in labels:
                if labels[label_name] > 0:
                    label_counts[label_name] = label_counts.get(label_name, 0) + 1

        if not all_labels:
            raise ValueError("لم يتم استخراج أي إشارات من التقارير")

        # تصفية الفئات النادرة
        frequent_labels = {
            name: count for name, count in label_counts.items()
            if count >= min_frequency
        }

        if not frequent_labels:
            # إذا لم توجد فئات متكررة كافية، نأخذ الأكثر شيوعاً
            sorted_labels = sorted(label_counts.items(), key=lambda x: -x[1])
            frequent_labels = dict(sorted_labels[:min(20, len(sorted_labels))])
            logger.warning(
                f"تصفية مريحة: استخدام {len(frequent_labels)} فئة الأكثر شيوعاً "
                f"(min_frequency={min_frequency} أقل من اللازم)"
            )

        class_names = sorted(frequent_labels.keys())
        label_matrix = np.zeros((len(all_labels), len(class_names)), dtype=np.float32)

        for i, labels in enumerate(all_labels):
            for j, class_name in enumerate(class_names):
                label_matrix[i, j] = labels.get(class_name, 0.0)

        stats = {
            "num_reports": len(all_labels),
            "num_classes": len(class_names),
            "class_distribution": {
                name: frequent_labels[name] for name in class_names
            },
            "label_density": float(np.mean(np.sum(label_matrix > 0, axis=1))),
            "avg_labels_per_report": float(np.mean(np.sum(label_matrix > 0, axis=1))),
        }

        logger.info(
            f"إشارات ضعيفة: {label_matrix.shape} "
            f"({stats['num_classes']} فئة, كثافة={stats['label_density']:.2f})"
        )

        return label_matrix, class_names, stats


class SegmentationLabelExtractor:
    """
    مستخرج إشارات التقسيم الدلالي من التقارير

    يحوّل وصف التقرير إلى قناع تقسيم تقريبي
    مفيد عندما لا تتوفر قناعات حقيقية (ground truth masks)

    مثال:
        "ارتشاح رئوي في الفص السفلي الأيمن" → قناع تقريبي في المنطقة السفلية اليمنى
    """

    # تعيين مناطق تشريحية إلى مناطق الصورة (نسب مئوية)
    ANATOMY_REGIONS = {
        "right_upper_lobe": {"x": (0.0, 0.5), "y": (0.0, 0.33)},
        "right_middle_lobe": {"x": (0.0, 0.5), "y": (0.33, 0.5)},
        "right_lower_lobe": {"x": (0.0, 0.5), "y": (0.5, 1.0)},
        "left_upper_lobe": {"x": (0.5, 1.0), "y": (0.0, 0.5)},
        "left_lower_lobe": {"x": (0.5, 1.0), "y": (0.5, 1.0)},
        "mediastinum": {"x": (0.4, 0.6), "y": (0.2, 0.8)},
        "right_hilum": {"x": (0.35, 0.5), "y": (0.35, 0.55)},
        "left_hilum": {"x": (0.5, 0.65), "y": (0.35, 0.55)},
        "right_costophrenic": {"x": (0.0, 0.45), "y": (0.8, 1.0)},
        "left_costophrenic": {"x": (0.55, 1.0), "y": (0.8, 1.0)},
        "apex": {"x": (0.25, 0.75), "y": (0.0, 0.15)},
        "base": {"x": (0.2, 0.8), "y": (0.85, 1.0)},
    }

    # أنماط التعيين من النص إلى المنطقة
    # ملاحظة: الأنماطة مصممة لتناسب النص بعد التطبيع (إزالة التشكيل وتوحيد الأحرف)
    REGION_PATTERNS = [
        (r"(?:الفص|فص)\s*(?:السفلي|اسفل|سفلي)\s*(?:الايمن|ايمن|اليمين|يمين)", "right_lower_lobe"),
        (r"(?:الفص|فص)\s*(?:العلوي|اعلى|علوي)\s*(?:الايمن|ايمن|اليمين|يمين)", "right_upper_lobe"),
        (r"(?:الفص|فص)\s*(?:الاو|اوسط|وسط)\s*(?:الايمن|ايمن|اليمين|يمين)", "right_middle_lobe"),
        (r"(?:الفص|فص)\s*(?:العلوي|اعلى|علوي)\s*(?:الايسر|ايسر|اليسار|يسار)", "left_upper_lobe"),
        (r"(?:الفص|فص)\s*(?:السفلي|اسفل|سفلي)\s*(?:الايسر|ايسر|اليسار|يسار)", "left_lower_lobe"),
        (r"منصف|mediastinum", "mediastinum"),
        (r"سرة|منشة|hilum", "right_hilum"),
        (r"قبة|سقف|apex", "apex"),
        (r"قاعدة|base", "base"),
        (r"منعطف|costophrenic", "right_costophrenic"),
        (r"(?:الرئه|رئه|الرئة|رئة)\s*(?:اليمينه|ايمن|الايمن|اليمنى)", "right_upper_lobe"),
        (r"(?:الرئه|رئه|الرئة|رئة)\s*(?:اليسرى|الايسر|ايسر|اليسار)", "left_upper_lobe"),
        (r"both lungs|bilaterally|ثنائي الجانب|ثنائي الجانب", "full_lung"),
    ]

    def __init__(self, image_size: Tuple[int, int] = (512, 512)):
        self.image_size = image_size
        self.ner = ArabicMedicalNER()
        self.text_handler = TextHandler()

    def extract_mask(
        self,
        report_text: str,
        abnormality_type: str = "all",
    ) -> np.ndarray:
        """
        توليد قناع تقسيم تقريبي من وصف التقرير

        Args:
            report_text: نص التقرير
            abnormality_type: نوع التشوه (all, consolidation, effusion, nodule, ...)

        Returns:
            قناع NumPy [H, W] بقيم بين 0 و 1
        """
        import re

        cleaned = self.text_handler.clean(report_text)
        mask = np.zeros(self.image_size, dtype=np.float32)

        # استخراج الكيانات
        ner_results = self.ner.extract(cleaned)
        entities = ner_results.get("entities", [])
        negated = ner_results.get("negated", [])

        # تحديد المناطق المذكورة
        detected_regions = set()
        for pattern, region_name in self.REGION_PATTERNS:
            if re.search(pattern, cleaned, re.IGNORECASE):
                detected_regions.add(region_name)

        # إنشاء القناع لكل منطقة مكتشفة
        for region_name in detected_regions:
            if region_name == "full_lung":
                # كلا الرئتين
                mask = np.maximum(mask, self._create_lung_mask())
            elif region_name in self.ANATOMY_REGIONS:
                region_mask = self._create_region_mask(
                    self.ANATOMY_REGIONS[region_name]
                )
                mask = np.maximum(mask, region_mask)

        # التحقق من النفي
        has_negation = len(negated) > 0
        if has_negation:
            mask = mask * 0.1  # تقليل الثقة بشكل كبير عند وجود نفي

        # تطبيق Gaussian smoothing لتليين الحواف
        mask = self._smooth_mask(mask)

        return mask

    def extract_batch_masks(
        self,
        reports: List[str],
        image_size: Optional[Tuple[int, int]] = None,
    ) -> np.ndarray:
        """
        توليد أقنعة تقسيم لمجموعة تقارير

        Args:
            reports: قائمة نصوص التقارير
            image_size: حجم القناع (لا شيء = الافتراضي)

        Returns:
            مصفوفة أقنعة [N, H, W]
        """
        if image_size:
            self.image_size = image_size

        masks = []
        for report in reports:
            mask = self.extract_mask(report)
            masks.append(mask)

        return np.stack(masks, axis=0)

    def _create_region_mask(
        self,
        region: Dict[str, Tuple[float, float]],
        softness: float = 0.1,
    ) -> np.ndarray:
        """إنشاء قناع لمنطقة تشريحية"""
        h, w = self.image_size
        y_coords = np.linspace(0, 1, h)
        x_coords = np.linspace(0, 1, w)
        xx, yy = np.meshgrid(x_coords, y_coords)

        # إنشاء قناع ناعم باستخدام الدالة السينية
        x_min, x_max = region["x"]
        y_min, y_max = region["y"]

        x_mask = (self._sigmoid((xx - x_min) / softness) *
                  self._sigmoid((x_max - xx) / softness))
        y_mask = (self._sigmoid((yy - y_min) / softness) *
                  self._sigmoid((y_max - yy) / softness))

        return (x_mask * y_mask).astype(np.float32)

    def _create_lung_mask(self) -> np.ndarray:
        """إنشاء قناع تقريبي للرئتين"""
        mask = np.zeros(self.image_size, dtype=np.float32)
        # الرئة اليمنى (أكبر قليلاً في الأشعة السينية)
        right = self._create_region_mask({
            "x": (0.05, 0.48), "y": (0.1, 0.9)
        })
        # الرئة اليسرى
        left = self._create_region_mask({
            "x": (0.52, 0.95), "y": (0.1, 0.85)
        })
        mask = np.maximum(right, left)
        return mask

    @staticmethod
    def _sigmoid(x: np.ndarray) -> np.ndarray:
        return 1.0 / (1.0 + np.exp(-x))

    @staticmethod
    def _smooth_mask(mask: np.ndarray, sigma: float = 5.0) -> np.ndarray:
        """تليين القناع بفلتر Gaussian"""
        try:
            from scipy.ndimage import gaussian_filter
            return gaussian_filter(mask, sigma=sigma)
        except ImportError:
            return mask


class WeakLabelExtractor:
    """
    مستخرج إشارات ضعيفة شامل
    يجمع بين الاستخراج الثنائي والتقسيمي
    """

    def __init__(
        self,
        image_size: Tuple[int, int] = (512, 512),
        min_label_confidence: float = 0.8,
    ):
        self.binary_extractor = BinaryLabelExtractor()
        self.seg_extractor = SegmentationLabelExtractor(image_size)
        self.min_confidence = min_label_confidence

    def extract(
        self,
        report_text: str,
        extract_binary: bool = True,
        extract_segmentation: bool = True,
    ) -> Dict[str, Any]:
        """
        استخراج جميع أنواع الإشارات الضعيفة

        Args:
            report_text: نص التقرير
            extract_binary: استخراج إشارات ثنائية
            extract_segmentation: استخراج أقنعة تقسيم

        Returns:
            قاموس شامل بالنتائج
        """
        results = {}

        if extract_binary:
            results["binary_labels"] = self.binary_extractor.extract(report_text)

        if extract_segmentation:
            results["segmentation_mask"] = self.seg_extractor.extract_mask(report_text)

        return results

    def extract_dataset(
        self,
        reports: List[str],
        images_paths: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        إنشاء مجموعة بيانات كاملة مع إشارات ضعيفة

        Args:
            reports: قائمة نصوص التقارير
            images_paths: مسارات الصور المقابلة (اختياري)

        Returns:
            قاموس بمجموعة البيانات
        """
        binary_labels = []
        seg_masks = []
        valid_indices = []

        logger.info(f"بناء مجموعة بيانات من {len(reports)} تقرير")

        for i, report in enumerate(reports):
            if not report or len(report.strip()) < 10:
                continue

            try:
                result = self.extract(report)
                binary_labels.append(result.get("binary_labels", {}))
                seg_masks.append(result.get("segmentation_mask"))
                valid_indices.append(i)
            except Exception as e:
                logger.warning(f"تخطي تقرير {i}: {e}")

        # تحويل إلى مصفوفات
        if binary_labels:
            # تجميع جميع أسماء الفئات
            all_classes = set()
            for labels in binary_labels:
                all_classes.update(labels.keys())
            class_names = sorted(all_classes)

            # بناء المصفوفة
            label_matrix = np.zeros((len(binary_labels), len(class_names)), dtype=np.float32)
            for i, labels in enumerate(binary_labels):
                for j, cls in enumerate(class_names):
                    label_matrix[i, j] = labels.get(cls, 0.0)
        else:
            label_matrix = np.array([])
            class_names = []

        seg_matrix = np.stack(seg_masks, axis=0) if seg_masks else np.array([])

        dataset = {
            "binary_labels": label_matrix,
            "binary_class_names": class_names,
            "segmentation_masks": seg_matrix,
            "valid_indices": valid_indices,
            "num_valid": len(valid_indices),
            "total_reports": len(reports),
            "images_paths": images_paths,
        }

        logger.info(
            f"مجموعة البيانات: {dataset['num_valid']}/{dataset['total_reports']} صالح "
            f"({len(class_names)} فئة ثنائية)"
        )

        return dataset
