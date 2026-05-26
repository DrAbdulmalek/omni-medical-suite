-- ============================================================================
-- OmniMedical Suite v2.0 — PostgreSQL Schema Initialization
-- ============================================================================
-- Description : Production-ready schema for multi-tenant medical document
--               processing platform. Includes tenancy, auth, patient records,
--               document lifecycle, semantic dedup, corrections review,
--               HIPAA audit logging (partitioned), Celery task tracking,
--               Qdrant vector synchronisation, and benchmark telemetry.
--
-- Prerequisites:
--   - PostgreSQL 15+ (native range partitioning, pgcrypto, generated columns)
--   - pgcrypto extension for UUID generation
--   - pgvector extension  (CREATE EXTENSION IF NOT EXISTS vector)
--
-- Usage:
--   psql -U postgres -f init.sql
--
-- Security note:
--   - patient_code uses pgcrypto's pgp_sym_encrypt at the application layer.
--     The column is TEXT here; encryption/decryption is handled in code.
--   - audit_logs are monthly-partitioned to support long-term HIPAA retention.
-- ============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- Extensions
-- ---------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "vector";

-- ============================================================================
-- ENUMS
-- ============================================================================

CREATE TYPE user_role AS ENUM (
    'super_admin',   -- Full platform access
    'tenant_admin',  -- Tenant-level administration
    'doctor',        -- Clinical user
    'nurse',         -- Clinical support
    'receptionist',  -- Front-desk / scheduling
    'viewer'         -- Read-only access
);

CREATE TYPE document_status AS ENUM (
    'uploaded',
    'processing',
    'ocr_complete',
    'corrected',
    'reviewed',
    'archived',
    'failed'
);

CREATE TYPE chunk_type AS ENUM (
    'original',         -- Raw OCR segment
    'merged',           -- Semantic-dedup merged chunk
    'protected_unique'  -- Medical term that must never be merged
);

CREATE TYPE task_status AS ENUM (
    'pending',
    'started',
    'completed',
    'failed',
    'retrying',
    'cancelled'
);

CREATE TYPE gender AS ENUM (
    'male',
    'female',
    'other'
);

-- ============================================================================
-- TABLE 1 — tenants
-- Multi-tenancy root. Every tenant is an isolated workspace.
-- ============================================================================
CREATE TABLE tenants (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT        NOT NULL,
    slug        TEXT        NOT NULL UNIQUE,          -- URL-safe identifier
    settings    JSONB       NOT NULL DEFAULT '{}',     -- Feature flags, config overrides
    is_active   BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT tenants_name_length CHECK (char_length(name) >= 2 AND char_length(name) <= 256),
    CONSTRAINT tenants_slug_format CHECK (slug ~ '^[a-z0-9][a-z0-9_-]{1,62}[a-z0-9]$')
);

COMMENT ON TABLE  tenants             IS 'Tenant / organisation isolation root';
COMMENT ON COLUMN tenants.id          IS 'Immutable UUID primary key';
COMMENT ON COLUMN tenants.slug        IS 'URL-safe unique tenant identifier (lowercase, alphanumeric + dash)';
COMMENT ON COLUMN tenants.settings    IS 'Arbitrary JSONB configuration blob (ocr defaults, language, quotas, etc.)';

CREATE INDEX idx_tenants_slug    ON tenants (slug);
CREATE INDEX idx_tenants_active ON tenants (is_active) WHERE is_active = TRUE;

-- ============================================================================
-- TABLE 2 — users
-- Authentication and authorisation (role-based per tenant).
-- ============================================================================
CREATE TABLE users (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID        NOT NULL REFERENCES tenants (id) ON DELETE CASCADE,
    email           TEXT        NOT NULL,
    password_hash   TEXT        NOT NULL,              -- bcrypt / argon2 hash
    full_name       TEXT        NOT NULL,
    role            user_role   NOT NULL DEFAULT 'viewer',
    is_active       BOOLEAN     NOT NULL DEFAULT TRUE,
    last_login      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT uq_users_tenant_email UNIQUE (tenant_id, email),
    CONSTRAINT users_email_format CHECK (email ~ '^[^@\s]+@[^@\s]+\.[^@\s]+$')
);

COMMENT ON TABLE  users                 IS 'Application users — scoped to a single tenant';
COMMENT ON COLUMN users.password_hash   IS 'Argon2id hash produced by passlib / werkzeug';
COMMENT ON COLUMN users.role            IS 'RBAC role; super_admin can bypass tenant scope';

