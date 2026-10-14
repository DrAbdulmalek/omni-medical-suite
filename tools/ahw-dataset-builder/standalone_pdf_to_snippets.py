#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Arabic Handwriting Word Segmentation Pipeline
- يقرأ PDF
- يزيل أشرطة الحواف والخطوط المسطرة
- يكشف الأعمدة والأسطر
- يقطّع الكلمات (Arabic-aware)
- يولّد crops + HTML viewer

تشغيل:
    python segment.py scan.pdf --sample S001 --pages 4 7 8 10 12 13 15
"""

import argparse, json, base64, io
from pathlib import Path
from datetime import datetime
import numpy as np
import cv2
from scipy.signal import find_peaks
from skimage.filters import threshold_sauvola
import fitz  # PyMuPDF
import pandas as pd

# ---------- الطبقة 1: Preprocessing ----------
def remove_edge_bars(gray: np.ndarray, dark_thresh=50, ratio_thresh=0.85):
    """يزيل الأشرطة السوداء على الحواف (المشكلة الحرجة #1)."""
    binary = (gray < dark_thresh).astype(np.uint8)
    h, w = gray.shape

    # أعمدة/صفوف فيها كثافة عالية جدًا
    col_dark = binary.mean(axis=0)
    row_dark = binary.mean(axis=1)

    left = 0
    while left < w and col_dark[left] > ratio_thresh: left += 1
    right = w - 1
    while right > left and col_dark[right] > ratio_thresh: right -= 1
    top = 0
    while top < h and row_dark[top] > ratio_thresh: top += 1
    bottom = h - 1
    while bottom > top and row_dark[bottom] > ratio_thresh: bottom -= 1

    pad = 5
    return gray[max(0,top-pad):min(h,bottom+pad),
                max(0,left-pad):min(w,right+pad)]

def remove_ruling_lines(binary_inv: np.ndarray):
    """يزيل الخطوط المسطرة الأفقية الطويلة."""
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (200, 1))
    lines = cv2.morphologyEx(binary_inv, cv2.MORPH_OPEN, kernel)
    cleaned = cv2.subtract(binary_inv, lines)
    return cleaned

def preprocess(page_img: np.ndarray):
    """الطبقة 1 كاملة."""
    gray = cv2.cvtColor(page_img, cv2.COLOR_BGR2GRAY) if len(page_img.shape)==3 else page_img
    gray = remove_edge_bars(gray)

    # Sauvola binarization
    th = threshold_sauvola(gray, window_size=25, k=0.2)
    binary = (gray > th).astype(np.uint8) * 255  # نص=255
    binary_inv = 255 - binary                     # نص=255 للـCC

    # إزالة الخطوط المسطرة
    cleaned = remove_ruling_lines(binary_inv)

    # إزالة الضوضاء الصغيرة
    n, labels, stats, _ = cv2.connectedComponentsWithStats(cleaned)
    out = np.zeros_like(cleaned)
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] >= 20:
            out[labels == i] = 255

    return gray, out

# ---------- الطبقة 2: Layout ----------
def detect_columns(binary: np.ndarray):
    """كشف الأعمدة عبر Vertical Projection."""
    density = binary.sum(axis=0) / 255.0
    # تنعيم
    k = 15
    smooth = np.convolve(density, np.ones(k)/k, mode='same')

    if smooth.max() == 0:
        return [(0, binary.shape[1])]

    # ابحث عن valley في المنتصف
    w = len(smooth)
    center = w // 2
    window = int(w * 0.15)
    mid_region = smooth[center-window : center+window]
    if len(mid_region) > 0 and mid_region.min() < 0.02 * smooth.max():
        # ابحث عن أدنى نقطة
        valley_idx = center - window + np.argmin(mid_region)
        return [(0, valley_idx), (valley_idx, w)]

    return [(0, w)]

