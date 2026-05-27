"""
واجهة برمجة تطبيقات القواميس الطبية — OmniMedical Suite

نقاط نهاية REST API لإدارة القواميس الطبية:
- استيراد القواميس من ملفات BGL/DIC/JSON/CSV
- البحث في القواميس
- إدارة تصحيحات OCR
- تصدير القواميس
- إحصائيات

المسارات:
    POST   /api/dictionaries/import         — استيراد قاموس
    GET    /api/dictionaries                 — قائمة القواميس
    GET    /api/dictionaries/stats          — إحصائيات عامة
    GET    /api/dictionaries/{id}           — تفاصيل قاموس
    DELETE /api/dictionaries/{id}           — إزالة قاموس
    
    GET    /api/dictionaries/search         — بحث في القاموس
    GET    /api/dictionaries/categories     — التصنيفات
    GET    /api/dictionaries/prefix/{lang}  — بحث بالبادئة
    
    GET    /api/dictionaries/corrections    — تصحيحات OCR
    POST   /api/dictionaries/corrections    — إضافة تصحيح
    
    GET    /api/dictionaries/protected      — المصطلحات المحمية
    
    GET    /api/dictionaries/export/{format} — تصدير القاموس
"""

import os
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Query, Depends
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dictionaries", tags=["dictionaries"])

# === مسار قاعدة بيانات القواميس ===
DEFAULT_DB_PATH = os.environ.get(
    "MEDICAL_DICT_DB_PATH",
    "data/dictionaries/medical_terms.db"
)

# === تهيئة المدير (lazy loading) ===
_manager = None


def get_manager():
    """الحصول على نسخة واحدة من المدير (Singleton)"""
    global _manager
    if _manager is None:
        from packages.medical.dictionary_manager import MedicalDictionaryManager
        _manager = MedicalDictionaryManager(db_path=DEFAULT_DB_PATH)
    return _manager


# ============ نماذج Pydantic ============

class ImportRequest(BaseModel):
    """نموذج طلب استيراد قاموس"""
    file_path: Optional[str] = None
    title: Optional[str] = None
    source_lang: str = "ar"
    target_lang: str = "en"
    category: Optional[str] = None
    import_corrections: bool = True
    import_protected: bool = True
    dict_name: Optional[str] = None


class CorrectionRequest(BaseModel):
    """نموذج طلب إضافة تصحيح"""
    wrong_term: str = Field(..., min_length=1, description="المصطلح الخاطئ")
    correct_term: str = Field(..., min_length=1, description="المصطلح الصحيح")
    language: str = Field(default="ar", description="اللغة (ar/en)")
    confidence: float = Field(default=0.9, ge=0.0, le=1.0, description="مستوى الثقة")


class SearchParams(BaseModel):
    """معاملات البحث"""
    query: str = Field(..., min_length=1)
    language: Optional[str] = None
    category: Optional[str] = None
    limit: int = Field(default=50, ge=1, le=500)
    exact: bool = False
    dict_id: Optional[int] = None


# ============ نقاط النهاية ============

