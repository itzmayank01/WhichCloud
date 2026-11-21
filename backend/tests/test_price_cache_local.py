"""The cache tier that runs in production, which had no tests.

tests/test_price_cache.py needs a live Redis and skips without one -- so it
skips in CI and it skips on the deployed service, which is the one
configuration that matters: there is no Redis on Render. `_connect` fails
once, remembers it, and every later `get` returned None before touching a
counter. That is why /health reported the cache "enabled" with zero lookups
forever while every price lookup went to Postgres.

Survivable while Postgres is quick. Measured against the deployed Neon
instance it was not: /health (one query) answered in under two seconds while
/compare -- three tiers across three clouds, asking for the same SKUs over
and over -- did not finish in 240. The query COUNT is the problem.

These run with no Redis and no database, because that is the point.
"""

from __future__ import annotations

import time

import pytest

from whichcloud.pricing import cache


@pytest.fixture(autouse=True)
def cold_cache():
    cache.reset()
    yield
    cache.reset()


def test_a_value_survives_without_redis() -> None:
    """The whole point: no Redis, and the second ask still costs nothing."""
    key = cache.key("get", "aws", "ap-south-1", "compute", "t4g.large")
    assert cache.get(key) is None

    cache.put(key, {"sku": "t4g.large", "price_usd": "0.0896"})
    assert cache.get(key) == {"sku": "t4g.large", "price_usd": "0.0896"}


def test_a_hit_is_counted_so_health_stops_lying() -> None:
    """/health reported lookups: 0 forever, which read as "the cache is
    working and nothing needs it" rather than "nothing is reaching it"."""
    key = cache.key("get", "aws", "ap-south-1", "compute", "m6g.large")
    cache.get(key)                      # miss
    cache.put(key, {"price_usd": "1"})
    cache.get(key)                      # hit

    assert cache.STATS.hits == 1
    assert cache.STATS.misses == 1


def test_a_negative_is_cached_too() -> None:
    """store.get_price caches "no such SKU" as a sentinel. If the local tier
    dropped falsy values, an absent SKU would re-query Postgres every time --
    which is the exact lookup storm this exists to stop."""
    key = cache.key("get", "aws", "ap-south-1", "compute", "does-not-exist")
    sentinel = {"__absent__": True}
    cache.put(key, sentinel)
    assert cache.get(key) == sentinel


def test_it_expires(monkeypatch) -> None:
    """The TTL bounds how long a missed ingest generation can be served."""
    key = cache.key("get", "aws", "ap-south-1", "compute", "t4g.small")
    cache.put(key, {"price_usd": "0.01"})
    assert cache.get(key) is not None

    # Captured before patching: calling the patched time.time from inside
    # its own replacement is a recursion, not a clock.
    later = time.time() + cache.TTL_SECONDS + 60
    monkeypatch.setattr(cache.time, "time", lambda: later)
    assert cache.get(key) is None, "an expired entry must not be served"


def test_it_is_bounded() -> None:
    """An unbounded dict keyed by SKU on a 512 MB instance is the OOM this
    project already met once in _intake_cache."""
    for i in range(cache._LOCAL_MAX + 500):
        cache.put(cache.key("get", "aws", "r", "compute", f"sku-{i}"), {"n": i})

    assert len(cache._local) <= cache._LOCAL_MAX

    # Oldest evicted, newest kept.
    assert cache.get(cache.key("get", "aws", "r", "compute", "sku-0")) is None
    last = cache._LOCAL_MAX + 499
    assert cache.get(cache.key("get", "aws", "r", "compute", f"sku-{last}")) == {"n": last}


def test_reset_clears_it() -> None:
    key = cache.key("get", "aws", "r", "compute", "t4g.nano")
    cache.put(key, {"price_usd": "0.001"})
    cache.reset()
    assert cache.get(key) is None


def test_the_disable_switch_still_disables_everything(monkeypatch) -> None:
    """WHICHCLOUD_DISABLE_CACHE is an escape hatch, and a second tier that
    ignored it would make the hatch a lie."""
    monkeypatch.setattr(cache, "_DISABLED", True)
    key = cache.key("get", "aws", "r", "compute", "t4g.micro")
    cache.put(key, {"price_usd": "9"})
    assert cache.get(key) is None
