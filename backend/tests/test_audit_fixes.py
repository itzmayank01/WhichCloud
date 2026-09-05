"""Regression guards for the five defects the audit ranked by impact.

Each of these changed the answer a user would act on, not a rate by a few
percent. They are grouped here rather than scattered because they were found
by one process and share one property: every single one was invisible to the
existing suite, which was green throughout.
"""

from __future__ import annotations

import pytest

from whichcloud import engine, topology
from whichcloud.estimator import ArchitectureSpec, estimate
from whichcloud.requirements import Requirement


def db_available() -> bool:
    try:
        from whichcloud.pricing.store import connect

        with connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT count(*) AS n FROM price_points")
            return cur.fetchone()["n"] > 0
    except Exception:
        return False


needs_db = pytest.mark.skipif(
    not db_available(), reason="needs an ingested price catalog"
)


def _kinds(option) -> set[str]:
    return {n.kind for n in topology.build(
        option.spec, option.estimate, option.applied
    ).nodes}


def _tiers(requirement, provider):
    return {o.label: o for o in engine.recommend(requirement, provider, dsn=None)}


# ── 1. a warehouse is never free, and is never a compute box ──────────────


@needs_db
def test_a_data_warehouse_is_never_priced_at_zero():
    """BigQuery sells no provisioned capacity, so the catalog row for it is a
    zero-priced placeholder. Pricing the warehouse tier from it produced a
    $0.00 data warehouse -- and a "Most optimized" that cost LESS than the
    tier below it, having dropped the scan charge and gained nothing
    chargeable in return."""
    spec = ArchitectureSpec(
        name="etl", region="india", compute_count=0,
        warehouse_node_count=4, warehouse_node_vcpu=2, warehouse_node_memory_gb=16.0,
    )
    for provider in ("aws", "gcp", "azure"):
        est = estimate(spec, provider)
        warehouse = [
            i for i in est.items
            if topology._kind_for(i) in ("warehouse", "athena")
        ]
        assert warehouse, f"{provider}: no warehouse line at all"
        assert sum(i.monthly_usd for i in warehouse) > 0, (
            f"{provider}: a data warehouse priced at zero"
        )


@needs_db
def test_the_warehouse_is_drawn_as_a_warehouse_on_every_cloud():
    """Azure's pool fell through to `compute`, so the diagram drew a
    $4,934/month data warehouse as an application server."""
    spec = ArchitectureSpec(
        name="etl", region="india", compute_count=0,
        warehouse_node_count=4, warehouse_node_vcpu=2, warehouse_node_memory_gb=16.0,
    )
    for provider in ("aws", "gcp", "azure"):
        est = estimate(spec, provider)
        kinds = {topology._kind_for(i) for i in est.items}
        assert kinds & {"warehouse", "athena"}, (
            f"{provider}: the warehouse is not drawn as one — kinds were {sorted(kinds)}"
        )
        assert "compute" not in kinds, (
            f"{provider}: something in a warehouse-only architecture is drawn as compute"
        )


@needs_db
def test_azure_buys_one_pool_rather_than_four_of_them():
    """Synapse dedicated SQL is ONE pool sized in data warehouse units. There
    is no such thing as four pools serving one warehouse, and "x 4" described
    a purchase nobody can make."""
    spec = ArchitectureSpec(
        name="etl", region="india", compute_count=0,
        warehouse_node_count=4, warehouse_node_vcpu=2, warehouse_node_memory_gb=16.0,
    )
    labels = [i.label for i in estimate(spec, "azure").items if "Synapse" in i.label]
    assert labels, "no Synapse line"
    assert any("DW400c" in x for x in labels), labels
    assert not any("× 4" in x for x in labels), labels


# ── 2. edge protection follows exposure, not request-serving ──────────────


def _internal_tool() -> Requirement:
    return Requirement(
        goal="Internal HR tool", workload_type="web", audience="internal",
        traffic_scale="low", region="india",
    )


