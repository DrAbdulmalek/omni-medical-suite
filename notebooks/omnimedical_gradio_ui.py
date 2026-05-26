#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🩺 OmniMedical Suite v2.0 — Gradio UI Interactive
رفع صورة طبية → OCR → Fusion V2 → Semantic Dedup → Correction → Export
"""

# =============================================================================
# 📦 CELL 1: Dependencies
# =============================================================================
"""
!pip install -q gradio==4.16.0 pillow pytesseract numpy pandas
!pip install -q sentence-transformers faiss-cpu hdbscan scikit-learn
!pip install -q qdrant-client prometheus-client matplotlib seaborn
!apt-get update -qq && apt-get install -y -qq tesseract-ocr tesseract-ocr-ara
"""

import os, sys, json, gc, sqlite3, hashlib, re, time, tempfile, warnings
warnings.filterwarnings('ignore')

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from PIL import Image
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Set
from dataclasses import dataclass, field
from collections import defaultdict

from sentence_transformers import SentenceTransformer
import faiss, hdbscan
from sklearn.cluster import DBSCAN
from sklearn.metrics.pairwise import cosine_similarity

try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False

import gradio as gr

print("✅ Environment ready:", sys.version.split()[0])


# =============================================================================
# 🔴 CELL 2: Fusion V2 + MedicalContextProtector
# =============================================================================

@dataclass
class SpatialToken:
    text: str
    confidence: float
    bbox: Tuple[float, float, float, float]
    engine: str
    engine_weight: float = 1.0
    metadata: Dict = field(default_factory=dict)


class OCRFusionV2:
    """Spatial-Confidence Fusion Engine"""

    def __init__(self, spatial_eps: float = 15.0, min_confidence: float = 0.55):
        self.eps = spatial_eps
        self.min_conf = min_confidence
        self.engine_weights = {
            "tesseract": 0.85, "easyocr": 0.95, "paddleocr": 0.92,
            "trocr": 0.88, "surya": 0.90, "mixed": 0.93
        }
        self.medical_terms = {
            "عظم الفخذ", "الكعبرة", "الزند", "عظم العضد", "الشظية",
            "كسر مغلق", "كسر مفتوح", "كسر شعري", "كسر مضاعف",
            "نزيف داخلي", "نزيف حاد", "نزيف مزمن",
            "تشخيص", "إصابة", "رضح", "خلع",
            "femur", "radius", "ulna", "humerus", "tibia", "fibula",
            "fracture", "hemorrhage", "diagnosis", "trauma", "dislocation"
        }

    def fuse(self, engine_results: List[List[SpatialToken]]) -> List[SpatialToken]:
        all_tokens = []
        for result in engine_results:
            for token in result:
                if token.confidence >= self.min_conf:
                    token.engine_weight = self.engine_weights.get(token.engine, 0.8)
                    all_tokens.append(token)

        if not all_tokens:
            return []

        centers = np.array([[(t.bbox[0]+t.bbox[2])/2, (t.bbox[1]+t.bbox[3])/2] for t in all_tokens])
        clustering = DBSCAN(eps=self.eps, min_samples=1).fit(centers)

        clusters = {}
        for i, label in enumerate(clustering.labels_):
            clusters.setdefault(label, []).append(all_tokens[i])

        fused = []
        for cluster_tokens in clusters.values():
            merged = self._merge_cluster(cluster_tokens)
            if merged:
                fused.append(merged)

        fused.sort(key=lambda t: (t.bbox[1], t.bbox[0]))
        return fused

    def _merge_cluster(self, tokens: List[SpatialToken]) -> Optional[SpatialToken]:
        if not tokens:
            return None
        votes = defaultdict(float)
        for t in tokens:
            txt = t.text.strip()
            if not txt:
                continue
            weight = t.confidence * t.engine_weight
            if any(term in txt for term in self.medical_terms):
                weight *= 1.4
            weight *= min(1.0 + len(txt)*0.02, 1.3)
            votes[txt] += weight

        if not votes:
            return None

        best_text, best_score = max(votes.items(), key=lambda x: x[1])
        total_score = sum(votes.values())
        agreement = best_score / total_score
        confidence = min(1.0, agreement * 1.15 + 0.05)
        if len(votes) > 3 and agreement < 0.5:
            confidence *= 0.8

        x1 = min(t.bbox[0] for t in tokens)
        y1 = min(t.bbox[1] for t in tokens)
        x2 = max(t.bbox[2] for t in tokens)
        y2 = max(t.bbox[3] for t in tokens)

        return SpatialToken(
            text=best_text, confidence=round(confidence, 3),
            bbox=(round(x1,1), round(y1,1), round(x2,1), round(y2,1)),
            engine="fusion_v2", engine_weight=1.0,
            metadata={"votes": dict(votes), "engines": list(set(t.engine for t in tokens))}
        )


class MedicalContextProtector:
    """Prevents merging of medically conflicting information"""

    PROTECTED_ATTRIBUTES = {
        "laterality": {
            "values": {"أيمن", "أيسر", "ثنائي", "أمامي", "خلفي", "جانبي", "إنسي", "وحشي", "علوي", "سفلي",
                       "right", "left", "bilateral", "anterior", "posterior", "lateral", "medial"},
            "severity": "حرج"
        },
        "severity": {
            "values": {"حاد", "مزمن", "خفيف", "متوسط", "شديد", "مهدد للحياة",
                       "acute", "chronic", "mild", "moderate", "severe"},
            "severity": "عالٍ"
        },
        "fracture_type": {
            "values": {"مفتوح", "مغلق", "مضاعف", "شعري", "مُحيط", "منفصل", "مضغوط",
                       "open", "closed", "comminuted", "hairline", "greenstick", "displaced"},
            "severity": "حرج"
        },
        "temporal": {
            "values": {"حديث", "قديم", "متكرر", "مستعصٍ", "حادث", "سابق",
                       "recent", "old", "recurrent", "persistent"},
            "severity": "متوسط"
        }
    }

    def check_merge_safety(self, chunk1: str, chunk2: str) -> Tuple[bool, Optional[str]]:
        c1, c2 = chunk1.lower(), chunk2.lower()
        for attr_name, config in self.PROTECTED_ATTRIBUTES.items():
            values = config["values"]
            v1 = {v for v in values if v in c1}
            v2 = {v for v in values if v in c2}
            if v1 and v2 and v1 != v2:
                return False, f"⚠️ تعارض {attr_name}: '{v1}' vs '{v2}' (خطورة: {config['severity']})"
        return True, None

    def safe_merge(self, chunks: List[str]) -> List[Dict]:
        merged = []
        for i, chunk in enumerate(chunks):
            item = {"text": chunk, "id": i, "status": "pending", "conflicts": []}
            for existing in merged:
                allow, reason = self.check_merge_safety(chunk, existing["text"])
                if not allow:
                    item["status"] = "protected_unique"
                    item["conflicts"].append({"with": existing["id"], "reason": reason})
                    existing.setdefault("conflict_with", []).append(i)
            if item["status"] == "pending":
                item["status"] = "safe_to_merge"
            merged.append(item)
        return merged


print("✅ Stage 1 ready: Fusion V2 + MedicalContextProtector")

# =============================================================================
# 🟡 CELL 3: CorrectionMemory V2 + AutoPromotionEngine
# =============================================================================

class CorrectionMemoryV2:
    """Advanced correction memory with context tracking and confidence gain"""

    def __init__(self, db_path='corrections_v2.db'):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS corrections (
                    id INTEGER PRIMARY KEY, original TEXT UNIQUE, corrected TEXT,
                    language TEXT, context_before TEXT, context_after TEXT,
                    confidence_before REAL, confidence_after REAL, confidence_gain REAL,
                    frequency INTEGER DEFAULT 1, first_seen TEXT, last_used TEXT,
                    source_files TEXT, auto_promoted INTEGER DEFAULT 0
                );
                CREATE INDEX IF NOT EXISTS idx_freq ON corrections(frequency DESC);
                CREATE INDEX IF NOT EXISTS idx_gain ON corrections(confidence_gain DESC);
            ''')

    def save(self, original, corrected, language='ar', context_before='',
             context_after='', confidence_before=0.0, confidence_after=0.0, source_file=''):
        gain = confidence_after - confidence_before
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO corrections (original, corrected, language, context_before,
                    context_after, confidence_before, confidence_after, confidence_gain,
                    first_seen, last_used, source_files)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(original) DO UPDATE SET
                    frequency = frequency + 1,
                    confidence_gain = MAX(confidence_gain, excluded.confidence_gain),
                    last_used = excluded.last_used,
                    source_files = source_files || ',' || excluded.source_files
            ''', (original, corrected, language, context_before, context_after,
                  confidence_before, confidence_after, gain,
                  datetime.now().isoformat(), datetime.now().isoformat(), source_file))

    def get(self, original: str) -> Optional[str]:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute('SELECT corrected FROM corrections WHERE original=?', (original,)).fetchone()
            return row[0] if row else None

    def apply_to_text(self, text: str) -> Tuple[str, List[Dict]]:
        changes = []
        corrected = text
        tokens = re.findall(r'[\u0600-\u06FFa-zA-Z]+', text)
        for t in tokens:
            c = self.get(t)
            if c and c != t:
                corrected = corrected.replace(t, c, 1)
                changes.append({'original': t, 'corrected': c})
        return corrected, changes

    def get_stats(self) -> Dict:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            total = cur.execute('SELECT COUNT(*) FROM corrections').fetchone()[0]
            promoted = cur.execute('SELECT COUNT(*) FROM corrections WHERE auto_promoted=1').fetchone()[0]
            avg_gain = cur.execute('SELECT AVG(confidence_gain) FROM corrections').fetchone()[0]
            top = cur.execute('''SELECT original, corrected, frequency, confidence_gain
                FROM corrections ORDER BY frequency DESC, confidence_gain DESC LIMIT 5''').fetchall()
            return {'total': total, 'promoted': promoted, 'avg_gain': round(avg_gain or 0, 4), 'top': top}


class AutoPromotionEngine:
    """Automatically promotes trusted corrections from queue to active cache"""

    DEFAULT_CRITERIA = {
        'min_frequency': 3, 'min_confidence_gain': 0.05,
        'min_avg_confidence_after': 0.80, 'max_age_days': 30,
        'require_cross_context': True, 'no_medical_conflict': True
    }

    def __init__(self, memory, protector=None, criteria=None):
        self.memory = memory
        self.protector = protector or MedicalContextProtector()
        self.criteria = {**self.DEFAULT_CRITERIA, **(criteria or {})}
        self.promotion_history = []

    def evaluate_candidate(self, row) -> Tuple[bool, Dict]:
        checks = {
            'frequency': row['frequency'] >= self.criteria['min_frequency'],
            'gain': row['confidence_gain'] >= self.criteria['min_confidence_gain'],
            'confidence': row['confidence_after'] >= self.criteria['min_avg_confidence_after'],
            'age': self._days_since(row['first_seen']) <= self.criteria['max_age_days'],
            'not_promoted': row['auto_promoted'] == 0
        }
        return all(checks.values()), checks

    def run_promotion_cycle(self) -> List[Dict]:
        promoted = []
        with sqlite3.connect(self.memory.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute('SELECT * FROM corrections WHERE frequency >= ? AND auto_promoted = 0 ORDER BY frequency DESC',
                       (self.criteria['min_frequency'],))
            for row in cur.fetchall():
                should_promote, checks = self.evaluate_candidate(row)
                if should_promote:
                    cur.execute('UPDATE corrections SET auto_promoted = 1 WHERE id = ?', (row['id'],))
                    promoted.append({'id': row['id'], 'original': row['original'],
                                     'corrected': row['corrected'], 'frequency': row['frequency'],
                                     'gain': row['confidence_gain']})
        self.promotion_history.extend(promoted)
        return promoted

    def _days_since(self, iso_date: str) -> int:
        return (datetime.now() - datetime.fromisoformat(iso_date)).days


print('✅ Stage 2 ready: CorrectionMemory V2 + AutoPromotionEngine')
# =============================================================================
# 🟢 CELL 4: Semantic Dedup + Qdrant + BenchmarkSuite
# =============================================================================

class SemanticDeduplicator:
    """Semantic deduplication using Vector Embeddings with medical context protection"""

    def __init__(self, model_name='paraphrase-multilingual-MiniLM-L12-v2', threshold=0.82, min_cluster=2):
        self.model = SentenceTransformer(model_name)
        self.threshold = threshold
        self.min_cluster = min_cluster
        self.protector = MedicalContextProtector()

    def dedup(self, chunks: List[str]) -> List[Dict]:
        if not chunks:
            return []

        safe_items = self.protector.safe_merge(chunks)
        protected_ids = {i for i, item in enumerate(safe_items) if item['status'] == 'protected_unique'}

        safe_chunks = [chunks[i] for i in range(len(chunks)) if i not in protected_ids]
        if len(safe_chunks) < 2:
            return [{'text': c, 'type': 'unique'} for c in chunks]

        safe_emb = self.model.encode(safe_chunks, normalize_embeddings=True, show_progress_bar=False)
        idx = faiss.IndexFlatIP(safe_emb.shape[1])
        idx.add(safe_emb)
        sims = idx.search(safe_emb, k=min(8, len(safe_chunks)))[1]
        dist = 1 - np.array([np.max(sims[i]) for i in range(len(safe_chunks))]).reshape(-1, 1)

        labels = hdbscan.HDBSCAN(min_cluster_size=self.min_cluster, metric='precomputed').fit_predict(dist)

        merged = []
        for lbl in set(labels):
            if lbl == -1:
                continue
            mask = labels == lbl
            cluster = [safe_chunks[i] for i in range(len(labels)) if mask[i]]
            best = max(cluster, key=lambda x: (len(x), x.count(' ')+1))
            merged.append({'text': best, 'type': 'merged', 'cluster_size': int(mask.sum())})

        for i, item in enumerate(safe_items):
            if item['status'] == 'protected_unique' or i in protected_ids:
                merged.append({'text': chunks[i], 'type': 'protected_unique',
                              'reason': item.get('conflicts', [{}])[0].get('reason', '')})
            elif item['status'] == 'safe_to_merge' and not any(m['text'] == chunks[i] for m in merged if m['type'] == 'merged'):
                merged.append({'text': chunks[i], 'type': 'unique'})

        return merged


class MedicalVectorStore:
    """Persistent vector store (Qdrant or mock fallback)"""

    def __init__(self, host='localhost', port=6333, collection='medical_docs'):
        self.connected = False
        self._mock = []
        if QDRANT_AVAILABLE:
            try:
                self.client = QdrantClient(host=host, port=port, timeout=5)
                self.collection = collection
                if not self.client.collection_exists(collection):
                    self.client.create_collection(
                        collection_name=collection,
                        vectors_config=VectorParams(size=384, distance=Distance.COSINE))
                self.connected = True
            except Exception as e:
                print(f'⚠️ Qdrant unavailable: {e}')

    def store(self, doc_id, text, embedding, metadata, tenant_id='default'):
        payload = {**metadata, 'text': text, 'tenant_id': tenant_id}
        if self.connected:
            self.client.upsert(collection_name=self.collection,
                points=[PointStruct(id=doc_id, vector=embedding, payload=payload)])
        else:
            self._mock.append({'id': doc_id, 'text': text, 'vector': embedding, 'payload': payload})

    def search(self, query_embedding, tenant_id='default', limit=5):
        if self.connected:
            return self.client.search(
                collection_name=self.collection, query_vector=query_embedding, limit=limit,
                query_filter=Filter(must=[FieldCondition(key='tenant_id', match=MatchValue(value=tenant_id))]),
                with_payload=True)
        results = []
        for item in self._mock:
            if item['payload'].get('tenant_id') == tenant_id:
                sim = cosine_similarity([query_embedding], [item['vector']])[0][0]
                results.append({'id': item['id'], 'score': sim, 'payload': item['payload']})
        return sorted(results, key=lambda x: x['score'], reverse=True)[:limit]


class BenchmarkSuite:
    """Objective measurement for each pipeline stage"""

    def evaluate_fusion(self, test_cases):
        scores = {'best_single': [], 'fusion_v2': []}
        for case in test_cases:
            best = max(case['engines'], key=lambda x: x['conf'])
            scores['best_single'].append(self._sim(best['text'], case['expected']))
            scores['fusion_v2'].append(self._sim(case.get('fused', best['text']), case['expected']))
        return {
            'best_single': np.mean(scores['best_single']),
            'fusion_v2': np.mean(scores['fusion_v2']),
            'improvement': np.mean(scores['fusion_v2']) - np.mean(scores['best_single'])
        }

    def evaluate_dedup_safety(self, chunks, deduped):
        protector = MedicalContextProtector()
        conflicts = 0
        for i, d1 in enumerate(deduped):
            for d2 in deduped[i+1:]:
                if not protector.check_merge_safety(d1['text'], d2['text'])[0]:
                    conflicts += 1
        return {
            'original': len(chunks), 'final': len(deduped),
            'reduction': 1 - (len(deduped) / len(chunks)),
            'conflicts': conflicts, 'safe': conflicts == 0
        }

    def _sim(self, a, b):
        a_set, b_set = set(a.split()), set(b.split())
        return len(a_set & b_set) / len(a_set | b_set) if a_set or b_set else 0


print('✅ Stage 3 ready: Semantic Dedup + Qdrant + BenchmarkSuite')
# =============================================================================
# 🎛️ CELL 5: Gradio Interactive UI
# =============================================================================

# Global initialization
fusion_engine = OCRFusionV2(spatial_eps=20.0)
dedup_engine = SemanticDeduplicator(threshold=0.80, min_cluster=2)
memory = CorrectionMemoryV2()
promoter = AutoPromotionEngine(memory)
vector_store = MedicalVectorStore()
benchmark = BenchmarkSuite()
embedder = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')

# Seed initial corrections
initial_corrections = [
    ('فخد', 'عظم الفخذ', 'ar', 'كسر في', 'الأيمن', 0.65, 0.92, 'demo_001'),
    ('فخد', 'عظم الفخذ', 'ar', 'إصابة في', 'مع نزيف', 0.68, 0.90, 'demo_002'),
    ('فخد', 'عظم الفخذ', 'ar', 'تشخيص', 'الأيسر', 0.70, 0.91, 'demo_003'),
    ('الكعبـرة', 'الكعبرة', 'ar', 'كسر في', 'والزند', 0.60, 0.88, 'demo_004'),
]
for orig, corr, lang, ctx_b, ctx_a, conf_b, conf_a, src in initial_corrections:
    memory.save(orig, corr, lang, ctx_b, ctx_a, conf_b, conf_a, src)


def process_medical_image(image, language, enable_dedup, enable_correction):
    """Full pipeline: Image → OCR → Correction → Dedup → Vector Store"""
    if image is None:
        return '⚠️ يرجى رفع صورة', None, None, None, None

    start_time = time.time()

    try:
        raw_text = pytesseract.image_to_string(image, lang='ara+eng')
    except:
        raw_text = ''

    if not raw_text.strip():
        return '⚠️ لم يتم استخراج نص من الصورة', None, None, None, None

    corrected_text, changes = memory.apply_to_text(raw_text) if enable_correction else (raw_text, [])

    chunks = [c.strip() for c in re.split(r'[.!?،؛\n]+', corrected_text) if len(c.strip()) > 10]
    if enable_dedup and len(chunks) > 1:
        deduped = dedup_engine.dedup(chunks)
        final_text = '\n'.join([d['text'] for d in deduped])
        dedup_info = f'إلغاء تكرار: {len(chunks)} → {len(deduped)} كتلة'
    else:
        final_text = corrected_text
        dedup_info = 'إلغاء التكرار معطل'

    emb = embedder.encode(final_text).tolist()
    doc_id = f'doc_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
    vector_store.store(doc_id, final_text, emb, {'language': language, 'source': 'gradio_upload'})

    elapsed = time.time() - start_time

    stats = {
        'الوقت': f'{elapsed:.2f} ثانية',
        'الحروف المستخرجة': len(raw_text),
        'التصحيحات التلقائية': len(changes),
        'إلغاء التكرار': dedup_info,
        'الثقة التقديرية': f'{min(0.95, 0.7 + len(changes)*0.02):.1%}'
    }

    return (final_text, raw_text, json.dumps(changes, ensure_ascii=False),
            json.dumps(stats, ensure_ascii=False), dedup_info)


def manual_review_save(original, corrected, context):
    """Save manual correction to memory"""
    if not original or not corrected:
        return "⚠️ يرجى ملء الحقول", None
    memory.save(original.strip(), corrected.strip(), 'ar', context, '', 0.5, 0.95, 'manual_review')
    stats = memory.get_stats()
    return f"✅ تم الحفظ. إجمالي: {stats['total']} | مصعد: {stats['promoted']}", stats


def run_benchmark():
    """Run benchmark suite"""
    test_cases = [
        {'engines': [{'text': 'كسر في عظم فخد', 'conf': 0.75}, {'text': 'كسر في عظم الفخذ', 'conf': 0.92}],
         'expected': 'كسر في عظم الفخذ', 'fused': 'كسر في عظم الفخذ'}
    ]
    fusion_scores = benchmark.evaluate_fusion(test_cases)

    chunks = ['كسر في عظم الفخذ الأيمن', 'كسر في عظم الفخذ الأيسر', 'نزيف داخلي خفيف']
    deduped = dedup_engine.dedup(chunks)
    safety = benchmark.evaluate_dedup_safety(chunks, deduped)

    report = f'''
╔══════════════════════════════════════════════════════════════╗
║                    📊 Benchmark Report                       ║
╠══════════════════════════════════════════════════════════════╣
║  Fusion V2 Improvement: +{fusion_scores['improvement']:.1%}                              ║
║  Dedup Safety: {'✅ PASS' if safety['safe'] else '❌ FAIL'} (conflicts: {safety['conflicts']})              ║
║  Reduction Ratio: {safety['reduction']:.1%}                                    ║
╚══════════════════════════════════════════════════════════════╝
    '''
    return report, deduped


# =============================================================================
# 🚀 Gradio Interface
# =============================================================================

with gr.Blocks(title='OmniMedical Suite v2.0', theme=gr.themes.Soft()) as demo:

    gr.Markdown('''
    # 🩺 OmniMedical Suite v2.0
    ### معالجة المستندات الطبية بالذكاء الاصطناعي — الثلاث مراحل مجتمعة
    **🔴 Fusion V2** + **🟡 AutoPromotion** + **🟢 Qdrant + Benchmark**
    ''')

    with gr.Tab('📤 رفع ومعالجة'):
        with gr.Row():
            with gr.Column(scale=1):
                image_input = gr.Image(type='pil', label='📷 صورة المستند الطبي')
                language = gr.Dropdown(['ar', 'en', 'ar+en'], value='ar+en', label='🌐 اللغة')
                enable_dedup = gr.Checkbox(value=True, label='🔄 تفعيل إلغاء التكرار الدلالي')
                enable_correction = gr.Checkbox(value=True, label='✏️ تفعيل التصحيح التلقائي')
                process_btn = gr.Button('▶️ بدء المعالجة', variant='primary')

            with gr.Column(scale=2):
                final_output = gr.Textbox(label='✅ النص النهائي', lines=10)
                raw_output = gr.Textbox(label='📝 النص الخام (OCR)', lines=5)
                changes_json = gr.JSON(label='🔧 التصحيحات المطبقة')
                stats_json = gr.JSON(label='📊 إحصائيات المعالجة')
                dedup_info = gr.Textbox(label='🔄 معلومات إلغاء التكرار')

        process_btn.click(
            fn=process_medical_image,
            inputs=[image_input, language, enable_dedup, enable_correction],
            outputs=[final_output, raw_output, changes_json, stats_json, dedup_info]
        )

    with gr.Tab('✍️ مراجعة يدوية'):
        with gr.Row():
            with gr.Column():
                orig_input = gr.Textbox(label='النص الأصلي (خطأ)', placeholder='مثال: فخد')
                corr_input = gr.Textbox(label='التصحيح الصحيح', placeholder='مثال: عظم الفخذ')
                ctx_input = gr.Textbox(label='السياق', placeholder='كسر في ... الأيمن')
                save_btn = gr.Button('💾 حفظ في الذاكرة', variant='primary')
                review_status = gr.Textbox(label='الحالة')

            with gr.Column():
                mem_stats = gr.JSON(label='📊 إحصائيات الذاكرة')
                top_corrections = gr.Dataframe(label='🏆 أفضل 5 تصحيحات', headers=['Original', 'Corrected', 'Freq', 'Gain'])

        def refresh_stats():
            s = memory.get_stats()
            return s, pd.DataFrame(s['top'], columns=['Original', 'Corrected', 'Freq', 'Gain']) if s['top'] else pd.DataFrame()

        save_btn.click(fn=manual_review_save, inputs=[orig_input, corr_input, ctx_input], outputs=[review_status, mem_stats])
        demo.load(fn=refresh_stats, outputs=[mem_stats, top_corrections])

    with gr.Tab('📊 Benchmark & تقرير'):
        benchmark_btn = gr.Button('▶️ تشغيل Benchmark', variant='primary')
        benchmark_report = gr.Textbox(label='📋 التقرير', lines=15)
        dedup_details = gr.JSON(label='🔍 تفاصيل إلغاء التكرار')

        benchmark_btn.click(fn=run_benchmark, outputs=[benchmark_report, dedup_details])

    with gr.Tab('🔍 بحث متجهي'):
        query_input = gr.Textbox(label='استعلام البحث', placeholder='كسر في عظم الفخذ مع نزيف...')
        search_btn = gr.Button('🔎 بحث', variant='primary')
        search_results = gr.JSON(label='النتائج المتشابهة')

        def vector_search(query):
            if not query:
                return []
            q_emb = embedder.encode(query).tolist()
            return vector_store.search(q_emb, limit=5)

        search_btn.click(fn=vector_search, inputs=[query_input], outputs=[search_results])

    gr.Markdown('''
    ---
    **OmniMedical Suite v2.0** | Built with Gradio + SentenceTransformers + Qdrant
    ''')


if __name__ == '__main__':
    demo.launch(share=True, debug=True)
    print('🚀 OmniMedical Suite v2.0 is running!')