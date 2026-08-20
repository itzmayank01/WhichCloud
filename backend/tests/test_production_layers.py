"""Tests for the production baseline and data-pipeline layers.

These cover the components added after the original seven-category engine:
read replicas, WAF, audit logging, KMS, NAT gateways, DNS, authentication,
backup, and the streaming/search/warehouse pipeline.

They live in their own module rather than in test_engine.py because they
test one question that file does not: whether adding a layer quietly broke
the layers already there. Several exist because the corresponding bug was
real -- those are marked REGRESSION-GUARD.
"""

from __future__ import annotations

import pytest

from whichcloud import engine
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


def reliable(req: Requirement):
    return {o.label: o for o in engine.recommend(req, "aws")}["Most reliable"]


def optimized(req: Requirement):
    return {o.label: o for o in engine.recommend(req, "aws")}["Most optimized"]


def labels(option) -> list[str]:
    return [i.label for i in option.estimate.items]


# ── read replicas ───────────────────────────────────────────────────────


def test_read_replicas_only_on_the_reliability_tier():
    """A replica is a reliability/scale feature, so it belongs where Multi-AZ
    already is -- not baked into every tier's default shape."""
    req = Requirement(goal="x", workload_type="web", traffic_scale="high")
    variants = {label: delta for label, _, delta, _ in engine._shape_variants(req)}
    assert variants["Most reliable"].get("database_read_replicas") == 2
    assert "database_read_replicas" not in variants["Cheapest"]
    # "Most optimized" adds replicas deliberately; only Cheapest goes without.
    assert "database_read_replicas" not in variants["Cheapest"]


def test_read_replicas_are_scale_gated_too():
    low = Requirement(goal="x", workload_type="web", traffic_scale="low")
    variants = {label: delta for label, _, delta, _ in engine._shape_variants(low)}
    assert "database_read_replicas" not in variants["Most reliable"]


def test_batch_workloads_never_get_replicas():
    """A batch job has no database, so a replica would replicate nothing."""
    req = Requirement(goal="x", workload_type="batch", traffic_scale="high")
    variants = {label: delta for label, _, delta, _ in engine._shape_variants(req)}
    assert "database_read_replicas" not in variants["Most reliable"]


@needs_db
def test_read_replicas_are_priced_for_real():
    option = reliable(
        Requirement(goal="shop", workload_type="web", traffic_scale="high")
    )
    lines = [i for i in option.estimate.items if "read replica" in i.label]
    assert len(lines) == 1
    assert lines[0].label == "Database read replica × 2"
    assert lines[0].monthly_usd > 0


# ── security & hygiene ──────────────────────────────────────────────────


@needs_db
def test_waf_is_priced_on_every_tier():
    """WAF is a security control, not a reliability upgrade: a workload that
    named an attack surface needs it on Cheapest as much as anywhere."""
    options = engine.recommend(
        Requirement(goal="shop", workload_type="web", needs_waf=True), "aws"
    )
    for option in options:
        waf = [i for i in option.estimate.items if "WAF" in i.label]
        assert "WAF Web ACL" in {i.label for i in waf}
        assert sum(i.monthly_usd for i in waf) > 0


@needs_db
def test_no_waf_when_no_attack_surface_was_named():
    """Except on "Most optimized", which turns protection on deliberately --
    that tier assumes an attack surface exists rather than waiting to be
    told about one. The cheaper tiers still only get WAF when asked."""
    options = {o.label: o for o in engine.recommend(
        Requirement(goal="shop", workload_type="web"), "aws"
    )}
    for label in ("Cheapest", "Most reliable"):
        assert not any("WAF" in i.label for i in options[label].estimate.items)
    assert any("WAF" in i.label for i in options["Most optimized"].estimate.items)


@needs_db
def test_audit_logging_is_present_and_genuinely_free():
    """REGRESSION-GUARD: CloudTrail's free trail is a real published $0. It
    must appear priced at zero, not vanish because a zero price was treated
    as no price at all -- which is what `_decimal` does everywhere else."""
    for option in engine.recommend(Requirement(goal="shop", workload_type="web"), "aws"):
        audit = [i for i in option.estimate.items if i.label == "Audit logging"]
        assert len(audit) == 1
        assert audit[0].monthly_usd == 0


