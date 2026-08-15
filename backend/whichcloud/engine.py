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

from dataclasses import dataclass, field, replace
from decimal import Decimal

from .estimator import ArchitectureSpec, Estimate, LineItem, estimate
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

    # What this shape gives up. A cheap option that does not state its cost in
    # reliability is how people get burned.
    tradeoffs: tuple[str, ...] = ()

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


def _shape_variants(
    requirement: Requirement,
) -> list[tuple[str, str, dict, tuple[str, ...]]]:
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
            (
                "Single instance — a restart or crash is downtime",
                "No load balancer, so no room to scale out under load",
                "Single-zone database — a zone failure takes you offline",
            ),
        ),
        (
            "Balanced",
            "Handles the expected peak without cold starts, and fits a normal "
            "budget.",
            {},
            (
                "Database has no standby — a zone failure means recovery, not failover",
                "Sized for the expected peak, not an unexpected one",
            ),
        ),
        (
            "Most reliable",
            "Survives an availability-zone failure: extra capacity and a "
            "standby database.",
            {"database_multi_az": True, "load_balancer": True},
            (
                "The standby database roughly doubles the largest line on the bill",
                "Still one region — a regional outage is not covered",
            ),
        ),
    ]


def _what_changed(with_it: Estimate, without_it: Estimate) -> str:
    """Name the SKU this technique replaced.

    Comparing whole estimates and reporting items[0] would credit a database
    technique with beating a compute instance. Find the line that actually
    differs instead.
    """
    chosen = {i.label: i.sku for i in with_it.items}
    for item in without_it.items:
        if chosen.get(item.label) != item.sku:
            return item.sku

    # Same SKUs, different quantities — a duty-cycle change, not a swap.
    for item in without_it.items:
        match = next((i for i in with_it.items if i.label == item.label), None)
        if match and match.quantity != item.quantity:
            return f"{item.sku} at full duty"
    return without_it.items[0].sku if without_it.items else ""


def recommend(
    requirement: Requirement,
    provider: str = "aws",
    techniques: list[Technique] | None = None,
    dsn: str | None = None,
) -> list[Option]:
    """Produce three priced, explained architectures for one provider."""
    catalog = techniques if techniques is not None else load_techniques()
    options: list[Option] = []

    for label, rationale, delta, tradeoffs in _shape_variants(requirement):
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
                    counterfactual_sku=_what_changed(priced_with, priced_without),
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
                tradeoffs=tradeoffs,
                spec_budget=requirement.budget_monthly_usd,
            )
        )

    return options


@dataclass(frozen=True, slots=True)
class LineChange:
    """One line item's fate between two options."""

    label: str
    before: LineItem | None
    after: LineItem | None

    @property
    def delta(self) -> Decimal:
        a = self.after.monthly_usd if self.after else Decimal(0)
        b = self.before.monthly_usd if self.before else Decimal(0)
        return a - b

    @property
    def kind(self) -> str:
        if self.before is None:
            return "added"
        if self.after is None:
            return "removed"
        return "changed" if self.delta else "unchanged"


@dataclass(slots=True)
class OptionDiff:
    """What actually differs between two options.

    A price comparison tells you one option costs more. This tells you what
    the extra money buys — which is the question a user is really asking when
    they click between them.
    """

    from_label: str
    to_label: str
    changes: list[LineChange] = field(default_factory=list)

    @property
    def added(self) -> list[LineChange]:
        return [c for c in self.changes if c.kind == "added"]

    @property
    def removed(self) -> list[LineChange]:
        return [c for c in self.changes if c.kind == "removed"]

    @property
    def changed(self) -> list[LineChange]:
        return [c for c in self.changes if c.kind == "changed"]

    @property
    def unchanged(self) -> list[LineChange]:
        return [c for c in self.changes if c.kind == "unchanged"]

    @property
    def delta_monthly(self) -> Decimal:
        return sum((c.delta for c in self.changes), Decimal(0))


def _line_key(label: str) -> str:
    """Match line items across options by what they ARE, not what they cost.

    "Database" and "Database (Multi-AZ)" are the same line at different
    service levels; "Compute × 1" and "Compute × 3" are the same tier at
    different sizes. Matching on the raw label would report each as a removal
    plus an addition, which hides the very thing the user is trying to see.
    """
    return label.split(" ×")[0].split(" (")[0].strip()


def diff_options(before: Option, after: Option) -> OptionDiff:
    """Compare two priced options line by line."""
    result = OptionDiff(from_label=before.label, to_label=after.label)

    lhs = {_line_key(i.label): i for i in before.estimate.items}
    rhs = {_line_key(i.label): i for i in after.estimate.items}

    for key in list(lhs) + [k for k in rhs if k not in lhs]:
        result.changes.append(
            LineChange(label=key, before=lhs.get(key), after=rhs.get(key))
        )

    return result


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
