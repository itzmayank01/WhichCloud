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
