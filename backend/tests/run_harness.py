#!/usr/bin/env python3
"""Regression harness for the WhichCloud reasoning + tier-generation engine.

The gates the engine applies (Multi-AZ under availability=high, a cache
only at medium+ load and read-heavy, a CDN only when public-facing...)
were derived from one healthcare prompt. The risk this harness exists to
catch is the opposite of that prompt's original bug: the engine refusing
a component it should select, because a gate meant for one workload got
applied to all of them. Every fixture is one prompt, one set of expected
components, and a reason attached to every yes and every no.

    python tests/run_harness.py                  # every fixture
    python tests/run_harness.py --fixture FOO     # just FOO, for iterating
    python tests/run_harness.py --no-report       # skip report.md/history

Exits non-zero if any assertion in any fixture failed.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from whichcloud import plan as plan_module  # noqa: E402
from whichcloud.constraint_filter import check as filter_check  # noqa: E402
from whichcloud.objectives import compliance_notes  # noqa: E402
from whichcloud.plan import Plan  # noqa: E402
from whichcloud.pricing import store as pricing_store  # noqa: E402
from whichcloud.pricing.models import provider_region  # noqa: E402

FIXTURES_DIR = Path(__file__).parent / "fixtures"
REPORT_PATH = Path(__file__).parent / "report.md"
HISTORY_PATH = Path(__file__).parent / "harness_history.jsonl"
GOLDEN_PATH = Path(__file__).parent / "golden_totals.json"


# ─────────────────────────── assertion plumbing ───────────────────────────


@dataclass
class Result:
    fixture_id: str
    assertion_id: str
    passed: bool
    expected: str
    actual: str
    reason: str = ""  # the engine's own stated reason, when one exists


@dataclass
class FixtureRun:
    fixture_id: str
    results: list[Result] = field(default_factory=list)
    error: str | None = None
    tier_totals: dict[str, float] = field(default_factory=dict)

    @property
    def passed(self) -> list[Result]:
        return [r for r in self.results if r.passed]

    @property
    def failed(self) -> list[Result]:
        return [r for r in self.results if not r.passed]

    @property
    def ok(self) -> bool:
        return self.error is None and not self.failed


# ─────────────────────── component id -> predicate ────────────────────────
# What each fixture's "component" name checks against a priced Tier. Kept
# as one small table so a fixture author writes "cdn", not
# "tier.spec.cdn_gb > 0" -- the mapping is the one place that has to know
# the spec's field names.

COMPONENT_CHECKS = {
    "cross_region_backup_copy": lambda t: t.spec.backup_copy_gb > 0,
    "object_lock": lambda t: t.spec.object_lock,
    "multi_az_database": lambda t: t.spec.database_multi_az,
    "load_balancer": lambda t: t.spec.load_balancer,
    "read_replica": lambda t: t.spec.database_read_replicas > 0,
    "cache": lambda t: t.spec.cache_vcpu is not None,
    "cdn": lambda t: t.spec.cdn_gb > 0,
    "waf": lambda t: t.spec.waf_rule_count is not None,
    # Not a literal Auto Scaling Group flag -- this catalog does not model
    # scaling policies. Read as "compute sized above the availability
    # floor of 2", which is the observable trace of sizing having
    # responded to load rather than staying at the HA minimum.
    "autoscaling_compute": lambda t: (t.spec.compute_count or t.spec.fargate_task_count) > 2,
    "extended_retention_audit": lambda t: t.spec.audit_logging and t.spec.lifecycle_gb > 0,
    "nat_gateway": lambda t: t.spec.nat_gateway_count > 0,
    "vpc_flow_logs": lambda t: t.spec.flowlog_gb > 0,
}

#: When a must_exclude component is correctly absent, the reason usually
#: lives in load.excluded_with_reason under one of these labels.
_EXCLUSION_MARKER = {
    "cache": "ElastiCache",
    "read_replica": "Read replica",
    "cdn": "CloudFront",
    "waf": "AWS WAF",
}

#: nat_gateway/vpc_flow_logs are a topology decision, not a load gate --
#: their absence is explained by Plan.network_topology_reason, not by
#: anything in load.excluded_with_reason.
_TOPOLOGY_DRIVEN = {"nat_gateway", "vpc_flow_logs"}


def _excluded_reason(plan: Plan, component: str) -> str:
    if component in _TOPOLOGY_DRIVEN:
        return plan.network_topology_reason or "(no topology reason recorded)"
    marker = _EXCLUSION_MARKER.get(component)
    if marker:
        for line in plan.load.excluded_with_reason:
            if line.startswith(marker):
                return line
    return "(no exclusion reason recorded -- rung-1/2 items are gated by " \
           "extraction, not by the load model's excluded_with_reason list)"


# ─────────────────────────── prompt fixture checks ─────────────────────────


def _check_extraction(fx: dict, built: Plan) -> list[Result]:
    results = []
    c = built.constraints
    for field_name, spec in fx.get("extraction", {}).items():
        expected_value = spec["value"]
        expected_source = spec["source"]
        actual_value = getattr(c, field_name)
        actual_source = c.source(field_name)
        # Booleans/enums come through as their native type or a string --
        # compare on string form so "IN" == "IN" and True == "true" both
        # work from YAML's native bool/str typing.
        value_ok = str(actual_value).lower() == str(expected_value).lower()
        source_ok = actual_source == expected_source
        results.append(Result(
            fx["id"], f"extraction:{field_name}",
            passed=value_ok and source_ok,
            expected=f"{expected_value} ({expected_source})",
            actual=f"{actual_value} ({actual_source})",
            reason=c.evidence.get(field_name, ""),
        ))
    return results


def _check_sizing(fx: dict, built: Plan) -> list[Result]:
    results = []
    spec = fx.get("sizing")
    if not spec:
        return results
    basis = built.load.sizing_basis()
    for key in ("avg_rps", "peak_rps"):
        if key not in spec:
            continue
        expected = spec[key]
        actual = basis[key]
        tolerance = abs(expected) * 0.10 or 0.01
        ok = abs(actual - expected) <= tolerance
        results.append(Result(
            fx["id"], f"sizing:{key}", passed=ok,
            expected=f"{expected} (+/-10%)", actual=str(actual),
            reason=basis["sized_from"],
        ))
    if "load_tier" in spec:
        ok = basis["load_tier"] == spec["load_tier"]
        results.append(Result(
            fx["id"], "sizing:load_tier", passed=ok,
            expected=spec["load_tier"], actual=basis["load_tier"],
            reason=basis["sized_from"],
        ))
    return results


def _check_must_include(fx: dict, built: Plan) -> list[Result]:
    results = []
    for entry in fx.get("expect", {}).get("must_include", []) or []:
        component, tiers = entry["component"], entry["tiers"]
        check_fn = COMPONENT_CHECKS[component]
        for tier in built.tiers:
            if tier.name not in tiers:
                continue
            present = check_fn(tier)
            results.append(Result(
                fx["id"], f"must_include:{component}:{tier.name}",
                passed=present,
                expected=f"{component} present", actual="present" if present else "absent",
                reason="" if present else _excluded_reason(built, component),
            ))
    return results


def _check_must_exclude(fx: dict, built: Plan) -> list[Result]:
    results = []
    for component in fx.get("expect", {}).get("must_exclude", []) or []:
        check_fn = COMPONENT_CHECKS[component]
        for tier in built.tiers:
            present = check_fn(tier)
            results.append(Result(
                fx["id"], f"must_exclude:{component}:{tier.name}",
                passed=not present,
                expected=f"{component} absent", actual="present" if present else "absent",
                reason=_excluded_reason(built, component) if not present else
                       f"{component} was priced on {tier.name} -- see its line items",
            ))
    return results


def _check_compliance(fx: dict, built: Plan) -> list[Result]:
    results = []
    names = [n["regulation"] for n in built.compliance]
    for expected in fx.get("expect", {}).get("compliance", []) or []:
        ok = any(expected in n for n in names)
        results.append(Result(
            fx["id"], f"compliance:{expected}", passed=ok,
            expected=f"cites {expected}", actual="; ".join(names) or "(none)",
        ))
    for forbidden in fx.get("expect", {}).get("forbidden", []) or []:
        ok = not any(forbidden in n for n in names)
        results.append(Result(
            fx["id"], f"forbidden:{forbidden}", passed=ok,
            expected=f"never cites {forbidden}", actual="; ".join(names) or "(none)",
        ))
    return results


def _check_budget(fx: dict, built: Plan) -> list[Result]:
    results = []
    budget = built.constraints.budget_monthly_usd
    for tier_name, expected in (fx.get("expect", {}).get("budget") or {}).items():
        tier = next((t for t in built.tiers if t.name == tier_name), None)
        if tier is None:
            results.append(Result(
                fx["id"], f"budget:{tier_name}", passed=False,
                expected=str(expected), actual="tier not found",
            ))
            continue
        actual = tier.within_budget(budget)
        results.append(Result(
            fx["id"], f"budget:{tier_name}", passed=actual == expected,
            expected=str(expected), actual=str(actual),
            reason=f"${tier.monthly_total:,.2f} vs ${budget:,.2f} budget",
        ))
    note_substr = fx.get("expect", {}).get("over_budget_note_contains")
    if note_substr:
        ok = note_substr in built.over_budget_note
        results.append(Result(
            fx["id"], "over_budget_note", passed=ok,
            expected=f"contains {note_substr!r}", actual=built.over_budget_note,
        ))
    return results


def _check_network_topology(fx: dict, built: Plan) -> list[Result]:
    expected = fx.get("expect", {}).get("network_topology")
    if not expected:
        return []
    ok = built.network_topology == expected
    return [Result(
        fx["id"], "network_topology", passed=ok,
        expected=expected, actual=built.network_topology,
        reason=built.network_topology_reason,
    )]


# ──────────────────────────── global invariants ────────────────────────────


def inv_1_no_rung4_without_rung1(fx_id: str, built: Plan) -> list[Result]:
    results = []
    c = built.constraints
    for tier in built.tiers:
        rung4 = (
            tier.spec.cache_vcpu is not None
            or tier.spec.database_read_replicas > 0
            or tier.spec.cdn_gb > 0
        )
        rung1_ok = True
        if c.availability == "high":
            count = tier.spec.compute_count or tier.spec.fargate_task_count
            rung1_ok = rung1_ok and count >= 2 and tier.spec.database_multi_az \
                and tier.spec.load_balancer
        if c.durability == "high":
            rung1_ok = rung1_ok and tier.spec.backup_copy_gb > 0 and tier.spec.object_lock
        if c.country_lock:
            rung1_ok = rung1_ok and tier.spec.region_deny_guardrail
        ok = not (rung4 and not rung1_ok)
        results.append(Result(
            fx_id, f"INV-1:{tier.name}", passed=ok,
            expected="rung-1 satisfied whenever a rung-4 component is present",
            actual=f"rung4_present={rung4} rung1_ok={rung1_ok}",
        ))
    return results


def inv_2_nat_within_az_count(fx_id: str, built: Plan) -> list[Result]:
    az_count = 2 if built.constraints.availability == "high" else 1
    results = []
    for tier in built.tiers:
        ok = tier.spec.nat_gateway_count <= az_count
        results.append(Result(
            fx_id, f"INV-2:{tier.name}", passed=ok,
            expected=f"<= {az_count} NAT gateways", actual=str(tier.spec.nat_gateway_count),
        ))
    return results


def inv_3_hard_constraints_satisfied(fx_id: str, built: Plan) -> list[Result]:
    c = built.constraints
    in_country = (
        plan_module.in_country_regions(plan_module._country_name(c.country))
        if c.country_lock else ()
    )
    country_regions = plan_module._aws_regions(in_country)
    results = []
    for tier in built.tiers:
        region = provider_region(tier.spec.region, "aws")
        verdict = filter_check(
            plan_module._architecture_from(tier.spec, region),
            availability=c.availability, durability=c.durability,
            country=plan_module._country_name(c.country), country_regions=country_regions,
        )
        results.append(Result(
            fx_id, f"INV-3:{tier.name}", passed=verdict.valid,
            expected="passes constraint_filter.check()",
            actual="valid" if verdict.valid else "; ".join(verdict.violations),
        ))
    return results


def inv_4_assumed_values_not_in_prompt(fx_id: str, built: Plan, prompt: str) -> list[Result]:
    text = prompt.lower()
    results = []
    for field_name in built.constraints.assumed:
        value = getattr(built.constraints, field_name)
        if not isinstance(value, (int, float)) or not value:
            continue  # bool/enum/empty: "value in prompt" is not a meaningful check
        suspicious = str(int(value)) in text
        results.append(Result(
            fx_id, f"INV-4:{field_name}", passed=not suspicious,
            expected=f"{value} not written in the prompt",
            actual="found in prompt text" if suspicious else "not in prompt text",
        ))
    return results


def inv_5_exclusions_have_reasons(fx_id: str, built: Plan) -> list[Result]:
    results = []
    for line in built.load.excluded_with_reason:
        ok = bool(line.strip()) and ":" in line and "not added" in line
        results.append(Result(
            fx_id, f"INV-5:{line[:30]}", passed=ok,
            expected="non-empty reason string", actual=line or "(empty)",
        ))
    return results


def inv_6_pattern_diff_declared(fx_id: str, built: Plan) -> list[Result]:
    results = []
    for tier in built.tiers[1:]:
        ok = bool(tier.pattern_diff) or bool(tier.no_further_improvement)
        results.append(Result(
            fx_id, f"INV-6:{tier.name}", passed=ok,
            expected=">=1 pattern_diff, or an explicit no-further-improvement note",
            actual=f"pattern_diff={len(tier.pattern_diff)} "
                   f"no_further={bool(tier.no_further_improvement)}",
        ))
    return results


def inv_7_rto_rpo_present(fx_id: str, built: Plan) -> list[Result]:
    results = []
    for tier in built.tiers:
        ok = bool(tier.rto) and bool(tier.rpo)
        results.append(Result(
            fx_id, f"INV-7:{tier.name}", passed=ok,
            expected="non-null rto and rpo", actual=f"rto={tier.rto!r} rpo={tier.rpo!r}",
        ))
    return results


def inv_8_total_matches_line_items(fx_id: str, built: Plan) -> list[Result]:
    results = []
    for tier in built.tiers:
        computed = round(sum(float(i.monthly_usd) for i in tier.estimate.items), 2)
        displayed = round(tier.monthly_total, 2)
        ok = abs(computed - displayed) < 0.005
        results.append(Result(
            fx_id, f"INV-8:{tier.name}", passed=ok,
            expected=f"sum of line items == {displayed}", actual=str(computed),
        ))
    return results


def inv_9_items_resolve_to_catalog_region(fx_id: str, built: Plan) -> list[Result]:
    c = built.constraints
    regions_for_country = plan_module.COUNTRY_REGIONS.get(c.country, ())
    primary_region = provider_region(built.tiers[0].spec.region, "aws") if built.tiers else None
    standby_region = (
        provider_region(regions_for_country[1], "aws")
        if len(regions_for_country) > 1 else None
    )

    wanted_regions = {r for r in (primary_region, standby_region) if r}
    skus_by_region: dict[str, set[str]] = {}
    with pricing_store.connect() as conn, conn.cursor() as cur:
        for region in wanted_regions:
            cur.execute(
                "select distinct sku from price_points where provider='aws' and region=%s",
                (region,),
            )
            skus_by_region[region] = {r["sku"] for r in cur.fetchall()}

    results = []
    for tier in built.tiers:
        region = standby_region if standby_region and "(standby" in "".join(
            i.label for i in tier.estimate.items
        ) else primary_region
        for item in tier.estimate.items:
            item_region = standby_region if "(standby" in item.label and standby_region else primary_region
            found = item_region in skus_by_region and item.sku in skus_by_region[item_region]
            results.append(Result(
                fx_id, f"INV-9:{tier.name}:{item.sku}", passed=found,
                expected=f"sku exists in region {item_region}",
                actual="found" if found else "missing from that region's catalog",
                reason=item.label,
            ))
    return results


def inv_10_compliance_matches_table(fx_id: str, built: Plan) -> list[Result]:
    c = built.constraints
    expected = {n["regulation"] for n in compliance_notes(c.country, c.sector)}
    actual = {n["regulation"] for n in built.compliance}
    ok = actual == expected
    return [Result(
        fx_id, "INV-10", passed=ok,
        expected="; ".join(sorted(expected)) or "(none)",
        actual="; ".join(sorted(actual)) or "(none)",
    )]


def inv_11_topology_forced_private_when_it_must_be(fx_id: str, built: Plan) -> list[Result]:
    """public_simple is a topology only a genuinely low-stakes workload may
    have. Any of these three signals -- stated availability=high, stated
    durability=high, or a compliance obligation tagged
    requires_network_isolation -- must force private_standard regardless
    of what the topology decision otherwise computed."""
    c = built.constraints
    isolation_required = any(
        n.get("requires_network_isolation") for n in built.compliance
    )
    must_be_private = c.availability == "high" or c.durability == "high" or isolation_required
    ok = (not must_be_private) or built.network_topology == "private_standard"
    return [Result(
        fx_id, "INV-11", passed=ok,
        expected="private_standard whenever availability=high, durability=high, "
                 "or a compliance obligation requires network isolation",
        actual=f"topology={built.network_topology} "
               f"(availability={c.availability}, durability={c.durability}, "
               f"isolation_required={isolation_required})",
    )]


INVARIANTS = {
    "INV-1": inv_1_no_rung4_without_rung1,
    "INV-2": inv_2_nat_within_az_count,
    "INV-3": inv_3_hard_constraints_satisfied,
    "INV-5": inv_5_exclusions_have_reasons,
    "INV-6": inv_6_pattern_diff_declared,
    "INV-7": inv_7_rto_rpo_present,
    "INV-8": inv_8_total_matches_line_items,
    "INV-9": inv_9_items_resolve_to_catalog_region,
    "INV-10": inv_10_compliance_matches_table,
    "INV-11": inv_11_topology_forced_private_when_it_must_be,
}
# INV-4 takes the prompt as well as the plan, so it is dispatched separately
# in run_prompt_fixture rather than living in this table.


def run_invariants(fx: dict, built: Plan, prompt: str) -> list[Result]:
    wanted = fx.get("expect", {}).get("invariants") or []
    names = list(INVARIANTS) + ["INV-4"] if wanted == ["all"] else wanted
    results = []
    for name in names:
        if name == "INV-4":
            results.extend(inv_4_assumed_values_not_in_prompt(fx["id"], built, prompt))
        elif name in INVARIANTS:
            results.extend(INVARIANTS[name](fx["id"], built))
    return results


# ──────────────────────────── catalog fixture (7) ──────────────────────────


def _rate_differs_by_region(fx_id: str, a: dict) -> Result:
    r1 = pricing_store.get_price(a["provider"], a["region_a"], a["category"], a["sku"])
    r2 = pricing_store.get_price(a["provider"], a["region_b"], a["category"], a["sku"])
    ok = bool(r1 and r2 and r1.price_usd != r2.price_usd)
    return Result(
        fx_id, a["id"], passed=ok,
        expected=f"{a['region_a']} rate != {a['region_b']} rate for {a['sku']}",
        actual=f"{a['region_a']}={r1.price_usd if r1 else 'missing'} "
               f"{a['region_b']}={r2.price_usd if r2 else 'missing'}",
    )


def _every_entry_has_explicit_region(fx_id: str, a: dict) -> Result:
    with pricing_store.connect() as conn, conn.cursor() as cur:
        cur.execute(
            "select count(*) as n from price_points "
            "where provider=%s and (region is null or region = '')",
            (a["provider"],),
        )
        n = cur.fetchone()["n"]
    return Result(
        fx_id, a["id"], passed=n == 0,
        expected="0 rows with a null/empty region", actual=f"{n} rows",
    )


def _multi_az_greater_than_single_az(fx_id: str, a: dict) -> Result:
    single = pricing_store.get_price(a["provider"], a["region"], "database", a["single_az_sku"])
    multi = pricing_store.get_price(a["provider"], a["region"], "database", a["multi_az_sku"])
    ok = bool(single and multi and multi.price_usd > single.price_usd)
    return Result(
        fx_id, a["id"], passed=ok,
        expected=f"{a['multi_az_sku']} > {a['single_az_sku']}",
        actual=f"single={single.price_usd if single else 'missing'} "
               f"multi={multi.price_usd if multi else 'missing'}",
    )


def _security_cost_scales_with_resources(fx_id: str, a: dict) -> Result:
    """GuardDuty/Security Hub must be a function of resource count, not a
    constant -- priced directly through estimate(), not asserted from the
    catalog alone, since the thing under test is the per-vCPU/per-check
    formula the estimator applies, not just that a rate row exists."""
    from whichcloud.estimator import ArchitectureSpec, estimate

    def cost_for(instances: int) -> float:
        spec = ArchitectureSpec(
            name="probe", region="india", compute_count=instances, compute_vcpu=2,
            database_vcpu=2, threat_detection=True,
            posture_monthly_checks=(instances + 1) * 30.0,
        )
        est = estimate(spec, "aws")
        return sum(
            float(i.monthly_usd) for i in est.items
            if i.label.startswith("Threat detection") or i.label.startswith("Security posture")
        )

    small = cost_for(a["small_instances"])
    large = cost_for(a["large_instances"])
    ok = small > 0 and large > small
    return Result(
        fx_id, a["id"], passed=ok,
        expected=f"cost({a['large_instances']} instances) > cost({a['small_instances']} instances) > 0",
        actual=f"small=${small:.2f} large=${large:.2f}",
    )


CATALOG_CHECKS = {
    "rate_differs_by_region": _rate_differs_by_region,
    "every_entry_has_explicit_region": _every_entry_has_explicit_region,
    "multi_az_greater_than_single_az": _multi_az_greater_than_single_az,
    "security_cost_scales_with_resources": _security_cost_scales_with_resources,
}


def run_catalog_fixture(fx: dict) -> FixtureRun:
    run = FixtureRun(fixture_id=fx["id"])
    for a in fx["assertions"]:
        try:
            run.results.append(CATALOG_CHECKS[a["check"]](fx["id"], a))
        except Exception as exc:  # a broken probe is a failure, not a crash
            run.results.append(Result(
                fx["id"], a["id"], passed=False,
                expected="assertion to run", actual=f"raised {exc!r}",
            ))
    return run


# ─────────────────────────── prompt fixture runner ─────────────────────────


def build_prompt_fixtures(fixtures: list[dict]) -> dict[str, Plan | Exception]:
    """Build every prompt fixture's plan before any assertions run, keyed
    by fixture id regardless of file order. diff_against needs its
    reference fixture already built, and alphabetical file order does not
    guarantee that -- "hospital-pune-public.yaml" sorts before
    "hospital-pune.yaml" ('-' < '.'), so building lazily inside the
    assertion loop silently skipped the cross-check it exists to run.
    """
    cache: dict[str, Plan | Exception] = {}
    for fx in fixtures:
        if fx.get("type") == "catalog":
            continue
        try:
            cache[fx["id"]] = plan_module.build(fx["prompt"])
        except Exception as exc:  # noqa: BLE001 -- recorded as this fixture's error
            cache[fx["id"]] = exc
    return cache


def run_prompt_fixture(fx: dict, cache: dict[str, Plan | Exception]) -> FixtureRun:
    run = FixtureRun(fixture_id=fx["id"])
    built = cache[fx["id"]]
    if isinstance(built, Exception):
        run.error = f"{type(built).__name__}: {built}"
        return run

    run.tier_totals = {t.name: t.monthly_total for t in built.tiers}

    expect = fx.get("expect", {})
    run.results.extend(_check_extraction(fx, built))
    run.results.extend(_check_sizing(fx, built))
    run.results.extend(_check_must_include(fx, built))
    run.results.extend(_check_must_exclude(fx, built))
    run.results.extend(_check_compliance(fx, built))
    run.results.extend(_check_budget(fx, built))
    run.results.extend(_check_network_topology(fx, built))
    run.results.extend(run_invariants(fx, built, fx["prompt"]))

    other_id = expect.get("diff_against")
    if other_id:
        other = cache.get(other_id)
        if not isinstance(other, Plan):
            run.results.append(Result(
                fx["id"], f"diff_against:{other_id}", passed=False,
                expected=f"{other_id} built successfully",
                actual="not found or errored -- cannot cross-check",
            ))
        else:
            ok = built.load.sizing_basis()["avg_rps"] == other.load.sizing_basis()["avg_rps"] \
                and built.load.sizing_basis()["load_tier"] == other.load.sizing_basis()["load_tier"]
            run.results.append(Result(
                fx["id"], f"diff_against:{other_id}:sizing_unchanged", passed=ok,
                expected="sizing identical to " + other_id,
                actual="identical" if ok else "sizing drifted",
            ))
            compliance_ok = {n["regulation"] for n in built.compliance} == \
                {n["regulation"] for n in other.compliance}
            run.results.append(Result(
                fx["id"], f"diff_against:{other_id}:compliance_unchanged", passed=compliance_ok,
                expected="compliance identical to " + other_id,
                actual="identical" if compliance_ok else "compliance drifted",
            ))

    return run


# ──────────────────────────────── reporting ────────────────────────────────


def print_table(runs: list[FixtureRun]) -> None:
    rows = []
    for r in runs:
        if r.error:
            rows.append((r.fixture_id, 0, len(r.results) or 1, r.error[:60]))
            continue
        first_failure = r.failed[0] if r.failed else None
        rows.append((
            r.fixture_id, len(r.passed), len(r.failed),
            f"{first_failure.assertion_id}: expected {first_failure.expected!r}, "
            f"got {first_failure.actual!r}" if first_failure else "",
        ))
    w0 = max(len(r[0]) for r in rows) if rows else 10
    print(f"\n{'fixture':<{w0}}  passed  failed  first failure")
    print("-" * (w0 + 60))
    for fid, passed, failed, first in rows:
        marker = "OK" if failed == 0 else "FAIL"
        print(f"{fid:<{w0}}  {passed:>6}  {failed:>6}  {first}"[:200] +
              (f"  [{marker}]" if failed == 0 else ""))


def write_report(runs: list[FixtureRun], path: Path) -> None:
    lines = ["# WhichCloud regression harness report", ""]
    lines.append(f"Run at {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")
    lines.append("")
    lines.append("| fixture | passed | failed | status |")
    lines.append("|---|---|---|---|")
    for r in runs:
        status = "FAIL (error)" if r.error else ("OK" if r.ok else "FAIL")
        lines.append(f"| {r.fixture_id} | {len(r.passed)} | {len(r.failed)} | {status} |")

    lines.append("")
    for r in runs:
        lines.append(f"## {r.fixture_id}")
        lines.append("")
        if r.error:
            lines.append(f"**Errored:** `{r.error}`")
            lines.append("")
            continue
        if r.tier_totals:
            totals = ", ".join(f"{k}=${v:,.2f}" for k, v in r.tier_totals.items())
            lines.append(f"Tier totals: {totals}")
            lines.append("")
        lines.append("| assertion | result | expected | actual | reason |")
        lines.append("|---|---|---|---|---|")
        for res in r.results:
            mark = "pass" if res.passed else "**FAIL**"
            lines.append(
                f"| {res.assertion_id} | {mark} | {res.expected} | {res.actual} | "
                f"{res.reason} |"
            )
        lines.append("")

    path.write_text("\n".join(lines))


def append_history(runs: list[FixtureRun], path: Path) -> None:
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with path.open("a") as fh:
        for r in runs:
            fh.write(json.dumps({
                "timestamp": ts, "fixture": r.fixture_id,
                "tier_totals": r.tier_totals, "passed": len(r.passed),
                "failed": len(r.failed), "errored": r.error is not None,
            }) + "\n")


# ────────────────────────────── golden totals ──────────────────────────────
# The no-regression guard. Unlike a fixture's own must_include/must_exclude
# checks, this asks a narrower and stricter question: not "is this design
# still compliant" but "did the price move at all" -- the signal that a
# change meant for one class of workload (network_topology, in this task)
# leaked into a workload it was never meant to touch. Hardcoded cents were
# right for that one change; a runner that can only hardcode is wrong
# permanently, which is what this file replaces them with.


def load_golden(path: Path) -> dict[str, dict[str, float]]:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def check_golden_totals(
    plan_cache: dict[str, Plan | Exception], golden: dict[str, dict[str, float]],
) -> dict[str, list[Result]]:
    """Results keyed by fixture id, so main() can fold them into that
    fixture's own FixtureRun rather than inventing a pseudo-fixture."""
    by_fixture: dict[str, list[Result]] = {}
    for fx_id, expected_totals in golden.items():
        built = plan_cache.get(fx_id)
        results = []
        if not isinstance(built, Plan):
            results.append(Result(
                fx_id, "golden_totals", passed=False,
                expected="fixture built successfully",
                actual="not found or errored -- cannot check golden totals",
            ))
        else:
            actual_totals = {t.name: round(t.monthly_total, 2) for t in built.tiers}
            for tier_name, expected in expected_totals.items():
                actual = actual_totals.get(tier_name)
                ok = actual is not None and abs(actual - expected) < 0.005
                results.append(Result(
                    fx_id, f"golden_totals:{tier_name}", passed=ok,
                    expected=f"${expected:.2f}",
                    actual=f"${actual:.2f}" if actual is not None else "tier not found",
                ))
        by_fixture[fx_id] = results
    return by_fixture