@needs_db
def test_kms_key_only_where_there_is_a_database_to_encrypt():
    with_db = reliable(Requirement(goal="shop", workload_type="web"))
    kms = [i for i in with_db.estimate.items if "KMS" in i.label]
    assert len(kms) == 1
    assert kms[0].monthly_usd > 0

    without_db = reliable(Requirement(goal="job", workload_type="batch"))
    assert not any("KMS" in i.label for i in without_db.estimate.items)


# ── networking ──────────────────────────────────────────────────────────


@needs_db
def test_nat_gateways_follow_the_zones_the_tier_spans():
    """~$41/mo each and the line people most often forget. One zone gets one
    gateway; the multi-zone tiers get two, because a single gateway would
    strand the other zone in exactly the failure the tier pays to survive."""
    options = {
        o.label: o
        for o in engine.recommend(Requirement(goal="shop", workload_type="web"), "aws")
    }

    def gateways(option):
        line = next(i for i in option.estimate.items if i.label.startswith("NAT gateway"))
        return int(line.label.split("×")[1].strip())

    assert gateways(options["Cheapest"]) == 1
    assert gateways(options["Most reliable"]) == 2
    # Three zones on the top tier: two survives losing one, three survives
    # losing one while another is being patched.
    assert gateways(options["Most optimized"]) == 3
    assert gateways(options["Most reliable"]) == 2
    for option in options.values():
        assert any(
            i.label.startswith("NAT gateway") and i.monthly_usd > 0
            for i in option.estimate.items
        )


@needs_db
def test_dns_is_never_missing_from_a_production_blueprint():
    """REGRESSION-GUARD: hosted zones are published only in the global
    `aws-other` feed. Reading the regional file found nothing and returned
    an empty list, so DNS was silently absent from every architecture."""
    option = reliable(Requirement(goal="shop", workload_type="web"))
    zone = [i for i in option.estimate.items if i.label.startswith("DNS hosted zone")]
    assert len(zone) == 1
    assert zone[0].monthly_usd > 0


# ── data pipeline & analytics ───────────────────────────────────────────


def test_shard_count_is_derived_from_the_stated_transaction_rate():
    """Arithmetic, not a tier lookup: a shard ingests 1,000 records/second,
    so the count follows from the volume the description actually gave."""
    small = Requirement(goal="x", needs_event_streaming=True, daily_transactions=50_000)
    assert engine.stream_shards_for(small) == 1

    # 8.64M/day = 100/s mean; x4 peak = 400/s -> still one shard.
    mid = Requirement(goal="x", needs_event_streaming=True, daily_transactions=8_640_000)
    assert engine.stream_shards_for(mid) == 1

    # 86.4M/day = 1,000/s mean; x4 peak = 4,000/s -> four shards.
    big = Requirement(goal="x", needs_event_streaming=True, daily_transactions=86_400_000)
    assert engine.stream_shards_for(big) == 4


def test_volume_sizes_the_stream_but_the_requirement_decides_it_exists():
    """A high-volume CRUD app that never asked for streaming must not
    acquire a pipeline just because it is big."""
    req = Requirement(
        goal="x", needs_event_streaming=False, daily_transactions=50_000_000
    )
    assert engine.stream_shards_for(req) == 0
    assert not engine._wants_kafka(req)


def test_kafka_only_above_its_volume_threshold():
    """MSK's three-broker minimum costs many times a single Kinesis shard,
    so it is only the honest default where volume actually justifies it."""
    assert not engine._wants_kafka(
        Requirement(goal="x", needs_event_streaming=True, daily_transactions=999_999)
    )
    assert engine._wants_kafka(
        Requirement(goal="x", needs_event_streaming=True, daily_transactions=1_000_000)
    )


