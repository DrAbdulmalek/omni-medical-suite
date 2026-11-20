"""اختبارات omni_preprocess — تعمل في أي CI:
  - unit: mock كامل (بلا خادم، بلا httpx حتى)
  - integration: تُتخطى تلقائيًا بلا خادم Stirling حي أو fixture

تصحيح تدقيق: النسخة الأصلية (محادثة DeepSeek) كانت **تفشل حتمًا** في CI
(test_availability يفترض خادمًا يعمل + fixtures غير موجودة). أُعيدت
صياغتها skip-aware مع اختبارات وحدة حقيقية.
"""
import sys
from pathlib import Path

import pytest

# اجعل الحزمة قابلة للاستيراد من checkout (packages/ على المسار)
_PACKAGES = Path(__file__).resolve().parents[2]
if str(_PACKAGES) not in sys.path:
    sys.path.insert(0, str(_PACKAGES))

httpx = pytest.importorskip("httpx", reason="httpx غير مثبت — اختبارات العميل تُتخطى")


@pytest.fixture()
def live_client():
    """عميل متصل بخادم حي — None إن لم يتوفر (تُتخطى الاختبارات الحية)."""
    from omni_preprocess.backends.stirling_client import StirlingPDFClient
    c = StirlingPDFClient(base_url="http://localhost:8080")
    return c if c.is_available() else None


FIXTURE = Path(__file__).resolve().parents[4] / "tests" / "fixtures" / "scanned_arabic.pdf"