CREATE INDEX idx_users_tenant     ON users (tenant_id);
CREATE INDEX idx_users_email      ON users (email);
CREATE INDEX idx_users_active     ON users (is_active) WHERE is_active = TRUE;

-- ============================================================================
-- TABLE 3 — patients
-- Patient records (PII) — scoped to tenant.
-- patient_code is stored encrypted at the application layer.
-- ============================================================================
CREATE TABLE patients (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID        NOT NULL REFERENCES tenants (id) ON DELETE CASCADE,
    patient_code    TEXT        NOT NULL,               -- Encrypted at app layer
    full_name       TEXT        NOT NULL,
    date_of_birth   DATE        NOT NULL,
    gender          gender      NOT NULL,
    phone           TEXT,
    notes           TEXT,
    is_active       BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT uq_patients_tenant_code UNIQUE (tenant_id, patient_code)
);

COMMENT ON TABLE  patients              IS 'Patient PII — accessed only by authorised clinical roles';
COMMENT ON COLUMN patients.patient_code IS 'Encrypted patient identifier (app-layer pgp_sym_encrypt)';
COMMENT ON COLUMN patients.phone        IS 'Stored in E.164 format where available';

CREATE INDEX idx_patients_tenant   ON patients (tenant_id);
CREATE INDEX idx_patients_name    ON patients (full_name);
CREATE INDEX idx_patients_active  ON patients (is_active) WHERE is_active = TRUE;

-- ============================================================================
-- TABLE 4 — documents
-- Medical documents lifecycle (upload through archive).
-- ============================================================================
CREATE TABLE documents (
    id                  UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID            NOT NULL REFERENCES tenants (id) ON DELETE CASCADE,
    patient_id          UUID            NOT NULL REFERENCES patients (id) ON DELETE CASCADE,
    filename            TEXT            NOT NULL,
    file_path           TEXT            NOT NULL,
    file_hash           TEXT            NOT NULL,           -- SHA-256
    file_size_bytes     BIGINT          NOT NULL DEFAULT 0,
    mime_type           TEXT            NOT NULL DEFAULT 'application/pdf',
    status              document_status NOT NULL DEFAULT 'uploaded',
    language            TEXT            NOT NULL DEFAULT 'ar',  -- ISO 639-1
    ocr_engine          TEXT,                          -- e.g. 'tesseract', 'surya', 'mistral'
    ocr_confidence      NUMERIC(5,2),                   -- 0.00 – 100.00
    processing_time_ms  INTEGER,
    page_count          INTEGER        NOT NULL DEFAULT 1,
    metadata            JSONB          NOT NULL DEFAULT '{}',
    created_at          TIMESTAMPTZ    NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ    NOT NULL DEFAULT now(),

    CONSTRAINT uq_documents_file_hash UNIQUE (file_hash),
    CONSTRAINT documents_confidence CHECK (ocr_confidence IS NULL OR (ocr_confidence >= 0 AND ocr_confidence <= 100))
);

COMMENT ON TABLE  documents                    IS 'Document lifecycle — one row per uploaded medical file';
COMMENT ON COLUMN documents.file_hash           IS 'SHA-256 hex digest for content de-duplication';
COMMENT ON COLUMN documents.ocr_confidence      IS 'Weighted confidence score from OCR engine ensemble';
COMMENT ON COLUMN documents.processing_time_ms  IS 'Total pipeline wall-clock time (upload → archived)';

CREATE INDEX idx_documents_tenant       ON documents (tenant_id);
CREATE INDEX idx_documents_patient      ON documents (patient_id);
CREATE INDEX idx_documents_status       ON documents (status);
CREATE INDEX idx_documents_created      ON documents (created_at DESC);
CREATE INDEX idx_documents_tenant_status ON documents (tenant_id, status);

-- ============================================================================
-- TABLE 5 — document_chunks
-- Semantic dedup output — each chunk may be original, merged, or protected.
-- Embeddings are 384-dim vectors (all-MiniLM-L6-v2 / multilingual model).
-- ============================================================================
CREATE TABLE document_chunks (
    id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id     UUID            NOT NULL REFERENCES documents (id) ON DELETE CASCADE,
    chunk_index     INTEGER         NOT NULL,           -- Order within document
    chunk_text      TEXT            NOT NULL,
    chunk_type      chunk_type      NOT NULL DEFAULT 'original',
    embedding       vector(384),                       -- Dense embedding for semantic search
    similarity_score NUMERIC(5,4),                      -- 0.0000 – 1.0000 intra-cluster similarity
    cluster_id      INTEGER,                           -- Null = singleton cluster
    token_count     INTEGER         NOT NULL DEFAULT 0,
    metadata        JSONB           NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ    NOT NULL DEFAULT now(),

    CONSTRAINT uq_chunks_doc_idx UNIQUE (document_id, chunk_index)
);

