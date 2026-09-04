-- Package O: verified-user ownership for anonymous assessments.
-- Ordinary PostgreSQL 16+. No foreign key to auth.users; CI uses
-- provider-neutral PostgreSQL and the persistence layer stays vendor-neutral.
-- Historical migrations 0001 and 0002 must remain unchanged.

ALTER TABLE assessments
    ADD COLUMN IF NOT EXISTS owner_user_id TEXT NULL;

CREATE INDEX IF NOT EXISTS assessments_owner_user_id_idx
    ON assessments (owner_user_id)
    WHERE owner_user_id IS NOT NULL;
