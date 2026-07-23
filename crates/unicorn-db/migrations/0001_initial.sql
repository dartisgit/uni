-- Initial schema for Unicorn's persistence layer.
--
-- Table shapes mirror unicorn_core::models one-to-one where practical, so
-- mapping between a Postgres row and a Rust struct in unicorn-db's query
-- functions stays mechanical. Where a model field doesn't map cleanly
-- (e.g. Vec<u64> membership lists), it's normalized into its own table
-- instead of stored as an array, since relational integrity (a deleted
-- user disappearing from every org's member list automatically) matters
-- more here than matching the in-memory struct shape exactly.

CREATE TABLE users (
    id              BIGSERIAL PRIMARY KEY,
    username        TEXT NOT NULL UNIQUE,
    email           TEXT NOT NULL UNIQUE,
    is_admin        BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE organizations (
    id              BIGSERIAL PRIMARY KEY,
    name            TEXT NOT NULL UNIQUE,
    display_name    TEXT NOT NULL
);

CREATE TABLE organization_members (
    organization_id BIGINT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id         BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    PRIMARY KEY (organization_id, user_id)
);

CREATE TABLE repositories (
    id              BIGSERIAL PRIMARY KEY,
    owner           TEXT NOT NULL,
    name            TEXT NOT NULL,
    description     TEXT,
    default_branch  TEXT NOT NULL DEFAULT 'main',
    is_private      BOOLEAN NOT NULL DEFAULT FALSE,
    is_bare         BOOLEAN NOT NULL DEFAULT TRUE,
    star_count      INTEGER NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (owner, name)
);

-- The table SSH auth actually reads from. `fingerprint` is the SHA-256
-- form ("SHA256:...") that unicorn_ssh::auth::fingerprint_of produces and
-- ssh-keygen -l prints, so a value copied from either place matches
-- directly with no reformatting. `UNIQUE` here already gives Postgres an
-- index for the fingerprint lookup every SSH connection does - no
-- separate CREATE INDEX needed, that would just be a second identical
-- index costing extra write overhead for no read benefit.
CREATE TABLE ssh_keys (
    id              BIGSERIAL PRIMARY KEY,
    owner_id        BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    fingerprint     TEXT NOT NULL UNIQUE,
    algorithm       TEXT NOT NULL,
    added_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE webhooks (
    id              BIGSERIAL PRIMARY KEY,
    repository_id   BIGINT NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    target_url      TEXT NOT NULL,
    events          TEXT[] NOT NULL DEFAULT '{}',
    active          BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE action_runs (
    id              BIGSERIAL PRIMARY KEY,
    repository_id   BIGINT NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
    workflow_name   TEXT NOT NULL,
    status          TEXT NOT NULL CHECK (status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')),
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at     TIMESTAMPTZ
);

CREATE TABLE audit_log_entries (
    id              BIGSERIAL PRIMARY KEY,
    actor           TEXT NOT NULL,
    action          TEXT NOT NULL,
    target          TEXT NOT NULL,
    at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_audit_log_at ON audit_log_entries (at DESC);