@needs_db
def test_pipeline_prices_for_real_without_losing_the_baseline():
    """The whole risk of this layer: that adding it quietly drops a
    component the ten-layer production baseline already guaranteed.

    Checked on "Most optimized", because the pipeline is that tier's
    architectural choice -- the cheaper tiers answer the same requirement
    from the database they already have.
    """
    option = optimized(
        Requirement(
            goal="retail",
            workload_type="web",
            traffic_scale="medium",
            needs_event_streaming=True,
            needs_analytics=True,
            needs_search=True,
            daily_transactions=50_000,
        )
    )

    for expected in ("Event stream shards", "Search nodes", "Warehouse nodes"):
        matched = [i for i in option.estimate.items if i.label.startswith(expected)]
        assert len(matched) == 1, f"{expected} missing"
        assert matched[0].monthly_usd > 0, f"{expected} priced at zero"

    for baseline in (
        "Compute", "Database", "NAT gateway", "DNS hosted zone",
        "Load balancer", "Audit logging", "KMS keys", "Cache", "Monitoring",
    ):
        assert any(l.startswith(baseline) for l in labels(option)), f"{baseline} lost"

    # These were honest gaps before the adapters existed; they are real
    # priced lines now, so the gap text must be gone.
    assert not any("not yet priced" in m for m in option.estimate.missing)


@needs_db
def test_a_plain_workload_gets_no_pipeline_at_all():
    """The layer is conditional. A description asking for none of it must
    come out with the same bill it had before the layer existed."""
    option = reliable(Requirement(goal="shop", workload_type="web"))
    for absent in ("Event stream", "Kafka", "Search", "Warehouse"):
        assert not any(i.label.startswith(absent) for i in option.estimate.items)


@needs_db
def test_the_diagram_total_equals_the_bill_total():
    """The property the whole product rests on: what is drawn and what is
    charged can never disagree, however many layers are switched on."""
    from whichcloud import topology as topo

    option = reliable(
        Requirement(
            goal="retail",
            workload_type="web",
            needs_event_streaming=True,
            needs_analytics=True,
            needs_search=True,
            needs_waf=True,
            daily_transactions=50_000,
        )
    )
    graph = topo.build(option.spec, option.estimate, option.applied)
    assert graph.total_monthly == option.estimate.total_monthly


# ── compute sizing & arch detection ─────────────────────────────────────


def test_fargate_task_counts_are_derived_from_stated_volume():
    """Arithmetic where the description gives a number, with a floor of two
    because one task cannot survive losing its zone."""
    quiet = Requirement(goal="x", daily_transactions=8_000)
    assert engine.fargate_tasks_for(quiet) == (2, 2)

    # 1.5M/day is ~17 rps mean, x4 peak = ~69 rps -> 3 tasks at peak.
    busy = Requirement(goal="x", daily_transactions=1_500_000)
    base, peak = engine.fargate_tasks_for(busy)
    assert base == 2
    assert peak == 3

    # No stated volume still gets the availability floor, never one task.
    assert engine.fargate_tasks_for(Requirement(goal="x"))[0] >= 2


def test_fargate_is_opt_in_not_a_second_compute_tier():
    """REGRESSION-GUARD: setting Fargate while compute_count still held EC2
    instances billed both, roughly $42/mo of compute nobody asked for."""
    spec = engine.base_spec(Requirement(goal="x", workload_type="web"), "Most reliable")
    assert spec.fargate_task_count == 0
    assert spec.compute_count > 0


def test_graviton_families_are_detected_by_family_not_substring():
    """REGRESSION-GUARD: the old check looked for '.r6g.', which never
    matches 'r6g.large.search' because the family leads rather than sits
    between dots -- so every ARM OpenSearch node was labelled x86_64."""
    from whichcloud.pricing.aws import _arch_of

    for arm in ("r6g.large.search", "m7g.xlarge.search", "c8g.large.search",
                "r7gd.large.search", "i8ge.large.search"):
        assert _arch_of(arm) == "arm64", arm
    # Intel/AMD families end in a letter that is not 'g'.
    for x86 in ("m7i.large.search", "c7i.large.search", "i4i.large.search",
                "t3.small.search", "m5.large.search"):
        assert _arch_of(x86) == "x86_64", x86


@needs_db
def test_secrets_are_priced_where_there_is_a_database():
    option = reliable(Requirement(goal="shop", workload_type="web"))
    secrets = [i for i in option.estimate.items if i.label.startswith("Secrets")]
    assert len(secrets) == 1
    assert secrets[0].monthly_usd > 0

    batch = reliable(Requirement(goal="job", workload_type="batch"))
    assert not any(i.label.startswith("Secrets") for i in batch.estimate.items)


