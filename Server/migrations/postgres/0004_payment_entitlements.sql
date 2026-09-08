-- Package P: one-time Paystack payment attempts and Readiness Report entitlement.
-- Ordinary PostgreSQL 16+. Historical migrations 0001, 0002, and 0003 must
-- remain unchanged. This table stores payment attempts, not subscriptions.

CREATE TABLE IF NOT EXISTS assessment_payments (
    payment_id TEXT PRIMARY KEY,
    assessment_id TEXT NOT NULL REFERENCES assessments (assessment_id) ON DELETE CASCADE,
    owner_user_id TEXT NOT NULL,
    product_id TEXT NOT NULL,
    billing_model TEXT NOT NULL,
    provider TEXT NOT NULL,
    provider_reference TEXT NOT NULL,
    provider_transaction_id TEXT NULL,
    amount_minor INTEGER NOT NULL,
    currency TEXT NOT NULL,
    status TEXT NOT NULL,
    authorization_url TEXT NULL,
    paid_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT assessment_payments_product_id_check
        CHECK (product_id = 'readiness_report_v1'),
    CONSTRAINT assessment_payments_billing_model_check
        CHECK (billing_model = 'one_time'),
    CONSTRAINT assessment_payments_provider_check
        CHECK (provider = 'paystack'),
    CONSTRAINT assessment_payments_amount_minor_check
        CHECK (amount_minor > 0),
    CONSTRAINT assessment_payments_v1_price_check
        CHECK (amount_minor = 15900),
    CONSTRAINT assessment_payments_currency_check
        CHECK (currency = 'ZAR'),
    CONSTRAINT assessment_payments_status_check
        CHECK (
            status IN (
                'INITIALIZING',
                'INITIALIZED',
                'INITIALIZATION_FAILED',
                'SUCCEEDED'
            )
        ),
    CONSTRAINT assessment_payments_initialized_url_check
        CHECK (
            status <> 'INITIALIZED'
            OR (authorization_url IS NOT NULL AND btrim(authorization_url) <> '')
        ),
    CONSTRAINT assessment_payments_succeeded_check
        CHECK (
            status <> 'SUCCEEDED'
            OR (
                provider_transaction_id IS NOT NULL
                AND btrim(provider_transaction_id) <> ''
                AND paid_at IS NOT NULL
            )
        )
);

CREATE UNIQUE INDEX IF NOT EXISTS assessment_payments_provider_reference_uidx
    ON assessment_payments (provider_reference);

CREATE UNIQUE INDEX IF NOT EXISTS assessment_payments_provider_transaction_id_uidx
    ON assessment_payments (provider_transaction_id)
    WHERE provider_transaction_id IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS assessment_payments_one_active_checkout_uidx
    ON assessment_payments (assessment_id, product_id)
    WHERE status IN ('INITIALIZING', 'INITIALIZED');

CREATE INDEX IF NOT EXISTS assessment_payments_assessment_id_idx
    ON assessment_payments (assessment_id);

CREATE INDEX IF NOT EXISTS assessment_payments_owner_user_id_idx
    ON assessment_payments (owner_user_id);

ALTER TABLE assessment_payments ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE assessment_payments FROM PUBLIC;

DO $$
DECLARE
    role_name TEXT;
BEGIN
    FOREACH role_name IN ARRAY ARRAY['anon', 'authenticated']
    LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = role_name) THEN
            EXECUTE format('REVOKE ALL ON TABLE assessment_payments FROM %I', role_name);
        END IF;
    END LOOP;
END;
$$;
