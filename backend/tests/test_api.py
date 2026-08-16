"""Tests for the HTTP layer.

These run the app in-process with FastAPI's TestClient rather than over a
socket, so they exercise the real routes without needing a running server.

The API is a translation layer, so what is tested here is translation: that
requests reach the engine with the right shape, that engine errors become
sensible status codes, and that the fields the interface depends on — freshness
timestamps, what was assumed, which techniques were skipped — actually survive
serialisation.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from whichcloud.api import app


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def catalog_ready() -> bool:
    try:
        from whichcloud.pricing.store import stats

        return sum(r["n"] for r in stats()) > 0
    except Exception:
        return False


needs_db = pytest.mark.skipif(
    not catalog_ready(), reason="needs an ingested price catalog"
)


# ── routes that need no database ────────────────────────────────────────


def test_regions_lists_every_provider_mapping(client):
    body = client.get("/regions").json()
    assert "india" in body
    assert set(body["india"]) == {"aws", "azure", "gcp"}


def test_techniques_exposes_the_knowledge_base(client):
    body = client.get("/techniques").json()
    assert body["count"] >= 8

    ids = {t["id"] for t in body["techniques"]}
    assert "graviton-arm-compute" in ids

    for t in body["techniques"]:
        assert t["tool"], f"{t['id']} exposes no tool"
        assert t["tradeoffs"], f"{t['id']} exposes no tradeoffs"
        assert isinstance(t["priced"], bool)


def test_advisory_techniques_are_marked_unpriced(client):
    """The interface must be able to show advice as advice."""
    body = client.get("/techniques").json()
    by_id = {t["id"]: t for t in body["techniques"]}
    assert by_id["zram-memory-compression"]["priced"] is False
    assert by_id["graviton-arm-compute"]["priced"] is True


def test_unknown_region_is_a_400_not_a_500(client):
    response = client.get("/catalog", params={"region": "atlantis"})
    assert response.status_code == 400
    assert "atlantis" in response.json()["detail"]


def test_invalid_workload_is_rejected_before_the_engine(client):
    response = client.post("/recommend", json={"goal": "x", "workload_type": "quantum"})
    assert response.status_code == 422  # pydantic rejects the enum


def test_negative_egress_is_a_400(client):
    response = client.post("/recommend", json={"goal": "x", "egress_gb": -5})
    assert response.status_code == 400
    assert "negative" in response.json()["detail"]


# ── routes that need the catalog ────────────────────────────────────────


@needs_db
def test_health_reports_catalog_size_and_freshness(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["prices"] > 1000
    assert set(body["providers"]) == {"aws", "azure", "gcp"}
    assert body["last_updated"]  # ISO timestamp the UI can show


@needs_db
def test_catalog_returns_rows_with_a_freshness_stamp(client):
    body = client.get(
        "/catalog", params={"min_vcpu": 2, "min_memory_gb": 8, "limit": 5}
    ).json()

    assert body["count"] > 0
    for row in body["rows"]:
        assert row["provider"] in {"aws", "azure", "gcp"}
        assert row["hourly_usd"] > 0
        assert row["monthly_usd"] > row["hourly_usd"]
        assert row["fetched_at"], "every price must say when it was fetched"


@needs_db
def test_catalog_is_sorted_cheapest_first(client):
    rows = client.get("/catalog", params={"limit": 20}).json()["rows"]
    prices = [r["hourly_usd"] for r in rows]
    assert prices == sorted(prices)


@needs_db
def test_catalog_honours_the_arch_filter(client):
    rows = client.get(
        "/catalog", params={"arch": "arm64", "min_vcpu": 2, "limit": 20}
    ).json()["rows"]
    assert rows
    assert all(r["arch"] == "arm64" for r in rows)


@needs_db
def test_recommend_returns_three_priced_options(client):
    body = client.post(
        "/recommend",
        json={
            "goal": "an online shop",
            "workload_type": "web",
            "traffic_pattern": "spiky",
            "traffic_scale": "medium",
            "budget_monthly_usd": 400,
        },
    ).json()

    assert [o["label"] for o in body["options"]] == [
        "Cheapest",
        "Balanced",
        "Most reliable",
    ]
    for option in body["options"]:
        assert option["monthly_usd"] > 0
        assert option["items"]
        assert option["shape"]


@needs_db
def test_recommend_exposes_measured_savings_with_their_counterfactual(client):
    """A saving the interface cannot attribute is a number the user cannot check."""
    body = client.post(
        "/recommend",
        json={"goal": "shop", "workload_type": "web", "traffic_scale": "medium"},
    ).json()

    applied = [a for o in body["options"] for a in o["applied"]]
    assert applied, "expected at least one technique to apply"
    for technique in applied:
        assert technique["saved_monthly_usd"] > 0
        assert technique["versus_sku"], "a saving must name what it beat"


@needs_db
def test_recommend_explains_what_it_skipped(client):
    """Spot on a web workload should be absent AND explained."""
    body = client.post(
        "/recommend",
        json={"goal": "shop", "workload_type": "web", "interruptible": False},
    ).json()

    skipped = {n["id"]: n["reason"] for n in body["not_applied"]}
    assert "spot-interruptible-capacity" in skipped
    assert skipped["spot-interruptible-capacity"]


@needs_db
def test_sizing_basis_is_always_returned(client):
    """Sizing is heuristic; the caveat must reach the interface, not sit in a
    docstring nobody reads."""
    body = client.post("/recommend", json={"goal": "shop"}).json()
    assert "heuristic" in body["sizing_basis"].lower()


@needs_db
def test_compare_prices_every_cloud(client):
    body = client.post(
        "/compare",
        json={"goal": "shop", "workload_type": "web", "traffic_scale": "medium"},
    ).json()

    assert set(body["clouds"]) == {"aws", "azure", "gcp"}
    for options in body["clouds"].values():
        assert len(options) == 3


@needs_db
def test_incomplete_estimates_are_flagged_not_hidden(client):
    """GCP prices compute but not storage or egress. Those options must come
    back marked incomplete so the interface never presents a partial total as
    the cheaper answer."""
    body = client.post(
        "/compare",
        json={"goal": "shop", "workload_type": "web", "storage_gb": 200,
              "egress_gb": 500},
    ).json()

    gcp = body["clouds"]["gcp"]
    assert any(not o["complete"] for o in gcp)
    for option in gcp:
        if not option["complete"]:
            assert option["missing"], "incomplete estimates must say what is missing"


@needs_db
def test_budget_flag_reflects_the_stated_budget(client):
    body = client.post(
        "/recommend",
        json={"goal": "shop", "traffic_scale": "medium", "budget_monthly_usd": 50},
    ).json()
    # $50 is well under any real architecture here.
    assert all(o["within_budget"] is False for o in body["options"])


@needs_db
def test_no_budget_means_no_verdict(client):
    body = client.post("/recommend", json={"goal": "shop"}).json()
    assert all(o["within_budget"] is None for o in body["options"])


def test_provenance_splits_the_catalog_by_origin(client):
    """The split must add up to the catalog, or the page misreports itself."""
    body = client.get("/provenance").json()

    assert body["total"] == sum(body["split"].values())
    # Every bucket is one of the three the project actually distinguishes.
    assert set(body["split"]) <= {"fetched", "composed", "derived"}
    # Fetched has to dominate; if it ever does not, the claim on the landing
    # page is no longer true and this should fail rather than render quietly.
    assert body["split"]["fetched"] / body["total"] > 0.9