# ── the API boundary ────────────────────────────────────────────────────


def test_the_api_accepts_every_requirement_field_that_changes_the_shape():
    """REGRESSION-GUARD: RecommendIn is a hand-written mirror of Requirement,
    so it drifts silently. It once dropped daily_transactions and every
    needs_* signal, which meant the form path could not ask for streaming,
    analytics or search at all, and a stated volume never reached sizing --
    ten times the load produced an identical architecture."""
    from whichcloud.api import RecommendIn

    accepted = set(RecommendIn.model_fields)
    shape_changing = {
        "workload_type", "traffic_pattern", "traffic_scale", "region",
        "budget_monthly_usd", "storage_gb", "egress_gb", "interruptible",
        "high_availability", "arm_compatible", "provider_preference",
        "needs_waf", "needs_event_streaming", "needs_analytics",
        "needs_search", "daily_transactions", "latency_target_ms",
    }
    assert shape_changing <= accepted, shape_changing - accepted


def test_volume_drives_the_shape_rather_than_the_tier_alone():
    """A hundredfold difference in load must not produce identical hardware.
    The tier table is a floor; a stated volume is the answer."""
    def shape(n: int):
        req = Requirement(goal="x", traffic_scale="high", daily_transactions=n)
        return engine.size_for(req), engine.db_size_for(req)

    small = shape(500_000)
    huge = shape(50_000_000)
    assert huge != small
    # More compute, and a database sized for the write rate.
    assert huge[0][0] >= small[0][0]
    assert huge[1][0] > small[1][0]


def test_no_stated_volume_keeps_the_tier_floor():
    """Absent a number the engine must not invent one -- it falls back to
    the conventional starting point and says so."""
    req = Requirement(goal="x", traffic_scale="medium")
    assert engine.peak_rps_for(req) == 0.0
    assert engine.size_for(req) == engine.BASE_SIZING["medium"]


def test_cross_region_backup_is_priced_leaving_this_region_not_entering_it():
    """REGRESSION-GUARD: AWS names the meter "{SOURCE}-{DEST}-CrossRegion-..."
    and the regional file contains BOTH directions of every pair.

    Taking the cheapest of all of them picked "USE2-USE1" -- the rate for
    copying INTO us-east-1 -- and quoted $0.01/GB for an architecture whose
    copies actually leave it. Half the real cost, from a meter that is
    genuinely published and genuinely irrelevant.
    """
    from whichcloud.pricing import aws

    points = aws.load_backup_copy_prices("eu-west")
    assert points, "no cross-region backup price returned"
    point = points[0]

    # eu-west-1's cheapest outbound destination is a real region, and the
    # rate is the outbound one. If the direction flips, this lands on an
    # inbound meter and the destination stops being reachable from here.
    assert point.attributes["cheapest_destination"]
    assert point.attributes["resource_class"] == "database"
    assert point.price_usd > 0


def test_india_can_satisfy_residency_and_durability_together():
    """Both requirements hold at once, because India has two AWS regions.

    This test previously asserted the opposite. That was wrong, and wrong
    in the most misleading way available: it read a gap in our own catalog
    -- only Mumbai had been ingested -- as a fact about the country, and
    told a hospital its residency and durability requirements could not
    both be met. AWS has published ap-south-2 since 2022.

    The lesson is kept in the assertion below: coverage is a property of
    the catalog and must never be reported as a property of the world.
    """
    from whichcloud.planner import in_country_regions
    from whichcloud.pricing.store import connect

    with connect() as conn, conn.cursor() as cur:
        cur.execute(
            "select count(distinct region) n from price_points"
            " where provider = 'aws' and region like 'ap-south-%'"
        )
        ingested = cur.fetchone()["n"]

    assert ingested >= 2, (
        "ap-south-2 is missing from the catalog; without it a residency-locked "
        "Indian workload cannot be given a compliant cross-region copy"
    )
    assert len(in_country_regions("India")) >= 2
