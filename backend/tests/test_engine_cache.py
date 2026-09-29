"""Single-flight/TTL caching in front of /recommend and /compare.

Both routes are pure functions of (structured requirement, catalog state),
and the landing page relies on repeat identical asks coming back cheaply --
see the comment above `_cached_engine_call` in api.py for the production
incident (four of the landing page's own demo queries measured ~46s
wall-clock together on the deployed, single-worker, Redis-less backend)
this exists to fix. These tests assert the mechanism directly by counting
calls into the engine, rather than by timing, which would make them flaky
under CI load without proving anything a call count doesn't already prove.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import whichcloud.api as api_module
from whichcloud.api import app
from whichcloud.pricing.store import stats


def catalog_ready() -> bool:
    try:
        return sum(r["n"] for r in stats()) > 0
    except Exception:
        return False


needs_db = pytest.mark.skipif(
    not catalog_ready(), reason="needs an ingested price catalog"
)


@pytest.fixture
def client():
    """Function-scoped, unlike test_api.py's module-scoped one: each test
    here needs a clean `_engine_cache`, and clearing it around a shared
    client would race any other test module running in parallel."""
    api_module._engine_cache.clear()
    api_module._engine_inflight.clear()
    yield TestClient(app)
    api_module._engine_cache.clear()
    api_module._engine_inflight.clear()


BODY = {
    "goal": "an online shop",
    "workload_type": "web",
    "traffic_pattern": "spiky",
    "traffic_scale": "medium",
    "storage_gb": 200,
    "egress_gb": 500,
}


@needs_db
def test_identical_recommend_calls_hit_the_engine_once(client, monkeypatch):
    calls = []
    real = api_module.recommend

    def counting(*args, **kwargs):
        calls.append(1)
        return real(*args, **kwargs)

    monkeypatch.setattr(api_module, "recommend", counting)

    first = client.post("/recommend", json=BODY)
    second = client.post("/recommend", json=BODY)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()
    assert len(calls) == 1


@needs_db
def test_identical_compare_calls_hit_the_engine_once(client, monkeypatch):
    calls = []
    real = api_module.recommend_across_clouds

    def counting(*args, **kwargs):
        calls.append(1)
        return real(*args, **kwargs)

    monkeypatch.setattr(api_module, "recommend_across_clouds", counting)

    first = client.post("/compare", json=BODY)
    second = client.post("/compare", json=BODY)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()
    assert len(calls) == 1


@needs_db
def test_different_bodies_are_not_conflated(client, monkeypatch):
    calls = []
    real = api_module.recommend_across_clouds

    def counting(*args, **kwargs):
        calls.append(1)
        return real(*args, **kwargs)

    monkeypatch.setattr(api_module, "recommend_across_clouds", counting)

    other_body = {**BODY, "goal": "a read-heavy API", "workload_type": "api"}
    client.post("/compare", json=BODY)
    client.post("/compare", json=other_body)

    assert len(calls) == 2


@needs_db
def test_field_order_does_not_bust_the_cache(client, monkeypatch):
    """The cache key is built from the parsed model, not the raw JSON --
    two requests with the same fields in a different order must be the same
    cache entry, not two."""
    calls = []
    real = api_module.recommend_across_clouds

    def counting(*args, **kwargs):
        calls.append(1)
        return real(*args, **kwargs)

    monkeypatch.setattr(api_module, "recommend_across_clouds", counting)

    reordered = dict(reversed(list(BODY.items())))
    client.post("/compare", json=BODY)
    client.post("/compare", json=reordered)

    assert len(calls) == 1


@needs_db
def test_concurrent_identical_calls_single_flight(client, monkeypatch):
    """Two requests for the same body arriving at (almost) the same time
    must share one computation, not race the cache the way the pre-fix
    /describe + /describe/terraform/inspect pair did."""
    import threading
    import time as time_module

    calls = []
    real = api_module.recommend_across_clouds

    def slow(*args, **kwargs):
        calls.append(1)
        time_module.sleep(0.3)
        return real(*args, **kwargs)

    monkeypatch.setattr(api_module, "recommend_across_clouds", slow)

    results = []

    def fire():
        results.append(client.post("/compare", json=BODY))

    threads = [threading.Thread(target=fire) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert len(results) == 4
    assert all(r.status_code == 200 for r in results)
    assert len(calls) == 1


@needs_db
def test_engine_errors_are_not_cached(client, monkeypatch):
    """A transient engine failure must not poison the cache for the next,
    hopefully-successful, caller with the same body. `/compare` has no
    try/except around the engine call (same as before this cache existed),
    so TestClient's default `raise_server_exceptions=True` re-raises it here
    rather than turning it into a response -- that part of the behaviour is
    unchanged; what this asserts is that the failed attempt left nothing in
    the cache for the next call to (wrongly) reuse."""
    call_count = {"n": 0}
    real = api_module.recommend_across_clouds

    def flaky(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("transient")
        return real(*args, **kwargs)

    monkeypatch.setattr(api_module, "recommend_across_clouds", flaky)

    with pytest.raises(RuntimeError):
        client.post("/compare", json=BODY)

    second = client.post("/compare", json=BODY)
    assert second.status_code == 200
    assert call_count["n"] == 2


@needs_db
def test_warmer_populates_the_cache_for_every_known_landing_page_query(client):
    """The production incident this whole file exists for was the FIRST
    visitor after a cold start/cache expiry paying the full cost -- the
    warmer is what's supposed to make that visitor rare. Assert it actually
    leaves every query it claims to warm sitting in the cache, hit-ready."""
    api_module._warm_landing_page_queries()

    for raw in api_module._LANDING_PAGE_COMPARE_QUERIES:
        key = api_module._requirement_cache_key(
            "compare", api_module.RecommendIn(**raw)
        )
        assert key in api_module._engine_cache, f"not warmed: {raw['goal']!r}"

    for raw in api_module._LANDING_PAGE_RECOMMEND_QUERIES:
        key = api_module._requirement_cache_key(
            "recommend", api_module.RecommendIn(**raw)
        )
        assert key in api_module._engine_cache, f"not warmed: {raw['goal']!r}"


def test_warmer_never_raises_even_if_a_query_is_malformed(monkeypatch):
    """A future edit to the warm-query list that typos a field must not take
    the whole app down at startup -- see the per-query try/except in
    `_warm_landing_page_queries`."""
    monkeypatch.setattr(
        api_module, "_LANDING_PAGE_COMPARE_QUERIES", [{"goal": "x", "workload_type": "not-a-real-type"}]
    )
    monkeypatch.setattr(api_module, "_LANDING_PAGE_RECOMMEND_QUERIES", [])
    api_module._warm_landing_page_queries()  # must not raise


def test_warmer_does_not_start_under_pytest():
    """`_start_cache_warmer` checks `"pytest" in sys.modules` before
    spawning its background thread -- confirm it actually takes that
    branch when run the way every other test in this suite runs."""
    import threading

    before = threading.active_count()
    api_module._start_cache_warmer()
    after = threading.active_count()
    assert after == before, "warmer thread started during a pytest run"
