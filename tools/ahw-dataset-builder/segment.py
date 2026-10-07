#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Arabic Handwriting Word Segmentation Pipeline — v2
يضيف: تصدير Excel، دمج post-processing، API للـFlask server.
"""

import argparse, json, base64, io, hashlib
from pathlib import Path
from datetime import datetime
import numpy as np
import cv2
from scipy.signal import find_peaks
from skimage.filters import threshold_sauvola
import fitz
import pandas as pd

# استيراد post-processing
from postprocess import enhance_crop, merge_broken_components

# ==================================================
# الطبقة 1: Preprocessing
# ==================================================
def remove_edge_bars(gray, dark_thresh=50, ratio_thresh=0.85):
    binary = (gray < dark_thresh).astype(np.uint8)
    h, w = gray.shape
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

def remove_ruling_lines(binary_inv):
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (200, 1))
    lines = cv2.morphologyEx(binary_inv, cv2.MORPH_OPEN, kernel)
    return cv2.subtract(binary_inv, lines)

def preprocess(page_img):
    gray = cv2.cvtColor(page_img, cv2.COLOR_BGR2GRAY) \
           if len(page_img.shape)==3 else page_img
    gray = remove_edge_bars(gray)
    th = threshold_sauvola(gray, window_size=25, k=0.2)
    binary = (gray > th).astype(np.uint8) * 255
    binary_inv = 255 - binary
    cleaned = remove_ruling_lines(binary_inv)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(cleaned)
    out = np.zeros_like(cleaned)
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] >= 20:
            out[labels == i] = 255
    return gray, out

# ==================================================
# الطبقة 2: Layout
# ==================================================
def detect_columns(binary):
    density = binary.sum(axis=0) / 255.0
    k = 15
    smooth = np.convolve(density, np.ones(k)/k, mode='same')
    if smooth.max() == 0:
        return [(0, binary.shape[1])]
    w = len(smooth)
    center = w // 2
    window = int(w * 0.15)
    mid_region = smooth[center-window : center+window]
    if len(mid_region) > 0 and mid_region.min() < 0.02 * smooth.max():
        valley_idx = center - window + np.argmin(mid_region)
        return [(0, valley_idx), (valley_idx, w)]
    return [(0, w)]

def detect_lines_in_column(binary, x0, x1):
    col = binary[:, x0:x1]
    row_density = col.sum(axis=1) / 255.0
    k = 5
    smooth = np.convolve(row_density, np.ones(k)/k, mode='same')
    if smooth.max() == 0:
        return []
    peaks, _ = find_peaks(smooth,
        prominence=0.15 * smooth.max(), distance=20)
    lines = []
    for i, peak in enumerate(peaks):
        y_top = max(0, peak-40) if i==0 else (peaks[i-1]+peak)//2
        y_bot = min(binary.shape[0], peak+40) if i==len(peaks)-1 \
                else (peaks[i]+peaks[i+1])//2
        lines.append({'x0':x0,'x1':x1,'y0':y_top,'y1':y_bot,'y_center':peak})
    return lines

def detect_layout(binary):
    columns = detect_columns(binary)
    all_lines = []
    columns_sorted = sorted(columns, key=lambda c: -c[0])  # RTL
    for ci, (x0, x1) in enumerate(columns_sorted, start=1):
        col_lines = detect_lines_in_column(binary, x0, x1)
        for li, line in enumerate(col_lines, start=1):
            line['column'] = ci
            line['line_idx'] = li
            all_lines.append(line)
    return columns, all_lines

# ==================================================
# الطبقة 3/4: Word Segmentation (Arabic-aware)
# ==================================================
def extract_words_from_line(binary, line, padding=6):
    x0, x1 = line['x0'], line['x1']
    y0, y1 = line['y0'], line['y1']
    line_img = binary[y0:y1, x0:x1]
    n, labels, stats, centroids = cv2.connectedComponentsWithStats(
        line_img, connectivity=8)
    line_h = y1 - y0
    if line_h == 0:
        return []
    main_ccs, diacritics = [], []
    for i in range(1, n):
        area = stats[i, cv2.CC_STAT_AREA]
        if area < 15: continue
        h_cc = stats[i, cv2.CC_STAT_HEIGHT]
        w_cc = stats[i, cv2.CC_STAT_WIDTH]
        ratio = h_cc / line_h
        if ratio > 0.35:
            main_ccs.append({
                'x': stats[i, cv2.CC_STAT_LEFT],
                'y': stats[i, cv2.CC_STAT_TOP],
                'w': w_cc, 'h': h_cc,
                'cx': centroids[i][0]})
        elif ratio < 0.30:
            diacritics.append({
                'x': stats[i, cv2.CC_STAT_LEFT],
                'y': stats[i, cv2.CC_STAT_TOP],
                'w': w_cc, 'h': h_cc,
                'cx': centroids[i][0]})
    if not main_ccs: return []
    main_ccs.sort(key=lambda c: -c['cx'])
    median_h = np.median([c['h'] for c in main_ccs])
    gap_thresh = 0.35 * median_h
    words = [[main_ccs[0]]]
    for c in main_ccs[1:]:
        prev = words[-1][-1]
        gap = abs(prev['cx'] - c['cx']) - (prev['w'] + c['w']) / 2
        if gap < gap_thresh:
            words[-1].append(c)
        else:
            words.append([c])
    word_boxes = []
    for w_ccs in words:
        xs = [c['x'] for c in w_ccs]
        ys = [c['y'] for c in w_ccs]
        xe = [c['x']+c['w'] for c in w_ccs]
        ye = [c['y']+c['h'] for c in w_ccs]
        word_boxes.append([min(xs),min(ys),max(xe),max(ye)])
    for d in diacritics:
        best, best_dist = None, 999
        for wi, box in enumerate(word_boxes):
            if box[0]-5 <= d['cx'] <= box[2]+5:
                dist = abs(d['y']-box[1]) + abs(d['y']-box[3])
                if dist < best_dist:
                    best_dist, best = dist, wi
        if best is not None:
            b = word_boxes[best]
            word_boxes[best] = [min(b[0],d['x']),min(b[1],d['y']),
                               max(b[2],d['x']+d['w']),max(b[3],d['y']+d['h'])]
    crops = []
    for wi, box in enumerate(word_boxes, start=1):
        bx0 = max(0, box[0]-padding); by0 = max(0, box[1]-padding)
        bx1 = min(line_img.shape[1], box[2]+padding)
        by1 = min(line_img.shape[0], box[3]+padding)
        if bx1 <= bx0 or by1 <= by0: continue
        crop = line_img[by0:by1, bx0:bx1]
        if crop.size == 0: continue
        # ✅ post-processing (متصل بالنص العربي)
        crop = merge_broken_components(crop)
        crops.append({
            'word_idx': wi,
            'crop_array': crop,
            'bbox_in_page': (x0+bx0, y0+by0, x0+bx1, y0+by1)})
    return crops

# ==================================================
# الحفظ والعرض
# ==================================================
def save_crop_png(crop, path):
    inv = 255 - crop
    cv2.imwrite(str(path), inv)

def make_contact_sheet(crops, cols=8, cell=140):
    if not crops: return None
    rows = (len(crops) + cols - 1) // cols
    sheet = np.full((rows*cell, cols*cell, 3), 255, dtype=np.uint8)
    for i, c in enumerate(crops):
        r, cc = divmod(i, cols)
        img = 255 - c['crop_array']
        h, w = img.shape
        scale = min((cell-10)/w, (cell-30)/h)
        nw, nh = int(w*scale), int(h*scale)
        resized = cv2.resize(img, (nw, nh))
        sheet[r*cell+20:r*cell+20+nh, cc*cell+(cell-nw)//2:cc*cell+(cell-nw)//2+nw] = \
            cv2.cvtColor(resized, cv2.COLOR_GRAY2BGR)
        cv2.putText(sheet, str(i+1), (cc*cell+5, r*cell+15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0,0,255), 1)
    return sheet

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()

# ==================================================
# Main
# ==================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('pdf')
    ap.add_argument('--sample', default='S001')
    ap.add_argument('--pages', nargs='+', type=int, required=True)
    ap.add_argument('--out', default='output')
    ap.add_argument('--dpi', type=int, default=300)
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
        pix = page.get_pixmap(dpi=args.dpi)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
            pix.h, pix.w, pix.n)
        if pix.n == 4: img = cv2.cvtColor(img, cv2.COLOR_RGBA2RGB)
        elif pix.n == 1: img = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
        bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

        gray, binary = preprocess(bgr)
        cv2.imwrite(str(preview_dir / f'page{pg_num:02d}_L1_clean.png'),
                    255 - binary)

        columns, lines = detect_layout(binary)
        print(f"  Columns: {len(columns)}, Lines: {len(lines)}")

        overlay = bgr.copy()
        for (x0, x1) in columns:
            cv2.line(overlay, (x1, 0), (x1, overlay.shape[0]), (0,0,255), 3)
        for line in lines:
            cv2.rectangle(overlay, (line['x0'], line['y0']),
                         (line['x1'], line['y1']), (255, 0, 0), 2)
        cv2.imwrite(str(preview_dir / f'page{pg_num:02d}_L2_layout.png'),
                    overlay)

        for line in lines:
            crops = extract_words_from_line(binary, line)
            for c in crops:
                word_id = (f"{args.sample}_P{pg_num:02d}"
                           f"_C{line['column']:02d}"
                           f"_L{line['line_idx']:02d}"
                           f"_W{c['word_idx']:02d}")
                crop_path = crops_dir / f'{word_id}.png'
                save_crop_png(c['crop_array'], crop_path)

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
    # ✅ تصدير CSV + Excel
    df.to_csv(out_dir / 'metadata.csv', index=False, encoding='utf-8-sig')
    df.to_excel(out_dir / 'metadata.xlsx', index=False, engine='openpyxl')
    print(f"\n✅ {len(all_rows)} words")
    print(f"   CSV:   {out_dir / 'metadata.csv'}")
    print(f"   Excel: {out_dir / 'metadata.xlsx'}")
    print(f"   Crops: {crops_dir}")

    # manifest
    manifest = {
        'sample_id': args.sample,
        'source_pdf': str(args.pdf),
        'sha256': sha256_file(args.pdf),
        'pages_processed': args.pages,
        'page_count': len(args.pages),
        'word_count': len(all_rows),
        'created_at': datetime.utcnow().isoformat() + 'Z',
        'pipeline_version': '2.0.0'
    }
    (out_dir / 'manifest.json').write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding='utf-8')

    # HTML fallback viewer
    from templates.embed import render_viewer
    html = render_viewer(args.sample, all_crops_for_html)
    (out_dir / 'viewer.html').write_text(html, encoding='utf-8')
    print(f"   HTML:  {out_dir / 'viewer.html'}")
    print(f"   Server: python server.py --sample {args.sample}")

if __name__ == '__main__':
    main()
