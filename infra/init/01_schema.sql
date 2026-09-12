-- WhichCloud schema, applied on first `docker compose up`.

CREATE EXTENSION IF NOT EXISTS vector;

-- Ingested provider pricing. One row per SKU per region.
-- Refreshed by a scheduled job; the engine only ever reads this table.
CREATE TABLE IF NOT EXISTS price_points (
    id          BIGSERIAL PRIMARY KEY,
    provider    TEXT        NOT NULL,          -- aws | azure | gcp
    category    TEXT        NOT NULL,          -- compute | database | storage | network
    sku         TEXT        NOT NULL,          -- t4g.medium, Standard_B2s
    name        TEXT        NOT NULL,
    region      TEXT        NOT NULL,          -- provider's own code
    unit        TEXT        NOT NULL,          -- hour | GB-month | request
    price_usd   NUMERIC(18, 8) NOT NULL CHECK (price_usd >= 0),

    vcpu        INTEGER,
    memory_gb   REAL,
    arch        TEXT,                          -- x86_64 | arm64

    attributes  JSONB       NOT NULL DEFAULT '{}'::jsonb,
    fetched_at  TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (provider, region, sku, unit)
);

-- The engine's hot path: "cheapest thing meeting these specs, in this region".
CREATE INDEX IF NOT EXISTS idx_price_compute_lookup
    ON price_points (region, category, vcpu, memory_gb, price_usd)
    WHERE category = 'compute';

CREATE INDEX IF NOT EXISTS idx_price_provider_region
    ON price_points (provider, region, category);

