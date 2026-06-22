"""
خط أنابيب القواميس الموحد — OmniMedical Suite

ينسق عمليات استيراد القواميس من مصادر متعددة (BGL, StarDict, TMX, JSON, CSV)
ويدير التكامل مع قاعدة بيانات المشروع ومحرك NLP.

الاستخدام:
    from packages.medical.dictionary_pipeline import DictionaryPipeline

    pipeline = DictionaryPipeline(db_path="data/dictionaries/medical_terms.db")
    result = pipeline.import_bgl("medical.bgl")
    result = pipeline.import_tmx("terms.tmx")
    results = pipeline.search("fracture")
"""

import os
import shutil
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class DictionaryPipeline:
    """
    خط أنابيب القواميس الموحد.
    
    يوفر واجهة واحدة لاستيراد وبحث وتصدير القواميس من مصادر متعددة:
    - ملفات Babylon (.bgl) → عبر BGL Converter
    - قواميس StarDict (.ifo/.idx/.dict) → عبر StarDict Reader
    - ملفات TMX (.tmx) → عبر TMX Processor
    - ملفات JSON و CSV → عبر Dictionary Manager
    
    يدمج جميع المصادر في قاعدة بيانات موحدة مع فهرسة كاملة.
    """

    DEFAULT_DB_PATH = "data/dictionaries/medical_terms.db"
    DEFAULT_DATA_DIR = "data/dictionaries"

    def __init__(self, db_path: Optional[str] = None, data_dir: Optional[str] = None):
        self.db_path = db_path or self.DEFAULT_DB_PATH
        self.data_dir = data_dir or self.DEFAULT_DATA_DIR
        self._manager = None
        self._tmx_processor = None

        # إنشاء المجلدات
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(os.path.join(self.data_dir, "bgl_source"), exist_ok=True)
        os.makedirs(os.path.join(self.data_dir, "stardict"), exist_ok=True)
        os.makedirs(os.path.join(self.data_dir, "tmx"), exist_ok=True)

    def _get_manager(self):
        """الحصول على DictionaryManager (lazy loading)"""
        if self._manager is None:
            from packages.medical.dictionary_manager import MedicalDictionaryManager
            self._manager = MedicalDictionaryManager(db_path=self.db_path)
        return self._manager

    def _get_tmx_processor(self, tmx_file: Optional[str] = None):
        """الحصول على TMXProcessor"""
        db_path = os.path.join(self.data_dir, "tmx", f"{Path(tmx_file).stem}_review.db") if tmx_file else None
        return tmx_file, __import__("packages.medical.tmx_processor", fromlist=["TMXProcessor"]).TMXProcessor(db_path=db_path)

    # ============ استيراد BGL ============

    def import_bgl(self, file_path: str, title: Optional[str] = None,
                   source_lang: str = "ar", target_lang: str = "en",
                   category: Optional[str] = None) -> Dict[str, Any]:
        """
        استيراد قاموس Babylon (.bgl).
        
        يستخدم BGLConverter لفك الضغط واستخراج المداخل،
        ثم يحفظها في قاعدة البيانات عبر DictionaryManager.
        """
        logger.info(f"استيراد BGL: {file_path}")
        manager = self._get_manager()
        result = manager.import_dictionary(
            file_path=file_path,
            title=title,
            source_lang=source_lang,
            target_lang=target_lang,
            category=category,
        )
        return result.to_dict()

    def convert_bgl_to_stardict(self, bgl_path: str,
                                output_dir: Optional[str] = None) -> Dict[str, Any]:
        """
        تحويل ملف BGL إلى صيغة StarDict باستخدام PyGlossary (إن توفر).
        
        يحاول أولاً استخدام PyGlossary، وإذا لم يكن متاحاً يستخدم المحول الداخلي.
        """
        output_dir = output_dir or os.path.join(self.data_dir, "stardict")
        os.makedirs(output_dir, exist_ok=True)

        stem = Path(bgl_path).stem
        target_path = os.path.join(output_dir, stem)

        # محاولة استخدام PyGlossary
        try:
            from pyglossary import Glossary
            logger.info(f"تحويل BGL → StarDict عبر PyGlossary: {bgl_path}")
            Glossary.init()
            glos = Glossary()
            glos.read(bgl_path, direct=True)
            # PyGlossary يستخدم .ifo كامتداد للإخراج
            glos.write(f"{target_path}.ifo", format="Stardict")
            return {
                "success": True,
                "method": "pyglossary",
                "output_dir": output_dir,
                "files": [
                    f"{target_path}.ifo",
                    f"{target_path}.idx",
                    f"{target_path}.dict",
                ],
            }
        except ImportError:
            logger.info("PyGlossary غير متاح، استخدام المحول الداخلي")
        except Exception as e:
            logger.warning(f"فشل PyGlossary: {e}")

        # الرجوع للمحول الداخلي: BGL → JSON
        try:
            from packages.medical.bgl_converter import BGLConverter
            converter = BGLConverter()
            converter.convert(bgl_path, output_format="json",
                             output_path=f"{target_path}.json", output_dir=output_dir)
            return {
                "success": True,
                "method": "internal_bgl_converter",
                "output_dir": output_dir,
                "files": [f"{target_path}.json"],
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ============ استيراد StarDict ============

    def import_stardict(self, stardict_dir: str, title: Optional[str] = None,
                        source_lang: str = "ar", target_lang: str = "en",
                        category: Optional[str] = None) -> Dict[str, Any]:
        """
        استيراد قاموس StarDict (.ifo/.idx/.dict).
        """
        logger.info(f"استيراد StarDict من: {stardict_dir}")

        try:
            from packages.medical.stardict_reader import StarDictReader
            reader = StarDictReader(stardict_dir)
            reader.read_ifo()
            reader.read_idx()

            # تحويل المداخل وتخزينها مؤقتاً كـ JSON
            json_path = os.path.join(self.data_dir, "stardict",
                                    f"{Path(stardict_dir).stem}_temp.json")
            reader.export_to_json(json_path)

            # استيراد عبر DictionaryManager
            manager = self._get_manager()
            result = manager.import_dictionary(
                file_path=json_path,
                title=title or reader.metadata.bookname,
                source_lang=source_lang or reader.metadata.source_lang,
                target_lang=target_lang or reader.metadata.target_lang,
                category=category,
            )

            # تنظيف الملف المؤقت
            if os.path.exists(json_path):
                os.remove(json_path)

            stats = reader.get_statistics()
            return {
                "success": result.success,
                "total_entries": result.total_entries,
                "dict_stats": stats,
                "errors": result.errors,
            }

        except Exception as e:
            logger.error(f"فشل استيراد StarDict: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    # ============ استيراد TMX ============

    def import_tmx(self, file_path: str, auto_detect_medical: bool = True,
                   confidence_threshold: float = 0.0,
                   auto_approve_threshold: float = 0.9) -> Dict[str, Any]:
        """
        استيراد ملف TMX واستخراج المصطلحات الطبية.
        
        المعاملات:
            file_path: مسار ملف TMX
            auto_detect_medical: كشف المصطلحات الطبية تلقائياً
            confidence_threshold: الحد الأدنى للثقة
            auto_approve_threshold: اعتماد تلقائي فوق هذا الحد
            
        العائد:
            نتيجة الاستيراد مع إحصائيات
        """
        logger.info(f"استيراد TMX: {file_path}")

        tmx_file, processor = self._get_tmx_processor(file_path)
        if not os.path.exists(file_path):
            return {"success": False, "error": f"الملف غير موجود: {file_path}"}

        # استيراد وتحليل TMX
        result = processor.import_tmx(
            file_path, auto_detect_medical, confidence_threshold
        )

        if not result.success:
            return result.__dict__

        # استخراج المصطلحات الطبية المُعتمدة إلى قاعدة البيانات الرئيسية
        exported = 0
        if auto_detect_medical and result.medical_terms > 0:
            medical_export_path = os.path.join(
                self.data_dir, "tmx",
                f"{Path(file_path).stem}_medical.json"
            )
            if processor.export_medical_terms(medical_export_path):
                # استيراد المصطلحات الطبية إلى قاعدة البيانات الرئيسية
                manager = self._get_manager()
                imp_result = manager.import_dictionary(
                    file_path=medical_export_path,
                    title=f"TMX Medical: {Path(file_path).stem}",
                    source_lang="en",
                    target_lang="ar",
                    category="tmx_extracted",
                    import_corrections=False,
                )
                exported = imp_result.total_entries

                # الاعتماد التلقائي للمصطلحات عالية الثقة
                if auto_approve_threshold > 0:
                    approved = processor.batch_update(
                        processor._entries, status="auto_approved"
                    )
                    logger.info(f"اعتماد تلقائي: {approved} مدخلة")

        processor.close()

        return {
            "success": True,
            "total_tus": result.total_tus,
            "medical_terms_detected": result.medical_terms,
            "medical_terms_imported": exported,
            "duration_seconds": result.duration_seconds,
            "errors": result.errors,
        }

    def review_tmx(self, file_path: str):
        """الحصول على معالج TMX للمراجعة التفاعلية"""
        _, processor = self._get_tmx_processor(file_path)
        return processor

    # ============ بحث موحد ============

    def search(self, query: str, language: Optional[str] = None,
               category: Optional[str] = None, limit: int = 50,
               exact: bool = False) -> List[Dict[str, Any]]:
        """بحث موحد في جميع القواميس"""
        manager = self._get_manager()
        results = manager.search(query, language=language, category=category,
                                limit=limit, exact=exact)
        return [r.to_dict() for r in results]

    def search_by_prefix(self, prefix: str, language: str = "ar",
                         limit: int = 20) -> List[Dict[str, Any]]:
        """بحث بالبادئة"""
        manager = self._get_manager()
        results = manager.search_by_prefix(prefix, language=language, limit=limit)
        return [r.to_dict() for r in results]

    # ============ إحصائيات ============

    def get_stats(self) -> Dict[str, Any]:
        """إحصائيات شاملة لجميع القواميس"""
        manager = self._get_manager()
        return manager.get_dictionary_stats()

    def get_categories(self) -> List[Dict[str, Any]]:
        """التصنيفات المتاحة"""
        manager = self._get_manager()
        return manager.get_categories()

    def list_dictionaries(self) -> List[Dict[str, Any]]:
        """قائمة القواميس المستوردة"""
        manager = self._get_manager()
        dicts = manager.list_dictionaries()
        return [d.to_dict() for d in dicts]

    # ============ تصدير ============

    def export_all(self, output_dir: Optional[str] = None,
                   formats: List[str] = None) -> Dict[str, Any]:
        """
        تصدير جميع القواميس إلى صيغ متعددة.
        
        المعاملات:
            output_dir: مجلد الإخراج
            formats: صيغ التصدير (json, csv, omni)
        """
        output_dir = output_dir or os.path.join(self.data_dir, "export")
        formats = formats or ["json", "csv"]
        os.makedirs(output_dir, exist_ok=True)

        manager = self._get_manager()
        exported = {}

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if "json" in formats:
            path = os.path.join(output_dir, f"medical_dict_{timestamp}.json")
            exported["json"] = manager.export_to_json(path)
        if "csv" in formats:
            path = os.path.join(output_dir, f"medical_dict_{timestamp}.csv")
            exported["csv"] = manager.export_to_csv(path)
        if "omni" in formats:
            path = os.path.join(output_dir, f"medical_dict_omni_{timestamp}.json")
            exported["omni"] = manager.export_to_omni_format(path)

        return {"output_dir": output_dir, "formats": exported}

    # ============ تحقق وتكامل ============

    def validate_integrity(self) -> Dict[str, Any]:
        """التحقق من سلامة قاعدة البيانات"""
        manager = self._get_manager()
        stats = manager.get_dictionary_stats()

        issues = []
        warnings = []

        # فحص حجم قاعدة البيانات
        if stats["database_size_bytes"] == 0:
            issues.append("قاعدة البيانات فارغة")
        if stats["total_terms"] == 0:
            warnings.append("لا توجد مصطلحات مستوردة")

        # فحص التوازن اللغوي
        if stats["arabic_terms"] > 0 and stats["english_terms"] == 0:
            warnings.append("توجد مصطلحات عربية فقط بدون إنجليزية مقابلة")
        if stats["english_terms"] > 0 and stats["arabic_terms"] == 0:
            warnings.append("توجد مصطلحات إنجليزية فقط بدون عربية مقابلة")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "stats": stats,
        }

    def sync_with_nlp_pipeline(self) -> Dict[str, Any]:
        """
        مزامنة القاموس مع خط أنابيب NLP.
        يُحدّث ملفات JSON المستخدمة في SpellCorrector و ProtectedWordsManager.
        """
        manager = self._get_manager()

        # تصدير التصحيحات لـ NLP
        corrections = manager.get_correction_dict_for_pipeline()
        corrections_path = os.path.join(self.data_dir, "nlp_corrections.json")
        import json
        with open(corrections_path, "w", encoding="utf-8") as f:
            json.dump(corrections, f, ensure_ascii=False, indent=2)

        # تصدير المصطلحات المحمية
        protected = manager.get_protected_terms_for_pipeline()
        protected_path = os.path.join(self.data_dir, "nlp_protected.json")
        with open(protected_path, "w", encoding="utf-8") as f:
            json.dump(protected, f, ensure_ascii=False, indent=2)

        # تصدير مجموعة المصطلحات الطبية
        medical_terms_en = manager.get_medical_terms_set("en")
        medical_terms_ar = manager.get_medical_terms_set("ar")
        medical_path = os.path.join(self.data_dir, "nlp_medical_terms.json")
        with open(medical_path, "w", encoding="utf-8") as f:
            json.dump({
                "en": list(medical_terms_en),
                "ar": list(medical_terms_ar),
            }, f, ensure_ascii=False, indent=2)

        return {
            "success": True,
            "corrections_count": len(corrections),
            "protected_count": len(protected),
            "medical_en_count": len(medical_terms_en),
            "medical_ar_count": len(medical_terms_ar),
            "files": [corrections_path, protected_path, medical_path],
        }

    # ============ استيراد دفعي ============

    def batch_import(self, directory: str, pattern: str = "*",
                     file_type: str = "auto") -> List[Dict[str, Any]]:
        """
        استيراد مجموعة ملفات دفعة واحدة.
        
        المعاملات:
            directory: مجلد الملفات
            pattern: نمط أسماء الملفات (مثل "*.bgl")
            file_type: نوع الملفات (auto, bgl, stardict, tmx, json)
        """
        dir_path = Path(directory)
        results = []

        ext_map = {
            ".bgl": "bgl",
            ".tmx": "tmx",
            ".json": "json",
            ".csv": "csv",
        }

        files = list(dir_path.glob(pattern))
        if not files:
            files = list(dir_path.iterdir())

        for filepath in sorted(files):
            if not filepath.is_file():
                continue

            ext = filepath.suffix.lower()
            detected_type = ext_map.get(ext, "unknown")

            if file_type != "auto" and detected_type != file_type:
                continue

            try:
                if detected_type == "bgl":
                    result = self.import_bgl(str(filepath))
                elif detected_type == "tmx":
                    result = self.import_tmx(str(filepath))
                elif detected_type == "json":
                    result = self._get_manager().import_dictionary(str(filepath))
                elif detected_type == "csv":
                    result = self._get_manager().import_dictionary(str(filepath))
                else:
                    result = {"success": False, "error": f"صيغة غير مدعومة: {ext}"}

                result["source_file"] = str(filepath)
                results.append(result)
                logger.info(f"استيراد {filepath.name}: {'نجح' if result.get('success') else 'فشل'}")

            except Exception as e:
                results.append({
                    "source_file": str(filepath),
                    "success": False,
                    "error": str(e),
                })
                logger.error(f"فشل استيراد {filepath}: {e}")

        success_count = sum(1 for r in results if r.get("success"))
        logger.info(f"استيراد دفعي: {success_count}/{len(results)} نجح")
        return results
