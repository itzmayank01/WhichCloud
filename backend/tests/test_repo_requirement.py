"""A scan plus the answers a person must give becomes a Requirement.

The point of these is the seam: what the repository is allowed to decide,
and what it is not. A repository can prove it needs a queue. It cannot
know your traffic, and a default standing in for traffic would flow
straight into a bill presented as though the code had produced it.
"""

from __future__ import annotations

import inspect

import pytest

from whichcloud.connections.repo_requirement import build_requirement
from whichcloud.connections.repo_scan import scan_manifests

FULL_STACK = {
    "package.json": """
    {"dependencies": {
        "next": "15.0.0", "bullmq": "^5.13.0", "@sendgrid/mail": "^8.1.3",
        "ioredis": "^5.4.1", "prisma": "^5.20.0"
    }}
    """,
    "backend/requirements.txt": "fastapi>=0.115\nelasticsearch>=8.15\nopenai>=1.50\n",
}

ANSWERS = dict(
    goal="an online storefront",
    traffic_scale="medium",
    region="india",
    budget_monthly_usd=600.0,
    storage_gb=200.0,
    egress_gb=500.0,
)


def test_detections_become_engine_flags():
    rr = build_requirement(scan_manifests(FULL_STACK), **ANSWERS)
    req = rr.requirement
    assert req.needs_queue is True        # bullmq
    assert req.needs_email is True        # @sendgrid/mail
    assert req.needs_search is True       # elasticsearch
    assert req.ai_language is True        # openai
    assert req.ai is True                 # umbrella the engine prices on


def test_scale_answers_are_carried_through_untouched():
    rr = build_requirement(scan_manifests(FULL_STACK), **ANSWERS)
    req = rr.requirement
    assert req.budget_monthly_usd == 600.0
    assert req.traffic_scale == "medium"
    assert req.storage_gb == 200.0
    assert req.egress_gb == 500.0
    assert req.region == "india"


def test_the_scale_answers_cannot_be_omitted():
    """The signature is the enforcement. A default for traffic or budget
    would be a number nobody chose, flowing into a priced architecture as
    though the repository had supplied it."""
    params = inspect.signature(build_requirement).parameters
    for name in ("traffic_scale", "region", "budget_monthly_usd", "storage_gb", "egress_gb"):
        assert params[name].default is inspect.Parameter.empty, (
            f"{name} has a default; a repository cannot state it, so the "
            "caller must be made to"
        )
        assert params[name].kind is inspect.Parameter.KEYWORD_ONLY


def test_caller_supplied_values_are_reported_as_assumptions_not_findings():
    rr = build_requirement(scan_manifests(FULL_STACK), **ANSWERS)
    assert {"traffic_scale", "region", "storage_gb", "egress_gb"} <= set(rr.assumed)
    # ...and the budget was given, so it is not among them
    assert "budget_monthly_usd" not in rr.assumed


def test_a_missing_budget_is_recorded_as_assumed():
    rr = build_requirement(scan_manifests(FULL_STACK), **{**ANSWERS, "budget_monthly_usd": None})
    assert "budget_monthly_usd" in rr.assumed
    assert rr.requirement.budget_monthly_usd is None


def test_every_flag_can_name_the_dependency_that_set_it():
    rr = build_requirement(scan_manifests(FULL_STACK), **ANSWERS)
    assert rr.evidence
    for d in rr.evidence:
        assert " in " in d.evidence, d.evidence


def test_an_unrecognisable_repository_admits_it_guessed_the_workload():
    rr = build_requirement(scan_manifests({"go.mod": "module x\n\ngo 1.22\n"}), **ANSWERS)
    assert rr.requirement.workload_type == "mixed"
    assert "workload_type" in rr.assumed
    assert "no_datastore_detected" in rr.assumed


def test_a_recognised_framework_is_not_listed_as_an_assumption():
    rr = build_requirement(scan_manifests(FULL_STACK), **ANSWERS)
    assert rr.requirement.workload_type == "web"   # next
    assert "workload_type" not in rr.assumed


# ── end to end: a scan reaches the pricing engine ───────────────────────

from whichcloud.pricing.store import stats  # noqa: E402

needs_catalog = pytest.mark.skipif(
    sum(r["n"] for r in stats()) == 0, reason="needs an ingested price catalog"
)

PY_SERVICE = {"backend/requirements.txt": "fastapi>=0.115\npsycopg>=3.2\nopenai>=1.50\n"}


@needs_catalog
@pytest.mark.parametrize("provider", ["aws", "gcp", "azure"])
def test_a_scanned_repository_prices_on_every_cloud(provider):
    """The whole point of the feature: manifests in, costed architecture
    out, on each of the three clouds, through the existing engine rather
    than a second pricing path built alongside it."""
    from whichcloud import engine

    rr = build_requirement(scan_manifests(PY_SERVICE), **ANSWERS)
    options = engine.recommend(rr.requirement, provider, dsn=None)
    assert options, f"{provider} produced no options"
    for opt in options[:3]:
        assert opt.estimate.total_monthly > 0


@needs_catalog
def test_an_incomplete_estimate_says_so_rather_than_quoting_a_total():
    """A scan cannot make the catalog complete. When the engine cannot
    price every service it chose, it must report that rather than present
    a total as though it covered everything -- the same refusal the
    /describe path makes. On a thin catalog this is the normal case, and
    it is the behaviour that keeps a generated bill honest."""
    from whichcloud import engine

    rr = build_requirement(scan_manifests(PY_SERVICE), **ANSWERS)
    est = engine.recommend(rr.requirement, "aws", dsn=None)[0].estimate
    if not est.is_complete:
        assert est.missing, "incomplete estimate must name what it could not price"
