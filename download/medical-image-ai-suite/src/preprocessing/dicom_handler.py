"""
معالج ملفات DICOM - DICOM Handler
قراءة ومعالجة وتحويل ملفات DICOM إلى صيغ قياسية
يدعم Windowing وتطبيع القيم ومعالجة البيانات ثلاثية الأبعاد
"""

import os
import re
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Union, Any

import numpy as np

from ..utils.logger import get_logger

logger = get_logger("dicom_handler")


# ===== نطاقات Windowing الطبية القياسية =====
PRESET_WINDOWS = {
    "lung": {"center": -600, "width": 1500, "description": "نافذة الرئة"},
    "mediastinum": {"center": 40, "width": 400, "description": "نافذة المنصف"},
    "bone": {"center": 400, "width": 1800, "description": "نافذة العظام"},
    "brain": {"center": 40, "width": 80, "description": "نافذة الدماغ"},
    "liver": {"center": 60, "width": 150, "description": "نافذة الكبد"},
    "abdomen": {"center": 40, "width": 400, "description": "نافذة البطن"},
    "stroke": {"center": 40, "width": 40, "description": "نافذة السكتة الدماغية"},
    "subdural": {"center": 80, "width": 200, "description": "نافذة الجافية"},
}


class DICOMHandler:
    """
    معالج ملفات DICOM متكامل

    يدعم:
    - قراءة ملفات DICOM فردية وسلاسل DICOM (DICOM Series)
    - تطبيق Windowing الطبي الذكي
    - استخراج البيانات الوصفية (Metadata) المهمة
    - التحويل إلى مصفوفات NumPy / صور JPG
    - تجميع الشرائح في أحجام ثلاثية الأبعاد

    الاستخدام:
        handler = DICOMHandler()
        array, metadata = handler.load_dicom("path/to/file.dcm")
        jpg_array = handler.apply_windowing(array, window="lung")
        volume = handler.load_series("path/to/series_dir/")
    """

    def __init__(
        self,
        target_size: Tuple[int, int] = (512, 512),
        normalize: bool = True,
        normalize_range: Tuple[float, float] = (0.0, 1.0),
        default_window: str = "lung",
        custom_windows: Optional[Dict[str, Dict[str, float]]] = None,
    ):
        """
        Args:
            target_size: الحجم المستهدف (ارتفاع × عرض)
            normalize: تطبيع قيم البيكسلات
            normalize_range: نطاق التطبيع
            default_window: نافذة Windowing الافتراضية
            custom_windows: نوافذ Windowing مخصصة
        """
        self.target_size = target_size
        self.normalize = normalize
        self.normalize_range = normalize_range
        self.default_window = default_window
        self.windows = {**PRESET_WINDOWS}
        if custom_windows:
            self.windows.update(custom_windows)

        # التحقق من تثبيت pydicom
        try:
            import pydicom
            self.pydicom = pydicom
            self.dcmread = pydicom.dcmread
        except ImportError:
            raise ImportError(
                "pydicom غير مثبت. يرجى تشغيل: pip install pydicom"
            )

        logger.info(f"تم تهيئة معالج DICOM (حجم مستهدف: {target_size}, نافذة: {default_window})")

    def load_dicom(self, filepath: Union[str, Path]) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        تحميل ملف DICOM وتحويله إلى مصفوفة NumPy

        Args:
            filepath: مسار ملف DICOM

        Returns:
            tuple: (مصفوفة_الصورة [H, W], بيانات_وصفية)

        Raises:
            FileNotFoundError: إذا لم يكن الملف موجوداً
            ValueError: إذا كان الملف تالفاً أو غير صالح
        """
        filepath = Path(filepath)
        if not filepath.exists():
            raise FileNotFoundError(f"ملف DICOM غير موجود: {filepath}")

        try:
            # قراءة الملف مع إيقاف الفحص الصارم (بعض الملفات الطبية بها تنبيهات)
            ds = self.dcmread(str(filepath), force=True)

            # استخراج البيانات الوصفية
            metadata = self._extract_metadata(ds)

            # تحويل البيانات البكسلية إلى مصفوفة NumPy
            pixel_array = ds.pixel_array.astype(np.float64)

            # تطبيق Rescale Slope / Intercept إن وجدا
            if hasattr(ds, "RescaleSlope") and ds.RescaleSlope:
                pixel_array = pixel_array * float(ds.RescaleSlope)
            if hasattr(ds, "RescaleIntercept") and ds.RescaleIntercept:
                pixel_array = pixel_array + float(ds.RescaleIntercept)

            # تحويل الصور ذات النوافذ الموقعة (Signed) إلى غير موقعة
            pixel_array = self._handle_signed_pixels(pixel_array, ds)

            # تغيير الحجم
            pixel_array = self._resize_array(pixel_array)

            # التطبيع
            if self.normalize:
                pixel_array = self._normalize_array(pixel_array)

            metadata["shape_original"] = list(pixel_array.shape)
            metadata["pixel_range"] = [float(pixel_array.min()), float(pixel_array.max())]

            logger.debug(f"تم تحميل DICOM: {filepath.name} | الشكل: {pixel_array.shape}")
            return pixel_array, metadata

        except Exception as e:
            logger.error(f"فشل تحميل DICOM: {filepath} | الخطأ: {e}")
            raise ValueError(f"ملف DICOM تالف أو غير صالح: {filepath}") from e

    def load_series(
        self,
        series_dir: Union[str, Path],
        sort_by: str = "instance_number",
        max_slices: Optional[int] = None,
    ) -> Tuple[np.ndarray, List[Dict[str, Any]]]:
        """
        تحميل سلسلة DICOM كحجم ثلاثي الأبعاد

        Args:
            series_dir: مجلد السلسلة (يحتوي على شرائح .dcm)
            sort_by: معيار ترتيب الشرائح (instance_number أو slice_location)
            max_slices: أقصى عدد شرائح (لا شيء = الكل)

        Returns:
            tuple: (حجم_ثلاثي_الأبعاد [D, H, W], قائمة_البيانات_الوصفية)
        """
        series_dir = Path(series_dir)
        if not series_dir.exists():
            raise FileNotFoundError(f"مجلد السلسلة غير موجود: {series_dir}")

        # البحث عن ملفات DICOM
        dcm_files = [
            f for f in series_dir.iterdir()
            if f.is_file() and (f.suffix.lower() == ".dcm" or self._is_dicom_file(f))
        ]

        if not dcm_files:
            raise ValueError(f"لم يتم العثور على ملفات DICOM في: {series_dir}")

        logger.info(f"تم العثور على {len(dcm_files)} شريحة DICOM في {series_dir.name}")

        # تحميل جميع الشرائح
        slices_data = []
        for f in dcm_files:
            try:
                arr, meta = self.load_dicom(f)
                slices_data.append((arr, meta, f.name))
            except Exception as e:
                logger.warning(f"تخطي شريحة تالفة: {f.name} | {e}")
                continue

        # ترتيب الشرائح
        slices_data = self._sort_slices(slices_data, sort_by)

        # تحديد عدد الشرائح
        if max_slices and len(slices_data) > max_slices:
            step = len(slices_data) / max_slices
            indices = [int(i * step) for i in range(max_slices)]
            slices_data = [slices_data[i] for i in indices]
            logger.info(f"تم اختيار {max_slices} شريحة من {len(dcm_files)}")

        # تجميع الحجم ثلاثي الأبعاد
        volume = np.stack([s[0] for s in slices_data], axis=0)
        metadata_list = [s[1] for s in slices_data]

        logger.info(f"تم تحميل الحجم ثلاثي الأبعاد: {volume.shape}")
        return volume, metadata_list

    def apply_windowing(
        self,
        pixel_array: np.ndarray,
        window: Optional[str] = None,
        center: Optional[float] = None,
        width: Optional[float] = None,
    ) -> np.ndarray:
        """
        تطبيق Windowing الطبي على مصفوفة البيكسلات

        Windowing يحول قيم HU (Hounsfield Units) إلى نطاق عرض مرئي مناسب
        لكل نسيج (رئة، عظام، منصف، دماغ، إلخ)

        Args:
            pixel_array: مصفوفة البيكسلات الخام (HU values)
            window: اسم النافذة المسبقة الإعداد (lung, bone, brain, ...)
            center: مركز النافذة المخصص
            width: عرض النافذة المخصص

        Returns:
            مصفوفة بيكسلات بعد تطبيق Windowing [0, 255]
        """
        if window:
            if window not in self.windows:
                available = ", ".join(self.windows.keys())
                logger.warning(f"نافذة '{window}' غير موجودة. المتاحة: {available}. استخدام الافتراضية.")
                window = self.default_window
            center = self.windows[window]["center"]
            width = self.windows[window]["width"]
        elif center is None or width is None:
            center = self.windows[self.default_window]["center"]
            width = self.windows[self.default_window]["width"]

        # حساب الحدود الدنيا والعليا
        lower = center - (width / 2)
        upper = center + (width / 2)

        # تطبيق Windowing
        windowed = np.clip(pixel_array, lower, upper)

        # تحويل إلى نطاق [0, 255]
        if width > 0:
            windowed = ((windowed - lower) / width) * 255.0
        else:
            windowed = np.zeros_like(pixel_array)

        return np.clip(windowed, 0, 255).astype(np.uint8)

    def apply_multi_window(
        self,
        pixel_array: np.ndarray,
        windows: List[str],
    ) -> Dict[str, np.ndarray]:
        """
        تطبيق نوافذ Windowing متعددة للحصول على صور مختلفة لنفس الشريحة

        مفيد لفحوصات الصدر حيث تحتاج لرؤية الرئة والعظام والمنصف معاً

        Args:
            pixel_array: مصفوفة البيكسلات الخام
            windows: قائمة بأسماء النوافذ المطلوبة

        Returns:
            قاموس {اسم_النافذة: مصفوفة_بيكسلات}
        """
        result = {}
        for win_name in windows:
            if win_name in self.windows:
                result[win_name] = self.apply_windowing(pixel_array, window=win_name)
                logger.debug(f"تم تطبيق نافذة '{win_name}' على الصورة")
        return result

    def dicom_to_jpg(
        self,
        filepath: Union[str, Path],
        output_path: Optional[Union[str, Path]] = None,
        window: Optional[str] = None,
        quality: int = 95,
    ) -> np.ndarray:
        """
        تحويل ملف DICOM مباشرة إلى صورة JPG

        Args:
            filepath: مسار ملف DICOM
            output_path: مسار الإخراج (لا شيء = لا حفظ)
            window: نافذة Windowing
            quality: جودة JPEG (1-100)

        Returns:
            مصفوفة الصورة [H, W, 3] بصيغة uint8
        """
        pixel_array, metadata = self.load_dicom(filepath)
        windowed = self.apply_windowing(pixel_array, window=window)

        # تحويل إلى RGB (3 قنوات)
        if windowed.ndim == 2:
            rgb = np.stack([windowed] * 3, axis=-1)
        else:
            rgb = windowed

        # الحفظ إن طُلب
        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                from PIL import Image
                Image.fromarray(rgb).save(str(output_path), quality=quality)
                logger.info(f"تم حفظ JPG: {output_path}")
            except ImportError:
                import cv2
                cv2.imwrite(str(output_path), cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR), [int(cv2.IMWRITE_JPEG_QUALITY), quality])
                logger.info(f"تم حفظ JPG (OpenCV): {output_path}")

        return rgb

    def batch_process(
        self,
        input_dir: Union[str, Path],
        output_dir: Union[str, Path],
        modality_filter: Optional[str] = None,
        window: Optional[str] = None,
        format: str = "npy",
    ) -> Dict[str, Any]:
        """
        معالجة مجموعة ملفات DICOM بشكل جماعي

        Args:
            input_dir: مجلد الإدخال
            output_dir: مجلد الإخراج
            modality_filter: تصفية حسب نوع الفحص (CT, MR, XR, ...)
            window: نافذة Windowing
            format: صيغة الإخراج (npy, jpg, png, npz)

        Returns:
            قاموس بإحصائيات المعالجة
        """
        input_dir = Path(input_dir)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # جمع ملفات DICOM
        dcm_files = self._find_dicom_files(input_dir)
        logger.info(f"بدء المعالجة الجماعية: {len(dcm_files)} ملف DICOM")

        stats = {
            "total": len(dcm_files),
            "success": 0,
            "failed": 0,
            "skipped": 0,
            "modalities": {},
            "errors": [],
        }

        for f in dcm_files:
            try:
                arr, meta = self.load_dicom(f)

                # تصفية حسب نوع الفحص
                if modality_filter:
                    modality = meta.get("modality", "")
                    if modality_filter.upper() not in modality.upper():
                        stats["skipped"] += 1
                        continue

                stats["modalities"][meta.get("modality", "UNKNOWN")] = \
                    stats["modalities"].get(meta.get("modality", "UNKNOWN"), 0) + 1

                # التطبيق
                if format == "jpg" or format == "png":
                    windowed = self.apply_windowing(arr, window=window)
                    if windowed.ndim == 2:
                        windowed = np.stack([windowed] * 3, axis=-1)
                    out_path = output_dir / f"{f.stem}.{format}"
                    try:
                        from PIL import Image
                        Image.fromarray(windowed).save(str(out_path))
                    except ImportError:
                        import cv2
                        ext = format if format != "jpg" else "jpeg"
                        cv2.imwrite(str(out_path), cv2.cvtColor(windowed, cv2.COLOR_RGB2BGR), [int(cv2.IMWRITE_JPEG_QUALITY), 95] if format == "jpg" else [])
                else:
                    out_path = output_dir / f"{f.stem}.npy"
                    np.save(str(out_path), arr)

                stats["success"] += 1

            except Exception as e:
                stats["failed"] += 1
                stats["errors"].append({"file": str(f), "error": str(e)})
                logger.error(f"فشل معالجة {f.name}: {e}")

        logger.info(
            f"انتهت المعالجة الجماعية: نجح={stats['success']}, "
            f"فشل={stats['failed']}, تم تخطي={stats['skipped']}"
        )
        return stats

    # ===== دوال مساعدة داخلية =====

    def _extract_metadata(self, ds: Any) -> Dict[str, Any]:
        """استخراج البيانات الوصفية المهمة من كائن DICOM Dataset"""
        meta = {}

        # معلومات المريض
        meta["patient_id"] = self._safe_get(ds, "PatientID", "")
        meta["patient_name"] = self._safe_get(ds, "PatientName", "")
        meta["patient_age"] = self._safe_get(ds, "PatientAge", "")
        meta["patient_sex"] = self._safe_get(ds, "PatientSex", "")

        # معلومات الفحص
        meta["modality"] = self._safe_get(ds, "Modality", "")
        meta["study_description"] = self._safe_get(ds, "StudyDescription", "")
        meta["series_description"] = self._safe_get(ds, "SeriesDescription", "")
        meta["study_date"] = self._safe_get(ds, "StudyDate", "")
        meta["study_time"] = self._safe_get(ds, "StudyTime", "")
        meta["accession_number"] = self._safe_get(ds, "AccessionNumber", "")
        meta["institution"] = self._safe_get(ds, "InstitutionName", "")

        # معلومات الصورة
        meta["rows"] = self._safe_get(ds, "Rows", 0)
        meta["columns"] = self._safe_get(ds, "Columns", 0)
        meta["bits_allocated"] = self._safe_get(ds, "BitsAllocated", 16)
        meta["bits_stored"] = self._safe_get(ds, "BitsStored", 16)
        meta["pixel_spacing"] = self._safe_get(ds, "PixelSpacing", [0.0, 0.0])
        meta["slice_thickness"] = self._safe_get(ds, "SliceThickness", 0.0)
        meta["instance_number"] = self._safe_get(ds, "InstanceNumber", 0)

        # معلمات CT
        meta["rescale_slope"] = self._safe_get(ds, "RescaleSlope", 1.0)
        meta["rescale_intercept"] = self._safe_get(ds, "RescaleIntercept", 0.0)
        meta["window_center"] = self._safe_get(ds, "WindowCenter", 0)
        meta["window_width"] = self._safe_get(ds, "WindowWidth", 0)
        meta["convolution_kernel"] = self._safe_get(ds, "ConvolutionKernel", "")

        # معلومات الجهاز
        meta["manufacturer"] = self._safe_get(ds, "Manufacturer", "")
        meta["model"] = self._safe_get(ds, "ManufacturerModelName", "")

        # تنظيف القيم
        meta = {k: str(v) if not isinstance(v, (int, float, list)) else v for k, v in meta.items()}

        return meta

    def _safe_get(self, ds: Any, attr: str, default: Any = None) -> Any:
        """استخراج قيمة آمنة من كائن DICOM"""
        try:
            val = getattr(ds, attr, default)
            if val is None:
                return default
            if hasattr(val, "value"):
                return val.value
            return val
        except Exception:
            return default

    def _handle_signed_pixels(self, arr: np.ndarray, ds: Any) -> np.ndarray:
        """معالجة البيكسلات الموقعة"""
        if hasattr(ds, "PixelRepresentation"):
            if ds.PixelRepresentation == 1 and arr.min() < 0:
                bits = self._safe_get(ds, "BitsAllocated", 16)
                arr = arr + (2 ** (bits - 1))
        return arr

    def _resize_array(self, arr: np.ndarray) -> np.ndarray:
        """تغيير حجم المصفوفة إلى الحجم المستهدف"""
        if arr.shape[0] == self.target_size[0] and arr.shape[1] == self.target_size[1]:
            return arr

        try:
            import cv2
            if arr.ndim == 2:
                return cv2.resize(arr, (self.target_size[1], self.target_size[0]),
                                  interpolation=cv2.INTER_LINEAR)
            else:
                resized = np.zeros((arr.shape[0], self.target_size[0], self.target_size[1]))
                for i in range(arr.shape[0]):
                    resized[i] = cv2.resize(arr[i], (self.target_size[1], self.target_size[0]),
                                            interpolation=cv2.INTER_LINEAR)
                return resized
        except ImportError:
            from PIL import Image
            if arr.ndim == 2:
                img = Image.fromarray(arr.astype(np.float32))
                return np.array(img.resize((self.target_size[1], self.target_size[0]), Image.BILINEAR))
            return arr

    def _normalize_array(self, arr: np.ndarray) -> np.ndarray:
        """تطبيع المصفوفة إلى النطاق المحدد"""
        min_val, max_val = self.normalize_range
        arr_min, arr_max = arr.min(), arr.max()
        if arr_max - arr_min > 0:
            arr = (arr - arr_min) / (arr_max - arr_min)
            arr = arr * (max_val - min_val) + min_val
        return arr.astype(np.float32)

    def _sort_slices(
        self,
        slices: List[Tuple[np.ndarray, Dict, str]],
        sort_by: str,
    ) -> List[Tuple[np.ndarray, Dict, str]]:
        """ترتيب الشرائح حسب معيار محدد"""
        if sort_by == "instance_number":
            return sorted(slices, key=lambda x: int(x[1].get("instance_number", 0)))
        elif sort_by == "slice_location":
            return sorted(slices, key=lambda x: float(x[1].get("slice_thickness", 0)))
        return slices

    def _find_dicom_files(self, directory: Path) -> List[Path]:
        """البحث عن ملفات DICOM في المجلد والملفات الفرعية"""
        files = []
        for f in directory.rglob("*"):
            if f.is_file():
                if f.suffix.lower() == ".dcm" or self._is_dicom_file(f):
                    files.append(f)
        return sorted(files)

    @staticmethod
    def _is_dicom_file(filepath: Path) -> bool:
        """التحقق مما إذا كان الملف بصيغة DICOM (حتى بدون لاحقة)"""
        try:
            with open(filepath, "rb") as f:
                return f.read(132).endswith(b"DICM")
        except Exception:
            return False
