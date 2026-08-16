"""Postgres-backed price catalog.

The adapters fetch from the internet; this module is the only thing the engine
talks to. Once ingested, a lookup is a single indexed query — no 300 MB file
read, no provider API call on the request path.
"""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from decimal import Decimal

import psycopg
from psycopg.rows import dict_row

from .models import ComputeQuery, PricePoint

DSN = os.getenv(
    "WHICHCLOUD_DSN",
    "postgresql://whichcloud:whichcloud_dev@localhost:5432/whichcloud",
)


@contextmanager
def connect(dsn: str | None = None):
    with psycopg.connect(dsn or DSN, row_factory=dict_row) as conn:
        yield conn


UPSERT = """
INSERT INTO price_points
    (provider, category, sku, name, region, unit, price_usd,
     vcpu, memory_gb, arch, attributes, fetched_at)
VALUES
    (%(provider)s, %(category)s, %(sku)s, %(name)s, %(region)s, %(unit)s,
     %(price_usd)s, %(vcpu)s, %(memory_gb)s, %(arch)s, %(attributes)s, now())
ON CONFLICT (provider, region, sku, unit) DO UPDATE SET
    category   = EXCLUDED.category,
    name       = EXCLUDED.name,
    price_usd  = EXCLUDED.price_usd,
    vcpu       = EXCLUDED.vcpu,
    memory_gb  = EXCLUDED.memory_gb,
    arch       = EXCLUDED.arch,
    attributes = EXCLUDED.attributes,
    fetched_at = now()
"""


def upsert_prices(points: list[PricePoint], dsn: str | None = None) -> int:
    """Write price points, replacing any existing row for the same SKU.

    Idempotent by (provider, region, sku, unit), so re-running an ingest
    refreshes prices instead of duplicating them.
    """
    if not points:
        return 0

    rows = [
        {
            "provider": p.provider,
            "category": p.category,
            "sku": p.sku,
            "name": p.name,
            "region": p.region,
            "unit": p.unit,
            "price_usd": p.price_usd,
            "vcpu": p.vcpu,
            "memory_gb": p.memory_gb,
            "arch": p.arch,
            "attributes": json.dumps(p.attributes),
        }
        for p in points
    ]

    with connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.executemany(UPSERT, rows)
        conn.commit()
    return len(rows)


def _to_point(row: dict) -> PricePoint:
    attrs = row["attributes"]
    return PricePoint(
        provider=row["provider"],
        category=row["category"],
        sku=row["sku"],
        name=row["name"],
        region=row["region"],
        unit=row["unit"],
        price_usd=Decimal(row["price_usd"]),
        vcpu=row["vcpu"],
        memory_gb=row["memory_gb"],
        arch=row["arch"],
        attributes=attrs if isinstance(attrs, dict) else json.loads(attrs or "{}"),
    )


def cheapest_compute(
    query: ComputeQuery,
    provider: str | None = None,
    purchase: str = "ondemand",
    dsn: str | None = None,
) -> PricePoint | None:
    """Cheapest machine meeting the spec. The engine's hot path."""
    from .models import provider_region

    sql = """
        SELECT * FROM price_points
        WHERE category = 'compute'
          AND vcpu >= %(vcpu)s
          AND memory_gb >= %(memory)s
          AND attributes->>'purchase' = %(purchase)s
    """
    params: dict[str, object] = {
        "vcpu": query.min_vcpu,
        "memory": query.min_memory_gb,
        "purchase": purchase,
    }

    if provider:
        sql += " AND provider = %(provider)s AND region = %(region)s"
        params["provider"] = provider
        params["region"] = provider_region(query.region, provider)
    else:
        regions = []
        for prov in ("aws", "azure", "gcp"):
            try:
                regions.append(provider_region(query.region, prov))
            except ValueError:
                continue
        sql += " AND region = ANY(%(regions)s)"
        params["regions"] = regions

    if query.arch:
        sql += " AND arch = %(arch)s"
        params["arch"] = query.arch

    sql += " ORDER BY price_usd ASC LIMIT 1"

    with connect(dsn) as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
    return _to_point(row) if row else None


