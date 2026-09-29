"""ahw — Arabic HandWriting pipeline package (ATR phase).

حزمة خط اليد العربي داخل omni-medical-suite. أُنشئت ضمن ATR-F1/F4
(إعادة بناء موثقة بعد فقدان الملفات الأصلية مع env reset — سابقة M001).

الوحدات:
    ahw.segment        — تجزئة الصفحة (سطور + كلمات) بمعالجة صور كلاسيكية.
    ahw.arabic_trocr   — TrOCR مع محوّل AraBERT (ATR-F1).
"""

__version__ = "0.1.0"