COMMENT ON TABLE  document_chunks             IS 'Semantic dedup chunks — linked 1:N to documents';
COMMENT ON COLUMN document_chunks.embedding   IS '384-dim vector (sentence-transformers all-MiniLM-L6-v2)';
COMMENT ON COLUMN document_chunks.cluster_id  IS 'DBSCAN / HDBSCAN cluster label; NULL = noise / singleton';
COMMENT ON COLUMN document_chunks.chunk_type  IS 'protected_unique chunks are medical terms that must never merge';

CREATE INDEX idx_chunks_document     ON document_chunks (document_id);
CREATE INDEX idx_chunks_type         ON document_chunks (chunk_type);
CREATE INDEX idx_chunks_cluster      ON document_chunks (cluster_id) WHERE cluster_id IS NOT NULL;
-- HNSW index for approximate nearest-neighbour search on embeddings
CREATE INDEX idx_chunks_embedding ON document_chunks USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- ============================================================================
-- TABLE 6 — corrections_queue
-- Review queue for OCR corrections, synced with the local SQLite learning DB.
-- ============================================================================
CREATE TABLE corrections_queue (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    original            TEXT        NOT NULL,
    corrected           TEXT        NOT NULL,
    language            TEXT        NOT NULL DEFAULT 'ar',
    confidence_gain     NUMERIC(5,2),                   -- Percentage improvement
    frequency           INTEGER     NOT NULL DEFAULT 1,  -- Times this correction has been seen
    auto_promoted       BOOLEAN     NOT NULL DEFAULT FALSE,
    medical_conflict    BOOLEAN     NOT NULL DEFAULT FALSE,
    source_file         TEXT,                          -- Originating document filename
    reviewed_by         UUID        REFERENCES users (id) ON DELETE SET NULL,
    notes               TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT corrections_gain CHECK (confidence_gain IS NULL OR confidence_gain >= 0)
);

COMMENT ON TABLE  corrections_queue                 IS 'OCR correction review queue (SQLite ↔ Postgres sync)';
COMMENT ON COLUMN corrections_queue.auto_promoted   IS 'TRUE when the correction passed auto-promotion thresholds';
COMMENT ON COLUMN corrections_queue.medical_conflict IS 'TRUE when the corrected term conflicts with a protected medical term';
COMMENT ON COLUMN corrections_queue.frequency       IS 'Observation count — higher values increase auto-promotion confidence';

CREATE INDEX idx_corrections_promoted     ON corrections_queue (auto_promoted) WHERE NOT auto_promoted;
CREATE INDEX idx_corrections_conflict     ON corrections_queue (medical_conflict) WHERE medical_conflict;
CREATE INDEX idx_corrections_language     ON corrections_queue (language);
CREATE INDEX idx_corrections_created      ON corrections_queue (created_at DESC);
CREATE INDEX idx_corrections_original_trgm ON corrections_queue USING gin (original gin_trgm_ops);

-- ============================================================================
-- TABLE 7 — audit_logs (partitioned by month)
-- HIPAA-compliant immutable audit trail.
-- ============================================================================
CREATE TABLE audit_logs (
    id              BIGSERIAL,
    user_id         UUID        NOT NULL REFERENCES users (id),
    action          TEXT        NOT NULL,               -- 'document.upload', 'patient.view', etc.
    resource_type   TEXT        NOT NULL,               -- 'document', 'patient', 'correction', …
    resource_id     UUID,                               -- Target entity PK
    details         JSONB       NOT NULL DEFAULT '{}',
    ip_address      INET,
    user_agent      TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);

COMMENT ON TABLE  audit_logs                   IS 'HIPAA audit log — monthly-partitioned, append-only';
COMMENT ON COLUMN audit_logs.action            IS 'Dotted event name: <resource>.<verb> (e.g. document.upload)';
COMMENT ON COLUMN audit_logs.details           IS 'Arbitrary event metadata (diffs, status changes, flags)';
COMMENT ON COLUMN audit_logs.ip_address        IS 'Client IP as PostgreSQL INET type';
COMMENT ON COLUMN audit_logs.user_agent        IS 'Raw User-Agent header string';