@router.post("/import")
async def import_dictionary(
    file: Optional[UploadFile] = File(None),
    title: Optional[str] = Query(None),
    source_lang: str = Query("ar"),
    target_lang: str = Query("en"),
    category: Optional[str] = Query(None),
    import_corrections: bool = Query(True),
    import_protected: bool = Query(True),
    dict_name: Optional[str] = Query(None),
    file_path: Optional[str] = Query(None, description="مسار ملف محلي (للخوادم)"),
):
    """
    استيراد قاموس طبي من ملف.
    
    يدعم صيغ: BGL, DIC, JSON, CSV
    
    يمكن الرفع مباشرة عبر multipart/form-data أو تحديد مسار ملف محلي.
    """
    manager = get_manager()

    # تحديد مصدر الملف
    temp_file = None

    if file is not None:
        # حفظ الملف المرفوع مؤقتاً
        upload_dir = "services/api/uploads/dictionaries"
        os.makedirs(upload_dir, exist_ok=True)
        temp_file = os.path.join(upload_dir, file.filename or "uploaded_dict")
        
        with open(temp_file, "wb") as f:
            content = await file.read()
            f.write(content)

        import_path = temp_file
        effective_title = title or file.filename or "Imported Dictionary"
    elif file_path:
        import_path = file_path
        effective_title = title or os.path.basename(file_path)
    else:
        raise HTTPException(
            status_code=400,
            detail="يجب توفير ملف مرفوع أو مسار ملف محلي"
        )

    try:
        result = manager.import_dictionary(
            file_path=import_path,
            title=effective_title,
            source_lang=source_lang,
            target_lang=target_lang,
            category=category,
            import_corrections=import_corrections,
            import_protected=import_protected,
            dict_name=dict_name,
        )

        if not result.success:
            raise HTTPException(
                status_code=400,
                detail=f"فشل الاستيراد: {'; '.join(result.errors)}"
            )

        return JSONResponse(content={
            "success": True,
            "message": f"تم استيراد القاموس بنجاح: {result.title}",
            "data": result.to_dict(),
        })

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"خطأ في الاستيراد: {str(e)}")
    finally:
        # تنظيف الملف المؤقت
        if temp_file and os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except Exception:
                pass


