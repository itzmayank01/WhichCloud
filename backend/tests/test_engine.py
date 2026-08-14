"""Tests for the engine: requirements, knowledge base, matching, sizing.

Database-backed tests skip cleanly when Postgres is not running, so the suite
is still useful on a fresh checkout.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from whichcloud import engine
from whichcloud.knowledge import (
    KnowledgeBaseError,
    load_techniques,
    match_all,
    parse_technique,
    rejected,
)
from whichcloud.requirements import Requirement


@pytest.fixture(scope="module")
def techniques():
    return load_techniques()


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


# ── requirement validation ──────────────────────────────────────────────


def test_requirement_rejects_unknown_workload():
    with pytest.raises(ValueError, match="workload_type"):
        Requirement(goal="x", workload_type="quantum")


def test_requirement_rejects_negative_budget():
    with pytest.raises(ValueError, match="budget"):
        Requirement(goal="x", budget_monthly_usd=-5)


def test_requirement_rejects_negative_volumes():
    with pytest.raises(ValueError, match="negative"):
        Requirement(goal="x", egress_gb=-1)


def test_from_dict_rejects_unknown_fields():
    """An LLM will eventually emit these dicts; a typo must fail loudly."""
    with pytest.raises(ValueError, match="unknown requirement fields"):
        Requirement.from_dict({"goal": "x", "budgetUSD": 400})


def test_from_dict_round_trips():
    req = Requirement.from_dict(
        {"goal": "shop", "workload_type": "web", "compliance": ["GDPR"]}
    )
    assert req.goal == "shop"
    assert req.compliance == ("GDPR",)


def test_workload_shape_properties():
    assert Requirement(goal="x", workload_type="web").needs_database
    assert not Requirement(goal="x", workload_type="batch").needs_database
    assert Requirement(goal="x", workload_type="ml").is_batch


# ── knowledge base loading ──────────────────────────────────────────────


def test_knowledge_base_loads(techniques):
    assert len(techniques) >= 3
    ids = {t.id for t in techniques}
    assert "graviton-arm-compute" in ids
    assert "spot-interruptible-capacity" in ids


def test_every_technique_has_a_tool(techniques):
    """Advice without a tool is not actionable — a curation rule, enforced."""
    for t in techniques:
        assert t.tools, f"{t.id} has no implemented_by entry"


def test_every_technique_states_tradeoffs(techniques):
    """A technique with no downside is one nobody understood yet."""
    for t in techniques:
        assert t.tradeoffs, f"{t.id} lists no tradeoffs"


def test_effect_requires_counterfactual(tmp_path: Path):
    """Without a counterfactual there is nothing to measure a saving against."""
    doc = {
        "id": "x",
        "name": "X",
        "category": "compute",
        "summary": "s",
        "savings": {"typical_pct": 10},
        "providers": ["aws"],
        "effect": {"arch": "arm64"},
    }
    with pytest.raises(KnowledgeBaseError, match="counterfactual"):
        parse_technique(doc, tmp_path / "x.yaml")


def test_unknown_effect_is_rejected(tmp_path: Path):
    """A typo'd effect must fail loudly, not become a silent no-op."""
    doc = {
        "id": "x",
        "name": "X",
        "category": "compute",
        "summary": "s",
        "savings": {},
        "providers": ["aws"],
        "effect": {"architecture": "arm64"},
        "counterfactual": {"architecture": "x86_64"},
    }
    with pytest.raises(KnowledgeBaseError, match="not something the"):
        parse_technique(doc, tmp_path / "x.yaml")


def test_missing_required_field_is_rejected(tmp_path: Path):
    with pytest.raises(KnowledgeBaseError, match="missing fields"):
        parse_technique({"id": "x"}, tmp_path / "x.yaml")


def test_duplicate_ids_are_rejected(tmp_path: Path):
    doc = {
        "id": "dupe",
        "name": "X",
        "category": "compute",
        "summary": "s",
        "savings": {},
        "providers": ["aws"],
    }
    (tmp_path / "a.yaml").write_text(yaml.safe_dump(doc))
    (tmp_path / "b.yaml").write_text(yaml.safe_dump(doc))
    with pytest.raises(KnowledgeBaseError, match="duplicate"):
        load_techniques(tmp_path)