def detect_lines_in_column(binary: np.ndarray, x0: int, x1: int):
    """كشف الأسطر في عمود عبر Horizontal Projection."""
    col = binary[:, x0:x1]
    row_density = col.sum(axis=1) / 255.0

    k = 5
    smooth = np.convolve(row_density, np.ones(k)/k, mode='same')

    if smooth.max() == 0:
        return []

    peaks, props = find_peaks(
        smooth,
        prominence=0.15 * smooth.max(),
        distance=20
    )

    # حواف كل سطر = منتصف بين القمم
    lines = []
    for i, peak in enumerate(peaks):
        y_center = peak
        if i == 0:
            y_top = max(0, peak - 40)
        else:
            y_top = (peaks[i-1] + peak) // 2
        if i == len(peaks) - 1:
            y_bot = min(binary.shape[0], peak + 40)
        else:
            y_bot = (peaks[i] + peaks[i+1]) // 2
        lines.append({
            'x0': x0, 'x1': x1,
            'y0': y_top, 'y1': y_bot,
            'y_center': y_center
        })

    return lines

def detect_layout(binary: np.ndarray):
    """الطبقة 2 كاملة: أعمدة ثم أسطر."""
    columns = detect_columns(binary)
    all_lines = []

    # RTL: العمود الأيمن أولاً
    columns_sorted = sorted(columns, key=lambda c: -c[0])

    for ci, (x0, x1) in enumerate(columns_sorted, start=1):
        col_lines = detect_lines_in_column(binary, x0, x1)
        for li, line in enumerate(col_lines, start=1):
            line['column'] = ci
            line['line_idx'] = li
            all_lines.append(line)

    return columns, all_lines

# ---------- الطبقة 3/4: Word segmentation ----------
def extract_words_from_line(binary: np.ndarray, line: dict, padding=6):
    """Arabic-aware word extraction من سطر واحد."""
    x0, x1 = line['x0'], line['x1']
    y0, y1 = line['y0'], line['y1']
    line_img = binary[y0:y1, x0:x1]

    n, labels, stats, centroids = cv2.connectedComponentsWithStats(
        line_img, connectivity=8
    )

    line_h = y1 - y0
    if line_h == 0:
        return []

    # صنّف CCs
    main_ccs, diacritics = [], []
    for i in range(1, n):
        area = stats[i, cv2.CC_STAT_AREA]
        if area < 15:
            continue
        h_cc = stats[i, cv2.CC_STAT_HEIGHT]
        w_cc = stats[i, cv2.CC_STAT_WIDTH]
        ratio = h_cc / line_h
        if ratio > 0.35:
            main_ccs.append({
                'label': i,
                'x': stats[i, cv2.CC_STAT_LEFT],
                'y': stats[i, cv2.CC_STAT_TOP],
                'w': w_cc, 'h': h_cc, 'area': area,
                'cx': centroids[i][0]
            })
        elif ratio < 0.30:
            diacritics.append({
                'label': i,
                'x': stats[i, cv2.CC_STAT_LEFT],
                'y': stats[i, cv2.CC_STAT_TOP],
                'w': w_cc, 'h': h_cc, 'area': area,
                'cx': centroids[i][0]
            })

    if not main_ccs:
        return []

    # ترتيب RTL (من يمين لليسار)
    main_ccs.sort(key=lambda c: -c['cx'])

    median_h = np.median([c['h'] for c in main_ccs])
    gap_thresh = 0.35 * median_h

    # تجميع
    words = []
    current_word = [main_ccs[0]]

    for c in main_ccs[1:]:
        prev = current_word[-1]
        gap = abs(prev['cx'] - c['cx']) - (prev['w'] + c['w']) / 2
        if gap < gap_thresh:
            current_word.append(c)
        else:
            words.append(current_word)
            current_word = [c]
    words.append(current_word)

    # إلحاق الـdiacritics بأقرب كلمة
    word_boxes = []
    for w_ccs in words:
        xs = [c['x'] for c in w_ccs]
        ys = [c['y'] for c in w_ccs]
        xe = [c['x'] + c['w'] for c in w_ccs]
        ye = [c['y'] + c['h'] for c in w_ccs]
        word_boxes.append([min(xs), min(ys), max(xe), max(ye)])

    for d in diacritics:
        cx = d['cx']
        best = None
        best_dist = 999
        for wi, box in enumerate(word_boxes):
            if box[0] - 5 <= cx <= box[2] + 5:
                dist = abs(d['y'] - box[1]) + abs(d['y'] - box[3])
                if dist < best_dist:
                    best_dist = dist
                    best = wi
        if best is not None:
            b = word_boxes[best]
            word_boxes[best] = [
                min(b[0], d['x']),
                min(b[1], d['y']),
                max(b[2], d['x'] + d['w']),
                max(b[3], d['y'] + d['h'])
            ]

    # استخراج الصور
    crops = []
    for wi, box in enumerate(word_boxes, start=1):
        bx0 = max(0, box[0] - padding)
        by0 = max(0, box[1] - padding)
        bx1 = min(line_img.shape[1], box[2] + padding)
        by1 = min(line_img.shape[0], box[3] + padding)
        if bx1 <= bx0 or by1 <= by0:
            continue
        crop = line_img[by0:by1, bx0:bx1]
        if crop.size == 0:
            continue
        crops.append({
            'word_idx': wi,
            'crop_array': crop,
            'bbox_in_line': (bx0, by0, bx1, by1),
            'bbox_in_page': (x0 + bx0, y0 + by0, x0 + bx1, y0 + by1)
        })
    return crops