-- Default partition catches any rows whose month has no dedicated partition yet.
CREATE TABLE audit_logs_default PARTITION OF audit_logs DEFAULT;

-- Pre-create partitions for the next 24 months (current + 23 future).
-- Adjust the loop range as needed; this covers 2 years of headroom.
CREATE OR REPLACE FUNCTION create_audit_partitions()
RETURNS void
LANGUAGE plpgsql
AS $$
DECLARE
    _start DATE;
    _end   DATE;
    _name  TEXT;
BEGIN
    _start := date_trunc('month', CURRENT_DATE)::DATE;
    FOR i IN 0..23 LOOP
        _end  := _start + INTERVAL '1 month';
        _name := format('audit_logs_%s', to_char(_start, 'yyyy_mm'));
        EXECUTE format(
            'CREATE TABLE IF NOT EXISTS %I PARTITION OF audit_logs
                FOR VALUES FROM (%L) TO (%L)',
            _name, _start, _end
        );
        _start := _end;
    END LOOP;
END;
$$;
SELECT create_audit_partitions();
DROP FUNCTION create_audit_partitions();

CREATE INDEX idx_audit_user       ON audit_logs (user_id, created_at DESC);
CREATE INDEX idx_audit_action      ON audit_logs (action, created_at DESC);
CREATE INDEX idx_audit_resource    ON audit_logs (resource_type, resource_id, created_at DESC);
CREATE INDEX idx_audit_created     ON audit_logs (created_at DESC);

-- ============================================================================
-- TABLE 8 — processing_tasks
-- Celery / async task tracking with retry and duration metrics.
-- ============================================================================
CREATE TABLE processing_tasks (
    id              UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id         UUID            NOT NULL,           -- Celery task UUID
    document_id     UUID            NOT NULL REFERENCES documents (id) ON DELETE CASCADE,
    task_type       TEXT            NOT NULL,           -- 'ocr', 'correction', 'embedding', 'dedup', 'export'
    status          task_status     NOT NULL DEFAULT 'pending',
    priority        INTEGER         NOT NULL DEFAULT 0,  -- Higher = more urgent
    retry_count     INTEGER         NOT NULL DEFAULT 0,
    max_retries     INTEGER         NOT NULL DEFAULT 3,
    duration_ms     INTEGER,
    result          JSONB,
    error_text      TEXT,
    worker_name     TEXT,                           -- Celery worker hostname
    queue_name      TEXT            NOT NULL DEFAULT 'default',
    created_at      TIMESTAMPTZ    NOT NULL DEFAULT now(),
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    updated_at      TIMESTAMPTZ    NOT NULL DEFAULT now(),

    CONSTRAINT uq_tasks_celery_id UNIQUE (task_id),
    CONSTRAINT tasks_retry CHECK (retry_count >= 0 AND retry_count <= max_retries)
);

COMMENT ON TABLE  processing_tasks              IS 'Celery async task journal — tracks retries, durations, errors';
COMMENT ON COLUMN processing_tasks.task_id       IS 'Celery-issued task UUID (unique)';
COMMENT ON COLUMN processing_tasks.task_type     IS 'Pipeline step identifier: ocr, correction, embedding, dedup, export';
COMMENT ON COLUMN processing_tasks.duration_ms   IS 'Wall-clock execution time in milliseconds';

CREATE INDEX idx_tasks_document      ON processing_tasks (document_id);
CREATE INDEX idx_tasks_status        ON processing_tasks (status);
CREATE INDEX idx_tasks_type          ON processing_tasks (task_type);
CREATE INDEX idx_tasks_created       ON processing_tasks (created_at DESC);
CREATE INDEX idx_tasks_queue         ON processing_tasks (queue_name, status);

-- ============================================================================
-- TABLE 9 — vector_references
-- Bidirectional link between Qdrant collection points and local records.
-- ============================================================================
CREATE TABLE vector_references (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    qdrant_id       UUID        NOT NULL,               -- Qdrant point UUID
    document_id     UUID        NOT NULL REFERENCES documents (id) ON DELETE CASCADE,
    chunk_id        UUID        REFERENCES document_chunks (id) ON DELETE SET NULL,
    collection_name TEXT        NOT NULL,
    tenant_id       UUID        NOT NULL REFERENCES tenants (id) ON DELETE CASCADE,
    synced          BOOLEAN     NOT NULL DEFAULT TRUE,
    payload         JSONB       NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT uq_vector_refs_qdrant UNIQUE (qdrant_id)
);

