-- Package L: anonymous assessment persistence foundation.
-- Ordinary PostgreSQL 16+. No scoring logic lives in this schema.

CREATE OR REPLACE FUNCTION skillsignalza_reject_immutable_update()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'immutable assessment history cannot be updated'
        USING ERRCODE = 'restrict_violation';
END;
$$;

CREATE TABLE IF NOT EXISTS assessments (
    assessment_id TEXT PRIMARY KEY,
    candidate_ref TEXT NOT NULL,
    track TEXT NOT NULL,
    access_state TEXT NOT NULL DEFAULT 'PREVIEW',
    claim_token_hash CHAR(64) NULL,
    claimed_at TIMESTAMPTZ NULL,
    latest_run_id TEXT NULL,
    expires_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT assessments_track_check
        CHECK (track IN ('software_engineering', 'data_analytics')),
    CONSTRAINT assessments_access_state_check
        CHECK (access_state IN ('PREVIEW', 'UNLOCKED')),
    CONSTRAINT assessments_claim_token_hash_check
        CHECK (claim_token_hash IS NULL OR claim_token_hash ~ '^[a-f0-9]{64}$')
);

CREATE INDEX IF NOT EXISTS assessments_candidate_ref_idx ON assessments (candidate_ref);
CREATE INDEX IF NOT EXISTS assessments_created_at_idx ON assessments (created_at);
CREATE UNIQUE INDEX IF NOT EXISTS assessments_claim_token_hash_uidx
    ON assessments (claim_token_hash)
    WHERE claim_token_hash IS NOT NULL;

CREATE TABLE IF NOT EXISTS assessment_documents (
    assessment_id TEXT NOT NULL REFERENCES assessments (assessment_id) ON DELETE CASCADE,
    document_id TEXT NOT NULL,
    storage_path TEXT NOT NULL UNIQUE,
    original_filename TEXT NOT NULL,
    media_type TEXT NOT NULL,
    sha256 CHAR(64) NOT NULL,
    byte_size BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (assessment_id, document_id),
    CONSTRAINT assessment_documents_media_type_check
        CHECK (
            media_type IN (
                'application/pdf',
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            )
        ),
    CONSTRAINT assessment_documents_sha256_check
        CHECK (sha256 ~ '^[a-f0-9]{64}$'),
    CONSTRAINT assessment_documents_byte_size_check
        CHECK (byte_size > 0 AND byte_size <= 10485760)
);

CREATE TABLE IF NOT EXISTS assessment_runs (
    run_id TEXT PRIMARY KEY,
    assessment_id TEXT NOT NULL REFERENCES assessments (assessment_id) ON DELETE CASCADE,
    state TEXT NOT NULL,
    error_code TEXT NULL,
    pipeline_version TEXT NOT NULL,
    contract_version TEXT NOT NULL,
    rubric_version TEXT NOT NULL,
    track TEXT NOT NULL,
    assessment_input JSONB NOT NULL,
    scoring_context JSONB NULL,
    assessment_result JSONB NULL,
    review_flags JSONB NOT NULL,
    stages JSONB NOT NULL,
    assessed_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT assessment_runs_track_check
        CHECK (track IN ('software_engineering', 'data_analytics')),
    CONSTRAINT assessment_runs_state_check
        CHECK (
            state IN (
                'COMPLETED',
                'REVIEW_REQUIRED',
                'NOT_SCORABLE',
                'ASSESSMENT_PIPELINE_FAILED'
            )
        ),
    CONSTRAINT assessment_runs_review_flags_array_check
        CHECK (jsonb_typeof(review_flags) = 'array'),
    CONSTRAINT assessment_runs_stages_array_check
        CHECK (jsonb_typeof(stages) = 'array'),
    CONSTRAINT assessment_runs_state_consistency_check
        CHECK (
            (
                state = 'COMPLETED'
                AND error_code IS NULL
                AND assessment_result IS NOT NULL
                AND scoring_context IS NOT NULL
                AND review_flags = '[]'::jsonb
            )
            OR (
                state = 'REVIEW_REQUIRED'
                AND error_code IS NOT NULL
                AND assessment_result IS NULL
                AND scoring_context IS NOT NULL
                AND jsonb_array_length(review_flags) >= 1
            )
            OR (
                state = 'NOT_SCORABLE'
                AND error_code IS NOT NULL
                AND assessment_result IS NULL
            )
            OR (
                state = 'ASSESSMENT_PIPELINE_FAILED'
                AND error_code IS NOT NULL
                AND assessment_result IS NULL
            )
        )
);

CREATE INDEX IF NOT EXISTS assessment_runs_assessment_created_idx
    ON assessment_runs (assessment_id, created_at DESC);
