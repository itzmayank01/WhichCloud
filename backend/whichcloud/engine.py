"""The engine: requirements in, priced architectures out.

    Requirement -> sizing -> three shapes -> techniques applied -> priced

Two things are worth understanding before reading further.

**The sizing rules below are engineering judgement, not measured data.** Every
price in this project is fetched from a provider and validated against a second
source. The heuristics here are not: they are conventional starting points, and
they are collected in one table so they can be argued with, tuned, and replaced
by real load data later. They are labelled as heuristics everywhere they
surface. Do not let them borrow the credibility of the pricing layer.

**Savings are measured, never claimed.** A technique changes the architecture;
the estimator prices both versions against real catalogs; the difference is the
saving. Nothing sums the `typical_pct` values from the knowledge base, because
those are neither independent nor additive.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal

from .estimator import ArchitectureSpec, Estimate, estimate
from .knowledge import Match, Technique, load_techniques, match_all, rejected
from .requirements import Requirement

# ── sizing heuristics ───────────────────────────────────────────────────
#
# HEURISTIC, NOT MEASURED. Conventional starting points for a workload of each
# size. Replace with observed utilisation as soon as real data exists.

# traffic_scale -> (instances, vCPU each, GB each)
BASE_SIZING: dict[str, tuple[int, int, float]] = {
    "low": (1, 2, 4.0),
    "medium": (2, 2, 8.0),
    "high": (4, 4, 16.0),
}

# Spiky traffic needs headroom for the peak, since scaling is not instant.
SPIKE_INSTANCE_MULTIPLIER = 1.5

# Databases are sized below the app tier for typical CRUD workloads.
DB_SIZING: dict[str, tuple[int, float]] = {
    "low": (2, 4.0),
    "medium": (2, 8.0),
    "high": (4, 16.0),
}

SIZING_BASIS = (
    "Sizing is heuristic: conventional starting points per traffic tier, not "
    "measured from your workload. Validate under load before committing."
)


@dataclass(frozen=True, slots=True)
class AppliedTechnique:
    """A technique folded into a spec, with its saving measured.

    `saved` is the difference between pricing the architecture with this
    technique and pricing it with the technique's declared counterfactual —
    what the team would plausibly have chosen otherwise. It is never taken
    from the knowledge base's `typical_pct`.
    """

    match: Match
    saved: Decimal
    counterfactual_sku: str

    @property
    def technique(self) -> Technique:
        return self.match.technique


@dataclass(frozen=True, slots=True)
class Option:
    """One recommended architecture, priced, with its reasoning."""

    label: str  # "Cheapest" | "Balanced" | "Most reliable"
    rationale: str
    spec: ArchitectureSpec
    estimate: Estimate
    applied: tuple[AppliedTechnique, ...]  # folded in, with measured savings
    advisory: tuple[Match, ...]  # techniques we cannot price but should mention
    baseline_monthly: Decimal  # same shape with no techniques applied

    @property
    def monthly(self) -> Decimal:
        return self.estimate.total_monthly

    @property
    def measured_saving(self) -> Decimal:
        """Sum of each technique's measured saving against its counterfactual.

        Applied sequentially by the estimator, so these do not double-count:
        each is the difference the technique actually made to this shape.
        """
        return sum((a.saved for a in self.applied), Decimal(0))

    @property
    def saving_pct(self) -> float:
        reference = self.monthly + self.measured_saving
        if not reference:
            return 0.0
        return float(self.measured_saving / reference * 100)

    @property
    def within_budget(self) -> bool | None:
        budget = self.spec_budget
        return None if budget is None else self.monthly <= Decimal(str(budget))

    spec_budget: float | None = None


def size_for(requirement: Requirement) -> tuple[int, int, float]:
    """Instance count and size for a workload. HEURISTIC."""
    count, vcpu, memory = BASE_SIZING[requirement.traffic_scale]

    if requirement.traffic_pattern == "spiky":
        count = max(count, round(count * SPIKE_INSTANCE_MULTIPLIER))

    # Batch work runs on a schedule; a single worker pool is the usual shape.
    if requirement.is_batch:
        count = max(1, count // 2)

    return count, vcpu, memory


def base_spec(requirement: Requirement, label: str) -> ArchitectureSpec:
    """The untuned shape for this workload, before any technique applies."""
    count, vcpu, memory = size_for(requirement)
    db_vcpu, db_memory = DB_SIZING[requirement.traffic_scale]

    return ArchitectureSpec(
        name=label,
        region=requirement.region,
        compute_count=count,
        compute_vcpu=vcpu,
        compute_memory_gb=memory,
        database_vcpu=db_vcpu if requirement.needs_database else None,
        database_memory_gb=db_memory if requirement.needs_database else None,
        database_multi_az=False,
        storage_gb=requirement.storage_gb,
        egress_gb=requirement.egress_gb,
        load_balancer=requirement.needs_database and count > 1,
    )


def apply_effects(spec: ArchitectureSpec, matched: list[Match]) -> ArchitectureSpec:
    """Fold every priceable technique into the architecture."""
    updates: dict[str, object] = {}
    for match in matched:
        for key, value in match.technique.effect.items():
            updates[key] = value
    return replace(spec, **updates) if updates else spec


def _shape_variants(requirement: Requirement) -> list[tuple[str, str, dict]]:
    """The three options, as deltas from the base shape.

    Three, never one: a single "best" is always wrong for someone, and the
    first time it is wrong the user stops trusting the tool.
    """
    return [
        (
            "Cheapest",
            "Smallest footprint that still runs the workload. Accepts a single "
            "instance and no standby database.",
            {"compute_count": 1, "database_multi_az": False, "load_balancer": False},
        ),
        (
            "Balanced",
            "Handles the expected peak without cold starts, and fits a normal "
            "budget.",
            {},
        ),
        (
            "Most reliable",
            "Survives an availability-zone failure: extra capacity and a "
            "standby database.",
            {"database_multi_az": True, "load_balancer": True},
        ),
    ]


def recommend(
    requirement: Requirement,
    provider: str = "aws",
    techniques: list[Technique] | None = None,
    dsn: str | None = None,
) -> list[Option]:
    """Produce three priced, explained architectures for one provider."""
    catalog = techniques if techniques is not None else load_techniques()
    options: list[Option] = []

    for label, rationale, delta in _shape_variants(requirement):
        spec = base_spec(requirement, label)
        if delta:
            spec = replace(spec, **delta)
        if label == "Most reliable":
            spec = replace(spec, compute_count=max(2, spec.compute_count))

        baseline = estimate(spec, provider, dsn=dsn)

        matched = match_all(
            requirement,
            catalog,
            provider=provider,
            estimated_spend=float(baseline.total_monthly) or None,
        )
        advisory = [m for m in matched if not m.technique.is_priceable]

        # Apply each priceable technique one at a time, pricing the result
        # against that technique's counterfactual. Sequential application means
        # a later technique measures on top of the earlier ones, so savings add
        # up without double-counting.
        current = spec
        applied: list[AppliedTechnique] = []

        for match in (m for m in matched if m.technique.is_priceable):
            with_it = replace(current, **match.technique.effect)
            without_it = replace(current, **match.technique.counterfactual)

            priced_with = estimate(with_it, provider, dsn=dsn)
            priced_without = estimate(without_it, provider, dsn=dsn)

            if not priced_with.items or not priced_without.items:
                continue  # cannot measure it, so do not claim it

            saved = priced_without.total_monthly - priced_with.total_monthly
            if saved <= 0:
                continue  # an "optimization" that costs more is not one

            current = with_it
            applied.append(
                AppliedTechnique(
                    match=match,
                    saved=saved,
                    counterfactual_sku=(
                        priced_without.items[0].sku if priced_without.items else ""
                    ),
                )
            )

        final = estimate(current, provider, dsn=dsn) if applied else baseline

        options.append(
            Option(
                label=label,
                rationale=rationale,
                spec=current if applied else spec,
                estimate=final,
                applied=tuple(applied),
                advisory=tuple(advisory),
                baseline_monthly=baseline.total_monthly,
                spec_budget=requirement.budget_monthly_usd,
            )
        )

    return options


def recommend_across_clouds(
    requirement: Requirement,
    providers: tuple[str, ...] = ("aws", "azure", "gcp"),
    dsn: str | None = None,
) -> dict[str, list[Option]]:
    """Run the engine on every provider the user is open to."""
    if requirement.provider_preference:
        providers = (requirement.provider_preference,)

    catalog = load_techniques()
    return {p: recommend(requirement, p, catalog, dsn=dsn) for p in providers}


def why_not(requirement: Requirement, provider: str = "aws") -> list[tuple[Technique, str]]:
    """Techniques that did not apply, and why. Explainability, not filler."""
    return rejected(requirement, provider=provider)
