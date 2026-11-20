"""مولّد عينات المعيار الذهبي العربي (T1) — حتمي وقابل لإعادة الإنتاج.

يولّد 10 عينات صور عربية طبية (مطبوع نظيف، محاكاة مسح ضوئي، مختلط عربي/إنجليزي،
جدول جرعات) من نصوص ground truth مكتوبة يدوياً بترتيب منطقي (A2 — لا get_display).
كل عينة تُختم بـ sha256 في manifest.json. التشغيل: python generate_samples.py
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

SET_DIR = Path(__file__).parent
SAMPLES_DIR = SET_DIR / "samples"
FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/amiri/Amiri-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf",
    "/usr/share/fonts/opentype/noto/NotoNaskhArabic-Regular.ttf",
]

# (id, category, lines) — ground truth منطقي الترتيب، محتوى طبي، بلا PII.
SAMPLES: list[tuple[str, str, list[str]]] = [
    ("gs_ar_printed_001", "printed_clean", [
        "المريض يشكو من ألم في الصدر منذ يومين",
        "ضغط الدم 120 على 80 والنبض 72",
        "التشخيص المبدئي: التهاب الشعب الهوائية",
        "العلاج: أموكسيسيلين 500 ملغ ثلاث مرات يوميا",
    ]),
    ("gs_ar_printed_002", "printed_clean", [
        "وصفة طبية",
        "دواء: باراسيتامول 1000 ملغ",
        "الجرعة: قرص كل 8 ساعات بعد الأكل",
        "مدة العلاج: خمسة أيام",
        "ملاحظات: تجنب تناول المشروبات الكحولية",
    ]),
    ("gs_ar_printed_003", "printed_clean", [
        "تقرير المختبر",
        "الهيموغلوبين 13.5 غم/ديسيلتر",
        "كرياتينين 0.9 ملغ/ديسيلتر",
        "الصوديوم 140 ملي مول/لتر",
        "البوتاسيوم 4.2 ملي مول/لتر",
    ]),
    ("gs_ar_scanned_001", "scan_noisy", [
        "سجل المريض رقم 4521",
        "الحساسية: بنسلين",
        "الأدوية الحالية: ميتفورمين 850 ملغ مرتين يوميا",
        "آخر زيارة: 2026-08-15",
    ]),
    ("gs_ar_scanned_002", "scan_noisy", [
        "الشكوى الرئيسية: صداع مستمر وضبابية نظر",
        "الفحص السريري: لا وجود لعلامات وذمة حبل بصري",
        "الخطة: تصوير مقطعي محورب وإحالة إلى عيون",
    ]),
    ("gs_ar_mixed_001", "mixed_ar_en", [
        "التشخيص: Diabetes Mellitus Type 2",
        "الدواء: Metformin 850 ملغ",
        "مضاعفات محتملة: Diabetic Neuropathy",
        "المتابعة خلال 3 أشهر مع HbA1c",
    ]),
    ("gs_ar_mixed_002", "mixed_ar_en", [
        "تقرير الأشعة: Chest X-Ray",
        "النتيجة: لا يوجد infiltration واضح",
        "القلب بحجم طبيعي، CPR سلبية",
        "التوصية: متابعة سريرية فقط",
    ]),
    ("gs_ar_table_001", "dosage_table", [
        "جدول الجرعات",
        "الدواء | الجرعة | التكرار",
        "أموكسيسيلين | 500 ملغ | 3 مرات يوميا",
        "إيبوبروفين | 400 ملغ | كل 8 ساعات",
        "أوميبرازول | 20 ملغ | مرة صباحا",
    ]),
    ("gs_ar_table_002", "dosage_table", [
        "مؤشرات المختبر",
        "التحليل | القيمة | المدى الطبيعي",
        "WBC | 7.2 | 4.0-11.0",
        "Platelets | 250 | 150-400",
        "Glucose | 105 | 70-100",
    ]),
    ("gs_ar_anatomy_001", "printed_clean", [
        "الجهاز التنفسي: الرئة اليمنى ثلاث فصوص واليسرى فصان",
        "القلب: أربع حجرات، الأذين الأيسر والأيمن والبطينان",
        "الكبد في الربع العلوي الأيمن من البطن",
    ]),
]


def _font(size: int) -> ImageFont.FreeTypeFont:
    for p in FONT_CANDIDATES:
        if Path(p).is_file():
            return ImageFont.truetype(p, size)
    raise RuntimeError("لا يوجد خط عربي — ثبّت Amiri أو Noto Naskh Arabic")


def _render_clean(lines: list[str], font_size: int = 34) -> Image.Image:
    font = _font(font_size)
    line_h = int(font_size * 1.9)
    width = 1240
    height = 120 + line_h * len(lines) + 80
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)
    y = 60
    for ln in lines:
        draw.text((width - 60, y), ln, font=font, fill="black", anchor="ra", direction="rtl")
        y += line_h
    return img


def _apply_scan_noise(img: Image.Image, seed: int) -> Image.Image:
    """محاكاة مسح ضوئي: ضجيج غاوسي مُثبّت البذرة + ميل إضاءة خفيف."""
    rng = np.random.default_rng(seed)  # بذرة ثابتة لكل عينة — قابل لإعادة الإنتاج
    arr = np.asarray(img.convert("L"), dtype=np.float32)
    arr += rng.normal(0, 14, arr.shape)
    h, w = arr.shape
    grad = (np.linspace(-16, 16, w, dtype=np.float32)[None, :] * (1 + 0 * h))
    arr = np.clip(arr + grad, 0, 255).astype(np.uint8)
    return Image.fromarray(arr, "L").convert("RGB")


def main() -> None:
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    manifest = []
    gt_rows = []
    for sid, category, lines in SAMPLES:
        img = _render_clean(lines)
        if category == "scan_noisy":
            img = _apply_scan_noise(img, seed=int(sid.split("_")[-1]))
        path = SAMPLES_DIR / f"{sid}.png"
        img.save(path, "PNG")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        manifest.append({"id": sid, "category": category, "file": path.name, "sha256": digest})
        gt_rows.append({
            "id": sid,
            "category": category,
            "text": "\n".join(lines),
            "source": "hand-authored ground truth (logical order, A2)",
            "pii": False,
        })
    gt_path = SET_DIR / "ground_truth.jsonl"
    with gt_path.open("w", encoding="utf-8") as f:
        for row in gt_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    with (SET_DIR / "manifest.json").open("w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(f"generated {len(manifest)} samples + ground_truth.jsonl + manifest.json")


if __name__ == "__main__":
    main()