# ---------- الحفظ ----------
def save_crop_png(crop: np.ndarray, path: Path):
    """يحفظ crop كثنائي (نص أسود على أبيض)."""
    inv = 255 - crop  # نص أسود على خلفية بيضاء
    cv2.imwrite(str(path), inv)

def make_contact_sheet(crops, cols=8, cell=140):
    """يجمع القصاصات في ورقة اتصال."""
    if not crops: return None
    rows = (len(crops) + cols - 1) // cols
    sheet = np.full((rows*cell, cols*cell, 3), 255, dtype=np.uint8)
    for i, c in enumerate(crops):
        r, cc = divmod(i, cols)
        img = 255 - c['crop_array']
        h, w = img.shape
        scale = min((cell-10)/w, (cell-30)/h)
        new_w, new_h = int(w*scale), int(h*scale)
        resized = cv2.resize(img, (new_w, new_h))
        y0 = r*cell + 20
        x0 = cc*cell + (cell - new_w)//2
        sheet[y0:y0+new_h, x0:x0+new_w] = cv2.cvtColor(resized, cv2.COLOR_GRAY2BGR)
        cv2.putText(sheet, str(i+1), (cc*cell+5, r*cell+15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0,0,255), 1)
    return sheet

# ---------- Main ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('pdf', help='مسار PDF')
    ap.add_argument('--sample', default='S001', help='معرّف العينة')
    ap.add_argument('--pages', nargs='+', type=int, required=True,
                    help='أرقام الصفحات (1-based)')
    ap.add_argument('--out', default='output', help='مجلد المخرجات')
    args = ap.parse_args()

    out_dir = Path(args.out) / args.sample
    crops_dir = out_dir / 'crops'
    preview_dir = out_dir / 'preview'
    crops_dir.mkdir(parents=True, exist_ok=True)
    preview_dir.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(args.pdf)
    all_rows = []
    all_crops_for_html = []

    for pg_num in args.pages:
        print(f"\n=== Page {pg_num} ===")
        page = doc[pg_num - 1]
        pix = page.get_pixmap(dpi=300)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
            pix.h, pix.w, pix.n)
        if pix.n == 4:
            img = cv2.cvtColor(img, cv2.COLOR_RGBA2RGB)
        elif pix.n == 1:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
        bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

        # الطبقة 1
        gray, binary = preprocess(bgr)
        cv2.imwrite(str(preview_dir / f'page{pg_num:02d}_L1_clean.png'),
                    255 - binary)

        # الطبقة 2
        columns, lines = detect_layout(binary)
        print(f"  Columns: {len(columns)}, Lines: {len(lines)}")

        # overlay للتحقق البصري
        overlay = bgr.copy()
        for (x0, x1) in columns:
            cv2.line(overlay, (x1, 0), (x1, overlay.shape[0]), (0,0,255), 3)
        for line in lines:
            cv2.rectangle(overlay,
                (line['x0'], line['y0']),
                (line['x1'], line['y1']),
                (255, 0, 0), 2)
        cv2.imwrite(str(preview_dir / f'page{pg_num:02d}_L2_layout.png'),
                    overlay)

        # الطبقة 3+4
        for line in lines:
            crops = extract_words_from_line(binary, line)
            for c in crops:
                word_id = (f"{args.sample}_P{pg_num:02d}"
                           f"_C{line['column']:02d}"
                           f"_L{line['line_idx']:02d}"
                           f"_W{c['word_idx']:02d}")
                crop_path = crops_dir / f'{word_id}.png'
                save_crop_png(c['crop_array'], crop_path)

                # thumbnail للـHTML (base64)
                inv = 255 - c['crop_array']
                _, buf = cv2.imencode('.png', inv)
                b64 = base64.b64encode(buf).decode()

                all_crops_for_html.append({
                    'word_id': word_id,
                    'page': pg_num,
                    'column': line['column'],
                    'line_idx': line['line_idx'],
                    'word_idx': c['word_idx'],
                    'image_b64': b64,
                    'text': '',
                    'status': 'RAW'
                })

                all_rows.append({
                    'word_id': word_id,
                    'sample_id': args.sample,
                    'page': pg_num,
                    'column': line['column'],
                    'line_idx': line['line_idx'],
                    'word_idx': c['word_idx'],
                    'crop_path': str(crop_path.relative_to(out_dir)),
                    'text': '',
                    'status': 'RAW'
                })

    df = pd.DataFrame(all_rows)
    df.to_csv(out_dir / 'metadata.csv', index=False, encoding='utf-8-sig')
    print(f"\n✅ {len(all_rows)} words extracted")
    print(f"   CSV: {out_dir / 'metadata.csv'}")
    print(f"   Crops: {crops_dir}")

    # توليد HTML
    generate_html(out_dir, all_crops_for_html, args.sample)
    print(f"   HTML: {out_dir / 'viewer.html'}")

