-- =============================================================================
-- BilingualExtractor - Database Schema
-- Medical Arabic-English Parallel Corpus Database
-- =============================================================================
-- Compatible with: PostgreSQL 15+, MySQL 8+, SQLite 3.35+
-- =============================================================================

-- =============================================================================
-- 1. CORE TABLES
-- =============================================================================

-- Domain/medical field categories
CREATE TABLE IF NOT EXISTS medical_domains (
    domain_id        SERIAL PRIMARY KEY,
    domain_name_en   VARCHAR(100) NOT NULL UNIQUE,
    domain_name_ar   VARCHAR(100) NOT NULL UNIQUE,
    description_en   TEXT,
    description_ar   TEXT,
    parent_domain_id INTEGER REFERENCES medical_domains(domain_id),
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Source textbooks/documents
CREATE TABLE IF NOT EXISTS source_documents (
    doc_id           SERIAL PRIMARY KEY,
    title_en         VARCHAR(500) NOT NULL,
    title_ar         VARCHAR(500) NOT NULL,
    author           VARCHAR(200),
    publisher        VARCHAR(200),
    year_published   INTEGER,
    isbn            VARCHAR(20),
    language         VARCHAR(10) DEFAULT 'bilingual',
    domain_id        INTEGER REFERENCES medical_domains(domain_id),
    total_pages      INTEGER DEFAULT 0,
    file_path        VARCHAR(1000),
    file_hash        VARCHAR(64),
    ocr_quality     DECIMAL(3,2) CHECK (ocr_quality BETWEEN 0 AND 1),
    notes            TEXT,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_source_doc_file_hash UNIQUE (file_hash)
);

-- Pages within a source document
CREATE TABLE IF NOT EXISTS document_pages (
    page_id          SERIAL PRIMARY KEY,
    doc_id           INTEGER NOT NULL REFERENCES source_documents(doc_id) ON DELETE CASCADE,
    page_number      INTEGER NOT NULL,
    page_type        VARCHAR(20) DEFAULT 'content'
                     CHECK (page_type IN ('content', 'glossary', 'index', 'references', 'appendix')),
    text_ar          TEXT,
    text_en          TEXT,
    text_mixed       TEXT,
    char_count_ar    INTEGER DEFAULT 0,
    char_count_en    INTEGER DEFAULT 0,
    word_count_ar    INTEGER DEFAULT 0,
    word_count_en    INTEGER DEFAULT 0,
    ocr_errors_count INTEGER DEFAULT 0,
    has_figures      BOOLEAN DEFAULT FALSE,
    has_tables       BOOLEAN DEFAULT FALSE,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_doc_page UNIQUE (doc_id, page_number)
);

-- =============================================================================
-- 2. TERM EXTRACTION TABLES
-- =============================================================================

-- Extracted Arabic terms
CREATE TABLE IF NOT EXISTS arabic_terms (
    term_id          SERIAL PRIMARY KEY,
    term_text        VARCHAR(500) NOT NULL,
    term_normalized  VARCHAR(500) NOT NULL,
    stem             VARCHAR(200),
    term_length      INTEGER NOT NULL,
    domain_id        INTEGER REFERENCES medical_domains(domain_id),
    frequency        INTEGER DEFAULT 1,
    document_freq    INTEGER DEFAULT 1,
    is_verified      BOOLEAN DEFAULT FALSE,
    verified_by      VARCHAR(100),
    verified_at      TIMESTAMP,
    dialect_variants  JSONB,
    historical_evolution JSONB,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_ar_term_normalized UNIQUE (term_normalized)
);

-- Extracted English terms
CREATE TABLE IF NOT EXISTS english_terms (
    term_id          SERIAL PRIMARY KEY,
    term_text        VARCHAR(500) NOT NULL,
    term_normalized  VARCHAR(500) NOT NULL,
    stem             VARCHAR(200),
    term_length      INTEGER NOT NULL,
    domain_id        INTEGER REFERENCES medical_domains(domain_id),
    frequency        INTEGER DEFAULT 1,
    document_freq    INTEGER DEFAULT 1,
    is_verified      BOOLEAN DEFAULT FALSE,
    verified_by      VARCHAR(100),
    verified_at      TIMESTAMP,
    variants         JSONB,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_en_term_normalized UNIQUE (term_normalized)
);

-- Bilingual term pairs (mapping table)
CREATE TABLE IF NOT EXISTS term_pairs (
    pair_id          SERIAL PRIMARY KEY,
    arabic_term_id   INTEGER NOT NULL REFERENCES arabic_terms(term_id) ON DELETE CASCADE,
    english_term_id  INTEGER NOT NULL REFERENCES english_terms(term_id) ON DELETE CASCADE,
    confidence       DECIMAL(5,4) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    extraction_method VARCHAR(30) DEFAULT 'pattern'
                     CHECK (extraction_method IN ('pattern', 'morphological', 'statistical', 'manual', 'alignment')),
    frequency        INTEGER DEFAULT 1,
    co_occurrence_score DECIMAL(5,4),
    source_doc_id    INTEGER REFERENCES source_documents(doc_id),
    source_page_id   INTEGER REFERENCES document_pages(page_id),
    context_ar       TEXT,
    context_en       TEXT,
    is_verified      BOOLEAN DEFAULT FALSE,
    verified_by      VARCHAR(100),
    verified_at      TIMESTAMP,
    notes            TEXT,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_term_pair UNIQUE (arabic_term_id, english_term_id)
);

-- Term extraction occurrences (where each term was found)
CREATE TABLE IF NOT EXISTS term_occurrences (
    occurrence_id    SERIAL PRIMARY KEY,
    arabic_term_id   INTEGER REFERENCES arabic_terms(term_id) ON DELETE CASCADE,
    english_term_id  INTEGER REFERENCES english_terms(term_id) ON DELETE CASCADE,
    pair_id          INTEGER REFERENCES term_pairs(pair_id) ON DELETE SET NULL,
    page_id          INTEGER REFERENCES document_pages(page_id) ON DELETE CASCADE,
    position_ar      INTEGER,
    position_en      INTEGER,
    sentence_context_ar TEXT,
    sentence_context_en TEXT,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =============================================================================
-- 3. SENTENCE ALIGNMENT TABLES
-- =============================================================================

-- Aligned sentences
CREATE TABLE IF NOT EXISTS sentence_alignments (
    alignment_id     SERIAL PRIMARY KEY,
    doc_id           INTEGER NOT NULL REFERENCES source_documents(doc_id) ON DELETE CASCADE,
    source_page_id   INTEGER REFERENCES document_pages(page_id),
    sentence_ar      TEXT NOT NULL,
    sentence_en      TEXT NOT NULL,
    alignment_type   VARCHAR(10) DEFAULT '1:1'
                     CHECK (alignment_type IN ('1:1', '1:N', 'N:1', 'N:M')),
    confidence       DECIMAL(5,4) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    alignment_method VARCHAR(30) DEFAULT 'vector'
                     CHECK (alignment_method IN ('vector', 'length', 'dictionary', 'hybrid', 'manual')),
    vector_similarity DECIMAL(5,4),
    length_ratio     DECIMAL(5,4),
    dictionary_score DECIMAL(5,4),
    sentence_length_ar INTEGER,
    sentence_length_en INTEGER,
    word_count_ar    INTEGER,
    word_count_en    INTEGER,
    position_ar      INTEGER,
    position_en      INTEGER,
    is_verified      BOOLEAN DEFAULT FALSE,
    verified_by      VARCHAR(100),
    verified_at      TIMESTAMP,
    quality_score    DECIMAL(5,4),
    notes            TEXT,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =============================================================================
-- 4. WORD ALIGNMENT TABLES
-- =============================================================================

-- Aligned words within sentences
CREATE TABLE IF NOT EXISTS word_alignments (
    word_align_id    SERIAL PRIMARY KEY,
    alignment_id     INTEGER NOT NULL REFERENCES sentence_alignments(alignment_id) ON DELETE CASCADE,
    word_ar          VARCHAR(200) NOT NULL,
    word_en          VARCHAR(200) NOT NULL,
    position_ar      INTEGER NOT NULL,
    position_en      INTEGER NOT NULL,
    alignment_type   VARCHAR(10) DEFAULT '1:1'
                     CHECK (alignment_type IN ('1:1', '1:N', 'N:1', 'NULL:1', '1:NULL')),
    confidence       DECIMAL(5,4) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    alignment_score  DECIMAL(5,4),
    is_named_entity  BOOLEAN DEFAULT FALSE,
    ner_type_ar      VARCHAR(30),
    ner_type_en      VARCHAR(30),
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =============================================================================
-- 5. QUALITY & EVALUATION TABLES
-- =============================================================================

-- Quality assessment records
CREATE TABLE IF NOT EXISTS quality_assessments (
    assessment_id    SERIAL PRIMARY KEY,
    target_type      VARCHAR(20) NOT NULL
                     CHECK (target_type IN ('term_pair', 'sentence', 'word', 'document')),
    target_id        INTEGER NOT NULL,
    quality_score    DECIMAL(5,4) NOT NULL CHECK (quality_score BETWEEN 0 AND 1),
    fluency_ar       DECIMAL(5,4),
    fluency_en       DECIMAL(5,4),
    adequacy         DECIMAL(5,4),
    completeness     DECIMAL(5,4),
    terminology_accuracy DECIMAL(5,4),
    grammar_quality  DECIMAL(5,4),
    assessment_method VARCHAR(30)
                     CHECK (assessment_method IN ('automatic', 'manual', 'hybrid')),
    model_used       VARCHAR(100),
    assessor         VARCHAR(100),
    notes            TEXT,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Human review/annotation records
CREATE TABLE IF NOT EXISTS human_reviews (
    review_id        SERIAL PRIMARY KEY,
    target_type      VARCHAR(20) NOT NULL
                     CHECK (target_type IN ('term_pair', 'sentence', 'word')),
    target_id        INTEGER NOT NULL,
    reviewer         VARCHAR(100) NOT NULL,
    review_status    VARCHAR(20) DEFAULT 'pending'
                     CHECK (review_status IN ('pending', 'approved', 'rejected', 'modified', 'flagged')),
    rating           INTEGER CHECK (rating BETWEEN 1 AND 5),
    correction_ar    TEXT,
    correction_en    TEXT,
    correction_notes TEXT,
    reviewed_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =============================================================================
-- 6. EXPORT & PUBLISHING TABLES
-- =============================================================================

-- Export job records
CREATE TABLE IF NOT EXISTS export_jobs (
    export_id        SERIAL PRIMARY KEY,
    job_name         VARCHAR(200),
    export_format    VARCHAR(20) NOT NULL
                     CHECK (export_format IN ('csv', 'tsv', 'json', 'tmx', 'xlsx', 'sqlite', 'mongodb')),
    target_domain   INTEGER REFERENCES medical_domains(domain_id),
    target_doc_id    INTEGER REFERENCES source_documents(doc_id),
    filters          JSONB,
    total_records    INTEGER DEFAULT 0,
    file_path        VARCHAR(1000),
    file_size_bytes  BIGINT DEFAULT 0,
    status           VARCHAR(20) DEFAULT 'pending'
                     CHECK (status IN ('pending', 'running', 'completed', 'failed')),
    error_message    TEXT,
    started_at       TIMESTAMP,
    completed_at     TIMESTAMP,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Corpus versioning
CREATE TABLE IF NOT EXISTS corpus_versions (
    version_id       SERIAL PRIMARY KEY,
    version_number   VARCHAR(20) NOT NULL UNIQUE,
    version_name     VARCHAR(200),
    description      TEXT,
    total_terms      INTEGER DEFAULT 0,
    total_sentences  INTEGER DEFAULT 0,
    total_word_alignments INTEGER DEFAULT 0,
    changes          JSONB,
    created_by       VARCHAR(100),
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_current       BOOLEAN DEFAULT FALSE
);

-- =============================================================================
-- 7. INDEXES FOR PERFORMANCE
-- =============================================================================

CREATE INDEX idx_source_docs_domain ON source_documents(domain_id);
CREATE INDEX idx_source_docs_year ON source_documents(year_published);
CREATE INDEX idx_doc_pages_doc_id ON document_pages(doc_id);
CREATE INDEX idx_doc_pages_page_num ON document_pages(doc_id, page_number);
CREATE INDEX idx_ar_terms_domain ON arabic_terms(domain_id);
CREATE INDEX idx_ar_terms_freq ON arabic_terms(frequency);
CREATE INDEX idx_ar_terms_normalized ON arabic_terms(term_normalized);
CREATE INDEX idx_ar_terms_verified ON arabic_terms(is_verified);
CREATE INDEX idx_en_terms_domain ON english_terms(domain_id);
CREATE INDEX idx_en_terms_freq ON english_terms(frequency);
CREATE INDEX idx_en_terms_normalized ON english_terms(term_normalized);
CREATE INDEX idx_en_terms_verified ON english_terms(is_verified);
CREATE INDEX idx_term_pairs_ar ON term_pairs(arabic_term_id);
CREATE INDEX idx_term_pairs_en ON term_pairs(english_term_id);
CREATE INDEX idx_term_pairs_confidence ON term_pairs(confidence);
CREATE INDEX idx_term_pairs_method ON term_pairs(extraction_method);
CREATE INDEX idx_term_pairs_verified ON term_pairs(is_verified);
CREATE INDEX idx_term_pairs_doc ON term_pairs(source_doc_id);
CREATE INDEX idx_sent_align_doc ON sentence_alignments(doc_id);
CREATE INDEX idx_sent_align_confidence ON sentence_alignments(confidence);
CREATE INDEX idx_sent_align_method ON sentence_alignments(alignment_method);
CREATE INDEX idx_sent_align_quality ON sentence_alignments(quality_score);
CREATE INDEX idx_word_align_sent ON word_alignments(alignment_id);
CREATE INDEX idx_word_align_confidence ON word_alignments(confidence);
CREATE INDEX idx_quality_target ON quality_assessments(target_type, target_id);
CREATE INDEX idx_reviews_target ON human_reviews(target_type, target_id);
CREATE INDEX idx_reviews_status ON human_reviews(review_status);
CREATE INDEX idx_export_status ON export_jobs(status);

-- =============================================================================
-- 8. VIEWS FOR COMMON QUERIES
-- =============================================================================

CREATE OR REPLACE VIEW v_term_pairs_full AS
SELECT
    tp.pair_id,
    at.term_text AS arabic_term,
    et.term_text AS english_term,
    at.term_normalized AS arabic_normalized,
    et.term_normalized AS english_normalized,
    tp.confidence,
    tp.extraction_method,
    tp.frequency,
    md.domain_name_en AS domain,
    sd.title_en AS source_document,
    dp.page_number AS source_page,
    tp.context_ar,
    tp.context_en,
    tp.is_verified,
    CASE
        WHEN tp.confidence >= 0.7 THEN 'high'
        WHEN tp.confidence >= 0.4 THEN 'medium'
        ELSE 'low'
    END AS confidence_level,
    tp.created_at
FROM term_pairs tp
JOIN arabic_terms at ON tp.arabic_term_id = at.term_id
JOIN english_terms et ON tp.english_term_id = et.term_id
LEFT JOIN medical_domains md ON at.domain_id = md.domain_id
LEFT JOIN source_documents sd ON tp.source_doc_id = sd.doc_id
LEFT JOIN document_pages dp ON tp.source_page_id = dp.page_id;

CREATE OR REPLACE VIEW v_domain_statistics AS
SELECT
    md.domain_name_en,
    md.domain_name_ar,
    COUNT(DISTINCT tp.pair_id) AS total_term_pairs,
    AVG(tp.confidence) AS avg_term_confidence,
    COUNT(DISTINCT sd.doc_id) AS total_documents,
    SUM(CASE WHEN tp.confidence >= 0.7 THEN 1 ELSE 0 END) AS high_confidence_terms
FROM medical_domains md
LEFT JOIN arabic_terms at ON at.domain_id = md.domain_id
LEFT JOIN term_pairs tp ON tp.arabic_term_id = at.term_id
LEFT JOIN source_documents sd ON sd.domain_id = md.domain_id
GROUP BY md.domain_id, md.domain_name_en, md.domain_name_ar;

-- =============================================================================
-- 9. SEED DATA
-- =============================================================================

INSERT INTO medical_domains (domain_name_en, domain_name_ar, description_en, description_ar) VALUES
('Orthopedics', 'جراحة العظام', 'Musculoskeletal system surgery and conditions', 'جراحة وأمراض الجهاز العضلي الهيكلي'),
('Internal Medicine', 'الباطنة', 'Diagnosis and treatment of adult diseases', 'تشخيص وعلاج أمراض البالغين'),
('Surgery', 'الجراحة', 'Surgical procedures and operations', 'الإجراءات والعمليات الجراحية'),
('Cardiology', 'أمراض القلب', 'Heart and cardiovascular diseases', 'أمراض القلب والأوعية الدموية'),
('Neurology', 'الأعصاب', 'Nervous system disorders', 'اضطرابات الجهاز العصبي'),
('Pediatrics', 'طب الأطفال', 'Medical care for infants and children', 'الرعاية الطبية للرضع والأطفال'),
('Radiology', 'الأشعة', 'Medical imaging and diagnostics', 'التصوير الطبي والتشخيص'),
('Pathology', 'علم الأمراض', 'Study of disease causes and effects', 'دراسة أسباب الأمراض وتأثيراتها'),
('Anatomy', 'التشريح', 'Study of body structure', 'دراسة بنية الجسم'),
('Pharmacology', 'علم الأدوية', 'Study of drugs and medications', 'دراسة الأدوية والعقاقير');

-- =============================================================================
-- END OF SCHEMA
-- =============================================================================
