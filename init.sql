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
