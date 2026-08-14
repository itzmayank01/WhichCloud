"""The optimization-technique knowledge base, loaded and matched.

Until now `knowledge-base/techniques/*.yaml` was decorative — the most
important asset in the repo and nothing read it. This module loads it, checks
it, and decides which techniques apply to a given workload.

One design decision matters more than the rest:

    A technique never asserts a saving. It changes the architecture, and the
    estimator prices the result.

So there is no adding up of "9% + 62% + 20%". Those percentages are not
independent and summing them would invent a number. Instead a technique
declares an `effect` — "use arm64", "use spot" — the engine applies it, both
versions get priced against real catalogs, and the difference is *measured*.

Techniques with no modelable effect (zram, for instance, whose benefit depends
on how compressible a workload's memory is) are still surfaced as advice, and
are explicitly marked as unpriced rather than folded into a total.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

# knowledge-base/ lives beside backend/, not inside it.
DEFAULT_KB = Path(__file__).resolve().parents[2] / "knowledge-base" / "techniques"

# Effects the engine knows how to apply to an ArchitectureSpec. A technique
# declaring anything else is a loading error, not a silent no-op.
KNOWN_EFFECTS = {"arch", "use_spot", "database_multi_az"}

REQUIRED_FIELDS = ("id", "name", "category", "summary", "savings", "providers")


class KnowledgeBaseError(ValueError):
    """Raised when a technique file is malformed. Never swallowed."""


@dataclass(frozen=True, slots=True)
class Technique:
    id: str
    name: str
    category: str
    summary: str

    typical_pct: float | None
    confidence: str
    basis: str

    workload_types: tuple[str, ...]
    traffic_patterns: tuple[str, ...]
    min_monthly_spend_usd: float
    requires: tuple[str, ...]

    tradeoffs: tuple[str, ...]
    tools: tuple[dict, ...]
    providers: tuple[str, ...]
    obviousness: str
    effect: dict = field(default_factory=dict)
    counterfactual: dict = field(default_factory=dict)

    @property
    def is_priceable(self) -> bool:
        """Can the estimator measure this, or is it advice only?"""
        return bool(self.effect)

    @property
    def primary_tool(self) -> str:
        return self.tools[0]["name"] if self.tools else ""


def _tuple(value, name: str, path: Path) -> tuple:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if not isinstance(value, (list, tuple)):
        raise KnowledgeBaseError(f"{path.name}: {name} must be a list")
    return tuple(value)


def parse_technique(data: dict, path: Path) -> Technique:
    """Turn one YAML document into a Technique, or fail loudly."""
    missing = [f for f in REQUIRED_FIELDS if f not in data]
    if missing:
        raise KnowledgeBaseError(f"{path.name}: missing fields {missing}")

    applies = data.get("applies_when") or {}
    savings = data.get("savings") or {}

    effect = data.get("effect") or {}
    counterfactual = data.get("counterfactual") or {}
    for name, block in (("effect", effect), ("counterfactual", counterfactual)):
        if not isinstance(block, dict):
            raise KnowledgeBaseError(f"{path.name}: {name} must be a mapping")
        unknown = set(block) - KNOWN_EFFECTS
        if unknown:
            raise KnowledgeBaseError(
                f"{path.name}: {name} {sorted(unknown)} is not something the "
                f"engine can apply. Known: {sorted(KNOWN_EFFECTS)}"
            )
    if effect and not counterfactual:
        raise KnowledgeBaseError(
            f"{path.name}: a technique with an effect needs a counterfactual, "
            f"otherwise its saving cannot be measured against anything"
        )

    pct = savings.get("typical_pct")
    return Technique(
        id=str(data["id"]),
        name=str(data["name"]),
        category=str(data["category"]),
        summary=str(data["summary"]).strip(),
        typical_pct=float(pct) if pct is not None else None,
        confidence=str(savings.get("confidence", "unknown")),
        basis=str(savings.get("basis", "")).strip(),
        workload_types=_tuple(applies.get("workload_type"), "workload_type", path),
        traffic_patterns=_tuple(applies.get("traffic_pattern"), "traffic_pattern", path),
        min_monthly_spend_usd=float(applies.get("min_monthly_spend_usd") or 0),
        requires=_tuple(applies.get("requires"), "requires", path),
        tradeoffs=_tuple(data.get("tradeoffs"), "tradeoffs", path),
        tools=_tuple(data.get("implemented_by"), "implemented_by", path),
        providers=_tuple(data["providers"], "providers", path),
        obviousness=str(data.get("obviousness", "unknown")),
        effect=effect,
        counterfactual=counterfactual,
    )


def load_techniques(directory: Path | None = None) -> list[Technique]:
    """Load every technique file. A malformed file stops the load."""
    directory = directory or DEFAULT_KB
    if not directory.is_dir():
        raise KnowledgeBaseError(f"knowledge base not found at {directory}")

    techniques: list[Technique] = []
    seen: dict[str, Path] = {}

    for path in sorted(directory.glob("*.yaml")):
        try:
            data = yaml.safe_load(path.read_text())
        except yaml.YAMLError as exc:
            raise KnowledgeBaseError(f"{path.name}: invalid YAML — {exc}") from exc
        if not isinstance(data, dict):
            raise KnowledgeBaseError(f"{path.name}: expected a mapping at the top level")

        technique = parse_technique(data, path)
        if technique.id in seen:
            raise KnowledgeBaseError(
                f"duplicate technique id {technique.id!r} in {path.name} "
                f"and {seen[technique.id].name}"
            )
        seen[technique.id] = path
        techniques.append(technique)

    if not techniques:
        raise KnowledgeBaseError(f"no technique files found in {directory}")
    return techniques


@dataclass(frozen=True, slots=True)
class Match:
    technique: Technique
    reasons: tuple[str, ...]  # why it applied, for explainability


def matches(
    technique: Technique,
    requirement,
    provider: str | None = None,
    estimated_spend: float | None = None,
) -> tuple[bool, tuple[str, ...]]:
    """Does this technique apply? Returns the verdict and the reasoning.

    Every rejection is explainable — the engine can tell a user why spot was
    not suggested, which is more useful than silently omitting it.
    """
    reasons: list[str] = []

    if technique.workload_types and requirement.workload_type not in technique.workload_types:
        return False, (
            f"applies to {', '.join(technique.workload_types)} workloads, "
            f"not {requirement.workload_type}",
        )
    if technique.workload_types:
        reasons.append(f"suits {requirement.workload_type} workloads")

    if (
        technique.traffic_patterns
        and requirement.traffic_pattern != "unknown"
        and requirement.traffic_pattern not in technique.traffic_patterns
    ):
        return False, (
            f"applies to {', '.join(technique.traffic_patterns)} traffic, "
            f"not {requirement.traffic_pattern}",
        )

    if provider and technique.providers and provider not in technique.providers:
        return False, (f"not available on {provider}",)

    spend = estimated_spend if estimated_spend is not None else requirement.budget_monthly_usd
    if spend is not None and spend < technique.min_monthly_spend_usd:
        return False, (
            f"only worth it above ${technique.min_monthly_spend_usd:g}/mo "
            f"(this workload is ~${spend:.0f})",
        )

    # Gates that depend on properties of the work itself, not its size.
    if technique.effect.get("use_spot") and not requirement.interruptible:
        return False, ("work is not marked interruptible, so spot would risk it",)
    if technique.effect.get("arch") == "arm64" and not requirement.arm_compatible:
        return False, ("workload declares an x86-only dependency",)

    if technique.effect.get("use_spot"):
        reasons.append("work is restartable, so reclaimed capacity is survivable")
    if technique.effect.get("arch") == "arm64":
        reasons.append("no x86-only dependencies declared")

    return True, tuple(reasons)


def match_all(
    requirement,
    techniques: list[Technique] | None = None,
    provider: str | None = None,
    estimated_spend: float | None = None,
) -> list[Match]:
    """Every technique that applies, least obvious first.

    Ordering is deliberate: an `obviousness: low` technique is the reason
    someone uses this tool rather than reading a pricing page.
    """
    techniques = techniques if techniques is not None else load_techniques()
    rank = {"low": 0, "medium": 1, "high": 2, "unknown": 3}

    found = []
    for technique in techniques:
        ok, reasons = matches(technique, requirement, provider, estimated_spend)
        if ok:
            found.append(Match(technique=technique, reasons=reasons))

    return sorted(found, key=lambda m: (rank.get(m.technique.obviousness, 3), m.technique.id))


def rejected(
    requirement,
    techniques: list[Technique] | None = None,
    provider: str | None = None,
    estimated_spend: float | None = None,
) -> list[tuple[Technique, str]]:
    """Techniques that did not apply, with the reason. Powers "why not?"."""
    techniques = techniques if techniques is not None else load_techniques()
    out = []
    for technique in techniques:
        ok, reasons = matches(technique, requirement, provider, estimated_spend)
        if not ok:
            out.append((technique, reasons[0] if reasons else "did not match"))
    return out
