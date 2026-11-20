#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
معالجة PDF كبير على دفعات (batch processing).
يحفظ كل دفعة في مجلد منفصل حتى لا تُفقد النتائج عند الانقطاع.
"""

import argparse, json, base64, hashlib, gc
from pathlib import Path
from datetime import datetime
import numpy as np
import cv2
import fitz
import pandas as pd
from segment import preprocess, detect_layout, extract_words_from_line, save_crop_png

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()

def process_batch(doc, page_numbers, sample_id, batch_idx, out_dir, dpi=300):
    """يعالج دفعة من الصفحات ويحفظها في مجلد مستقل."""
    batch_dir = out_dir / f'batch_{batch_idx:03d}'
    crops_dir = batch_dir / 'crops'
    preview_dir = batch_dir / 'preview'
    crops_dir.mkdir(parents=True, exist_ok=True)
    preview_dir.mkdir(parents=True, exist_ok=True)

    all_rows = []
    all_crops_for_html = []

    for pg_num in page_numbers:
        print(f"  📄 Page {pg_num}...")
        page = doc[pg_num - 1]
        pix = page.get_pixmap(dpi=dpi)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
            pix.h, pix.w, pix.n)
        if pix.n == 4: img = cv2.cvtColor(img, cv2.COLOR_RGBA2RGB)
        elif pix.n == 1: img = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
        bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

        gray, binary = preprocess(bgr)
        cv2.imwrite(str(preview_dir / f'page{pg_num:02d}_L1.png'), 255 - binary)

        columns, lines = detect_layout(binary)
        overlay = bgr.copy()
        for (x0, x1) in columns:
            cv2.line(overlay, (x1, 0), (x1, overlay.shape[0]), (0,0,255), 3)
        for line in lines:
            cv2.rectangle(overlay, (line['x0'], line['y0']),
                         (line['x1'], line['y1']), (255, 0, 0), 2)
        cv2.imwrite(str(preview_dir / f'page{pg_num:02d}_L2.png'), overlay)

        for line in lines:
            crops = extract_words_from_line(binary, line)
            for c in crops:
                word_id = (f"{sample_id}_P{pg_num:02d}"
                           f"_C{line['column']:02d}"
                           f"_L{line['line_idx']:02d}"
                           f"_W{c['word_idx']:02d}")
                crop_path = crops_dir / f'{word_id}.png'
                save_crop_png(c['crop_array'], crop_path)

                inv = 255 - c['crop_array']
                _, buf = cv2.imencode('.png', inv)
                b64 = base64.b64encode(buf).decode()

                all_crops_for_html.append({
                    'word_id': word_id, 'page': pg_num,
                    'column': line['column'], 'line_idx': line['line_idx'],
                    'word_idx': c['word_idx'], 'image_b64': b64,
                    'text': '', 'status': 'RAW'
                })
                all_rows.append({
                    'word_id': word_id, 'sample_id': sample_id,
                    'page': pg_num, 'column': line['column'],
                    'line_idx': line['line_idx'], 'word_idx': c['word_idx'],
                    'crop_path': str(crop_path.relative_to(out_dir)),
                    'text': '', 'status': 'RAW'
                })

        # تحرير الذاكرة
        del bgr, binary, gray
        gc.collect()

    # حفظ الدفعة
    df = pd.DataFrame(all_rows)
    df.to_csv(batch_dir / 'metadata.csv', index=False, encoding='utf-8-sig')
    df.to_excel(batch_dir / 'metadata.xlsx', index=False, engine='openpyxl')

    batch_manifest = {
        'batch_idx': batch_idx,
        'pages': page_numbers,
        'word_count': len(all_rows),
        'created_at': datetime.utcnow().isoformat() + 'Z'
    }
    (batch_dir / 'manifest.json').write_text(
        json.dumps(batch_manifest, ensure_ascii=False, indent=2))

    print(f"  ✅ Batch {batch_idx}: {len(all_rows)} words, "
          f"pages {page_numbers[0]}-{page_numbers[-1]}")
    return len(all_rows)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('pdf')
    ap.add_argument('--sample', default='S001')
    ap.add_argument('--pages-per-batch', type=int, default=5,
                    help='عدد الصفحات في كل دفعة')
    ap.add_argument('--out', default='output')
    ap.add_argument('--dpi', type=int, default=300)
    ap.add_argument('--start-page', type=int, default=1)
    ap.add_argument('--end-page', type=int, default=0,
                    help='0 = حتى النهاية')
    args = ap.parse_args()

    doc = fitz.open(args.pdf)
    total_pages = doc.page_count
    end_page = args.end_page or total_pages
    all_pages = list(range(args.start_page, end_page + 1))

    out_dir = Path(args.out) / args.sample
    out_dir.mkdir(parents=True, exist_ok=True)

    # تقسيم الصفحات إلى دفعات
    batches = [all_pages[i:i + args.pages_per_batch]
               for i in range(0, len(all_pages), args.pages_per_batch)]

    print(f"📚 PDF: {total_pages} صفحة")
    print(f"📦 الدفعات: {len(batches)} دفعة × {args.pages_per_batch} صفحات")

    total_words = 0
    for bi, batch_pages in enumerate(batches, start=1):
        print(f"\n=== Batch {bi}/{len(batches)} ===")
        try:
            count = process_batch(doc, batch_pages, args.sample, bi,
                                  out_dir, args.dpi)
            total_words += count
            # حفظ حالة الدفعات للتتبع
            state_file = out_dir / 'batch_state.json'
            state = json.loads(state_file.read_text()) if state_file.exists() else {}
            state[f'batch_{bi:03d}'] = {
                'pages': batch_pages, 'words': count,
                'status': 'done',
                'completed_at': datetime.utcnow().isoformat() + 'Z'
            }
            state_file.write_text(json.dumps(state, indent=2))
        except Exception as e:
            print(f"  ❌ فشلت الدفعة {bi}: {e}")
            state_file = out_dir / 'batch_state.json'
            state = json.loads(state_file.read_text()) if state_file.exists() else {}
            state[f'batch_{bi:03d}'] = {
                'pages': batch_pages, 'status': 'failed', 'error': str(e)
            }
            state_file.write_text(json.dumps(state, indent=2))

    # manifest نهائي
    manifest = {
        'sample_id': args.sample,
        'source_pdf': str(args.pdf),
        'sha256': sha256_file(args.pdf),
        'total_pages': total_pages,
        'pages_processed': all_pages,
        'total_words': total_words,
        'batches_count': len(batches),
        'created_at': datetime.utcnow().isoformat() + 'Z'
    }
    (out_dir / 'manifest.json').write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2))

    print(f"\n✅ اكتمل! {total_words} كلمة من {len(batches)} دفعة")
    print(f"   📁 {out_dir}")

if __name__ == '__main__':
    main()
