"""A cold cache and a warm one produce the same answer.

That is the only property worth asserting about a cache, and it is not
optional: a cache that changes an answer is not a cache, it is a bug with
a latency improvement. Everything else here — hit counting, negative
caching, failing open — exists to serve it.

The Redis container has been running since the project started and
nothing had ever talked to it. infra/docker-compose.yml says why it
exists ("Redis caches price lookups so the engine never re-queries a
provider mid-request") and the lookup path went to Postgres every time.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from whichcloud.estimator import ArchitectureSpec, estimate
from whichcloud.pricing import cache, store
from whichcloud.pricing.store import stats

pytestmark = pytest.mark.skipif(
    sum(r["n"] for r in stats()) == 0, reason="needs an ingested price catalog"
)

SKU = ("aws", "ap-south-1", "storage", "s3:general-purpose")
#: A graduated rate, so the tier round-trip is exercised rather than
#: assumed. A cache that flattened tiers would price a workload past the
#: first band several-fold wrong and still look fine on a flat rate.
TIERED = ("aws", "ap-south-1", "queue", "sqs:requests")


@pytest.fixture(autouse=True)
def _cold():
    cache.reset()
    yield
    cache.reset()


# ── the property ─────────────────────────────────────────────────────


def test_cold_and_warm_return_equal_price_points():
    cold = store.get_price(*SKU)
    warm = store.get_price(*SKU)
    assert cold is not None
    assert cold == warm


def test_a_graduated_rate_survives_the_round_trip_intact():
    cold = store.get_price(*TIERED)
    warm = store.get_price(*TIERED)
    assert cold.tiers, "expected a graduated rate to test with"
    assert cold.tiers == warm.tiers
    # Not just equal objects -- equal ARITHMETIC, which is what a bill
    # actually depends on.
    for quantity in (Decimal("1"), Decimal("1000000"), Decimal("50000000")):
        assert cold.cost_for(quantity) == warm.cost_for(quantity)


def test_attributes_survive_so_the_caveats_do():
    """Provenance rides on `attributes`, and Part 8's disclosures are
    derived from it. A cache that dropped them would silently strip the
    "derived, not published" note off Azure's HA line."""
    sku = "Dsv3-1vcore:multi-az"
    cold = store.get_price("azure", "centralindia", "database", sku)
    assert cold is not None, f"{sku} should be in the catalog"
    warm = store.get_price("azure", "centralindia", "database", sku)
    assert cold.attributes == warm.attributes
    # The one that actually matters: the "derived, not published" note.
    assert cold.attributes.get("derived")
    from whichcloud.estimator import caveats_for

    assert caveats_for(cold, "azure") == caveats_for(warm, "azure")


def test_a_whole_estimate_is_identical_cold_and_warm():
    """The end-to-end version. Every line, every figure, every caveat."""
    spec = ArchitectureSpec(
        name="t", region="india", compute_count=2, compute_vcpu=2,
        database_vcpu=2, database_memory_gb=8.0, storage_gb=200,
        egress_gb=300, backup_gb=200,
    )
    cache.reset()
    cold = estimate(spec, "aws")
    warm = estimate(spec, "aws")

    assert cold.total_monthly == warm.total_monthly
    assert [i.label for i in cold.items] == [i.label for i in warm.items]
    assert [i.monthly_usd for i in cold.items] == [i.monthly_usd for i in warm.items]
    assert [i.caveats for i in cold.items] == [i.caveats for i in warm.items]
    assert cold.missing == warm.missing


# ── the mechanics that make it hold ──────────────────────────────────


def test_the_second_lookup_is_a_hit():
    """A cache with a 0% hit rate and a broken cache look identical from
    the outside, which is why the counter exists."""
    store.get_price(*SKU)
    before = cache.STATS.hits
    store.get_price(*SKU)
    assert cache.STATS.hits == before + 1


def test_an_absent_sku_is_cached_as_absent():
    """"Not in the cache" and "no such price" both look like None. Without
    a sentinel, every lookup for a SKU the catalog genuinely lacks would
    hit Postgres forever -- which is the path a partially-ingested region
    takes most often."""
    missing = ("aws", "ap-south-1", "storage", "s3:no-such-class")
    assert store.get_price(*missing) is None
    before = cache.STATS.hits
    assert store.get_price(*missing) is None
    assert cache.STATS.hits == before + 1


def test_the_key_carries_the_cache_schema():
    """A value written under an older shape must not be read as a current
    one -- the same rule the extraction cache follows."""
    assert cache.CACHE_SCHEMA in cache.key("get", "aws", "r", "c", "s")


def test_a_missing_redis_does_not_stop_pricing(monkeypatch):
    """Failing open is deliberate. A pricing engine that cannot answer
    because its cache is down is worse in every way than one that answers
    a little slower, and Redis being optional is what lets the whole
    thing run with no container at all."""
    monkeypatch.setattr(cache, "_connect", lambda: None)
    cache.reset()
    monkeypatch.setattr(cache, "_connect", lambda: None)
    point = store.get_price(*SKU)
    assert point is not None
    assert point.price_usd > 0


def test_the_cache_can_be_disabled_entirely(monkeypatch):
    monkeypatch.setattr(cache, "_DISABLED", True)
    cache.reset()
    assert cache._connect() is None
    assert store.get_price(*SKU) is not None
