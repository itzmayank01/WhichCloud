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
