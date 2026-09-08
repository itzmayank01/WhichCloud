"""What an archetype has to declare before it may be priced.

The engine had one shape and answered seven questions with it. This is
the contract each of the other six has to satisfy before it is allowed
into IMPLEMENTED_ARCHETYPES, and it is deliberately more than "a function
that returns a spec":

  CANDIDATES   the services this shape may draw from, grouped by role,
               every one confirmed to have a published rate in the target
               region. A candidate set is how "we considered these and
               chose those" becomes checkable rather than asserted.

  SIZING       the driver appropriate to the SHAPE. A batch job is sized
               by GB per run and how long a run takes; a realtime service
               by connections held open. Sizing every shape by
               requests-per-day is what produced a 40-machine estate
               costed as one small instance.

  FORBIDDEN    components this shape must never contain, each with the
               reason. A static site with a database is not an expensive
               static site, it is a different and wrong architecture, and
               stating that as data lets an invariant enforce it instead
               of a reviewer noticing.

  TIERS        three variants that differ BY SERVICE. Not three sizes:
               the rule is at least three services different between
               consecutive tiers, or an explicit statement that no
               further improvement is worth buying.

Every candidate set below is justified from AWS's own reference material
-- the Well-Architected cost and reliability pillars, the Architecture
Center reference architectures, and the service decision guides -- rather
than from memory, and each module says which. What is NOT allowed is a
model choosing services at request time: everything here is data and
rules, evaluated deterministically, so the same Constraints produce the
same architecture every run.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from whichcloud.constraints import Constraints
from whichcloud.estimator import ArchitectureSpec
from whichcloud.load_model import Load

#: The roles a service can play. Deliberately a closed set: it is the
#: vocabulary the candidate sets are grouped by, and an open one would
#: let two archetypes describe the same role with different words.
ROLES = (
    "edge",        # DNS, CDN, TLS, WAF -- what faces the internet
    "ingest",      # the door events/requests arrive through
    "compute",     # where the work happens
    "store",       # durable state
    "async",       # queues, buses, streams
    "analytics",   # query and warehouse layers
    "ops",         # monitoring, tracing, audit
    "security",    # identity, keys, secrets, detection
    "resilience",  # backup, DR copy, immutability
)


@dataclass(frozen=True)
class Candidate:
    """One service this archetype may select, and what it is for.

    `category` is the catalog category its rate comes from, which is what
    makes "confirmed priceable" mechanically checkable -- a candidate
    naming a category the catalog does not carry fails a test rather than
    silently costing zero.
    """

    name: str
    role: str
    category: str
    purpose: str
    #: Why this is here rather than the obvious alternative. Empty when
    #: there is no meaningful alternative (there is one DNS).
    instead_of: str = ""

    def __post_init__(self) -> None:
        if self.role not in ROLES:
            raise ValueError(f"{self.name}: unknown role {self.role!r}")


@dataclass(frozen=True)
class Forbidden:
    """A component this shape must never contain, and why.

    `probe` reads an ArchitectureSpec and returns True when the forbidden
    thing is PRESENT, so an invariant can assert the negative without
    knowing anything about the archetype.
    """

    component: str
    reason: str
    probe: Callable[[ArchitectureSpec], bool]


@dataclass(frozen=True)
class SizingDriver:
    """What this shape is measured in, and where the figure comes from.

    `describe` renders the actual numbers for a given Constraints, so a
    plan can say "sized from 40 machines totalling 160 vCPU" rather than
    leaving the reader to infer the basis from the bill.
    """

    name: str
    fields: tuple[str, ...]
    describe: Callable[[Constraints, Load], str]


@dataclass(frozen=True)
class ArchetypeGraph:
    """Everything one shape declares."""

    name: str
    summary: str
    #: Where the candidate set came from. A reference architecture, not a
    #: recollection.
    sources: tuple[str, ...]
    sizing: SizingDriver
    candidates: tuple[Candidate, ...]
    forbidden: tuple[Forbidden, ...]
    #: (tier_level, constraints, load, region, ...) -> ArchitectureSpec
    build: Callable[..., ArchitectureSpec]
    #: What each tier buys that the one below does not, in words. Indexed
    #: by tier level; level 1 has nothing below it.
    tier_notes: dict[int, str] = field(default_factory=dict)

    def by_role(self) -> dict[str, list[Candidate]]:
        out: dict[str, list[Candidate]] = {}
        for candidate in self.candidates:
            out.setdefault(candidate.role, []).append(candidate)
        return out

    def categories(self) -> set[str]:
        return {c.category for c in self.candidates}

    def violations(self, spec: ArchitectureSpec) -> list[str]:
        """Which forbidden components this spec contains. Empty is the
        only acceptable answer, and an invariant says so."""
        return [
            f"{rule.component}: {rule.reason}"
            for rule in self.forbidden
            if rule.probe(spec)
        ]


# ── forbidden-component probes, shared across archetypes ─────────────
# Written once because several shapes forbid the same things for
# different reasons, and duplicating the predicate is how two archetypes
# end up disagreeing about what "has a database" means.


def has_relational_database(spec: ArchitectureSpec) -> bool:
    return bool(spec.database_vcpu)


def has_load_balancer(spec: ArchitectureSpec) -> bool:
    return bool(spec.load_balancer)


def has_nat_gateway(spec: ArchitectureSpec) -> bool:
    return spec.nat_gateway_count > 0


def has_vpc_compute(spec: ArchitectureSpec) -> bool:
    return spec.compute_count > 0 or spec.fargate_task_count > 0


def has_cdn(spec: ArchitectureSpec) -> bool:
    return spec.cdn_gb > 0


def has_arm(spec: ArchitectureSpec) -> bool:
    """ARM anywhere in the spec. Used by migration, where it is not a
    cost question but a will-it-boot one."""
    return spec.arch == "arm64" or spec.fargate_arm and spec.fargate_task_count > 0


def has_serverless_compute(spec: ArchitectureSpec) -> bool:
    return spec.fargate_task_count > 0 or spec.lambda_invocations_per_month > 0


def has_warehouse(spec: ArchitectureSpec) -> bool:
    return spec.warehouse_node_count > 0