CREATE INDEX IF NOT EXISTS assessment_runs_state_idx ON assessment_runs (state);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'assessments_latest_run_id_fkey'
    ) THEN
        ALTER TABLE assessments
            ADD CONSTRAINT assessments_latest_run_id_fkey
            FOREIGN KEY (latest_run_id) REFERENCES assessment_runs (run_id)
            DEFERRABLE INITIALLY DEFERRED;
    END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS assessment_sources (
    run_id TEXT NOT NULL REFERENCES assessment_runs (run_id) ON DELETE CASCADE,
    source_id TEXT NOT NULL,
    source_type TEXT NOT NULL,
    submitted_by_candidate BOOLEAN NOT NULL,
    access_status TEXT NOT NULL,
    ownership_status TEXT NOT NULL,
    retrieved_at TIMESTAMPTZ NULL,
    content_hash CHAR(64) NULL,
    extractor_version TEXT NOT NULL,
    locator TEXT NOT NULL,
    notes TEXT NULL,
    PRIMARY KEY (run_id, source_id),
    CONSTRAINT assessment_sources_source_type_check
        CHECK (
            source_type IN (
                'cv',
                'repository',
                'portfolio',
                'project',
                'deployed_project',
                'kaggle',
                'dashboard',
                'other_professional'
            )
        ),
    CONSTRAINT assessment_sources_access_status_check
        CHECK (
            access_status IN (
                'accessible',
                'inaccessible',
                'unsafe',
                'unsupported',
                'not_attempted'
            )
        ),
    CONSTRAINT assessment_sources_ownership_status_check
        CHECK (ownership_status IN ('attributed', 'unclear', 'conflicting')),
    CONSTRAINT assessment_sources_content_hash_check
        CHECK (content_hash IS NULL OR content_hash ~ '^[a-f0-9]{64}$')
);

CREATE TABLE IF NOT EXISTS assessment_evidence (
    run_id TEXT NOT NULL,
    evidence_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    locator TEXT NOT NULL,
    fact_type TEXT NOT NULL,
    subject TEXT NOT NULL,
    explicit_text TEXT NOT NULL,
    evidence_level TEXT NOT NULL,
    attribution_status TEXT NOT NULL,
    rule_id TEXT NOT NULL,
    review_status TEXT NOT NULL,
    PRIMARY KEY (run_id, evidence_id),
    CONSTRAINT assessment_evidence_source_fkey
        FOREIGN KEY (run_id, source_id)
        REFERENCES assessment_sources (run_id, source_id)
        ON DELETE CASCADE,
    CONSTRAINT assessment_evidence_fact_type_check
        CHECK (
            fact_type IN (
                'skill_name',
                'skill_application',
                'tool_name',
                'tool_application',
                'project_proof',
                'project_context',
                'project_process',
                'project_outcome',
                'qualification',
                'professional_behaviour',
                'role_alignment',
                'document_quality'
            )
        ),
    CONSTRAINT assessment_evidence_level_check
        CHECK (
            evidence_level IN (
                'demonstrated',
                'documented',
                'named_only',
                'missing_unverifiable'
            )
        ),
    CONSTRAINT assessment_evidence_attribution_check
        CHECK (attribution_status IN ('attributed', 'unclear', 'conflicting')),
    CONSTRAINT assessment_evidence_review_status_check
        CHECK (review_status = 'accepted')
);

DROP TRIGGER IF EXISTS assessment_runs_immutable_update ON assessment_runs;
CREATE TRIGGER assessment_runs_immutable_update
    BEFORE UPDATE ON assessment_runs
    FOR EACH ROW
    EXECUTE FUNCTION skillsignalza_reject_immutable_update();

DROP TRIGGER IF EXISTS assessment_sources_immutable_update ON assessment_sources;
CREATE TRIGGER assessment_sources_immutable_update
    BEFORE UPDATE ON assessment_sources
    FOR EACH ROW
    EXECUTE FUNCTION skillsignalza_reject_immutable_update();

DROP TRIGGER IF EXISTS assessment_evidence_immutable_update ON assessment_evidence;
CREATE TRIGGER assessment_evidence_immutable_update
    BEFORE UPDATE ON assessment_evidence
    FOR EACH ROW
    EXECUTE FUNCTION skillsignalza_reject_immutable_update();

ALTER TABLE assessments ENABLE ROW LEVEL SECURITY;
ALTER TABLE assessment_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE assessment_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE assessment_sources ENABLE ROW LEVEL SECURITY;
ALTER TABLE assessment_evidence ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE assessments FROM PUBLIC;
REVOKE ALL ON TABLE assessment_documents FROM PUBLIC;
REVOKE ALL ON TABLE assessment_runs FROM PUBLIC;
REVOKE ALL ON TABLE assessment_sources FROM PUBLIC;
REVOKE ALL ON TABLE assessment_evidence FROM PUBLIC;

DO $$
DECLARE
    role_name TEXT;
BEGIN
    FOREACH role_name IN ARRAY ARRAY['anon', 'authenticated']
    LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = role_name) THEN
            EXECUTE format('REVOKE ALL ON TABLE assessments FROM %I', role_name);
            EXECUTE format('REVOKE ALL ON TABLE assessment_documents FROM %I', role_name);
            EXECUTE format('REVOKE ALL ON TABLE assessment_runs FROM %I', role_name);
            EXECUTE format('REVOKE ALL ON TABLE assessment_sources FROM %I', role_name);
            EXECUTE format('REVOKE ALL ON TABLE assessment_evidence FROM %I', role_name);
        END IF;
    END LOOP;
END;
$$;