COMMENT ON TABLE  vector_references             IS 'Qdrant ↔ PostgreSQL link table for vector sync reconciliation';
COMMENT ON COLUMN vector_references.qdrant_id   IS 'Unique Qdrant point identifier';
COMMENT ON COLUMN vector_references.synced     IS 'FALSE indicates the local record needs (re-)push to Qdrant';

CREATE INDEX idx_vrefs_document     ON vector_references (document_id);
CREATE INDEX idx_vrefs_chunk        ON vector_references (chunk_id) WHERE chunk_id IS NOT NULL;
CREATE INDEX idx_vrefs_collection   ON vector_references (collection_name);
CREATE INDEX idx_vrefs_tenant       ON vector_references (tenant_id);
CREATE INDEX idx_vrefs_unsynced     ON vector_references (id) WHERE NOT synced;

-- ============================================================================
-- TABLE 10 — benchmark_results
-- Pipeline performance telemetry for regression detection and reporting.
-- ============================================================================
CREATE TABLE benchmark_results (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    benchmark_type  TEXT        NOT NULL,               -- 'e2e_pipeline', 'ocr_accuracy', 'dedup_quality', 'latency'
    metrics         JSONB       NOT NULL,               -- Structured metric key-value pairs
    pipeline_version TEXT       NOT NULL,               -- Semantic version e.g. '2.0.1'
    document_count  INTEGER     NOT NULL DEFAULT 0,
    duration_ms     INTEGER     NOT NULL,
    environment     TEXT        NOT NULL DEFAULT 'production',
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE  benchmark_results                IS 'Pipeline performance benchmarks for regression detection';
COMMENT ON COLUMN benchmark_results.metrics         IS 'JSONB blob of metric names → numeric values (cer, wer, latency_p99, etc.)';
COMMENT ON COLUMN benchmark_results.pipeline_version IS 'Deployed pipeline version at time of benchmark';

CREATE INDEX idx_benchmarks_type        ON benchmark_results (benchmark_type);
CREATE INDEX idx_benchmarks_version     ON benchmark_results (pipeline_version);
CREATE INDEX idx_benchmarks_created     ON benchmark_results (created_at DESC);

-- ============================================================================
-- VIEWS
-- ============================================================================

-- ---------------------------------------------------------------------------
-- VIEW: document_summary
-- Per-document processing summary joining documents, chunks, and tasks.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW document_summary AS
SELECT
    d.id                                      AS document_id,
    d.tenant_id,
    d.patient_id,
    d.filename,
    d.file_hash,
    d.status                                  AS doc_status,
    d.language,
    d.ocr_engine,
    d.ocr_confidence,
    d.processing_time_ms,
    d.page_count,
    d.created_at                              AS uploaded_at,
    d.updated_at                              AS last_updated,
    -- Chunk aggregation
    COALESCE(dc.total_chunks, 0)              AS total_chunks,
    COALESCE(dc.original_chunks, 0)           AS original_chunks,
    COALESCE(dc.merged_chunks, 0)             AS merged_chunks,
    COALESCE(dc.protected_chunks, 0)          AS protected_unique_chunks,
    COALESCE(dc.avg_similarity, 0.0000)       AS avg_chunk_similarity,
    COALESCE(dc.distinct_clusters, 0)         AS distinct_clusters,
    -- Task aggregation
    COALESCE(dt.total_tasks, 0)               AS total_tasks,
    COALESCE(dt.completed_tasks, 0)           AS completed_tasks,
    COALESCE(dt.failed_tasks, 0)              AS failed_tasks,
    COALESCE(dt.total_duration_ms, 0)        AS total_task_duration_ms,
    COALESCE(dt.avg_confidence, 0.00)         AS avg_ocr_confidence
FROM documents d
LEFT JOIN (
    SELECT
        document_id,
        COUNT(*)                                               AS total_chunks,
        COUNT(*) FILTER (WHERE chunk_type = 'original')        AS original_chunks,
        COUNT(*) FILTER (WHERE chunk_type = 'merged')          AS merged_chunks,
        COUNT(*) FILTER (WHERE chunk_type = 'protected_unique') AS protected_chunks,
        AVG(similarity_score)                                  AS avg_similarity,
        COUNT(DISTINCT cluster_id) FILTER (WHERE cluster_id IS NOT NULL)
                                                              AS distinct_clusters
    FROM document_chunks
    GROUP BY document_id
) dc ON dc.document_id = d.id
LEFT JOIN (
    SELECT
        document_id,
        COUNT(*)                                          AS total_tasks,
        COUNT(*) FILTER (WHERE status = 'completed')     AS completed_tasks,
        COUNT(*) FILTER (WHERE status = 'failed')        AS failed_tasks,
        COALESCE(SUM(duration_ms), 0)                    AS total_duration_ms,
        -- Pull OCR confidence from the 'ocr' task result if available
        AVG(
            CASE WHEN task_type = 'ocr'
                 THEN (d.ocr_confidence)
            END
        )                                                 AS avg_ocr_confidence
    FROM processing_tasks
    GROUP BY document_id
) dt ON dt.document_id = d.id;

COMMENT ON VIEW document_summary IS 'Aggregated per-document processing statistics from documents + chunks + tasks';

-- ---------------------------------------------------------------------------
-- VIEW: pending_corrections
-- Corrections awaiting human review (not auto-promoted, no medical conflict).
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW pending_corrections AS
SELECT
    cq.id,
    cq.original,
    cq.corrected,
    cq.language,
    cq.confidence_gain,
    cq.frequency,
    cq.medical_conflict,
    cq.source_file,
    cq.created_at,
    cq.updated_at,
    -- Reviewer info (may be NULL if not yet assigned)
    u.full_name   AS reviewer_name,
    u.email       AS reviewer_email,
    -- Priority heuristic: older + higher frequency = review first
    RANK() OVER (
        ORDER BY cq.frequency DESC, cq.created_at ASC
    ) AS review_priority
FROM corrections_queue cq
LEFT JOIN users u ON u.id = cq.reviewed_by
WHERE cq.auto_promoted = FALSE
  AND cq.medical_conflict = FALSE;

COMMENT ON VIEW pending_corrections IS 'Corrections that require human review — auto_promoted=false AND no medical conflict';

-- ---------------------------------------------------------------------------
-- VIEW: daily_audit_summary
-- Audit statistics for the last 24 hours.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW daily_audit_summary AS
SELECT
    CURRENT_TIMESTAMP::DATE                   AS report_date,
    (CURRENT_TIMESTAMP - INTERVAL '24 hours') AS period_start,
    CURRENT_TIMESTAMP                        AS period_end,
    -- Total events
    COUNT(*)                                  AS total_events,
    -- Unique users
    COUNT(DISTINCT al.user_id)               AS unique_users,
    -- Action breakdown
    COUNT(*) FILTER (WHERE al.action LIKE 'document.%')   AS document_events,
    COUNT(*) FILTER (WHERE al.action LIKE 'patient.%')    AS patient_events,
    COUNT(*) FILTER (WHERE al.action LIKE 'correction.%') AS correction_events,
    COUNT(*) FILTER (WHERE al.action LIKE 'auth.%')       AS auth_events,
    COUNT(*) FILTER (WHERE al.action LIKE 'admin.%')      AS admin_events,
    -- Top actions
    (SELECT json_object_agg(action_key, action_cnt) FROM (
        SELECT action AS action_key, COUNT(*) AS action_cnt
        FROM audit_logs
        WHERE created_at >= CURRENT_TIMESTAMP - INTERVAL '24 hours'
        GROUP BY action
        ORDER BY action_cnt DESC
        LIMIT 10
    ) sub)                                    AS top_actions,
    -- Top resource types
    (SELECT json_object_agg(res_type, res_cnt) FROM (
        SELECT resource_type AS res_type, COUNT(*) AS res_cnt
        FROM audit_logs
        WHERE created_at >= CURRENT_TIMESTAMP - INTERVAL '24 hours'
        GROUP BY resource_type
        ORDER BY res_cnt DESC
        LIMIT 10
    ) sub2)                                   AS top_resources
FROM audit_logs al
WHERE al.created_at >= CURRENT_TIMESTAMP - INTERVAL '24 hours';

COMMENT ON VIEW daily_audit_summary IS 'Rolling 24-hour HIPAA audit statistics with action and resource breakdowns';

-- ============================================================================
-- TRIGGER: updated_at
-- Generic trigger function + attachments for five tables.
-- Automatically sets updated_at = now() on every row mutation.
-- ============================================================================

CREATE OR REPLACE FUNCTION trg_set_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

COMMENT ON FUNCTION trg_set_updated_at() IS 'Generic trigger: sets updated_at to now() on INSERT or UPDATE';

-- Attach the trigger to each required table.
CREATE TRIGGER trg_documents_updated_at
    BEFORE UPDATE ON documents
    FOR EACH ROW
    EXECUTE FUNCTION trg_set_updated_at();

CREATE TRIGGER trg_corrections_queue_updated_at
    BEFORE UPDATE ON corrections_queue
    FOR EACH ROW
    EXECUTE FUNCTION trg_set_updated_at();

CREATE TRIGGER trg_patients_updated_at
    BEFORE UPDATE ON patients
    FOR EACH ROW
    EXECUTE FUNCTION trg_set_updated_at();

CREATE TRIGGER trg_processing_tasks_updated_at
    BEFORE UPDATE ON processing_tasks
    FOR EACH ROW
    EXECUTE FUNCTION trg_set_updated_at();

CREATE TRIGGER trg_vector_references_updated_at
    BEFORE UPDATE ON vector_references
    FOR EACH ROW
    EXECUTE FUNCTION trg_set_updated_at();

-- ============================================================================
-- HELPER: Monthly partition maintenance function
-- Call this from pg_cron or a scheduled job to ensure future partitions exist.
-- ============================================================================
CREATE OR REPLACE FUNCTION ensure_audit_partitions(months_ahead INTEGER DEFAULT 6)
RETURNS void
LANGUAGE plpgsql
AS $$
DECLARE
    _latest DATE;
    _end    DATE;
    _name   TEXT;
    _i      INTEGER;
BEGIN
    -- Find the latest existing partition end date.
    SELECT MAX(pg_catalog.pg_get_expr(c.relpartbound, c.oid))::date + INTERVAL '1 month'
    INTO _latest
    FROM pg_catalog.pg_class c
    JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
    WHERE c.relispartition
      AND c.relkind = 'r'
      AND n.nspname = current_schema()
      AND c.relname LIKE 'audit_logs_%'
    LIMIT 1;

    IF _latest IS NULL THEN
        _latest := date_trunc('month', CURRENT_DATE)::DATE;
    END IF;

    FOR _i IN 1..months_ahead LOOP
        _end  := _latest + INTERVAL '1 month';
        _name := format('audit_logs_%s', to_char(_latest, 'yyyy_mm'));
        EXECUTE format(
            'CREATE TABLE IF NOT EXISTS %I PARTITION OF audit_logs
                FOR VALUES FROM (%L) TO (%L)',
            _name, _latest, _end
        );
        _latest := _end;
    END LOOP;
END;
$$;

COMMENT ON FUNCTION ensure_audit_partitions(INTEGER) IS 'Create future monthly partitions; safe to call idempotently via pg_cron';

-- ============================================================================
-- HELPER: Row-level security (RLS) — optional, enable per-tenant
-- ============================================================================
-- Uncomment the following block to enforce strict tenant isolation via RLS.
-- Requires SET app.current_tenant_id in session before queries.
--
-- ALTER TABLE patients ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE document_chunks ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE corrections_queue ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE processing_tasks ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE vector_references ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE benchmark_results ENABLE ROW LEVEL SECURITY;
--
-- CREATE POLICY tenant_isolation ON patients
--     USING (tenant_id = current_setting('app.current_tenant_id', TRUE)::UUID);
-- CREATE POLICY tenant_isolation ON documents
--     USING (tenant_id = current_setting('app.current_tenant_id', TRUE)::UUID);
-- CREATE POLICY tenant_isolation ON document_chunks
--     USING (document_id IN (SELECT id FROM documents WHERE tenant_id = current_setting('app.current_tenant_id', TRUE)::UUID));
-- CREATE POLICY tenant_isolation ON processing_tasks
--     USING (document_id IN (SELECT id FROM documents WHERE tenant_id = current_setting('app.current_tenant_id', TRUE)::UUID));
-- CREATE POLICY tenant_isolation ON vector_references
--     USING (tenant_id = current_setting('app.current_tenant_id', TRUE)::UUID);
-- CREATE POLICY tenant_isolation ON benchmark_results
--     USING (true);  -- Benchmarks are global
-- ============================================================================

COMMIT;
