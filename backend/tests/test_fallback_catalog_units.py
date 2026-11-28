"""The fallback catalog must price in the same units the estimator feeds it.

When Postgres is unreachable the engine serves prices from
`pricing/fallback_catalog.json` instead of the ingested catalog. Both are
read through the same `_by_role` lookup and handed to the same line builders,
so an entry there is only correct if it uses the SAME unit as the ingested
SKU of that name.

Two did not. `route53:dns-queries` was stored as "million-queries" at $0.40
and `waf:request` as "million-requests" at $0.60 -- which are AWS's real
published rates, and were wrong here anyway, because the estimator passes a
raw count of queries and of requests. A 10,000,000-query month was therefore
billed 10,000,000 x $0.40 and an online shop was quoted $4,000,386/mo, with
every other line on the estimate correct to the cent.

Nothing failed. The number was simply a million times too large, on the one
figure the whole product exists to produce, and only on machines without
Postgres -- which includes every local run without Docker.
"""

import json
import re
from decimal import Decimal
from pathlib import Path

CATALOG = Path(__file__).parent.parent / "whichcloud" / "pricing" / "fallback_catalog.json"

#: A unit naming a MULTIPLE of the thing being metered. The estimator has no
#: notion of these -- it multiplies its own count by the stored rate -- so any
#: entry carrying one is off by that multiple.
BULK_UNIT = re.compile(r"million|thousand|\b1k\b|\b1m\b|10k|100k|per[-_]k", re.I)


def _entries():
    return json.loads(CATALOG.read_text())


def test_no_entry_prices_in_bulk_units():
    offenders = [
        f"{e['sku']} (unit={e['unit']!r})"
        for e in _entries()
        if BULK_UNIT.search(e.get("unit") or "")
    ]
    assert not offenders, (
        "fallback entries priced per bulk unit, but the estimator feeds raw "
        "counts, so each is off by that multiple: " + ", ".join(offenders)
    )


def test_metered_rates_are_plausibly_per_unit():
    """A per-request/query/event rate is fractions of a cent, never dimes.

    Catches the same mistake spelled a different way -- a unit of "query"
    carrying the per-million price.
    """
    per_unit = {"query", "request", "requests", "event", "trace", "check"}
    loud = [
        f"{e['sku']} = ${e['price_usd']}/{e['unit']}"
        for e in _entries()
        if (e.get("unit") or "").lower() in per_unit
        and Decimal(str(e["price_usd"])) > Decimal("0.001")
    ]
    assert not loud, (
        "per-unit rates above $0.001 are almost certainly a bulk rate stored "
        "against a single-unit label: " + ", ".join(loud)
    )
