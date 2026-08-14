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