-- Knowledge base: one row per optimization technique, mirrored from the YAML
-- files in knowledge-base/techniques/ so RAG can retrieve over it.
CREATE TABLE IF NOT EXISTS techniques (
    id            TEXT PRIMARY KEY,            -- matches the YAML `id`
    name          TEXT NOT NULL,
    category      TEXT NOT NULL,
    summary       TEXT NOT NULL,
    typical_pct   REAL,
    confidence    TEXT,
    obviousness   TEXT,
    providers     TEXT[]  NOT NULL DEFAULT '{}',
    spec          JSONB   NOT NULL,            -- the full YAML document
    embedding     vector(1024),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_techniques_embedding
    ON techniques USING hnsw (embedding vector_cosine_ops);

-- Extracted architectures, keyed by what produced them.
--
-- A model asked the same question twice does not reliably answer the same
-- way. Measured on one description at temperature 0: three runs gave 23, 22
-- and 23 nodes, with 48, 32 and 48 edges. Greedy decoding is not reproducible
-- serving, and no provider guarantees it is.
--
-- That is fatal for this product in a way it would not be for a chatbot: a
-- user re-opening their own saved architecture must see the same system they
-- saw yesterday, or nothing built on top of it -- a diagram, a cost, a
-- Terraform file -- can be trusted to mean anything.
--
-- So the first answer is kept and reused. The key covers the model and schema
-- version as well as the text, so changing either produces a new extraction
-- rather than silently serving one made under different rules.
CREATE TABLE IF NOT EXISTS architecture_cache (
    key           TEXT PRIMARY KEY,            -- sha256(description|reader|model|schema)
    description   TEXT NOT NULL,
    reader        TEXT NOT NULL,
    model         TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    payload       JSONB NOT NULL,              -- the Architecture, as returned
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Architectures someone chose to keep.
--
-- Distinct from architecture_cache, which is keyed by the text and shared by
-- everyone who describes the same system. This is a person saying "this one
-- is mine, let me back into it" -- so it is keyed by owner and carries a name
-- they gave it.
--
-- The description is stored rather than the drawn result. The cache turns a
-- description back into the same architecture, so keeping the geometry too
-- would be a second copy that could drift from the first. What is saved is
-- the question; the answer is looked up.
CREATE TABLE IF NOT EXISTS saved_architectures (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner       TEXT NOT NULL,               -- the identity provider's user id
    title       TEXT NOT NULL,
    description TEXT NOT NULL,
    services    INTEGER NOT NULL DEFAULT 0,  -- for the list, without redrawing
    regions     INTEGER NOT NULL DEFAULT 1,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_saved_owner
    ON saved_architectures (owner, created_at DESC);

-- Extracted constraints, keyed by the prompt text.
--
-- Same reasoning as architecture_cache, applied to the other half of the
-- pipeline. Extraction moved from phrase tables to a language model because
-- the tables refused 85% of real phrasings (tests/probes/classifier_accuracy.md),
-- and a model is the right tool for reading text. But a model asked the same
-- question twice does not reliably answer the same way, and "the numbers are
-- computed, not guessed" is this project's whole claim.
--
-- So the claim is split rather than weakened: the DECISION layer is fully
-- deterministic given a Constraints object, and EXTRACTION is made
-- reproducible by keeping the first answer. Two separately measurable
-- statements instead of one blanket one.
CREATE TABLE IF NOT EXISTS constraints_cache (
    key            TEXT PRIMARY KEY,           -- sha256(prompt|model|schema)
    description    TEXT NOT NULL,
    reader         TEXT NOT NULL,
    model          TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    payload        JSONB NOT NULL,             -- the extraction, as returned
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── Connected cloud accounts ─────────────────────────────────────────
--
-- A billing CSV is something a person can read before they hand it over.
-- A connection is standing access to their account, which is a different
-- kind of trust, so the shape of what is stored matters more than usual:
--
--   AWS    role ARN + external id. No keys. We call AssumeRole.
--   GCP    project + dataset. No keys. They grant OUR service account.
--   Azure  tenant + client id + a SECRET, which is the one long-lived
--          credential this product holds. Encrypted at rest, and said
--          out loud in the interface rather than buried here.
--
-- `config` is provider-shaped and non-secret; `secret` is ciphertext or
-- NULL. Keeping them in separate columns means a query that dumps config
-- for debugging cannot accidentally print a credential.
CREATE TABLE IF NOT EXISTS cloud_connections (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner          TEXT NOT NULL,              -- verified Clerk subject
    provider       TEXT NOT NULL CHECK (provider IN ('aws', 'gcp', 'azure')),
    display_name   TEXT NOT NULL,
    account_id     TEXT NOT NULL DEFAULT '',   -- account / project / subscription

    config         JSONB NOT NULL DEFAULT '{}'::jsonb,
    secret         BYTEA,                      -- Fernet ciphertext, Azure only

    -- pending  -> created, the user has not finished their side
    -- active   -> we proved access at least once
    -- error    -> we tried and could not, with the reason kept
    status         TEXT NOT NULL DEFAULT 'pending'
                   CHECK (status IN ('pending', 'active', 'error')),
    last_error     TEXT NOT NULL DEFAULT '',
    last_synced_at TIMESTAMPTZ,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- One connection per account per person. Re-connecting the same
    -- account should update the existing row rather than silently
    -- doubling every figure in their report.
    UNIQUE (owner, provider, account_id)
);

CREATE INDEX IF NOT EXISTS idx_connections_owner
    ON cloud_connections (owner, created_at DESC);

-- ── Synced billing facts ─────────────────────────────────────────────
--
-- One row per day per service per region per charge type. The columns
-- are the reason connecting an account is worth anything over uploading
-- a CSV: a bill is not one number.
--
--   unblended  what the line actually cost that day
--   amortized  a commitment's up-front cost spread over its term, so a
--              reserved instance bought in January does not make January
--              look like a disaster and February look free
--   blended    AWS's cross-account average rate
--
-- All three are kept rather than one being chosen at write time. Which
-- one answers a question depends on the question -- "what did we pay in
-- March" and "what does this workload cost us" have different right
-- answers -- and a sync that picked would foreclose the other.
--
-- Credits, tax and refunds are SEPARATE columns rather than negative
-- usage rows: a report that can exclude tax has to be able to find it,
-- and folding it into the cost makes that impossible after the fact.
CREATE TABLE IF NOT EXISTS billing_line_items (
    id             BIGSERIAL PRIMARY KEY,
    connection_id  UUID NOT NULL REFERENCES cloud_connections(id) ON DELETE CASCADE,
    owner          TEXT NOT NULL,              -- denormalized: every read filters on it

    usage_date     DATE NOT NULL,
    service        TEXT NOT NULL,
    region         TEXT NOT NULL DEFAULT '',
    resource_type  TEXT NOT NULL DEFAULT '',
    account_id     TEXT NOT NULL DEFAULT '',   -- member account, for orgs

    unblended_usd  NUMERIC(18, 6) NOT NULL DEFAULT 0,
    amortized_usd  NUMERIC(18, 6) NOT NULL DEFAULT 0,
    blended_usd    NUMERIC(18, 6) NOT NULL DEFAULT 0,
    credit_usd     NUMERIC(18, 6) NOT NULL DEFAULT 0,
    tax_usd        NUMERIC(18, 6) NOT NULL DEFAULT 0,
    usage_amount   NUMERIC(20, 6) NOT NULL DEFAULT 0,
    usage_unit     TEXT NOT NULL DEFAULT '',

    -- on_demand | reserved | savings_plan | spot. What a commitment
    -- covers is the difference between unblended and amortized, so the
    -- report cannot explain that gap without knowing which is which.
    purchase_type  TEXT NOT NULL DEFAULT 'on_demand',

    synced_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Re-syncing an overlapping window must correct rows, not add them.
    -- Providers restate recent days for a week or more, so overlap is
    -- the normal case rather than the exception.
    UNIQUE (connection_id, usage_date, service, region, resource_type,
            account_id, purchase_type)
);

CREATE INDEX IF NOT EXISTS idx_billing_owner_date
    ON billing_line_items (owner, usage_date DESC);

CREATE INDEX IF NOT EXISTS idx_billing_connection_date
    ON billing_line_items (connection_id, usage_date DESC);

-- ── Sync history ─────────────────────────────────────────────────────
--
-- Kept because "your costs look wrong" is answered by what we pulled and
-- when, and a sync that half-failed is otherwise indistinguishable from
-- an account that genuinely spent less.
CREATE TABLE IF NOT EXISTS sync_runs (
    id             BIGSERIAL PRIMARY KEY,
    connection_id  UUID NOT NULL REFERENCES cloud_connections(id) ON DELETE CASCADE,
    started_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at    TIMESTAMPTZ,
    status         TEXT NOT NULL DEFAULT 'running'
                   CHECK (status IN ('running', 'ok', 'error')),
    rows_written   INTEGER NOT NULL DEFAULT 0,
    window_start   DATE,
    window_end     DATE,
    message        TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_sync_runs_connection
    ON sync_runs (connection_id, started_at DESC);