def get_price(
    provider: str, region: str, category: str, sku: str, dsn: str | None = None
) -> PricePoint | None:
    """Exact lookup for a known SKU."""
    with connect(dsn) as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT * FROM price_points
               WHERE provider=%s AND region=%s AND category=%s AND sku=%s
               ORDER BY price_usd ASC LIMIT 1""",
            (provider, region, category, sku),
        )
        row = cur.fetchone()
    return _to_point(row) if row else None


def cheapest_database(
    provider: str,
    region: str,
    min_vcpu: int,
    min_memory_gb: float = 0.0,
    multi_az: bool = False,
    arch: str | None = None,
    dsn: str | None = None,
) -> PricePoint | None:
    """Cheapest managed database meeting the spec.

    Multi-AZ is a distinct SKU (suffixed ':multi-az' at ingest), not a
    multiplier, so the reliable option gets a real published price.
    """
    # A Single-AZ request must never match a Multi-AZ SKU, and vice versa.
    match = "sku LIKE '%%:multi-az'" if multi_az else "sku NOT LIKE '%%:multi-az'"
    arch_clause = "AND arch = %(arch)s" if arch else ""
    sql = f"""
        SELECT * FROM price_points
        WHERE provider = %(provider)s
          AND region = %(region)s
          AND category = 'database'
          AND vcpu >= %(vcpu)s
          AND memory_gb >= %(memory)s
          AND {match}
          {arch_clause}
        ORDER BY price_usd ASC LIMIT 1
    """
    with connect(dsn) as conn, conn.cursor() as cur:
        cur.execute(
            sql,
            {
                "provider": provider,
                "region": region,
                "vcpu": min_vcpu,
                "memory": min_memory_gb,
                "arch": arch,
            },
        )
        row = cur.fetchone()
    return _to_point(row) if row else None


def cheapest_compute_like(
    provider: str,
    region: str,
    category: str,
    min_vcpu: int,
    min_memory_gb: float = 0.0,
    dsn: str | None = None,
) -> PricePoint | None:
    """Cheapest node in a category that meets a vCPU/memory spec.

    Cache nodes are sized like compute but priced in their own category, so
    they need spec matching rather than a flat cheapest-in-category lookup.
    """
    with connect(dsn) as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT * FROM price_points
               WHERE provider=%s AND region=%s AND category=%s
                 AND (vcpu IS NULL OR vcpu >= %s) AND memory_gb >= %s
               ORDER BY price_usd ASC LIMIT 1""",
            (provider, region, category, min_vcpu, min_memory_gb),
        )
        row = cur.fetchone()
    return _to_point(row) if row else None


def cheapest_in_category(
    provider: str, region: str, category: str, dsn: str | None = None
) -> PricePoint | None:
    with connect(dsn) as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT * FROM price_points
               WHERE provider=%s AND region=%s AND category=%s
               ORDER BY price_usd ASC LIMIT 1""",
            (provider, region, category),
        )
        row = cur.fetchone()
    return _to_point(row) if row else None


def priced_regions(dsn: str | None = None) -> set[str]:
    """Provider-level regions that have at least one price."""
    with connect(dsn) as conn, conn.cursor() as cur:
        cur.execute("SELECT DISTINCT region FROM price_points")
        return {row["region"] for row in cur.fetchall()}


def db_now(dsn: str | None = None):
    """The database's clock.

    Rows are stamped with Postgres `now()`, so a cutoff used to prune them has
    to come from the same clock. Taking it from the Python process instead
    compares two clocks that agree only approximately -- and `now()` is
    transaction *start* time, so the write is stamped slightly earlier than it
    lands. A cutoff a millisecond ahead of the write makes every fresh row
    look stale, and the prune deletes the entire provider it just ingested.
    """
    with connect(dsn) as conn, conn.cursor() as cur:
        cur.execute("SELECT now() AS now")
        return cur.fetchone()["now"]


def prune_stale(
    provider: str, region: str, cutoff, dsn: str | None = None
) -> int:
    """Delete rows this ingest did not refresh.

    Without this, a SKU that stops being published — or one we deliberately
    stop mapping — lingers forever and the engine can quote a price the
    provider no longer offers.
    """
    with connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """DELETE FROM price_points
                   WHERE provider = %s AND region = %s AND fetched_at < %s""",
                (provider, region, cutoff),
            )
            removed = cur.rowcount
        conn.commit()
    return removed


def stats(dsn: str | None = None) -> list[dict]:
    """What is actually in the catalog — used by the ingest report."""
    with connect(dsn) as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT provider, region, category,
                      count(*) AS n,
                      max(fetched_at) AS fetched
               FROM price_points
               GROUP BY provider, region, category
               ORDER BY provider, region, category"""
        )
        return cur.fetchall()