def write_golden(plan_cache: dict[str, Plan | Exception], fixture_ids: list[str], path: Path) -> None:
    golden = {}
    for fx_id in fixture_ids:
        built = plan_cache.get(fx_id)
        if isinstance(built, Plan):
            golden[fx_id] = {t.name: round(t.monthly_total, 2) for t in built.tiers}
    path.write_text(json.dumps(golden, indent=2) + "\n")


# ────────────────────────────────── main ───────────────────────────────────


def load_fixtures() -> list[dict]:
    paths = sorted(FIXTURES_DIR.glob("*.yaml"))
    return [yaml.safe_load(p.read_text()) for p in paths]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--fixture", help="run only this fixture id")
    ap.add_argument("--no-report", action="store_true", help="skip report.md/history")
    ap.add_argument(
        "--approve-golden", action="store_true",
        help="write current totals to golden_totals.json instead of checking "
             "against it -- use only when a total's move is intended",
    )
    args = ap.parse_args()

    all_fixtures = load_fixtures()
    if args.fixture and not any(f["id"] == args.fixture for f in all_fixtures):
        print(f"No fixture named {args.fixture!r} in {FIXTURES_DIR}", file=sys.stderr)
        return 2

    # Every prompt fixture is built once, up front, keyed by id -- not in
    # file order -- so diff_against always finds its reference plan
    # regardless of --fixture filtering or alphabetical file order.
    plan_cache = build_prompt_fixtures(all_fixtures)

    if args.approve_golden:
        fixture_ids = sorted(load_golden(GOLDEN_PATH))
        write_golden(plan_cache, fixture_ids, GOLDEN_PATH)
        print(f"Wrote current totals for {len(fixture_ids)} fixture(s) to {GOLDEN_PATH}")
        return 0

    to_run = [f for f in all_fixtures if not args.fixture or f["id"] == args.fixture]
    runs: list[FixtureRun] = []
    for fx in to_run:
        if fx.get("type") == "catalog":
            runs.append(run_catalog_fixture(fx))
        else:
            runs.append(run_prompt_fixture(fx, plan_cache))

    golden = load_golden(GOLDEN_PATH)
    golden_results = check_golden_totals(plan_cache, golden)
    totals_drifted = False
    for run in runs:
        for res in golden_results.get(run.fixture_id, []):
            run.results.append(res)
            if not res.passed:
                totals_drifted = True

    print_table(runs)
    if totals_drifted:
        print(
            "\ntotals changed — review and run --approve-golden if intended"
        )

    total_failed = sum(len(r.failed) for r in runs) + sum(1 for r in runs if r.error)
    if total_failed:
        print(f"\n{total_failed} assertion(s) failed across "
              f"{sum(1 for r in runs if not r.ok)} fixture(s). Detail:\n")
        for r in runs:
            if r.ok:
                continue
            print(f"--- {r.fixture_id} ---")
            if r.error:
                print(f"  ERRORED: {r.error}")
            for res in r.failed:
                print(f"  [{res.assertion_id}] expected {res.expected!r}, got {res.actual!r}")
                if res.reason:
                    print(f"    engine's stated reason: {res.reason}")

    if not args.no_report:
        write_report(runs, REPORT_PATH)
        append_history(runs, HISTORY_PATH)
        print(f"\nWrote {REPORT_PATH} and appended to {HISTORY_PATH}")

    return 1 if total_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