@router.get("")
async def list_dictionaries():
    """قائمة جميع القواميس المستوردة"""
    manager = get_manager()
    try:
        dicts = manager.list_dictionaries()
        return {
            "success": True,
            "data": [d.to_dict() for d in dicts],
            "total": len(dicts),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_statistics():
    """إحصائيات عامة عن القواميس"""
    manager = get_manager()
    try:
        stats = manager.get_dictionary_stats()
        return {
            "success": True,
            "data": stats,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{dict_id}")
async def get_dictionary(dict_id: int):
    """تفاصيل قاموس محدد"""
    manager = get_manager()
    try:
        dicts = manager.list_dictionaries()
        for d in dicts:
            if d.id == dict_id:
                return {"success": True, "data": d.to_dict()}
        raise HTTPException(status_code=404, detail="القاموس غير موجود")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{dict_id}")
async def delete_dictionary(dict_id: int, remove_entries: bool = True):
    """إزالة قاموس"""
    manager = get_manager()
    try:
        success = manager.remove_dictionary(dict_id, remove_entries=remove_entries)
        if not success:
            raise HTTPException(status_code=404, detail="فشل إزالة القاموس")
        return {
            "success": True,
            "message": f"تم إزالة القاموس {dict_id} بنجاح",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search")
async def search_dictionary(
    q: str = Query(..., min_length=1, description="نص البحث"),
    language: Optional[str] = Query(None, description="لغة البحث (ar/en)"),
    category: Optional[str] = Query(None, description="التصنيف"),
    limit: int = Query(50, ge=1, le=500),
    exact: bool = Query(False),
    dict_id: Optional[int] = Query(None),
):
    """بحث في القاموس الطبي"""
    manager = get_manager()
    try:
        results = manager.search(
            query=q,
            language=language,
            category=category,
            limit=limit,
            exact=exact,
            dict_id=dict_id,
        )
        return {
            "success": True,
            "data": [r.to_dict() for r in results],
            "total": len(results),
            "query": q,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/categories")
async def get_categories():
    """قائمة التصنيفات مع عدد المصطلحات"""
    manager = get_manager()
    try:
        categories = manager.get_categories()
        return {
            "success": True,
            "data": categories,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/prefix/{language}")
async def search_by_prefix(
    language: str,
    prefix: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=100),
):
    """بحث بالمصطلحات التي تبدأ ببادئة معينة"""
    manager = get_manager()
    try:
        results = manager.search_by_prefix(prefix, language=language, limit=limit)
        return {
            "success": True,
            "data": [r.to_dict() for r in results],
            "total": len(results),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/corrections")
async def get_corrections(language: Optional[str] = Query(None)):
    """الحصول على تصحيحات OCR"""
    manager = get_manager()
    try:
        corrections = manager.get_ocr_corrections(language=language)
        return {
            "success": True,
            "data": corrections,
            "total": len(corrections),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/corrections")
async def add_correction(request: CorrectionRequest):
    """إضافة تصحيح OCR جديد"""
    manager = get_manager()
    try:
        success = manager.add_correction(
            wrong=request.wrong_term,
            correct=request.correct_term,
            language=request.language,
            confidence=request.confidence,
        )
        if not success:
            raise HTTPException(status_code=400, detail="فشل إضافة التصحيح")
        return {
            "success": True,
            "message": "تم إضافة التصحيح بنجاح",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/corrections/lookup/{term}")
async def lookup_correction(term: str):
    """البحث عن تصحيح لمصطلح"""
    manager = get_manager()
    try:
        correction = manager.lookup_correction(term)
        if correction:
            return {
                "success": True,
                "data": {"term": term, "correction": correction},
            }
        return {
            "success": True,
            "data": None,
            "message": "لم يتم العثور على تصحيح",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/protected")
async def get_protected_terms(language: Optional[str] = Query(None)):
    """الحصول على المصطلحات المحمية"""
    manager = get_manager()
    try:
        terms = manager.get_protected_terms(language=language)
        return {
            "success": True,
            "data": terms,
            "total": len(terms),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pipeline/corrections")
async def get_pipeline_corrections():
    """
    تصحيحات بصيغة مناسبة لخط أنابيب OCR/NLP.
    يُستخدم من SpellCorrector و MedicalOCR.
    """
    manager = get_manager()
    try:
        corrections = manager.get_correction_dict_for_pipeline()
        return {
            "success": True,
            "data": corrections,
            "format": "dict",
            "total": len(corrections),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pipeline/protected")
async def get_pipeline_protected():
    """
    مصطلحات محمية بصيغة مناسبة لخط أنابيب NLP.
    يُستخدم من ProtectedWordsManager.
    """
    manager = get_manager()
    try:
        terms = manager.get_protected_terms_for_pipeline()
        return {
            "success": True,
            "data": terms,
            "format": "list",
            "total": len(terms),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/export/json")
async def export_json(
    dict_id: Optional[int] = Query(None),
    filename: str = Query("medical_dictionary_export.json"),
):
    """تصدير القاموس إلى JSON"""
    manager = get_manager()
    output_path = os.path.join("data/dictionaries", filename)

    try:
        success = manager.export_to_json(output_path, dict_id=dict_id)
        if not success:
            raise HTTPException(status_code=500, detail="فشل التصدير")
        return FileResponse(
            path=output_path,
            media_type="application/json",
            filename=filename,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/export/csv")
async def export_csv(
    dict_id: Optional[int] = Query(None),
    filename: str = Query("medical_dictionary_export.csv"),
):
    """تصدير القاموس إلى CSV"""
    manager = get_manager()
    output_path = os.path.join("data/dictionaries", filename)

    try:
        success = manager.export_to_csv(output_path, dict_id=dict_id)
        if not success:
            raise HTTPException(status_code=500, detail="فشل التصدير")
        return FileResponse(
            path=output_path,
            media_type="text/csv",
            filename=filename,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/export/omni")
async def export_omni_format(
    filename: str = Query("medical_dictionary_omni.json"),
):
    """تصدير القاموس بتنسيق OmniMedical (متوافق مع medical_dictionary.json)"""
    manager = get_manager()
    output_path = os.path.join("data/dictionaries", filename)

    try:
        success = manager.export_to_omni_format(output_path)
        if not success:
            raise HTTPException(status_code=500, detail="فشل التصدير")
        return FileResponse(
            path=output_path,
            media_type="application/json",
            filename=filename,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