def provenance(dsn: str | None = None) -> list[dict]:
    """How each price in the catalog got here.

    Three ways, and the distinction is the point of the project rather than
    bookkeeping. `fetched` came back from a provider's own pricing API and is
    stored as it arrived. `composed` is a provider selling a resource by its
    parts -- Cloud SQL quotes vCPU and RAM separately, so a 2-vCPU/8GB
    instance is their vCPU rate times two plus their RAM rate times eight,
    every term of it theirs. `derived` applies a documented multiplier to a
    fetched rate: Azure bills an HA standby as a second instance, so the
    multi-AZ figure is 2x the primary.

    Nothing is predicted, interpolated or averaged, and there is no fourth
    bucket -- a price that cannot be reached one of these three ways is
    reported missing rather than guessed.
    """
    with connect(dsn) as conn:
        return [
            dict(r)
            for r in conn.execute(
                """
                SELECT CASE
                         WHEN attributes ? 'composed' THEN 'composed'
                         WHEN attributes ? 'derived'  THEN 'derived'
                         ELSE 'fetched'
                       END AS kind,
                       count(*) AS n
                FROM price_points
                GROUP BY 1
                ORDER BY n DESC
                """
            ).fetchall()
        ]


def cached_architecture(key: str, dsn: str | None = None) -> str | None:
    """The stored extraction for this key, or None."""
    with connect(dsn) as conn:
        row = conn.execute(
            "SELECT payload FROM architecture_cache WHERE key = %s", (key,)
        ).fetchone()
    return json.dumps(row["payload"]) if row else None


def cache_architecture(
    key: str,
    description: str,
    reader: str,
    model: str,
    schema_version: str,
    payload: str,
    dsn: str | None = None,
) -> None:
    """Keep an extraction so the same description answers the same way.

    ON CONFLICT DO NOTHING rather than overwriting: the first answer is the
    one already shown to the user, and replacing it with a later one is
    exactly the drift this table exists to prevent.
    """
    with connect(dsn) as conn:
        conn.execute(
            """
            INSERT INTO architecture_cache
                (key, description, reader, model, schema_version, payload)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (key) DO NOTHING
            """,
            (key, description, reader, model, schema_version, payload),
        )


def save_architecture(
    owner: str,
    title: str,
    description: str,
    services: int,
    regions: int,
    dsn: str | None = None,
) -> dict:
    """Keep an architecture for someone, and hand back what was kept."""
    with connect(dsn) as conn:
        row = conn.execute(
            """
            INSERT INTO saved_architectures
                (owner, title, description, services, regions)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id, title, description, services, regions, created_at
            """,
            (owner, title, description, services, regions),
        ).fetchone()
    return dict(row)


def list_architectures(owner: str, dsn: str | None = None) -> list[dict]:
    """Someone's saved architectures, newest first."""
    with connect(dsn) as conn:
        return [
            dict(r)
            for r in conn.execute(
                """
                SELECT id, title, description, services, regions, created_at
                FROM saved_architectures
                WHERE owner = %s
                ORDER BY created_at DESC
                LIMIT 100
                """,
                (owner,),
            ).fetchall()
        ]


def delete_architecture(owner: str, architecture_id: str, dsn: str | None = None) -> bool:
    """Remove one, if it belongs to this owner.

    The owner is part of the WHERE clause rather than checked beforehand, so
    an id belonging to somebody else deletes nothing instead of racing between
    the check and the delete.
    """
    with connect(dsn) as conn:
        row = conn.execute(
            "DELETE FROM saved_architectures WHERE owner = %s AND id = %s RETURNING id",
            (owner, architecture_id),
        ).fetchone()
    return row is not None