def test_malformed_yaml_is_rejected(tmp_path: Path):
    (tmp_path / "bad.yaml").write_text("id: [unclosed")
    with pytest.raises(KnowledgeBaseError):
        load_techniques(tmp_path)


# ── technique matching ──────────────────────────────────────────────────


def test_spot_is_offered_to_interruptible_batch(techniques):
    req = Requirement(goal="ml", workload_type="batch", interruptible=True)
    ids = {m.technique.id for m in match_all(req, techniques, "aws", 500)}
    assert "spot-interruptible-capacity" in ids


def test_spot_is_withheld_from_web_traffic(techniques):
    req = Requirement(goal="shop", workload_type="web", interruptible=False)
    ids = {m.technique.id for m in match_all(req, techniques, "aws", 500)}
    assert "spot-interruptible-capacity" not in ids


def test_spot_is_withheld_when_work_cannot_restart(techniques):
    """Batch alone is not enough — losing an instance must be survivable."""
    req = Requirement(goal="ml", workload_type="batch", interruptible=False)
    ids = {m.technique.id for m in match_all(req, techniques, "aws", 500)}
    assert "spot-interruptible-capacity" not in ids


def test_arm_is_withheld_from_x86_only_workloads(techniques):
    req = Requirement(goal="legacy", workload_type="web", arm_compatible=False)
    ids = {m.technique.id for m in match_all(req, techniques, "aws", 500)}
    assert "graviton-arm-compute" not in ids


def test_rejections_carry_a_reason(techniques):
    req = Requirement(goal="shop", workload_type="web")
    reasons = dict(
        (t.id, why) for t, why in rejected(req, techniques, "aws", 500)
    )
    assert "spot-interruptible-capacity" in reasons
    assert reasons["spot-interruptible-capacity"]


def test_least_obvious_techniques_rank_first(techniques):
    """The non-obvious entry is the reason to use this over a pricing page."""
    req = Requirement(goal="shop", workload_type="web")
    matched = match_all(req, techniques, "aws", 500)
    obviousness = [m.technique.obviousness for m in matched]
    assert obviousness == sorted(
        obviousness, key=lambda o: {"low": 0, "medium": 1, "high": 2}.get(o, 3)
    )


def test_technique_below_spend_floor_is_skipped(techniques):
    """Graviton declares min_monthly_spend_usd: 30."""
    req = Requirement(goal="tiny", workload_type="web")
    ids = {m.technique.id for m in match_all(req, techniques, "aws", estimated_spend=5)}
    assert "graviton-arm-compute" not in ids


# ── sizing heuristics ───────────────────────────────────────────────────


def test_spiky_traffic_gets_more_instances():
    steady = Requirement(goal="x", traffic_pattern="steady", traffic_scale="medium")
    spiky = Requirement(goal="x", traffic_pattern="spiky", traffic_scale="medium")
    assert engine.size_for(spiky)[0] > engine.size_for(steady)[0]


def test_larger_scale_gets_more_capacity():
    low = engine.size_for(Requirement(goal="x", traffic_scale="low"))
    high = engine.size_for(Requirement(goal="x", traffic_scale="high"))
    assert high[0] >= low[0]
    assert high[1] >= low[1]
    assert high[2] >= low[2]


def test_batch_workloads_skip_the_database():
    spec = engine.base_spec(
        Requirement(goal="x", workload_type="batch"), "Cheapest"
    )
    assert spec.database_vcpu is None


def test_web_workloads_get_a_database():
    spec = engine.base_spec(Requirement(goal="x", workload_type="web"), "Balanced")
    assert spec.database_vcpu is not None


# ── end to end ──────────────────────────────────────────────────────────


@needs_db
def test_engine_returns_three_priced_options():
    req = Requirement(goal="shop", workload_type="web", traffic_scale="medium")
    options = engine.recommend(req, "aws")
    assert [o.label for o in options] == ["Cheapest", "Balanced", "Most reliable"]
    for option in options:
        assert option.monthly > 0
        assert option.estimate.items


