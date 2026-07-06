"""
مقاييس التقييم الطبي - Medical Evaluation Metrics
مقاييس مخصصة لتقييم نماذج الصور الطبية
"""

import numpy as np
from typing import List, Dict, Tuple, Optional, Union
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score,
    f1_score, roc_auc_score, confusion_matrix,
)
from .logger import get_logger

logger = get_logger("metrics")


class MedicalMetrics:
    """
    مجموعة مقاييس التقييم للنماذج الطبية
    تشمل مقاييس التصنيف والتقسيم وتوليد الصور والتقارير
    """

    def __init__(self, num_classes: int = 10, class_names: Optional[List[str]] = None):
        self.num_classes = num_classes
        self.class_names = class_names or [f"class_{i}" for i in range(num_classes)]
        self.reset()

    def reset(self):
        """إعادة تعيين جميع المقاييس"""
        self.predictions = []
        self.targets = []
        self.probas = []

    def update(
        self,
        y_pred: np.ndarray,
        y_true: np.ndarray,
        y_prob: Optional[np.ndarray] = None,
    ):
        """
        تحديث المقاييس بنتائج جديدة

        Args:
            y_pred: التوقعات [batch_size]
            y_true: القيم الحقيقية [batch_size]
            y_prob: احتمالات الفئات [batch_size, num_classes]
        """
        self.predictions.extend(y_pred.flatten().tolist())
        self.targets.extend(y_true.flatten().tolist())
        if y_prob is not None:
            self.probas.extend(y_prob.tolist())

    def compute_classification(self) -> Dict[str, float]:
        """
        حساب مقاييس التصنيف: الدقة، الاستدعاء، F1، AUC-ROC

        Returns:
            قاموس بالمقاييس المحسوبة
        """
        if not self.targets:
            logger.warning("لا توجد بيانات لحساب المقاييس")
            return {}

        y_true = np.array(self.targets)
        y_pred = np.array(self.predictions)

        results = {
            "accuracy": accuracy_score(y_true, y_pred),
            "precision_macro": precision_score(y_true, y_pred, average="macro", zero_division=0),
            "recall_macro": recall_score(y_true, y_pred, average="macro", zero_division=0),
            "f1_macro": f1_score(y_true, y_pred, average="macro", zero_division=0),
            "f1_weighted": f1_score(y_true, y_pred, average="weighted", zero_division=0),
        }

        # AUC-ROC إذا توفرت الاحتمالات
        if self.probas and len(self.probas[0]) > 1:
            y_prob = np.array(self.probas)
            try:
                results["auc_roc_macro"] = roc_auc_score(
                    y_true, y_prob, multi_class="ovr", average="macro"
                )
            except ValueError:
                pass

        # مصفوفة الالتباس
        cm = confusion_matrix(y_true, y_pred)
        results["confusion_matrix"] = cm.tolist()

        return results

    @staticmethod
    def dice_coefficient(y_true: np.ndarray, y_pred: np.ndarray, smooth: float = 1e-6) -> float:
        """
        حساب معامل Dice للتقسيم الدلالي

        Args:
            y_true: القناع الحقيقي [H, W] أو [H, W, D]
            y_pred: القناع المتوقع بنفس الأبعاد
            smooth: ثابت التنظيم لتجنب القسمة على صفر

        Returns:
            قيمة معامل Dice بين 0 و 1
        """
        y_true_f = y_true.flatten().astype(np.float32)
        y_pred_f = y_pred.flatten().astype(np.float32)
        intersection = np.sum(y_true_f * y_pred_f)
        return (2.0 * intersection + smooth) / (np.sum(y_true_f) + np.sum(y_pred_f) + smooth)

    @staticmethod
    def iou_score(y_true: np.ndarray, y_pred: np.ndarray, smooth: float = 1e-6) -> float:
        """
        حساب تقاطع فوق الاتحاد (IoU) للتقسيم الدلالي

        Args:
            y_true: القناع الحقيقي
            y_pred: القناع المتوقع
            smooth: ثابت التنظيم

        Returns:
            قيمة IoU بين 0 و 1
        """
        y_true_f = y_true.flatten().astype(np.float32)
        y_pred_f = y_pred.flatten().astype(np.float32)
        intersection = np.sum(y_true_f * y_pred_f)
        union = np.sum(y_true_f) + np.sum(y_pred_f) - intersection
        return (intersection + smooth) / (union + smooth)

    @staticmethod
    def hausdorff_distance(y_true: np.ndarray, y_pred: np.ndarray) -> float:
        """
        حساب مسافة Hausdorff المعدّلة للتقسيم

        Args:
            y_true: القناع الحقيقي
            y_pred: القناع المتوقع

        Returns:
            مسافة Hausdorff المعدّلة
        """
        from scipy.ndimage import distance_transform_edt

        true_points = np.argwhere(y_true > 0)
        pred_points = np.argwhere(y_pred > 0)

        if len(true_points) == 0 or len(pred_points) == 0:
            return float("inf")

        true_surface = distance_transform_edt(y_true == 0)
        pred_surface = distance_transform_edt(y_pred == 0)

        hd1 = np.max(true_surface[y_pred > 0]) if np.any(y_pred > 0) else 0.0
        hd2 = np.max(pred_surface[y_true > 0]) if np.any(y_true > 0) else 0.0

        return float(max(hd1, hd2))

    @staticmethod
    def ssim_index(img1: np.ndarray, img2: np.ndarray) -> float:
        """
        حساب مؤشر التشابه الهيكلي (SSIM)

        Args:
            img1: الصورة الأولى [H, W]
            img2: الصورة الثانية [H, W]

        Returns:
            قيمة SSIM بين -1 و 1
        """
        from skimage.metrics import structural_similarity as ssim

        if img1.ndim == 3 and img1.shape[0] in (1, 3):
            img1 = img1.transpose(1, 2, 0)
            img2 = img2.transpose(1, 2, 0)

        return float(ssim(img1, img2, data_range=img1.max() - img1.min()))

    @staticmethod
    def psnr(img1: np.ndarray, img2: np.ndarray, max_val: float = 255.0) -> float:
        """
        حساب نسبة الذروة إلى نسبة الضوضاء (PSNR)

        Args:
            img1: الصورة الأولى
            img2: الصورة الثانية
            max_val: أقصى قيمة ممكنة

        Returns:
            قيمة PSNR بالديسيبل
        """
        mse = np.mean((img1.astype(np.float64) - img2.astype(np.float64)) ** 2)
        if mse == 0:
            return float("inf")
        return float(10.0 * np.log10((max_val ** 2) / mse))

    def compute_report_metrics(
        self,
        references: List[str],
        hypotheses: List[str],
    ) -> Dict[str, float]:
        """
        حساب مقاييس تقييم التقارير النصية (BLEU, ROUGE, BERTScore)

        Args:
            references: القوائم المرجعية
            hypotheses: القوائم المتوقعة

        Returns:
            قاموس بمقاييس التقييم
        """
        results = {}

        # BLEU Score
        try:
            from nltk.translate.bleu_score import corpus_bleu
            refs = [[ref.split()] for ref in references]
            hyps = [hyp.split() for hyp in hypotheses]
            results["bleu_1"] = corpus_bleu(refs, hyps, weights=(1.0, 0, 0, 0))
            results["bleu_4"] = corpus_bleu(refs, hyps, weights=(0.25, 0.25, 0.25, 0.25))
        except (ImportError, Exception):
            logger.warning("تعذر حساب BLEU - يرجى تثبيت nltk")

        # ROUGE Score
        try:
            from rouge_score import rouge_scorer
            scorer = rouge_scorer.RougeScorer(["rouge1", "rouge2", "rougeL"], use_stemmer=False)
            rouge_scores = {"rouge1": [], "rouge2": [], "rougeL": []}
            for ref, hyp in zip(references, hypotheses):
                scores = scorer.score(ref, hyp)
                for key in rouge_scores:
                    rouge_scores[key].append(scores[key].fmeasure)
            for key in rouge_scores:
                results[key] = float(np.mean(rouge_scores[key]))
        except (ImportError, Exception):
            logger.warning("تعذر حساب ROUGE - يرجى تثبيت rouge-score")

        return results
