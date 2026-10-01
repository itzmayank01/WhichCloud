"""A rate-limited response must still be a CORS response.

The rate limiter short-circuits before any route runs. It used to be
registered AFTER CORSMiddleware, which in Starlette means it sat OUTSIDE
it -- so its 429 never passed back through CORS and reached the browser
with no Access-Control-Allow-Origin header.

The browser reports that as "blocked by CORS policy", not as "rate
limited", and `fetchThroughWake` in the frontend cannot tell that failure
apart from a cold backend: both surface as a thrown TypeError. So it
retried five times over ~61 seconds, turning one rate-limited page load
into roughly forty more requests and keeping the limit tripped. One
landing page visit makes seven backend calls, so this was reachable in
ordinary use and presented as the landing page hanging with blank panels.

These tests pin the ordering, because it is invisible at the call site --
`add_middleware` looks like registration order and is the reverse of it.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from whichcloud import api as api_module
from whichcloud.api import app

ORIGIN = "http://localhost:3000"


@pytest.fixture()
def fresh_client():
    """A client whose rate-limit counters start empty.

    The middleware instance holds its windows in memory for the life of
    the app, and the rest of the suite shares that app -- so without
    rebuilding the stack (which constructs a new RateLimitMiddleware)
    these tests would inherit whatever hits other tests happened to make.
    """
    app.middleware_stack = app.build_middleware_stack()
    yield TestClient(app)
    # Leave a clean stack behind, since _DEFAULT_LIMIT monkeypatching in
    # these tests is read at construction time.
    app.middleware_stack = app.build_middleware_stack()


def test_a_normal_response_carries_cors_headers(fresh_client):
    resp = fresh_client.get("/health", headers={"Origin": ORIGIN})
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == ORIGIN


def test_a_rate_limited_response_still_carries_cors_headers(fresh_client, monkeypatch):
    """The regression this file exists for.

    Without CORS outermost this 429 arrives header-less and the browser
    reports a CORS failure instead of the rate limit that actually
    happened.
    """
    monkeypatch.setattr(api_module, "_DEFAULT_LIMIT", 3)
    app.middleware_stack = app.build_middleware_stack()

    last = None
    for _ in range(6):
        last = fresh_client.get("/health", headers={"Origin": ORIGIN})
        if last.status_code == 429:
            break

    assert last is not None and last.status_code == 429, "expected to hit the limit"
    assert last.headers.get("access-control-allow-origin") == ORIGIN, (
        "a 429 without CORS headers reaches the browser as an opaque CORS "
        "error, which the frontend retries for ~61s instead of failing fast"
    )
    assert last.headers.get("retry-after")


def test_the_rate_limited_body_says_what_happened(fresh_client, monkeypatch):
    monkeypatch.setattr(api_module, "_DEFAULT_LIMIT", 2)
    app.middleware_stack = app.build_middleware_stack()

    last = None
    for _ in range(5):
        last = fresh_client.get("/health", headers={"Origin": ORIGIN})
        if last.status_code == 429:
            break

    assert last is not None and last.status_code == 429
    body = last.json()
    assert body["ok"] is False
    assert "rate limit" in body["message"].lower()


def test_cors_is_the_outermost_middleware():
    """Pinned directly, so the ordering cannot regress silently.

    `add_middleware` prepends, so user_middleware[0] is the outermost.
    """
    from fastapi.middleware.cors import CORSMiddleware

    assert app.user_middleware[0].cls is CORSMiddleware


def test_public_read_endpoints_are_cacheable(fresh_client):
    resp = fresh_client.get("/health")
    assert resp.status_code == 200
    cache_control = resp.headers.get("cache-control", "")
    assert "public" in cache_control
    assert "max-age=" in cache_control
    assert "stale-while-revalidate" in cache_control


def test_an_authorized_request_is_never_publicly_cached(fresh_client):
    """A shared cache holding a caller-specific answer would serve one
    person's data to the next visitor. Pinned because the allow-list makes
    it look safe by path alone."""
    resp = fresh_client.get("/health", headers={"Authorization": "Bearer whatever"})
    assert "public" not in resp.headers.get("cache-control", "")


def test_per_user_routes_are_not_in_the_cacheable_allow_list():
    for path in api_module._CACHEABLE_PATHS:
        assert not path.startswith("/api/finops"), path
        assert not path.startswith("/api/github"), path
        assert not path.startswith("/api/connections"), path


def test_the_default_read_budget_clears_several_landing_page_visits():
    """One landing page visit is seven backend calls.

    A budget under ~100 means a handful of ordinary reloads trips it --
    and on Vercel, server-rendered calls for EVERY visitor share one IP.
    """
    assert api_module._DEFAULT_LIMIT >= 300
    # The budget that actually bounds abuse is the strict one, and this
    # change must not have loosened it.
    assert api_module._STRICT_LIMIT <= 10