def _public_site() -> Requirement:
    return Requirement(
        goal="Product catalogue", workload_type="web", audience="public",
        traffic_scale="high", region="india", egress_gb=500.0,
    )


def test_serving_requests_is_not_the_same_as_being_on_the_internet():
    assert not _internal_tool().internet_facing
    assert _internal_tool().serves_requests, "an internal tool still serves requests"
    assert _public_site().internet_facing


@needs_db
def test_an_internal_tool_is_not_sold_a_web_firewall():
    """The top tier used to assume an attack surface because it "should".
    Assuming one put $368/month of Azure Application Gateway in front of a
    workload whose attacker is not on the network."""
    for provider in ("aws", "gcp", "azure"):
        for label, option in _tiers(_internal_tool(), provider).items():
            assert "waf" not in _kinds(option), (
                f"{provider}/{label}: a web firewall for eighty internal staff"
            )


# ── 3. every derived role says why it is there ────────────────────────────


@needs_db
def test_no_role_appears_without_a_reason():
    """A role that cannot say why it is present is indistinguishable from a
    default that leaked in. Baseline roles are exempt BY NAME -- the exemption
    list is short on purpose, since anything on it stops having to justify
    its cost."""
    for requirement in (_internal_tool(), _public_site()):
        for provider in ("aws", "gcp", "azure"):
            for label, option in _tiers(requirement, provider).items():
                nodes = topology.build(
                    option.spec, option.estimate, option.applied
                ).nodes
                silent = [
                    n.kind for n in nodes
                    if not n.because and not n.baseline and n.kind != "client"
                ]
                assert not silent, f"{provider}/{label}: {silent} have no reason"


def test_the_baseline_exemption_stays_short():
    """This list is the escape hatch from the rule above. Every name on it is
    a role excused from justifying its cost, so it growing is a regression
    even when nothing else fails."""
    assert len(topology.BASELINE_KINDS) <= 14, sorted(topology.BASELINE_KINDS)
    for earned in ("compute", "database", "cache", "waf", "cdn", "warehouse"):
        assert earned not in topology.BASELINE_KINDS


# ── 4. a public site earns a CDN on readers, not on bytes ─────────────────


@needs_db
def test_a_public_read_heavy_site_gets_a_cdn_under_the_byte_threshold():
    """Five million page views of near-static content is the textbook CDN
    case, and every vendor reference for it puts one in front. It came out at
    500 GB of egress, under the one-terabyte bar, and got none."""
    site = _public_site()
    assert site.egress_gb < 1000, "this test is pointless above the threshold"
    for provider in ("aws", "gcp", "azure"):
        for label, option in _tiers(site, provider).items():
            assert "cdn" in _kinds(option), f"{provider}/{label}: no CDN"


@needs_db
def test_an_internal_tool_still_gets_no_cdn():
    """The other half. A rule that gives everything a CDN has not derived
    anything."""
    for provider in ("aws", "gcp", "azure"):
        for label, option in _tiers(_internal_tool(), provider).items():
            assert "cdn" not in _kinds(option), f"{provider}/{label}: CDN for 80 staff"


@needs_db
def test_a_cdn_and_plain_egress_are_not_the_same_box():
    """They shared the `network` kind, so an architecture WITH an edge cache
    and one without drew the identical node -- and on GCP and Azure that node
    is already named "Cloud CDN" and "Azure Front Door", which put a CDN on
    the picture for workloads that had none."""
    with_cdn = _tiers(_public_site(), "gcp")["Most reliable"]
    without = _tiers(_internal_tool(), "gcp")["Most reliable"]
    assert "cdn" in _kinds(with_cdn)
    assert "cdn" not in _kinds(without)
    assert _kinds(with_cdn) != _kinds(without)


# ── 6. the free allowance every cloud gives, actually applied ─────────────


