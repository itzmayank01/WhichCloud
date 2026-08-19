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
    assert "database_read_replicas" not in variants["Balanced"]


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
    options = engine.recommend(Requirement(goal="shop", workload_type="web"), "aws")
    assert not any("WAF" in i.label for o in options for i in o.estimate.items)


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
    assert len(kms) == 1 and kms[0].monthly_usd > 0

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
    assert gateways(options["Balanced"]) == 2
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
    component the ten-layer production baseline already guaranteed."""
    option = reliable(
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
