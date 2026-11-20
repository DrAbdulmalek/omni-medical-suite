"""التباسات شائعة في التعرف الطبي — أمثلة مملوكة، ليست قاموساً منسوخاً."""

from __future__ import annotations

CONFUSIONS: tuple[dict[str, str], ...] = (
    {"guess": "أموكسيسيلبن", "text": "أموكسيسيلين", "role": "drug", "note": "باء بدل ياء"},
    {"guess": "500 محم", "text": "500 مجم", "role": "dose", "note": "ح بدل ج"},
    {"guess": "هيموعلوبين", "text": "هيموغلوبين", "role": "drug", "note": "ع بدل غ"},
    {"guess": "تلات مرات يوميا", "text": "ثلاث مرات يومياً", "role": "note", "note": "ت بدل ث"},
    {"guess": "13.2 q/dL", "text": "13.2 g/dL", "role": "dose", "note": "q بدل g"},
    {"guess": "ضيام 8 ساعات", "text": "صيام 8 ساعات", "role": "note", "note": "ض بدل ص"},
    {"guess": "مراجهة بعد اسبوع", "text": "مراجعة بعد أسبوع", "role": "note", "note": "ح بدل ج وإسقاط الهمزة"},
    {"guess": "لا حساسيه معروفه", "text": "لا حساسية معروفة", "role": "note", "note": "هاء التأنيث"},
)


def suggest(guess: str) -> dict[str, str] | None:
    key = (guess or "").strip()
    for row in CONFUSIONS:
        if row["guess"] == key:
            return dict(row)
    return None