@needs_db
def test_the_first_hundred_gigabytes_of_egress_are_free():
    """All three clouds give this away, and this billed from the first byte.

    On a large workload the difference is rounding. On an internal tool
    moving 5 GB it was the whole line -- traffic none of the three would have
    charged for. A free allowance nobody applies is the same error as a wrong
    rate; it just looks more defensible.
    """
    from whichcloud.estimator import EGRESS_FREE_TIER_GB

    for provider in ("aws", "gcp", "azure"):
        inside = ArchitectureSpec(
            name="small", region="india", compute_count=1,
            egress_gb=EGRESS_FREE_TIER_GB - 5,
        )
        assert not [
            i for i in estimate(inside, provider).items if i.label == "Egress"
        ], f"{provider}: charged for egress inside the free tier"

        outside = ArchitectureSpec(
            name="big", region="india", compute_count=1,
            egress_gb=EGRESS_FREE_TIER_GB + 400,
        )
        line = next(
            i for i in estimate(outside, provider).items if i.label == "Egress"
        )
        assert float(line.quantity) == 400, (
            f"{provider}: billed {line.quantity} GB, the allowance was not deducted"
        )


# ── 7. replicas and a cache are earned by READS, not by size ──────────────


def _read_heavy_site() -> Requirement:
    return Requirement(
        goal="Product catalogue", workload_type="web", audience="public",
        read_write_mix="read-heavy", traffic_scale="medium", region="india",
        egress_gb=500.0,
    )


def _write_heavy_at_the_same_size() -> Requirement:
    return Requirement(
        goal="Order capture", workload_type="web", audience="public",
        read_write_mix="write-heavy", traffic_scale="medium", region="india",
        egress_gb=500.0,
    )


@needs_db
def test_a_read_heavy_store_gets_replicas_a_write_heavy_one_does_not():
    """traffic_scale cannot tell these apart, and they want opposite things.

    A catalogue read five million times and a ledger written to five million
    times land in the same bucket. The first wants copies to read from; the
    second wants a primary that can take the writes.
    """
    read = _tiers(_read_heavy_site(), "aws")["Most reliable"]
    write = _tiers(_write_heavy_at_the_same_size(), "aws")["Most reliable"]
    assert read.spec.database_read_replicas > 0, "read-heavy got no replicas"
    assert write.spec.database_read_replicas == 0, "write-heavy bought replicas"


@needs_db
def test_a_stated_latency_target_earns_a_cache_over_any_store():
    """A managed key-value store scales on its own. That is not the same as
    meeting a p99 somebody asked for, and every vendor answers this case with
    a cache."""
    fast = Requirement(
        goal="Public read API", workload_type="api", audience="public",
        read_write_mix="read-heavy", data_shape="key-value",
        traffic_scale="medium", latency_target_ms=100, region="india",
    )
    for provider in ("aws", "gcp", "azure"):
        assert "cache" in _kinds(_tiers(fast, provider)["Most reliable"]), (
            f"{provider}: p99 target over a key-value store, no cache"
        )


@needs_db
def test_a_small_workload_still_buys_no_cache():
    """The guard that stops this becoming a default: a cache billing $38 a
    month to memoise queries a site serving two hundred visitors a day does
    not repeat often enough."""
    tiny = Requirement(
        goal="Internal tool", workload_type="web", audience="internal",
        traffic_scale="low", region="india",
    )
    for label in ("Cheapest", "Most reliable"):
        # The top tier turns on everything a well-resourced team would run and
        # is excluded on purpose; these two are sized to the workload.
        assert "cache" not in _kinds(_tiers(tiny, "aws")[label]), (
            f"{label}: cache for a low-traffic tool"
        )


# ── 8. the shape comes from the axes, not from two booleans ───────────────


def test_files_arriving_in_near_real_time_is_a_function_pipeline():
    """The axes exist to DRIVE the architecture, and were not being read.

    Documents uploaded and classified at two thousand an hour came back with
    every flag false and got a load-balanced fleet of always-on servers --
    for work that is bursty, arrives as uploads, and is idle between them.
    """
    uploads = Requirement(
        goal="Process uploaded documents", workload_type="api",
        ingress_shape="files", processing_mode="near-real-time",
        needs_queue=True, traffic_pattern="spiky", region="india",
    )
    assert uploads.is_serverless
    assert not uploads.is_event_driven, "files are functions, streams are processors"

    stream = Requirement(
        goal="Clickstream", workload_type="api", ingress_shape="streams",
        processing_mode="near-real-time", region="india",
    )
    assert stream.is_event_driven
    assert not stream.is_serverless


