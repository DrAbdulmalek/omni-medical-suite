#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
خادم Flask لتصحيح النصوص مع تخزين دائم في SQLite.
"""

import argparse, base64, csv, io, json, sqlite3
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file
import pandas as pd

app = Flask(__name__)
DB_PATH = None
CROPS_DIR = None
SAMPLE_ID = None

# ==================================================
# Database
# ==================================================
def init_db(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS words (
            word_id     TEXT PRIMARY KEY,
            sample_id   TEXT NOT NULL,
            page        INTEGER,
            column_idx  INTEGER,
            line_idx    INTEGER,
            word_idx    INTEGER,
            crop_path   TEXT,
            text        TEXT DEFAULT '',
            status      TEXT DEFAULT 'RAW',
            updated_at  TEXT,
            created_at  TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON words(status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sample ON words(sample_id)")
    conn.commit()
    return conn

def seed_from_metadata(csv_path, sample_id, conn):
    """يحمّل metadata.csv إلى DB إن كانت فارغة."""
    cur = conn.execute("SELECT COUNT(*) FROM words WHERE sample_id=?",
                       (sample_id,))
    if cur.fetchone()[0] > 0:
        return  # موجود مسبقاً
    df = pd.read_csv(csv_path)
    for _, row in df.iterrows():
        conn.execute("""
            INSERT OR IGNORE INTO words
            (word_id, sample_id, page, column_idx, line_idx, word_idx,
             crop_path, text, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            row['word_id'], sample_id, row['page'], row['column'],
            row['line_idx'], row['word_idx'], row['crop_path'],
            row.get('text', ''), 'RAW'
        ))
    conn.commit()

# ==================================================
# Routes
# ==================================================
@app.route('/')
def index():
    conn = init_db(DB_PATH)
    rows = conn.execute("""
        SELECT word_id, page, column_idx, line_idx, word_idx,
               crop_path, text, status
        FROM words WHERE sample_id=?
        ORDER BY page, column_idx, line_idx, word_idx
    """, (SAMPLE_ID,)).fetchall()
    conn.close()

    words = []
    for r in rows:
        crop_file = CROPS_DIR / Path(r[5]).name
        b64 = ''
        if crop_file.exists():
            b64 = base64.b64encode(crop_file.read_bytes()).decode()
        words.append({
            'word_id': r[0], 'page': r[1], 'column': r[2],
            'line_idx': r[3], 'word_idx': r[4],
            'crop_path': r[5], 'text': r[6] or '',
            'status': r[7], 'image_b64': b64
        })
    return render_template('viewer.html', sample_id=SAMPLE_ID, words=words)

@app.route('/api/word/<word_id>', methods=['POST'])
def update_word(word_id):
    data = request.get_json()
    text = data.get('text', '').strip()
    status = 'USER_CORRECTED' if text else 'RAW'
    conn = init_db(DB_PATH)
    conn.execute("""
        UPDATE words SET text=?, status=?, updated_at=?
        WHERE word_id=?
    """, (text, status, datetime.utcnow().isoformat(), word_id))
    conn.commit()
    conn.close()
    return jsonify({'ok': True, 'status': status})

@app.route('/api/stats')
def stats():
    conn = init_db(DB_PATH)
    cur = conn.execute("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN text != '' THEN 1 ELSE 0 END) as done
        FROM words WHERE sample_id=?
    """, (SAMPLE_ID,))
    row = cur.fetchone()
    conn.close()
    return jsonify({'total': row[0], 'done': row[1] or 0})

@app.route('/api/export/csv')
def export_csv():
    conn = init_db(DB_PATH)
    rows = conn.execute("""
        SELECT word_id, page, column_idx, line_idx, word_idx,
               crop_path, text, status
        FROM words WHERE sample_id=?
        ORDER BY page, column_idx, line_idx, word_idx
    """, (SAMPLE_ID,)).fetchall()
    conn.close()
    buf = io.StringIO()
    buf.write('\ufeff')
    writer = csv.writer(buf)
    writer.writerow(['word_id','page','column','line_idx','word_idx',
                     'crop_path','text','status'])
    for r in rows: writer.writerow(r)
    return send_file(
        io.BytesIO(buf.getvalue().encode('utf-8')),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'corrections_{SAMPLE_ID}.csv')

@app.route('/api/export/xlsx')
def export_xlsx():
    conn = init_db(DB_PATH)
    df = pd.read_sql_query("""
        SELECT word_id, page, column_idx as column, line_idx, word_idx,
               crop_path, text, status
        FROM words WHERE sample_id=?
        ORDER BY page, column, line_idx, word_idx
    """, conn, params=(SAMPLE_ID,))
    conn.close()
    out = io.BytesIO()
    df.to_excel(out, index=False, engine='openpyxl')
    out.seek(0)
    return send_file(
        out,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'corrections_{SAMPLE_ID}.xlsx')

# ==================================================
# Main
# ==================================================
def main():
    global DB_PATH, CROPS_DIR, SAMPLE_ID
    ap = argparse.ArgumentParser()
    ap.add_argument('--sample', default='S001')
    ap.add_argument('--out', default='output')
    ap.add_argument('--host', default='127.0.0.1')
    ap.add_argument('--port', type=int, default=5000)
    args = ap.parse_args()

    SAMPLE_ID = args.sample
    sample_dir = Path(args.out) / SAMPLE_ID
    DB_PATH = sample_dir / 'corrections.db'
    CROPS_DIR = sample_dir / 'crops'

    if not sample_dir.exists():
        print(f"❌ {sample_dir} غير موجود. شغّل segment.py أولاً.")
        return

    conn = init_db(DB_PATH)
    metadata_csv = sample_dir / 'metadata.csv'
    if metadata_csv.exists():
        seed_from_metadata(metadata_csv, SAMPLE_ID, conn)
    conn.close()

    print(f"\n🌐 Server ready: http://{args.host}:{args.port}")
    print(f"   Sample: {SAMPLE_ID}")
    print(f"   DB:     {DB_PATH}")
    app.run(host=args.host, port=args.port, debug=False)

if __name__ == '__main__':
    main()