@needs_db
def test_reliable_option_costs_more_than_cheapest():
    req = Requirement(goal="shop", workload_type="web", traffic_scale="medium")
    options = {o.label: o for o in engine.recommend(req, "aws")}
    assert options["Most reliable"].monthly > options["Cheapest"].monthly


@needs_db
def test_savings_are_measured_not_taken_from_the_knowledge_base():
    """The headline number must come from pricing, not from typical_pct.

    Graviton's YAML says 9%. The engine must report what it actually measured
    against the counterfactual SKU, which will differ.
    """
    req = Requirement(
        goal="ml", workload_type="batch", interruptible=True, traffic_scale="high"
    )
    option = engine.recommend(req, "aws")[0]
    assert option.applied, "expected at least one technique to apply"

    for applied in option.applied:
        assert applied.saved > 0
        assert applied.counterfactual_sku, "saving must name what it beat"
        # the measured figure is independent of the YAML's claim
        assert applied.technique.typical_pct is not None


@needs_db
def test_an_optimization_never_increases_the_bill():
    req = Requirement(goal="shop", workload_type="web", traffic_scale="medium")
    for option in engine.recommend(req, "aws"):
        for applied in option.applied:
            assert applied.saved > 0, f"{applied.technique.id} raised the cost"


@needs_db
def test_unpriceable_techniques_stay_out_of_the_total():
    """zram is advice; it must never be folded into a measured saving."""
    req = Requirement(goal="shop", workload_type="web", traffic_scale="medium")
    for option in engine.recommend(req, "aws"):
        applied_ids = {a.technique.id for a in option.applied}
        assert "zram-memory-compression" not in applied_ids
        advisory_ids = {m.technique.id for m in option.advisory}
        assert "zram-memory-compression" in advisory_ids


@needs_db
def test_counterfactual_names_the_line_it_replaced():
    """REGRESSION: reporting items[0] credited a database technique with
    beating a compute instance ('ARM database ... vs t4g.large')."""
    req = Requirement(
        goal="shop", workload_type="web", traffic_scale="medium",
        traffic_pattern="spiky",
    )
    options = engine.recommend(req, "aws")
    for option in options:
        for applied in option.applied:
            sku = applied.counterfactual_sku
            if applied.technique.category == "database":
                assert sku.startswith("db."), (
                    f"database technique cites {sku!r}, not a database SKU"
                )


@needs_db
def test_more_knowledge_means_more_measured_saving():
    """The engine is only as good as the knowledge base feeding it."""
    req = Requirement(
        goal="shop", workload_type="web", traffic_scale="medium",
        traffic_pattern="spiky",
    )
    option = engine.recommend(req, "aws")[0]
    assert len(option.applied) >= 2, "expected several techniques to apply"
    assert option.measured_saving > 0


def test_mixed_workloads_are_not_silently_starved(techniques):
    """REGRESSION: 'mixed' is a valid workload_type the engine accepts, but
    four techniques omitted it from applies_when. A video platform labelled
    'mixed' instead of 'web' silently lost Graviton and scale-to-zero —
    $32.73/mo on a medium workload — with no indication anything was skipped.

    The rule: a technique that suits both web and api suits mixed, since mixed
    is those combined. Techniques scoped to batch/ml only (spot) are exempt —
    a mixed workload serves live traffic, so reclaimable capacity is correctly
    withheld.
    """
    for t in techniques:
        if {"web", "api"} <= set(t.workload_types):
            assert "mixed" in t.workload_types, (
                f"{t.id} applies to web and api but not mixed"
            )


def test_recommend_cli_parser_builds():
    """REGRESSION: a second --provider flag was added for the model provider,
    colliding with the existing one for the cloud. argparse raises at parser
    construction, so every CLI invocation crashed — but no test touched the
    parser, so the suite stayed green. This builds it."""
    import importlib.util
    import sys
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "scripts" / "recommend.py"
    spec = importlib.util.spec_from_file_location("recommend_cli", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["recommend_cli"] = module
    spec.loader.exec_module(module)

    # main() builds the parser; call it with --help, which exits cleanly.
    sys.argv = ["recommend.py", "--help"]
    with pytest.raises(SystemExit) as exc:
        module.main()
    assert exc.value.code == 0