@needs_db
def test_a_document_pipeline_runs_no_always_on_fleet():
    uploads = Requirement(
        goal="Process uploaded documents", workload_type="api",
        ingress_shape="files", processing_mode="near-real-time",
        data_shape="document", needs_queue=True, needs_notifications=True,
        traffic_pattern="spiky", traffic_scale="low", region="india",
    )
    for provider in ("aws", "gcp", "azure"):
        kinds = _kinds(_tiers(uploads, provider)["Most reliable"])
        assert "lambda" in kinds, f"{provider}: no functions"
        assert "compute" not in kinds, f"{provider}: always-on servers"
        assert "loadbalancer" not in kinds, f"{provider}: a balancer with no fleet"


def test_a_queue_is_not_evidence_of_an_application_tier():
    """Buffering bursty arrivals so the processor is not sized for the peak
    IS the job of an event pipeline. Reading a queue as proof of a full
    application inverted the test: the pipeline was handed always-on servers
    BECAUSE it asked for the one component that says it does not need them."""
    from whichcloud.engine import _has_application_tier

    queue_only = Requirement(
        goal="Pipeline", workload_type="api", needs_queue=True, region="india",
    )
    assert not _has_application_tier(queue_only)


# ── 9. volumes derived from the right quantity ────────────────────────────


def test_tracing_volume_follows_requests_not_data_volume():
    """`traffic_scale` on a batch job measures DATA, so a nightly ETL over
    2 TB landed in the `high` bucket and was billed for twenty million traces
    -- $99.50/month of X-Ray for a job that runs thirty times, and the single
    largest line on that architecture."""
    from whichcloud.engine import TRACING_MONTHLY_TRACES, tracing_traces_for

    batch = Requirement(
        goal="Nightly ETL", workload_type="batch", traffic_scale="high",
        region="india",
    )
    serving = Requirement(
        goal="Busy API", workload_type="api", traffic_scale="high", region="india",
    )
    assert tracing_traces_for(batch) == TRACING_MONTHLY_TRACES["low"]
    assert tracing_traces_for(serving) == TRACING_MONTHLY_TRACES["high"]


@needs_db
def test_google_functions_are_not_five_times_cheaper_than_everyone_else():
    """Cloud Run bills vCPU and memory as TWO meters; Lambda and Azure
    Functions fold both into one GB-second rate. Charging only memory put
    Google's serverless at $17 against $98 and $107 for identical work -- a
    5x lead it does not have, on a meter nobody had charged.

    Warm instances are billed on Google's min-instance meter, which this
    catalog does not carry, so that part is REPORTED rather than guessed:
    an estimate that says it is incomplete cannot win a comparison it cannot
    deliver on.
    """
    spec = ArchitectureSpec(
        name="fn", region="india", compute_count=0,
        lambda_invocations_per_month=1_440_000, lambda_avg_ms=150.0,
        lambda_memory_mb=512.0,
    )
    totals = {}
    for provider in ("aws", "gcp", "azure"):
        est = estimate(spec, provider)
        totals[provider] = float(
            sum(i.monthly_usd for i in est.items if "Lambda" in i.label)
        )
    # The defect was Google being FIVE TIMES CHEAPER on a meter nobody had
    # charged. Cloud Run genuinely costs more per invocation than Lambda for
    # a short handler -- Lambda's ARM rate is aggressive -- so the guard is
    # against the under-price, not against Google being dearer.
    assert totals["gcp"] > totals["aws"], (
        f"Google is cheaper than AWS for identical serverless work: {totals}"
    )
    assert totals["gcp"] < totals["aws"] * 4, f"overcorrected: {totals}"
