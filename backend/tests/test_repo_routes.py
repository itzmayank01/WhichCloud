"""The repo-sync endpoints.

/api/repo/scan stops short of a price on purpose. A scan reads the shape
of a workload; nothing in a repository states the traffic, data volumes or
budget that decide what it costs. The endpoint returns those field names
in `must_supply` so an interface can ask for exactly them.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from whichcloud.api import MUST_SUPPLY, app
from whichcloud.pricing.store import stats

client = TestClient(app)

REPO_FILES = {
    "package.json": '{"dependencies": {"next": "15.0.0", "bullmq": "^5.13.0", "ioredis": "^5.4.1"}}',
    "backend/requirements.txt": "fastapi>=0.115\npsycopg>=3.2\n",
}


def test_scan_reports_the_stack_and_what_it_cannot_know():
    with patch("whichcloud.connections.repo_scan.fetch_manifests", return_value=REPO_FILES):
        res = client.post("/api/repo/scan", json={"repo_url": "https://github.com/a/b", "token": "t"})
    assert res.status_code == 200, res.text
    body = res.json()
    assert "Next.js" in body["frameworks"]
    assert "Redis" in body["datastores"]
    assert any(d["signal"] == "queue" for d in body["detections"])
    # the scan refuses to invent these, and says which they are
    assert body["must_supply"] == MUST_SUPPLY
    assert "budget_monthly_usd" in body["must_supply"]


def test_every_detection_carries_its_evidence_over_the_wire():
    """A detection that cannot cite its source does not belong in a bill,
    and that has to survive serialisation, not just hold in Python."""
    with patch("whichcloud.connections.repo_scan.fetch_manifests", return_value=REPO_FILES):
        body = client.post(
            "/api/repo/scan", json={"repo_url": "https://github.com/a/b", "token": "t"}
        ).json()
    for d in body["detections"]:
        assert d["evidence"] and " in " in d["evidence"]
        assert d["source"]


def test_an_explainable_failure_is_a_400_with_the_reason():
    """connections/ raises ValueError for what it can explain -- a bad
    token, a missing branch, no manifests. That reason is the useful part,
    so it reaches the caller rather than becoming a generic 500."""
    with patch(
        "whichcloud.connections.repo_scan.fetch_manifests",
        side_effect=ValueError("No recognisable manifests were found in a/b."),
    ):
        res = client.post("/api/repo/scan", json={"repo_url": "https://github.com/a/b", "token": "t"})
    assert res.status_code == 400
    assert "No recognisable manifests" in res.json()["detail"]


@pytest.mark.skipif(
    sum(r["n"] for r in stats()) == 0, reason="needs an ingested price catalog"
)
def test_estimate_prices_the_repository_and_marks_the_answers_as_assumed():
    with patch("whichcloud.connections.repo_scan.fetch_manifests", return_value=REPO_FILES):
        res = client.post(
            "/api/repo/estimate",
            json={
                "repo_url": "https://github.com/a/b",
                "token": "t",
                "provider": "aws",
                "traffic_scale": "medium",
                "budget_monthly_usd": 600.0,
            },
        )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["options"], "expected priced options"
    assert body["scan"]["frameworks"], "the scan should ride along with the price"
    # the caller typed these; they must not be presented as findings
    assert {"traffic_scale", "region", "storage_gb", "egress_gb"} <= set(body["assumed"])
