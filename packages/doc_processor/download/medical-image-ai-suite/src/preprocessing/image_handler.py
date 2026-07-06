"""
معالج الصور العامة - Image Handler
معالجة صور JPG/PNG وتحسينها وتعزيزها للنماذج الطبية
"""

import os
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Union, Any

import numpy as np

from ..utils.logger import get_logger

logger = get_logger("image_handler")


class ImageHandler:
    """
    معالج صور JPG/PNG للنماذج الطبية

    يدعم:
    - قراءة وتحويل الصور بأشكال مختلفة
    - تطبيع وتوحيد الحجم
    - تعزيز البيانات (Data Augmentation) الطبي
    - تصحيح السطوع والتباين
    - دعم الصور ثلاثية القنوات وثنائية الأبعاد

    الاستخدام:
        handler = ImageHandler(target_size=(512, 512))
        array = handler.load_image("xray.jpg")
        augmented = handler.apply_augmentation(array)
    """

    def __init__(
        self,
        target_size: Tuple[int, int] = (512, 512),
        normalize: bool = True,
        normalize_range: Tuple[float, float] = (0.0, 1.0),
        augment_config: Optional[Dict[str, Any]] = None,
    ):
        """
        Args:
            target_size: الحجم المستهدف (ارتفاع × عرض)
            normalize: تطبيع قيم البيكسلات
            normalize_range: نطاق التطبيع
            augment_config: إعدادات تعزيز البيانات
        """
        self.target_size = target_size
        self.normalize = normalize
        self.normalize_range = normalize_range
        self.augment_config = augment_config or {
            "rotation_range": 15,
            "zoom_range": 0.1,
            "brightness_range": [0.8, 1.2],
            "contrast_range": [0.9, 1.1],
            "horizontal_flip": True,
            "vertical_flip": False,
            "gaussian_noise": 0.02,
            "elastic_deform": False,
        }

    def load_image(
        self,
        filepath: Union[str, Path],
        grayscale: bool = True,
    ) -> np.ndarray:
        """
        تحميل صورة JPG/PNG وتحويلها إلى مصفوفة NumPy

        Args:
            filepath: مسار الصورة
            grayscale: تحويل إلى تدرج رمادي

        Returns:
            مصفوفة NumPy [H, W] أو [H, W, 3]
        """
        filepath = Path(filepath)
        if not filepath.exists():
            raise FileNotFoundError(f"الصورة غير موجودة: {filepath}")

        # محاولة القراءة بـ OpenCV أولاً
        try:
            import cv2
            img = cv2.imread(str(filepath), cv2.IMREAD_UNCHANGED)
            if img is None:
                raise ValueError("فشل قراءة الصورة")
            # تحويل BGR إلى RGB
            if img.ndim == 3:
                img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        except ImportError:
            from PIL import Image
            img = np.array(Image.open(filepath))

        # تحويل إلى تدرج رمادي إن طُلب
        if grayscale and img.ndim == 3:
            img = self._to_grayscale(img)

        # تغيير الحجم
        img = self._resize(img)

        # التطبيع
        if self.normalize:
            img = self._normalize(img)

        return img.astype(np.float32)

    def load_batch(
        self,
        directory: Union[str, Path],
        extensions: Tuple[str, ...] = (".jpg", ".jpeg", ".png", ".bmp", ".tiff"),
        grayscale: bool = True,
        max_files: Optional[int] = None,
    ) -> Tuple[np.ndarray, List[str]]:
        """
        تحميل مجموعة صور من مجلد

        Args:
            directory: مسار المجلد
            extensions: صيغ الملفات المقبولة
            grayscale: تحويل إلى تدرج رمادي
            max_files: أقصى عدد صور (لا شيء = الكل)

        Returns:
            tuple: (مصفوفة_الصور [N, H, W], قائمة_المسارات)
        """
        directory = Path(directory)
        files = []
        for ext in extensions:
            files.extend(directory.rglob(f"*{ext}"))
            files.extend(directory.rglob(f"*{ext.upper()}"))

        files = sorted(set(files))
        if max_files:
            files = files[:max_files]

        logger.info(f"تحميل {len(files)} صورة من {directory.name}")

        images = []
        valid_paths = []
        for f in files:
            try:
                img = self.load_image(f, grayscale=grayscale)
                images.append(img)
                valid_paths.append(str(f))
            except Exception as e:
                logger.warning(f"تخطي {f.name}: {e}")

        if not images:
            raise ValueError(f"لم يتم تحميل أي صورة من {directory}")

        batch = np.stack(images, axis=0)
        logger.info(f"تم تحميل مجموعة: {batch.shape}")
        return batch, valid_paths

    def apply_augmentation(
        self,
        image: np.ndarray,
        config: Optional[Dict[str, Any]] = None,
    ) -> np.ndarray:
        """
        تطبيق تعزيز البيانات على صورة واحدة

        يشمل: دوران، تكبير، تعديل السطوع والتباين، قلب، ضوضاء غاوسية

        Args:
            image: مصفوفة الصورة [H, W] أو [H, W, 3]
            config: إعدادات التعزيز (لا شيء = الإعدادات الافتراضية)

        Returns:
            صورة مُحسّنة بنفس الأبعاد
        """
        cfg = config or self.augment_config
        augmented = image.copy()

        # دوران عشوائي
        if cfg.get("rotation_range", 0) > 0:
            angle = np.random.uniform(-cfg["rotation_range"], cfg["rotation_range"])
            augmented = self._rotate(augmented, angle)

        # تكبير/تصغير
        if cfg.get("zoom_range", 0) > 0:
            scale = 1.0 + np.random.uniform(-cfg["zoom_range"], cfg["zoom_range"])
            augmented = self._zoom(augmented, scale)

        # تعديل السطوع
        brightness_range = cfg.get("brightness_range", [1.0, 1.0])
        if brightness_range[0] != 1.0 or brightness_range[1] != 1.0:
            factor = np.random.uniform(brightness_range[0], brightness_range[1])
            augmented = self._adjust_brightness(augmented, factor)

        # تعديل التباين
        contrast_range = cfg.get("contrast_range", [1.0, 1.0])
        if contrast_range[0] != 1.0 or contrast_range[1] != 1.0:
            factor = np.random.uniform(contrast_range[0], contrast_range[1])
            augmented = self._adjust_contrast(augmented, factor)

        # قفل أفقي
        if cfg.get("horizontal_flip", False) and np.random.random() > 0.5:
            augmented = np.fliplr(augmented)

        # قفل عمودي
        if cfg.get("vertical_flip", False) and np.random.random() > 0.5:
            augmented = np.flipud(augmented)

        # ضوضاء غاوسية
        noise_std = cfg.get("gaussian_noise", 0.0)
        if noise_std > 0:
            augmented = self._add_gaussian_noise(augmented, noise_std)

        # تشوه مرن
        if cfg.get("elastic_deform", False):
            augmented = self._elastic_deformation(augmented)

        return augmented

    def apply_clahe(
        self,
        image: np.ndarray,
        clip_limit: float = 2.0,
        tile_grid_size: Tuple[int, int] = (8, 8),
    ) -> np.ndarray:
        """
        تطبيق CLAHE (Equalization التكيفي المقيد بالنافذة)

        يعزز التباين المحلي دون تضخيم الضوضاء - مثالي للأشعة السينية

        Args:
            image: مصفوفة الصورة
            clip_limit: حد القص
            tile_grid_size: حجم شبكة البلاط

        Returns:
            صورة مُحسّنة
        """
        import cv2

        if image.ndim == 3:
            image = self._to_grayscale(image)

        # تحويل إلى uint8
        if image.dtype != np.uint8:
            img_uint8 = self._to_uint8(image)
        else:
            img_uint8 = image.copy()

        clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid_size)
        result = clahe.apply(img_uint8)
        return result.astype(np.float32)

    def histogram_matching(
        self,
        source: np.ndarray,
        reference: np.ndarray,
    ) -> np.ndarray:
        """
        مطابقة الرسم البياني لتوحيد الإضاءة بين الصور

        مفيد عند وجود تباين كبير في جودة الصور

        Args:
            source: الصورة المصدر
            reference: الصورة المرجعية

        Returns:
            صورة المصدر بعد مطابقة الرسم البياني
        """
        from skimage.exposure import match_histograms

        if source.ndim == 2:
            source = np.expand_dims(source, axis=-1)
        if reference.ndim == 2:
            reference = np.expand_dims(reference, axis=-1)

        matched = match_histograms(source, reference, channel_axis=-1)
        return np.squeeze(matched).astype(np.float32)

    def remove_artifacts(
        self,
        image: np.ndarray,
        kernel_size: int = 5,
        method: str = "morphology",
    ) -> np.ndarray:
        """
        إزالة العيوب والضوضاء من الصور الطبية

        Args:
            image: مصفوفة الصورة
            kernel_size: حجم الفلتر
            method: طريقة الإزالة (morphology, median, gaussian, bilateral)

        Returns:
            صورة مُنظّفة
        """
        import cv2

        if image.ndim == 3:
            image = self._to_grayscale(image)
        if image.dtype != np.uint8:
            image = self._to_uint8(image)

        if method == "morphology":
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
            result = cv2.morphologyEx(image, cv2.MORPH_CLOSE, kernel)
            result = cv2.morphologyEx(result, cv2.MORPH_OPEN, kernel)
        elif method == "median":
            result = cv2.medianBlur(image, kernel_size)
        elif method == "gaussian":
            result = cv2.GaussianBlur(image, (kernel_size, kernel_size), 0)
        elif method == "bilateral":
            result = cv2.bilateralFilter(image, 9, 75, 75)
        else:
            result = image

        return result.astype(np.float32)

    # ===== دوال تعزيز البيانات =====

    def generate_augmented_dataset(
        self,
        images: np.ndarray,
        augmentations_per_image: int = 5,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        توليد مجموعة بيانات مُحسّنة من مجموعة أصلية

        Args:
            images: مجموعة الصور الأصلية [N, H, W]
            augmentations_per_image: عدد النسخ المُحسّنة لكل صورة

        Returns:
            tuple: (مجموعة_مُحسّنة, فهرس_الصورة_الأصلية)
        """
        augmented = [images]
        labels = [np.arange(len(images))]

        for _ in range(augmentations_per_image):
            batch = np.array([self.apply_augmentation(img) for img in images])
            augmented.append(batch)
            labels.append(np.arange(len(images)))

        augmented_all = np.concatenate(augmented, axis=0)
        labels_all = np.concatenate(labels, axis=0)

        logger.info(
            f"تم توليد {len(augmented_all)} صورة مُحسّنة "
            f"({len(images)} أصلية × {augmentations_per_image + 1})"
        )
        return augmented_all, labels_all

    # ===== دوال مساعدة داخلية =====

    def _to_grayscale(self, img: np.ndarray) -> np.ndarray:
        """تحويل إلى تدرج رمادي"""
        if img.ndim == 3:
            return np.dot(img[..., :3], [0.299, 0.587, 0.114])
        return img

    def _to_uint8(self, img: np.ndarray) -> np.ndarray:
        """تحويل إلى uint8"""
        if img.max() <= 1.0:
            return (img * 255).clip(0, 255).astype(np.uint8)
        return img.clip(0, 255).astype(np.uint8)

    def _resize(self, img: np.ndarray) -> np.ndarray:
        """تغيير حجم الصورة"""
        if img.shape[0] == self.target_size[0] and img.shape[1] == self.target_size[1]:
            return img
        try:
            import cv2
            if img.ndim == 2:
                return cv2.resize(img, (self.target_size[1], self.target_size[0]),
                                  interpolation=cv2.INTER_LINEAR)
            return cv2.resize(img, (self.target_size[1], self.target_size[0]),
                              interpolation=cv2.INTER_LINEAR)
        except ImportError:
            from PIL import Image
            pil_img = Image.fromarray(img.astype(np.float32) if img.dtype == np.float32 else img)
            return np.array(pil_img.resize((self.target_size[1], self.target_size[0]), Image.BILINEAR))

    def _normalize(self, img: np.ndarray) -> np.ndarray:
        """تطبيع الصورة"""
        min_val, max_val = self.normalize_range
        img_min, img_max = img.min(), img.max()
        if img_max - img_min > 0:
            img = (img - img_min) / (img_max - img_min)
            img = img * (max_val - min_val) + min_val
        return img

    def _rotate(self, img: np.ndarray, angle: float) -> np.ndarray:
        """دوران الصورة"""
        try:
            import cv2
            h, w = img.shape[:2]
            M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1)
            return cv2.warpAffine(img, M, (w, h), borderMode=cv2.BORDER_REFLECT)
        except ImportError:
            from PIL import Image
            return np.array(Image.fromarray(img).rotate(angle, fillcolor=0))

    def _zoom(self, img: np.ndarray, scale: float) -> np.ndarray:
        """تكبير/تصغير"""
        try:
            import cv2
            h, w = img.shape[:2]
            new_h, new_w = int(h * scale), int(w * scale)
            zoomed = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
            # اقتصاص أو حشو للحفاظ على الحجم الأصلي
            if scale > 1:
                start_h = (new_h - h) // 2
                start_w = (new_w - w) // 2
                return zoomed[start_h:start_h + h, start_w:start_w + w]
            else:
                pad_h = (h - new_h) // 2
                pad_w = (w - new_w) // 2
                result = np.zeros_like(img)
                result[pad_h:pad_h + new_h, pad_w:pad_w + new_w] = zoomed
                return result
        except ImportError:
            return img

    def _adjust_brightness(self, img: np.ndarray, factor: float) -> np.ndarray:
        """تعديل السطوع"""
        return np.clip(img * factor, 0, img.max() if img.max() > 1 else 1)

    def _adjust_contrast(self, img: np.ndarray, factor: float) -> np.ndarray:
        """تعديل التباين"""
        mean = np.mean(img)
        return np.clip((img - mean) * factor + mean, 0, img.max() if img.max() > 1 else 1)

    def _add_gaussian_noise(self, img: np.ndarray, std: float) -> np.ndarray:
        """إضافة ضوضاء غاوسية"""
        noise = np.random.normal(0, std, img.shape).astype(np.float32)
        return np.clip(img + noise, 0, img.max() if img.max() > 1 else 1)

    def _elastic_deformation(self, img: np.ndarray) -> np.ndarray:
        """تشوه مرن بسيط"""
        try:
            from scipy.ndimage import gaussian_filter
            h, w = img.shape[:2]
            dx = gaussian_filter(np.random.randn(h, w), 5) * 5
            dy = gaussian_filter(np.random.randn(h, w), 5) * 5
            y, x = np.meshgrid(np.arange(h), np.arange(w), indexing="ij")
            indices = np.clip(y + dy, 0, h - 1).astype(int), np.clip(x + dx, 0, w - 1).astype(int)
            return img[indices]
        except ImportError:
            return img
