"""/describe is memoised, and the key tells workloads apart.

The route had no response cache, so every resubmission of the same text
re-ran the whole planner. Measured against production: a /describe took
46s and the IDENTICAL repeat took 47s, with `read_by` reporting
"groq (cached)" -- so the model read was already cached and the ~40s was
the planner itself, re-run from scratch on a 0.1-CPU instance.

The half that matters more than the memoisation is single-flight. The
studio submits on mount, there is one uvicorn worker, and a visitor who
retries a slow request puts two identical computations in flight -- the
second not merely wasted but holding the worker the first needs.

The risk a response cache introduces is the Phase 1 stale-result bug: a
key too coarse to tell two workloads apart serves one's prices for the
other. Every test below that asserts a MISS is guarding that, not the
speed-up.
"""

from __future__ import annotations

import whichcloud.api as api


def _clear() -> None:
    with api._engine_cache_lock:
        api._engine_cache.clear()
        api._engine_inflight.clear()


def _key(description: str, provider: str = "aws", reader: str | None = None) -> str:
    body = api.DescribeIn(description=description, provider=provider, reader=reader)
    return "describe:" + (body.reader or "") + ":" + api.build_workload_cache_key(
        body.description, body.provider or "aws",
    )


# ── the memoisation ──────────────────────────────────────────────────


def test_the_second_identical_call_does_not_recompute():
    _clear()
    calls = []

    def compute():
        calls.append(1)
        return {"total": 123}

    k = _key("a reporting database for the finance team")
    first = api._cached_engine_call(k, compute)
    second = api._cached_engine_call(k, compute)

    assert first == second == {"total": 123}
    assert len(calls) == 1, "the repeat re-ran the planner"


def test_a_cache_hit_returns_the_same_object_not_a_rebuild():
    """Identity, not just equality: a rebuilt-but-equal value would mean
    the compute ran again and the assertion above passed by luck."""
    _clear()
    sentinel = object()
    k = _key("an internal equipment tracker for twelve staff")
    assert api._cached_engine_call(k, lambda: sentinel) is sentinel
    assert api._cached_engine_call(k, lambda: object()) is sentinel


# ── the stale-result guards ──────────────────────────────────────────


def test_two_different_descriptions_do_not_share_an_entry():
    _clear()
    a = _key("a hospital records system for 450 staff, must stay in-country")
    b = _key("a marketing site with a contact form")
    assert a != b

    first = api._cached_engine_call(a, lambda: {"monthly": 5331})
    second = api._cached_engine_call(b, lambda: {"monthly": 40})
    assert first == {"monthly": 5331}
    assert second == {"monthly": 40}, "the second workload was served the first's price"


def test_the_same_text_on_a_different_cloud_does_not_share_an_entry():
    """The whole point of the provider override is pricing one requirement
    against three clouds. A key that ignored it would quote AWS's bill for
    GCP and the comparison would be a single number shown three times."""
    _clear()
    text = "a reporting database loaded overnight, 2 TB of history"
    keys = {c: _key(text, provider=c) for c in ("aws", "gcp", "azure")}
    assert len(set(keys.values())) == 3

    for cloud, k in keys.items():
        api._cached_engine_call(k, lambda c=cloud: {"provider": c})
    for cloud, k in keys.items():
        assert api._cached_engine_call(k, lambda: {"provider": "WRONG"}) == {
            "provider": cloud
        }


def test_a_different_reader_does_not_share_an_entry():
    """`reader` is not threaded into planning.build today, so these two
    requests currently compute the same thing. Keyed anyway: the day it is
    threaded through, a shared entry would hand a caller who asked for
    anthropic a groq reading with `read_by` claiming anthropic -- a wrong
    answer that looks authoritative."""
    _clear()
    text = "a payments service for a regulated lender"
    assert _key(text, reader="groq") != _key(text, reader="anthropic")
    assert _key(text, reader=None) != _key(text, reader="groq")


def test_whitespace_only_differences_do_share_an_entry():
    """The flip side: the key normalises, so a trailing newline from a
    textarea is not a different workload needing its own 40s."""
    _clear()
    base = "a reporting database for the finance team"
    assert _key(base) == _key(f"  {base}\n\n")


# ── single-flight ────────────────────────────────────────────────────


def test_concurrent_identical_calls_compute_once():
    """Six threads, one computation. This is the landing-page pattern: the
    studio and the dashboard both submit on mount."""
    import threading

    _clear()
    calls = []
    started = threading.Event()

    def compute():
        calls.append(1)
        started.wait(timeout=5)  # hold the slot so the others must queue
        return {"total": 7}

    k = _key("a batch pipeline that runs nightly")
    results: list[object] = []
    lock = threading.Lock()

    def run():
        value = api._cached_engine_call(k, compute)
        with lock:
            results.append(value)

    threads = [threading.Thread(target=run) for _ in range(6)]
    for t in threads:
        t.start()
    started.set()
    for t in threads:
        t.join(timeout=10)

    assert len(calls) == 1, f"computed {len(calls)} times, not once"
    assert results == [{"total": 7}] * 6


def test_a_failed_compute_is_not_cached_and_releases_the_slot():
    """A raise must not leave an in-flight marker behind: the next caller
    would wait on an event nobody will ever set."""
    _clear()
    k = _key("a workload whose first pricing attempt fails")

    class Boom(RuntimeError):
        pass

    def failing():
        raise Boom("engine unavailable")

    import pytest

    with pytest.raises(Boom):
        api._cached_engine_call(k, failing)

    # The slot is free and a later good compute succeeds and is cached.
    assert api._cached_engine_call(k, lambda: {"ok": True}) == {"ok": True}
    assert api._cached_engine_call(k, failing) == {"ok": True}


def test_an_expired_entry_is_recomputed():
    _clear()
    k = _key("a workload whose entry has aged out")
    assert api._cached_engine_call(k, lambda: {"v": 1}) == {"v": 1}

    with api._engine_cache_lock:
        cached_at, value = api._engine_cache[k]
        api._engine_cache[k] = (cached_at - api._ENGINE_CACHE_TTL_S - 1, value)

    assert api._cached_engine_call(k, lambda: {"v": 2}) == {"v": 2}
