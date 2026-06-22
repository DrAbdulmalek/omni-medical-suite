-- OmniMedical Suite v2.0 Database Schema
-- This file is executed when the PostgreSQL container starts for the first time.

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Documents table
CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    original_path VARCHAR(512),
    status VARCHAR(20) DEFAULT 'uploaded',
    file_size INTEGER,
    mime_type VARCHAR(100),
    ocr_text_ar TEXT,
    ocr_text_en TEXT,
    fused_text TEXT,
    confidence_score FLOAT,
    ocr_engines_used JSONB DEFAULT '[]',
    medical_terms JSONB DEFAULT '[]',
    translated_terms JSONB DEFAULT '[]',
    processing_time FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Corrections table with context tracking
CREATE TABLE IF NOT EXISTS corrections (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    original_text TEXT NOT NULL,
    corrected_text TEXT NOT NULL,
    context TEXT,
    confidence FLOAT DEFAULT 0.0,
    auto_applied BOOLEAN DEFAULT FALSE,
    frequency INTEGER DEFAULT 1,
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    max_confidence FLOAT DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Processing tasks table
CREATE TABLE IF NOT EXISTS processing_tasks (
    id SERIAL PRIMARY KEY,
    task_id VARCHAR(100) UNIQUE NOT NULL,
    document_id INTEGER REFERENCES documents(id) ON DELETE SET NULL,
    status VARCHAR(20) DEFAULT 'pending',
    engine VARCHAR(50),
    result JSONB,
    error TEXT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- OCR engine results table
CREATE TABLE IF NOT EXISTS ocr_results (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    engine VARCHAR(50) NOT NULL,
    raw_text TEXT,
    processed_text TEXT,
    confidence FLOAT,
    processing_time FLOAT,
    bbox_data JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Medical terms table
CREATE TABLE IF NOT EXISTS medical_terms_cache (
    id SERIAL PRIMARY KEY,
    term_ar TEXT NOT NULL,
    term_en TEXT,
    category VARCHAR(100),
    frequency INTEGER DEFAULT 1,
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(term_ar)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);
CREATE INDEX IF NOT EXISTS idx_documents_created ON documents(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_corrections_document ON corrections(document_id);
CREATE INDEX IF NOT EXISTS idx_corrections_original ON corrections(original_text);
CREATE INDEX IF NOT EXISTS idx_corrections_frequency ON corrections(frequency DESC);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON processing_tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_task_id ON processing_tasks(task_id);
CREATE INDEX IF NOT EXISTS idx_ocr_results_document ON ocr_results(document_id);
CREATE INDEX IF NOT EXISTS idx_medical_terms_term ON medical_terms_cache(term_ar);
CREATE INDEX IF NOT EXISTS idx_medical_terms_category ON medical_terms_cache(category);
CREATE INDEX IF NOT EXISTS idx_documents_fused_trgm ON documents USING gin(fused_text gin_trgm_ops);

-- Views for reporting
CREATE OR REPLACE VIEW v_processing_stats AS
SELECT
    status,
    COUNT(*) as count,
    AVG(processing_time) as avg_time,
    AVG(confidence_score) as avg_confidence
FROM documents
GROUP BY status;

CREATE OR REPLACE VIEW v_top_corrections AS
SELECT
    original_text,
    corrected_text,
    frequency,
    max_confidence,
    last_seen
FROM corrections
ORDER BY frequency DESC, max_confidence DESC
LIMIT 100;

CREATE OR REPLACE VIEW v_engine_performance AS
SELECT
    engine,
    COUNT(*) as total_docs,
    AVG(confidence) as avg_confidence,
    AVG(processing_time) as avg_time
FROM ocr_results
GROUP BY engine;

-- Triggers
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE OR REPLACE TRIGGER update_documents_updated_at
    BEFORE UPDATE ON documents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE OR REPLACE FUNCTION update_correction_stats()
RETURNS TRIGGER AS $$
BEGIN
    NEW.frequency = OLD.frequency + 1;
    NEW.last_seen = CURRENT_TIMESTAMP;
    IF NEW.confidence > OLD.max_confidence THEN
        NEW.max_confidence = NEW.confidence;
    END IF;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- ============================================================
-- Dictionary Management System (Medical Dictionary Import)
-- ============================================================

-- Dictionaries registry
CREATE TABLE IF NOT EXISTS dictionaries (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    title TEXT,
    source_lang TEXT DEFAULT 'ar',
    target_lang TEXT DEFAULT 'en',
    total_entries INTEGER DEFAULT 0,
    format_version TEXT DEFAULT '1.0',
    import_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    file_path TEXT,
    file_size INTEGER DEFAULT 0,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    last_imported TIMESTAMP
);

-- Extended medical terms table (replaces old medical_terms_cache for dict management)
CREATE TABLE IF NOT EXISTS medical_terms (
    id SERIAL PRIMARY KEY,
    term_ar TEXT,
    term_en TEXT,
    definition TEXT,
    category VARCHAR(100),
    frequency INTEGER DEFAULT 1,
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    dict_id INTEGER REFERENCES dictionaries(id) ON DELETE CASCADE,
    source_entry_id INTEGER,
    CONSTRAINT unique_term UNIQUE(term_ar, term_en)
);

-- OCR corrections dictionary
CREATE TABLE IF NOT EXISTS ocr_corrections (
    id SERIAL PRIMARY KEY,
    wrong_term TEXT NOT NULL,
    correct_term TEXT NOT NULL,
    language TEXT CHECK(language IN ('ar', 'en', 'both')) DEFAULT 'ar',
    confidence FLOAT DEFAULT 0.0,
    usage_count INTEGER DEFAULT 0,
    source TEXT,
    dict_id INTEGER REFERENCES dictionaries(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used TIMESTAMP
);

-- Protected terms (prevented from spell correction)
CREATE TABLE IF NOT EXISTS protected_terms (
    id SERIAL PRIMARY KEY,
    term TEXT UNIQUE NOT NULL,
    language TEXT DEFAULT 'both',
    category TEXT,
    reason TEXT,
    dict_id INTEGER REFERENCES dictionaries(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Synonyms mapping
CREATE TABLE IF NOT EXISTS term_synonyms (
    id SERIAL PRIMARY KEY,
    term1_id INTEGER REFERENCES medical_terms(id) ON DELETE CASCADE,
    term2_id INTEGER REFERENCES medical_terms(id) ON DELETE CASCADE,
    similarity FLOAT DEFAULT 1.0
);

-- Import audit log
CREATE TABLE IF NOT EXISTS dictionary_import_log (
    id SERIAL PRIMARY KEY,
    dict_id INTEGER REFERENCES dictionaries(id) ON DELETE SET NULL,
    action TEXT NOT NULL,
    entries_processed INTEGER DEFAULT 0,
    entries_added INTEGER DEFAULT 0,
    entries_skipped INTEGER DEFAULT 0,
    errors TEXT,
    duration_ms INTEGER DEFAULT 0,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Dictionary management indexes
CREATE INDEX IF NOT EXISTS idx_medical_terms_ar ON medical_terms(term_ar) WHERE term_ar IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_medical_terms_en ON medical_terms(term_en) WHERE term_en IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_medical_terms_category ON medical_terms(category) WHERE category IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_medical_terms_frequency ON medical_terms(frequency DESC);
CREATE INDEX IF NOT EXISTS idx_medical_terms_dict ON medical_terms(dict_id);
CREATE INDEX IF NOT EXISTS idx_medical_terms_ar_trgm ON medical_terms USING gin(term_ar gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_medical_terms_en_trgm ON medical_terms USING gin(term_en gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_medical_terms_def_trgm ON medical_terms USING gin(definition gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_ocr_corrections_wrong ON ocr_corrections(wrong_term);
CREATE INDEX IF NOT EXISTS idx_ocr_corrections_correct ON ocr_corrections(correct_term);
CREATE INDEX IF NOT EXISTS idx_ocr_corrections_lang ON ocr_corrections(language);
CREATE INDEX IF NOT EXISTS idx_protected_term ON protected_terms(term);
CREATE INDEX IF NOT EXISTS idx_protected_lang ON protected_terms(language);
CREATE INDEX IF NOT EXISTS idx_dicts_active ON dictionaries(is_active);
CREATE INDEX IF NOT EXISTS idx_dict_import_log ON dictionary_import_log(timestamp DESC);

-- View: Dictionary statistics
CREATE OR REPLACE VIEW v_dictionary_stats AS
SELECT
    d.id, d.name, d.title, d.source_lang, d.target_lang,
    d.total_entries, d.import_date, d.last_imported,
    COALESCE(t.actual_count, 0) as actual_entries,
    COALESCE(c.corrections_count, 0) as corrections_count
FROM dictionaries d
LEFT JOIN (
    SELECT dict_id, COUNT(*) as actual_count FROM medical_terms GROUP BY dict_id
) t ON t.dict_id = d.id
LEFT JOIN (
    SELECT dict_id, COUNT(*) as corrections_count FROM ocr_corrections GROUP BY dict_id
) c ON c.dict_id = d.id
WHERE d.is_active = TRUE;

-- View: Category breakdown
CREATE OR REPLACE VIEW v_category_breakdown AS
SELECT
    category,
    COUNT(*) as term_count,
    AVG(frequency) as avg_frequency,
    COUNT(DISTINCT dict_id) as source_dicts
FROM medical_terms
WHERE category IS NOT NULL
GROUP BY category
ORDER BY term_count DESC;

-- Function: Update term frequency on match
CREATE OR REPLACE FUNCTION update_term_frequency()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE medical_terms
    SET frequency = frequency + 1,
        last_seen = CURRENT_TIMESTAMP
    WHERE id = NEW.id;
    RETURN NEW;
END;
$$ language 'plpgsql';