def generate_html(out_dir: Path, crops: list, sample_id: str):
    """يولّد جدول HTML تفاعلي."""
    html = f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<title>تصحيح النصوص — {sample_id}</title>
<style>
body {{ font-family: Tahoma, sans-serif; background: #f5f5f5;
       margin: 0; padding: 20px; }}
h1 {{ color: #333; }}
.progress {{ position: sticky; top: 0; background: #fff;
            padding: 15px; border-bottom: 2px solid #007bff;
            z-index: 100; display: flex; gap: 20px;
            align-items: center; }}
.progress-bar {{ flex: 1; height: 20px; background: #eee;
                border-radius: 10px; overflow: hidden; }}
.progress-fill {{ height: 100%; background: #28a745;
                 transition: width 0.3s; width: 0%; }}
.card {{ background: #fff; border: 1px solid #ddd;
        border-radius: 8px; padding: 12px; margin: 10px 0;
        display: flex; gap: 15px; align-items: center; }}
.card.done {{ border-color: #28a745; background: #f0fff4; }}
.crop {{ flex-shrink: 0; padding: 8px; background: #fafafa;
        border: 1px solid #e0e0e0; border-radius: 4px;
        min-width: 200px; text-align: center; }}
.crop img {{ max-width: 190px; max-height: 80px;
            image-rendering: crisp-edges; }}
.info {{ flex: 1; }}
.info small {{ color: #888; }}
input[type=text] {{ width: 100%; padding: 10px; font-size: 18px;
                   border: 2px solid #ccc; border-radius: 6px;
                   direction: rtl; box-sizing: border-box; }}
input.done {{ border-color: #28a745; background: #f0fff4; }}
.actions {{ display: flex; gap: 10px; margin-top: 20px;
           position: sticky; bottom: 20px; background: #fff;
           padding: 15px; border-radius: 8px;
           box-shadow: 0 -2px 10px rgba(0,0,0,0.1); }}
button {{ padding: 12px 24px; font-size: 16px; border: none;
         border-radius: 6px; cursor: pointer; }}
.primary {{ background: #007bff; color: white; }}
.success {{ background: #28a745; color: white; }}
button:disabled {{ opacity: 0.5; cursor: not-allowed; }}
</style>
</head>
<body>
<h1>تصحيح نصوص الكلمات — {sample_id}</h1>
<p>املأ النص المقابل لكل قصاصة. تُحفظ تلقائياً في المتصفح. عند الانتهاء اضغط <b>تصدير CSV</b>.</p>

<div class="progress">
    <div class="progress-bar"><div class="progress-fill" id="pbar"></div></div>
    <span id="pcount">0 / {len(crops)}</span>
</div>

<div id="cards"></div>

<div class="actions">
    <button class="primary" onclick="exportCSV()">📥 تصدير CSV</button>
    <button onclick="clearAll()">🗑️ مسح الكل</button>
    <button onclick="window.scrollTo(0,0)">⬆️ أعلى</button>
</div>

<script>
const data = {json.dumps(crops, ensure_ascii=False)};
const STORE_KEY = 'wh-corrections-{sample_id}';

// استرجاع من localStorage
const saved = JSON.parse(localStorage.getItem(STORE_KEY) || '{{}}');
data.forEach(d => {{ if (saved[d.word_id]) d.text = saved[d.word_id]; }});

const container = document.getElementById('cards');
data.forEach((d, i) => {{
    const card = document.createElement('div');
    card.className = 'card' + (d.text ? ' done' : '');
    card.innerHTML = `
        <div class="crop">
            <img src="data:image/png;base64,${{d.image_b64}}">
        </div>
        <div class="info">
            <small>${{d.word_id}}</small>
            <input type="text" value="${{d.text}}"
                   placeholder="اكتب النص هنا..."
                   oninput="onEdit(${{i}}, this.value, this)">
        </div>`;
    container.appendChild(card);
}});

function onEdit(idx, value, input) {{
    data[idx].text = value;
    input.classList.toggle('done', !!value);
    input.parentElement.parentElement.classList.toggle('done', !!value);
    const obj = {{}};
    data.forEach(d => {{ if (d.text) obj[d.word_id] = d.text; }});
    localStorage.setItem(STORE_KEY, JSON.stringify(obj));
    updateProgress();
}}

function updateProgress() {{
    const done = data.filter(d => d.text.trim()).length;
    document.getElementById('pcount').textContent =
        `${{done}} / ${{data.length}}`;
    document.getElementById('pbar').style.width =
        `${{(done / data.length) * 100}}%`;
}}

function exportCSV() {{
    const headers = ['word_id','page','column','line_idx','word_idx',
                     'text','status'];
    const rows = [headers.join(',')];
    data.forEach(d => {{
        const text = (d.text || '').replace(/"/g, '""');
        const status = d.text ? 'USER_CORRECTED' : 'RAW';
        rows.push([d.word_id, d.page, d.column, d.line_idx,
                   d.word_idx, `"${{text}}"`, status].join(','));
    }});
    const blob = new Blob(['\\ufeff' + rows.join('\\n')],
                          {{type:'text/csv;charset=utf-8'}});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'corrections_{sample_id}.csv';
    a.click();
    URL.revokeObjectURL(url);
}}

function clearAll() {{
    if (!confirm('هل أنت متأكد؟ سيُمسح كل التصحيح.')) return;
    localStorage.removeItem(STORE_KEY);
    location.reload();
}}

updateProgress();
</script>
</body>
</html>"""
    (out_dir / 'viewer.html').write_text(html, encoding='utf-8')

if __name__ == '__main__':
    main()
