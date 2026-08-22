"""The output contract: description in, three compliant tiers out.

This is where the four reasoning modules meet the price catalog. The order
is deliberate and is the whole design:

    extract  ->  derive the rate  ->  filter  ->  price

Filtering BEFORE pricing is the behaviour change. The old flow priced a
cheapest option and then noticed it failed a stated requirement, which
produces a cheap number attached to a design the user already ruled out --
and a cheap number wins arguments. Nothing that fails the filter is ever
given a price here; it is shown separately, with its violations, if at all.

The three tiers are not three sizes of the same design -- see PHILOSOPHY.
Spend is allocated in a strict order (the spend priority ladder): stated
hard requirements first, then sector-mandated security and audit, then
operational maturity, and only then performance capacity. Tier 1 stops
after the first rung. Tier 2 adds the second and third. Tier 3 adds a
genuine architectural pattern change -- multi-region standby, not more of
what Tier 2 already has -- and buys capacity only as a last resort, only
where the workload's own rate justifies it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from decimal import Decimal

from whichcloud import archetype as archetype_module
from whichcloud import llm_extract
from whichcloud.constraint_filter import Architecture, check
from whichcloud.constraints import Constraints
from whichcloud.estimator import ArchitectureSpec, Estimate, estimate
from whichcloud.load_model import Load, build_load
from whichcloud.network_topology import PUBLIC_SIMPLE, TopologyDecision
from whichcloud.network_topology import decide as decide_topology
from whichcloud.objectives import compliance_notes, objectives
from whichcloud.planner import RPS_PER_VCPU, in_country_regions
from whichcloud.pricing import store as pricing_store
from whichcloud.pricing.models import HOURS_PER_MONTH, provider_region

#: Neutral region keys per country, in the order a plan should prefer them.
COUNTRY_REGIONS: dict[str, tuple[str, ...]] = {
    "IN": ("india", "india-south"),
    "SG": ("singapore",),
    "US": ("us-east",),
    "IE": ("eu-west",),
    "DE": ("eu-west",),
    "FR": ("eu-west",),
    "GB": ("eu-west",),
}

#: Storage assumed when the description gives none. Flagged, never hidden:
#: it drives the largest single line on a records-heavy workload, so an
#: unexamined default here quietly sets the total.
#: Storage and egress assumed when the description gives neither. These
#: are heuristics in the same class as BASE_SIZING -- conventional
#: judgement, collected here so they can be argued with -- but a single
#: flat constant was not even that: it assumed a 12-person equipment
#: tracker and a 450-staff hospital hold the same 500 GB, which is the
#: sort of unexamined default that quietly sets a total.
#:
#: Two inputs, because both matter and neither subsumes the other: the
#: load band says how much traffic the system carries, the user count
#: says how much data it accumulates. A busy public site with few
#: accounts and a quiet internal system with many both exist.
_STORAGE_BASE_BY_TIER: dict[str, float] = {
    "trivial": 25.0, "small": 100.0, "medium": 500.0, "large": 2000.0,
}
_EGRESS_BASE_BY_TIER: dict[str, float] = {
    "trivial": 10.0, "small": 50.0, "medium": 250.0, "large": 1000.0,
}
#: DEFECT 2. NAT processes traffic a private subnet ORIGINATES -- package
#: installs, third-party API calls, outbound webhooks. Responses to
#: inbound user requests return the way they came and never touch it.
#: Billing NAT for a mirror of internet egress double-counted every byte
#: the users pulled.
NAT_SHARE_OF_EGRESS = 0.05

#: When a CDN is in front, user-facing bytes leave from the EDGE, not the
#: origin. What still leaves the origin is cache fill -- each object
#: fetched once per edge location rather than once per viewer. Billing
#: the full user traffic as origin egress AND again as CDN transfer was
#: the same double-count as NAT, on a different pair.
ORIGIN_FILL_SHARE = 0.15

#: Egress still scales with headcount -- unlike storage, more users
#: genuinely does mean more bytes pulled. Kept per-user for that reason.
_EGRESS_PER_USER_GB = 0.1

# ── DEFECT 7: storage is two independent things ──────────────────────
#
# The old model was `base + users x 0.5GB x sector`, which assumed every
# user carries half a gigabyte of their own data. Almost no workload
# works that way, and on a 40,000-student coaching platform it produced
# 40 TB and 86% of the bill. 40,000 students share ONE video library.
#
# So: shared content does not scale with users at all, and per-user data
# is measured in MEGABYTES.

#: Per-user records: profile, submissions, history. Megabytes, and
#: deliberately at the low end -- these are rows and small attachments,
#: not media. Anything above low-tens of MB needs justifying, and none of
#: these are.
_USER_DATA_MB_BY_SECTOR: dict[str, float] = {
    "healthcare": 25.0,     # notes and referrals per person on the system
    "fintech": 15.0,        # statements, KYC documents
    "education": 10.0,      # submissions and progress history
    "ecommerce": 5.0,       # order history
    "internal_tools": 5.0,
    "public_web": 2.0,
    "other": 5.0,
}

#: Shared repository: the record store, catalogue or library everybody
#: reads from. Independent of headcount -- a 3-hospital records system
#: and a 30-hospital one differ in this figure, but not because of how
#: many staff log in.
_REPOSITORY_GB_BY_SECTOR: dict[str, float] = {
    "healthcare": 500.0, "fintech": 250.0, "ecommerce": 100.0,
    "education": 50.0, "internal_tools": 20.0, "public_web": 10.0,
    "other": 25.0,
}

#: A media library, when the description says media is the product. This
#: is the figure most likely to be wrong by an order of magnitude, which
#: is why `storage_is_dominant` exists to say so out loud rather than
#: letting it quietly set the total.
_CONTENT_GB_BY_ASSETS: dict[str, float] = {
    "none": 0.0, "light": 250.0, "heavy": 2000.0,
}

#: Hard ceiling on what headcount alone may contribute. The assertion
#: this backs is not decoration: without it, a million-user consumer app
#: would reproduce exactly the defect being fixed here at a larger scale.
MAX_USER_DERIVED_GB = 1024.0

#: A stated async workload with no stated volume still has a queue. This
#: floor exists so the COMPONENT appears; the figure is nominal and, like
#: every other derived quantity here, is surfaced as an assumption rather
#: than presented as measured.
_QUEUE_FLOOR_UNITS = 10_000.0

# ── DEFECT 8: what actually crosses a region boundary each month ─────
#
# The old model copied the whole dataset every month, so a cross-region
# backup cost 3.4x the storage it was protecting. What crosses monthly is
# what CHANGED. How much that is depends on the workload: a video library
# is written once and read forever; a transactional database rewrites a
# meaningful slice of itself every month.
_MONTHLY_CHANGE_RATE_BY_SECTOR: dict[str, float] = {
    "fintech": 0.15,        # transactions accumulate continuously
    "ecommerce": 0.12,
    "healthcare": 0.08,     # records appended, rarely rewritten
    "internal_tools": 0.08,
    "education": 0.04,      # a course library changes between terms
    "public_web": 0.04,
    "other": 0.10,
}
#: Media is written once and read forever, whatever the sector. A heavy
#: asset library changes far less than the records beside it.
_MEDIA_CHANGE_RATE = 0.02


def _monthly_change_rate(constraints: Constraints) -> float:
    if constraints.static_assets == "heavy":
        return _MEDIA_CHANGE_RATE
    return _MONTHLY_CHANGE_RATE_BY_SECTOR.get(constraints.sector, 0.10)


def _content_storage_gb(constraints: Constraints) -> float:
    """Shared assets. Does not scale with users, by construction."""
    return max(
        _CONTENT_GB_BY_ASSETS.get(constraints.static_assets, 0.0),
        _REPOSITORY_GB_BY_SECTOR.get(constraints.sector, 25.0),
    )


def _user_data_gb(constraints: Constraints) -> float:
    """Per-user records, in GB, capped so headcount can never dominate."""
    per_user_mb = _USER_DATA_MB_BY_SECTOR.get(constraints.sector, 5.0)
    return min(constraints.users * per_user_mb / 1024.0, MAX_USER_DERIVED_GB)


def _default_storage_gb(constraints: Constraints, load: Load) -> float:
    """Shared content plus per-user data. The load band no longer enters
    it: how much traffic a system carries says nothing about how much
    data it holds."""
    if constraints.content_storage_gb or constraints.user_data_gb:
        return constraints.content_storage_gb + constraints.user_data_gb
    return _content_storage_gb(constraints) + _user_data_gb(constraints)


def _default_egress_gb(constraints: Constraints, load: Load) -> float:
    return (
        _EGRESS_BASE_BY_TIER.get(load.tier, 100.0)
        + constraints.users * _EGRESS_PER_USER_GB
    )

#: Named only when the description forces x86: everything else defaults to
#: Graviton, on price and on the pricing rule that says so. A workload never
#: gets ARM by omission-of-evidence -- it gets ARM unless something here
#: rules it out.
_X86_REQUIRED = (
    "x86-only", "x86 only", "requires x86", "must run on x86",
    "not arm compatible", "cannot run on arm", "no arm support",
    ".net framework", "windows server", "sql server",
)

# ── Part 1: tier philosophy ─────────────────────────────────────────
# Three different designs for the same requirements, not three sizes of
# one design. Each tier renders its line above the price.
PHILOSOPHY: dict[int, str] = {
    1: "Cheapest design that satisfies every requirement you stated. "
       "Nothing bought beyond that — patching, deploys and on-call are "
       "your team's, by hand.",
    2: "The same guarantees, far less of your time to run them: managed "
       "compute instead of patched servers, managed identity and secrets, "
       "and the security baseline your sector expects.",
    3: "The design still worth running in three years. Every addition "
       "here either survives losing the region or is capacity the stated "
       "rate actually justifies — never both, and never headroom for its "
       "own sake.",
}

#: One AWS Foundational Security Best Practices standard evaluated roughly
#: once a day per resource -- the conservative floor for how SecurityHub's
#: per-check billing scales, not a measured account figure (that depends on
#: enabled standards and account activity, which this catalog cannot know).
#: Keeps the line proportional to the footprint instead of a flat fee.
CHECKS_PER_RESOURCE_PER_MONTH = 30.0

#: Interface endpoints Part 3 names beyond S3 (which moved to the free
#: gateway kind alongside DynamoDB, per the correction on NAT/endpoint
#: cost). Priced as a single "interface endpoints" line, one hourly rate
#: covering all five -- the catalog carries one interface-hour rate, not a
#: rate per named AWS service.
_INTERFACE_ENDPOINT_SERVICES = ("ECR", "SSM", "Secrets Manager",
                                 "CloudWatch Logs", "KMS")


@dataclass
class Tier:
    name: str
    label: str
    philosophy: str
    spec: ArchitectureSpec
    estimate: Estimate
    rto: str = ""
    rpo: str = ""
    region_rto: str = ""
    region_rpo: str = ""
    gives_up: list[str] = field(default_factory=list)
    justifications: dict[str, str] = field(default_factory=dict)
    #: What changed vs. the tier below, each line naming the risk it
    #: removes. Empty only when Part 4's fallback fires: no legitimate
    #: pattern change existed at this workload's size.
    pattern_diff: list[str] = field(default_factory=list)
    no_further_improvement: str = ""
    #: Non-fatal findings from validation -- e.g. NAT still costing more
    #: than compute after endpoints were correctly added. Recorded and
    #: shown, never hidden, but never a reason to fail the build.
    warnings: list[str] = field(default_factory=list)
    #: Advisory only -- never folded into monthly_total. List pricing has no
    #: committed-use rate to look up, so this is a labelled range, not a
    #: catalog figure, exactly like the advisory techniques in the
    #: knowledge base that are surfaced without being priced.
    committed_use_note: str = ""

    @property
    def monthly_total(self) -> float:
        return float(self.estimate.total_monthly)

    def within_budget(self, budget: float) -> bool:
        return not budget or self.monthly_total <= budget


@dataclass
class Plan:
    constraints: Constraints
    load: Load
    tiers: list[Tier] = field(default_factory=list)
    below_requirements: dict | None = None
    compliance: list[dict] = field(default_factory=list)
    over_budget_note: str = ""
    unspent_budget: dict | None = None
    #: Part 1/3: which network shape every tier was built inside of, and
    #: why -- never silent, and naming the compliance obligation when one
    #: forced private_standard regardless of how small the workload is.
    network_topology: str = ""
    network_topology_reason: str = ""
    #: The workload shape as classified: a real archetype name, or
    #: "unknown". Always the honest answer -- never flattened to hide a
    #: recognised-but-unbuildable shape, which `archetype_state` reports
    #: separately.
    archetype: str = ""
    archetype_note: str = ""
    #: One of archetype.PRICED / RECOGNISED_UNPRICED / STATE_UNKNOWN.
    #: Two of the three withhold pricing, but for different reasons and
    #: with different copy -- "we know what this is and haven't built it"
    #: is a more useful answer than "we don't know what this is".
    archetype_state: str = ""
    #: What this shape's architecture needs, in words. Populated only for
    #: recognised_unpriced: describing a shape is not pricing it.
    archetype_requirements: str = ""
    #: Whether tiers were priced at all. False means `tiers` is empty by
    #: decision, not by failure -- INV-12's subject.
    priced: bool = True
    withheld_reason: str = ""
    covered_archetypes: list[dict] = field(default_factory=list)
    coverage_summary: dict = field(default_factory=dict)
    clarifying_questions: list[str] = field(default_factory=list)
    #: Priced, but resting on an assumption that would change the answer
    #: if wrong. A number with a named caveat, not a refusal.
    provisional: bool = False
    provisional_reasons: list[str] = field(default_factory=list)
    #: Part 4.1: every required field's confidence, high or low, not just
    #: the low ones in assumed_fields() -- so "what did the model trust"
    #: is answerable without inferring it from what is absent.
    extraction_confidence: dict[str, str] = field(default_factory=dict)
    #: How the Constraints were read. `degraded` means the phrase-table
    #: fallback produced them because no model could be reached -- it
    #: reads far fewer phrasings, so a plan built on it must say so
    #: rather than pass for one built on a full extraction.
    extraction_reader: str = ""
    extraction_model: str = ""
    extraction_cached: bool = False
    degraded: bool = False
    degraded_reason: str = ""
    #: True when a provider other than the pinned primary answered.
    #: Marked for the same reason DEGRADED is: different models read the
    #: same prompt differently, so the published agreement figures --
    #: which are primary-to-primary -- do not cover this plan.
    extraction_failover: bool = False
    extraction_failover_note: str = ""
    #: Why the archetype was believed or refused, in words.
    archetype_evidence_verdict: str = ""
    #: When archetype_state is COMPOSITE: the shapes that both cleared
    #: the bar. Costing one and presenting it as the whole would be the
    #: confident wrong answer this engine exists to refuse.
    composite_of: list[str] = field(default_factory=list)
    #: field name -> the substring of the prompt it was drawn from.
    extraction_spans: dict[str, str] = field(default_factory=dict)
    #: DEFECT 7. Set when storage is the largest line AND was derived
    #: rather than stated. An assumption that sets most of the total has
    #: to say so -- the reader otherwise has no way to know the number
    #: turns on a figure nobody supplied.
    storage_dominates: bool = False
    storage_note: str = ""


class BudgetMisallocationError(AssertionError):
    """A tier bought rung-4 capacity while a rung-1 requirement was unmet.

    Should be unreachable by construction -- rung-4 fields are only ever
    set on a spec that already passed the rung-1 filter -- but Part 2 asks
    for it as a named, explicit assertion rather than an implicit one, so
    a future change to the gating order fails loudly here instead of
    shipping a cache next to a missing cross-region copy.
    """


def _vcpu_for(peak_rps: float) -> int:
    """vCPU per instance, from the rate. Two is the floor, not a default."""
    return max(2, 2 * math.ceil(peak_rps / (RPS_PER_VCPU * 2)))


def _instances_for(peak_rps: float, *, high_availability: bool) -> int:
    needed = max(1, math.ceil(peak_rps / RPS_PER_VCPU))
    return max(needed, 2) if high_availability else needed


WITHHELD_MESSAGE = (
    "This workload does not match an architecture pattern the engine has "
    "been validated on. Pricing is withheld rather than guessed."
)

#: recognised_unpriced says something more specific than the generic
#: refusal above: the shape IS known, and what is missing is a validated
#: price for it. Estimating one anyway is exactly the failure the
#: coverage map documented.
RECOGNISED_UNPRICED_MESSAGE = (
    "We recognise this shape, but pricing for it has not been validated "
    "yet, so no figure is shown. An estimate produced by pricing it as "
    "the one architecture this engine does model would be wrong in the "
    "components, not merely in the total."
)

#: Fields whose being assumed rather than stated would change the
#: architecture, not merely its size -- so a plan resting on one is
#: PROVISIONAL. Deliberately not every low-confidence field: an assumed
#: egress_gb moves a number, an assumed durability moves whether backups
#: and a cross-region copy exist at all.
_ARCHITECTURE_DECIDING_FIELDS = ("availability", "durability", "public_facing")


def _provisional_reasons(constraints: Constraints) -> list[str]:
    """Named assumptions that would change the shape of the answer, each
    paired with what it currently assumes and what it would become."""
    changes = {
        "availability": "no redundancy is bought; if uptime actually matters, "
                        "every tier gains a second instance, a load balancer "
                        "and a Multi-AZ database",
        "durability": "no backup, cross-region copy or object lock is bought; "
                      "if this data cannot be lost, all three become mandatory",
        "public_facing": "no WAF or CDN is considered; if the public reaches "
                         "this directly, both come back into scope",
    }
    return [
        f"{name} was assumed to be {getattr(constraints, name)!r}, not stated. "
        f"On that assumption {changes[name]}."
        for name in _ARCHITECTURE_DECIDING_FIELDS
        if constraints.confidence(name) == "low"
    ]


#: A stated security/audit need, distinct from a compliance obligation.
#: Narrow on purpose: "secure" appears in almost every prompt and means
#: nothing; these phrases ask specifically for the network to be watched.
_NETWORK_AUDIT_HINTS = (
    "network audit", "audit network", "traffic log", "flow log",
    "network monitoring", "intrusion detection", "detect intrusion",
    "security audit", "forensic", "who accessed what",
)


def _flow_logs_wanted(
    constraints: Constraints, compliance: list[dict], description: str,
) -> tuple[bool, str]:
    """DEFECT 3. Flow logs are an audit control, and audit controls are
    bought because something requires them -- not by default.

    Unconditionally on and sized at half of egress, they were $134/mo and
    17% of a media workload's bill, scaling with traffic nobody had asked
    to have logged. Returns (wanted, reason) so the refusal can be
    explained rather than merely happening.
    """
    obligation = next(
        (str(c["regulation"]) for c in compliance
         if c.get("requires_network_isolation")),
        "",
    )
    if obligation:
        return True, f"required by {obligation}"

    text = description.lower()
    hit = next((h for h in _NETWORK_AUDIT_HINTS if h in text), "")
    if hit and constraints.availability == "high":
        return True, f"availability=high and {hit!r} was stated"

    why = "no compliance obligation requires network audit"
    if hit:
        why = f"{hit!r} was stated, but availability is low"
    return False, why


def _requires_x86(description: str) -> bool:
    """Graviton is the default; only explicit evidence rules it out."""
    text = description.lower()
    return any(hint in text for hint in _X86_REQUIRED)


def _database_size_for(load_tier: str) -> tuple[int, float]:
    """vCPU and memory for the database, from the load band -- the same
    "size from the rate, not a default" rule already applied to compute.

    Only trivial gets its own size. Everything at small and above keeps
    the (2, 8.0) sizing every other verified number in this codebase was
    measured against, so this closes the trivial-tier over-provisioning
    (an internal tool with 200 views a day does not need db.t4g.large)
    without touching sizing that already has other tests pinned to it.
    """
    if load_tier == "trivial":
        return 2, 1.0  # smallest managed instance the catalog carries
    return 2, 8.0


def _replica_count(load: Load, database_vcpu: int) -> int:
    """0, 1, or 2 -- never guessed past what the rate demonstrably needs.

    One replica is the default once the gate fires at all. A second is
    added only when the read rate would exceed what a single replica of
    this size carries; Part 3 forbids adding more "just in case".
    """
    if "database_replica" not in load.included:
        return 0
    single_replica_capacity = RPS_PER_VCPU * database_vcpu
    return 2 if load.peak_rps > single_replica_capacity else 1


@dataclass(frozen=True)
class EndpointPlan:
    """What Part 3's endpoint-before-NAT rule actually buys, and why.

    S3 and DynamoDB gateway endpoints are free, so there is no decision to
    make -- add them whenever there is traffic to divert. Interface
    endpoints bill per AZ per hour; five of them is a real monthly cost,
    so they are added only when the NAT data-processing charge they divert
    is larger than that cost, using the catalog's own rates for both sides
    rather than a rule of thumb.
    """

    gateway_endpoints: int
    interface_endpoints: int
    interface_endpoint_gb: float
    diverted_gb: float
    justified: bool
    interface_monthly_cost: float
    nat_savings: float


def _endpoint_plan(
    *, egress_gb: float, az_count: int, aws_region: str, dsn: str | None,
    nat_present: bool,
) -> EndpointPlan:
    """Gateway endpoints always (free); interface endpoints only if they
    pay for themselves against the NAT data-processing charge they avoid
    -- and only when there is a NAT charge to avoid in the first place.
    Under public_simple there is no NAT gateway, so an interface endpoint
    would be pure cost with nothing to divert; gateway endpoints still
    make sense on their own (S3/DynamoDB traffic never needs a route to
    the internet regardless of topology).
    """
    gateway_endpoints = 2 if egress_gb else 0  # S3 + DynamoDB

    # The traffic interface endpoints could plausibly divert: AWS-API-bound
    # calls (image pulls, log export, secret reads) rather than traffic to
    # the public internet, which no endpoint can shortcut. Half of stated
    # egress is the same convention already used for flow-log volume.
    diverted_gb = egress_gb * 0.5

    if not nat_present:
        return EndpointPlan(gateway_endpoints, 0, 0.0, diverted_gb, False, 0.0, 0.0)

    interface_rate = pricing_store.get_price(
        "aws", aws_region, "endpoint", "vpce:interface-hour", dsn
    )
    nat_rate = pricing_store.get_price(
        "aws", aws_region, "nat", "nat:gb-processed", dsn
    )
    if not interface_rate or not nat_rate or not diverted_gb:
        return EndpointPlan(gateway_endpoints, 0, 0.0, diverted_gb, False, 0.0, 0.0)

    endpoint_count = len(_INTERFACE_ENDPOINT_SERVICES) * az_count
    interface_monthly_cost = (
        float(interface_rate.price_usd) * endpoint_count * float(HOURS_PER_MONTH)
    )
    nat_savings = diverted_gb * float(nat_rate.price_usd)
    justified = nat_savings > interface_monthly_cost

    return EndpointPlan(
        gateway_endpoints=gateway_endpoints,
        interface_endpoints=endpoint_count if justified else 0,
        interface_endpoint_gb=diverted_gb if justified else 0.0,
        diverted_gb=diverted_gb,
        justified=justified,
        interface_monthly_cost=interface_monthly_cost,
        nat_savings=nat_savings,
    )


def _fargate_sizing(vcpu: int, instances: int) -> tuple[float, float]:
    """Same total capacity as the EC2 spec it replaces -- a pattern change,
    not a resize. Splitting the same vCPU envelope across the same instance
    count keeps the two tiers comparable on everything except the platform."""
    return float(vcpu), float(vcpu) * 2


def _spec_for(
    *,
    name: str,
    constraints: Constraints,
    load: Load,
    region: str,
    instances: int,
    tier_level: int,
    requires_x86: bool,
    endpoints: EndpointPlan,
    posture_resource_count: int,
    topology: TopologyDecision,
    flow_logs: bool,
) -> ArchitectureSpec:
    """One tier's spec. Every optional component traces to a filter or a
    gate, and rung 2-4 additions only ever appear at tier_level >= 2 --
    Tier 1's whole point is that it stops after rung 1."""
    high_availability = constraints.availability == "high"
    durable = constraints.durability == "high"
    # Backups are not an availability feature. "If it's down for an hour
    # nobody minds" says nothing about whether losing the data would be
    # survivable, and the previous ladder conflated the two -- suppressing
    # backups entirely whenever durability was merely `normal`. Only an
    # explicitly STATED `ephemeral` removes them now.
    ephemeral = constraints.durability == "ephemeral"
    public_simple = topology.value == PUBLIC_SIMPLE
    managed = tier_level >= 2  # Fargate + the rung 2/3 additions it buys
    storage = constraints.storage_gb or _default_storage_gb(constraints, load)
    #: Total bytes reaching users, however they get there.
    user_traffic_gb = constraints.egress_gb or _default_egress_gb(constraints, load)
    vcpu = _vcpu_for(load.peak_rps)

    db_vcpu, db_memory_gb = _database_size_for(load.tier)

    # Performance capacity (rung 4) is never Tier 1's to buy, however the
    # load gate reads -- Tier 1's cheapness comes from omitting optional
    # things, and a cache or a replica is optional by Part 2's own ranking.
    replicas = _replica_count(load, database_vcpu=db_vcpu) if managed else 0
    cache_wanted = managed and "cache" in load.included
    # DEFECT 1. A CDN is rung 4 -- a performance nicety -- only while the
    # media it would serve is incidental. When serving media IS the
    # product, the origin is otherwise pushing terabytes itself, and the
    # CDN becomes rung 1: present in every tier including the cheapest,
    # exactly like a load balancer under availability=high.
    media_heavy = constraints.static_assets == "heavy"
    cdn_wanted = "network" in load.included and (media_heavy or managed)

    # DEFECT 2, second pair. Route the user traffic to exactly one meter:
    # the edge when a CDN is present, the origin otherwise. `egress` from
    # here on is ORIGIN egress only.
    cdn_gb = user_traffic_gb if cdn_wanted else 0.0
    egress = user_traffic_gb * ORIGIN_FILL_SHARE if cdn_wanted else user_traffic_gb
    #: What the application itself initiates outbound -- package pulls,
    #: third-party APIs, webhooks. A fraction of user traffic, never a
    #: mirror of it, and the only thing NAT actually processes.
    nat_eligible_gb = user_traffic_gb * NAT_SHARE_OF_EGRESS

    fargate_vcpu, fargate_memory = _fargate_sizing(vcpu, instances)

    resources = posture_resource_count

    return ArchitectureSpec(
        name=name,
        region=region,
        # ── compute: the Part 1 pattern change ──
        # Tier 1 is self-managed EC2 + ASG. Tier 2/3 move the same total
        # vCPU envelope onto Fargate -- a deployment-model change, not a
        # resize, which is what Part 4 requires a pattern diff to be.
        compute_count=0 if managed else instances,
        compute_vcpu=vcpu,
        compute_memory_gb=float(vcpu) * 2,
        fargate_task_count=instances if managed else 0,
        fargate_task_vcpu=fargate_vcpu if managed else 0.0,
        fargate_task_memory_gb=fargate_memory if managed else 0.0,
        fargate_arm=not requires_x86,
        arch=None if requires_x86 else "arm64",
        database_vcpu=db_vcpu,
        database_memory_gb=db_memory_gb,
        # Required by availability=high; not a tier upsell -- present on
        # every tier that has stated it needs to survive a zone failure.
        database_multi_az=high_availability,
        database_arch="arm64",
        database_read_replicas=replicas,
        storage_gb=storage,
        egress_gb=egress,
        load_balancer=high_availability,
        serves_requests=True,
        # rung 4 -- same gate as cache: gated on the load model AND on
        # tier_level >= 2, so a public workload's Tier 1 still omits it.
        cdn_gb=cdn_gb,
        cdn_monthly_requests=(
            float(constraints.requests_per_day) * 30.0 if cdn_wanted else 0.0
        ),
        # rung 4 -- gated on the derived rate AND on tier_level >= 2.
        cache_vcpu=2 if cache_wanted else None,
        # Capped at the database's own memory: a cache larger than what
        # the database could itself buffer buys nothing more, whatever
        # the instance family's default size would suggest.
        cache_memory_gb=min(4.0, db_memory_gb) if cache_wanted else None,
        # DEFECT 5. Priced only where the workload stated the volume.
        emails_per_month=float(constraints.emails_per_month),
        # One enqueue + one dequeue + one delete per unit of async work,
        # which is SQS's own billing shape rather than a round number.
        #
        # Sized from whatever signal exists, and never from request rate
        # ALONE: the coaching prompt states async grading and 30,000
        # notifications but no request figure, and keying off
        # requests_per_day dropped the queue entirely -- turning "we
        # cannot size this" into "this workload has no queue", which is a
        # different and wrong claim. Whether a queue EXISTS is a
        # selection decision; how big it is, is a sizing one.
        queue_requests_per_month=(
            max(
                float(constraints.requests_per_day) * 30.0,
                float(constraints.emails_per_month),
                _QUEUE_FLOOR_UNITS,
            ) * 3.0
            if constraints.async_processing else 0.0
        ),
        notifications_per_month=float(constraints.emails_per_month),
        monitored_metrics=30,
        # WAF is exposure-driven, not a capacity upsell -- present on every
        # tier once the workload is public-facing, including Tier 1.
        waf_rule_count=3 if "waf" in load.included else None,
        # Required by durability=high, on every tier.
        # Every workload is backed up unless it stated its data is
        # disposable. What durability=high adds on top is survival of
        # losing the whole REGION -- a second copy elsewhere and
        # immutability -- not the existence of a backup at all.
        backup_gb=0.0 if ephemeral else storage,
        backup_retention_days=0 if ephemeral else (35 if durable else 7),
        backup_copy_gb=storage if durable else 0.0,
        # DEFECT 8: only the changed fraction crosses each month; the
        # full dataset crosses once, at seed, and is reported as a
        # one-off rather than folded into a monthly total.
        backup_transfer_gb=(
            storage * _monthly_change_rate(constraints) if durable else 0.0
        ),
        backup_seed_gb=storage if durable else 0.0,
        object_lock=durable,
        lifecycle_gb=storage * 0.4 if durable else 0.0,
        # Only a stated residency requirement earns a guardrail. Naming a
        # city tells us where the business is, not that data may never
        # leave the country -- that needs its own trigger phrase.
        region_deny_guardrail=constraints.country_lock,
        # Free gateway endpoints on every tier; interface endpoints only
        # where the NAT savings justify their own cost (see _endpoint_plan).
        gateway_endpoints=endpoints.gateway_endpoints,
        vpc_endpoints=endpoints.interface_endpoints,
        vpc_endpoint_gb=endpoints.interface_endpoint_gb,
        # public_simple: no private application subnet means nothing routes
        # through a NAT gateway to reach it -- not a smaller NAT, none at
        # all. See whichcloud.network_topology.
        nat_gateway_count=0 if public_simple else (2 if high_availability else 1),
        # DEFECT 2: a fraction of egress, not a mirror of it. Endpoints
        # divert part of even that, so the two reductions compose.
        # Endpoints divert a share of the NAT-eligible traffic, not of
        # everything -- diverting a fraction of total egress was how this
        # clamped to zero once egress stopped being NAT's mirror.
        nat_gb_processed=(
            0.0 if public_simple
            else nat_eligible_gb * (0.5 if endpoints.justified else 1.0)
        ),
        audit_logging=True,
        tls_certificate=True,
        dns_hosted_zones=1,
        kms_key_count=1,
        # DEFECT 3: flow logs are an AUDIT control, not infrastructure.
        # Unconditionally on, sized at half of egress, they were 17% of a
        # media workload's bill for a capability nothing had asked for.
        # Now gated on a compliance obligation or a stated security need
        # -- see _flow_logs_wanted.
        flowlog_gb=(egress * 0.5) if flow_logs else 0.0,
        # ── rung 2/3: bought starting Tier 2, not Tier 1 ──
        secret_count=1 if managed else 0,
        tracing_monthly_traces=1_000_000 if managed else 0,
        threat_detection=managed,
        posture_monthly_checks=(
            resources * CHECKS_PER_RESOURCE_PER_MONTH if managed else 0.0
        ),
        # Managed identity: Cognito with MFA replaces static IAM users.
        auth_monthly_active_users=float(constraints.users) if managed and constraints.users else 0.0,
    )


def _architecture_from(spec: ArchitectureSpec, region_code: str) -> Architecture:
    """The spec, in the terms the filter checks. Fargate tasks count as
    compute instances here -- the filter cares how many independent copies
    of the app are running, not which platform runs them."""
    return Architecture(
        compute_instance_count=spec.compute_count or spec.fargate_task_count,
        availability_zones=spec.nat_gateway_count or 1,
        load_balancer=spec.load_balancer,
        database_multi_az=spec.database_multi_az,
        automated_backups=bool(spec.backup_gb),
        cross_region_copy_region=(
            "ap-south-2" if spec.backup_copy_gb and region_code == "ap-south-1" else ""
        ),
        object_lock=spec.object_lock,
        regions=(region_code,) + (("ap-south-2",) if spec.backup_copy_gb else ()),
        region_deny_guardrail=spec.region_deny_guardrail,
    )


def _check_budget_allocation(spec: ArchitectureSpec, filter_valid: bool) -> None:
    """Part 2's hard assertion: rung 4 never ships beside a failed rung 1."""
    rung4_present = bool(spec.cache_vcpu) or spec.database_read_replicas > 0
    if rung4_present and not filter_valid:
        raise BudgetMisallocationError(
            "BUDGET_MISALLOCATION: cache/read-replica present while a "
            "rung-1 requirement is unmet "
            f"(cache={bool(spec.cache_vcpu)}, replicas={spec.database_read_replicas})"
        )


def _nat_warning(tier_name: str, est: Estimate) -> str | None:
    """WARNING, not a build failure: at trivial load a single NAT gateway
    can legitimately cost more than the compute it serves, because NAT is
    priced by the hour and compute this small is priced by the same hour
    at a lower rate. The re-check this performs is the one Part 3 actually
    wants -- confirming endpoints were added first -- rather than shrinking
    NAT gateway count, which would also drop the AZ count the availability
    filter is reading it as a proxy for."""
    nat_total = sum(
        i.monthly_usd for i in est.items
        if i.label.startswith("NAT gateway") or i.label.startswith("NAT data")
    )
    compute_total = sum(
        i.monthly_usd for i in est.items
        if i.label.startswith("Compute") or i.label.startswith("Fargate")
    )
    if nat_total and compute_total and nat_total > compute_total:
        return (
            f"NAT_DISPROPORTIONATE ({tier_name}): NAT costs "
            f"${nat_total:.2f}/mo against ${compute_total:.2f}/mo of compute. "
            "Endpoints are already in place; at this traffic level a single "
            "NAT gateway is genuinely pricier than the trivial compute it "
            "serves, which is a fact about small workloads, not a sizing bug."
        )
    return None


def _standby_spec(
    *, region: str, constraints: Constraints, requires_x86: bool,
) -> ArchitectureSpec:
    """Tier 3's multi-region pattern change: a small, always-on footprint
    in the second in-country region, kept warm enough to promote quickly.
    Deliberately minimal -- this is the "still worth running in three
    years" tier buying survival, not a second copy of Tier 2's capacity."""
    return ArchitectureSpec(
        name="tier_3_standby",
        region=region,
        compute_count=0,  # Fargate only -- ArchitectureSpec defaults this to 1.
        fargate_task_count=1,
        fargate_task_vcpu=1.0,
        fargate_task_memory_gb=2.0,
        fargate_arm=not requires_x86,
        database_vcpu=2,
        database_memory_gb=8.0,
        database_multi_az=False,
        database_arch="arm64",
        storage_gb=0.0,
        egress_gb=0.0,
        serves_requests=False,
        tls_certificate=True,
        kms_key_count=1,
        audit_logging=True,
    )


def _merge_standby(primary: Estimate, standby: Estimate) -> Estimate:
    """Fold the standby region's line items into the tier's own bill,
    labelled so they read as the second region they are, not a doubled
    primary. total_monthly is a property over items, so concatenating the
    lists is the whole merge."""
    from whichcloud.estimator import LineItem

    relabelled = [
        LineItem(
            label=f"{i.label} (standby — second region)",
            sku=i.sku, unit=i.unit, unit_price=i.unit_price,
            quantity=i.quantity, monthly_usd=i.monthly_usd,
        )
        for i in standby.items
    ]
    return Estimate(
        provider=primary.provider,
        region=primary.region,
        spec=primary.spec,
        items=[*primary.items, *relabelled],
        missing=[*primary.missing, *standby.missing],
    )


def _pattern_diff(
    prev: ArchitectureSpec | None, curr: ArchitectureSpec, *, standby_added: bool,
    capacity_before: int, capacity_after: int, capacity_rps: float,
) -> list[str]:
    """What changed vs. the tier below, each line naming the risk removed.
    Diffs the specs directly rather than re-deciding from scratch, so this
    can never claim a change that the specs themselves do not show."""
    diffs: list[str] = []
    if prev is None:
        return diffs

    if prev.compute_count and not curr.compute_count and curr.fargate_task_count:
        diffs.append(
            "Compute: self-managed EC2 + Auto Scaling → ECS on Fargate — "
            "removes unpatched-host compromise and manual patch-window "
            "downtime as risks."
        )
    if not prev.auth_monthly_active_users and curr.auth_monthly_active_users:
        diffs.append(
            "Identity: static IAM users → Cognito with MFA — removes a "
            "shared or unrotated credential as a risk."
        )
    if not prev.secret_count and curr.secret_count:
        diffs.append(
            "Secrets: environment variables → Secrets Manager with "
            "rotation — removes a credential leaking through logs as a risk."
        )
    if not prev.threat_detection and curr.threat_detection:
        diffs.append(
            "Security: GuardDuty + Security Hub switched on — removes an "
            "intrusion or misconfiguration going unnoticed as a risk."
        )
    if not prev.tracing_monthly_traces and curr.tracing_monthly_traces:
        diffs.append(
            "Observability: X-Ray tracing switched on — removes "
            "diagnosis-by-guesswork as the only option when something "
            "is slow."
        )
    if standby_added:
        diffs.append(
            "Topology: single-region Multi-AZ → warm standby in a second "
            "in-country region — removes a whole-region outage as a risk."
        )
    if capacity_after > capacity_before:
        diffs.append(
            f"Capacity: {capacity_before} → {capacity_after} compute units, "
            f"sized for {capacity_rps:.2f} req/sec (3x the stated peak) — "
            "the only capacity change made, and made last."
        )
    return diffs


def _attach_extraction_meta(plan: Plan, meta: llm_extract.ExtractionMeta) -> None:
    """Record how the Constraints were read, on whichever plan resulted."""
    plan.extraction_reader = meta.reader
    plan.extraction_model = meta.model
    plan.extraction_cached = meta.cached
    plan.degraded = meta.degraded
    plan.degraded_reason = meta.degraded_reason
    plan.extraction_failover = meta.failover
    plan.extraction_failover_note = meta.failover_note
    plan.archetype_evidence_verdict = meta.evidence_verdict
    plan.composite_of = list(meta.composite_of)
    plan.extraction_spans = dict(meta.spans)


def _withheld_plan(
    constraints: Constraints, load: Load, detected: str, evidence: str,
    composite_of: list[str] | None = None,
) -> Plan:
    """Everything the engine did work out, and no price. The extraction
    and the sizing are still returned -- they are real findings, and a
    reader who can see them can tell whether the refusal is reasonable.
    What is withheld is only the number nothing has validated."""
    composite = detected == archetype_module.COMPOSITE
    state = (
        archetype_module.COMPOSITE if composite
        else archetype_module.state_for(detected)
    )
    recognised = state == archetype_module.RECOGNISED_UNPRICED
    if composite:
        note = archetype_module.composite_message(composite_of or [])
    elif recognised:
        note = (
            f"Recognised as {detected!r} ({evidence}), which this engine can "
            "name but has not yet been taught to build."
        )
    else:
        note = f"Could not classify the workload: {evidence}."
    return Plan(
        constraints=constraints,
        load=load,
        compliance=compliance_notes(constraints.country, constraints.sector),
        archetype=detected,
        archetype_state=state,
        archetype_note=note,
        archetype_requirements=archetype_module.requirements_for(detected),
        priced=False,
        withheld_reason=(
            archetype_module.composite_message(composite_of or []) if composite
            else RECOGNISED_UNPRICED_MESSAGE if recognised
            else WITHHELD_MESSAGE
        ),
        covered_archetypes=archetype_module.coverage(),
        coverage_summary=archetype_module.coverage_summary(),
        # Only useful when nothing was recognised. Asking a user to
        # clarify a shape we have already named correctly would be
        # busywork -- what they need there is the shape's requirements.
        # A composite prompt does not need the "what shape is this"
        # questions -- both shapes were identified. What it needs is a
        # decision about which to cost, which the message asks for.
        clarifying_questions=(
            [] if (recognised or composite)
            else list(archetype_module.CLARIFYING_QUESTIONS)
        ),
        extraction_confidence=constraints.confidence_map(),
    )


def build(description: str, provider: str = "aws", dsn: str | None = None) -> Plan:
    """The whole contract, in the order the modules are meant to run.

    EXTRACTION is the only step that reads free text, and the only step
    that is not deterministic. Everything below `constraints` is pure
    computation over the object it produces -- which is why `plan_from`
    exists and why the decision layer can be tested without a model.
    """
    constraints, meta = llm_extract.extract(description, dsn=dsn)
    return plan_from(constraints, description, meta, provider=provider, dsn=dsn)


def plan_from(
    constraints: Constraints,
    description: str = "",
    meta: llm_extract.ExtractionMeta | None = None,
    *,
    archetype: str | None = None,
    provider: str = "aws",
    dsn: str | None = None,
) -> Plan:
    """The deterministic half: Constraints in, priced tiers out.

    Split out from build() so it can be driven directly, with no model
    call and no text parsing. Given the same Constraints this returns the
    same components and the same totals, every time -- asserted at 100
    iterations in tests/test_determinism.py. `description` is still
    accepted because a handful of gates (x86, network isolation) read raw
    text; passing "" simply means those signals are absent.

    `archetype` must be supplied when calling this directly: feeding
    Constraints in bypasses classification, and defaulting the shape here
    would reintroduce exactly the silent default that classification
    exists to prevent. Omitting it yields a withheld plan, which is the
    correct answer to "price this, I won't say what it is".
    """
    meta = meta or llm_extract.ExtractionMeta(
        reader="direct", model="none",
        archetype=archetype or llm_extract.UNKNOWN,
    )
    if archetype is not None:
        meta.archetype = archetype
    load = build_load(constraints, description)

    # CLASSIFY BEFORE PRICING, AND REFUSE TO PRICE WHAT IS NOT COVERED.
    # The same discipline as filter-before-price one layer up: an engine
    # that only knows how to build one shape must not answer questions
    # about the other six by building that shape anyway. A refusal is a
    # usable answer; a confident bill for the wrong architecture is not.
    detected = meta.archetype
    evidence = (
        f"confidence {meta.archetype_confidence:.2f}, "
        f"{len(meta.archetype_spans)} supporting span(s)"
    )
    if not archetype_module.is_priceable(detected):
        plan = _withheld_plan(
            constraints, load, detected, evidence, meta.composite_of,
        )
        _attach_extraction_meta(plan, meta)
        return plan

    regions = COUNTRY_REGIONS.get(constraints.country, ("india",))
    region = regions[0]
    # Only enforced when the text actually locked the country -- see
    # Constraints.country_lock. A bare place name does not restrict regions.
    in_country = (
        in_country_regions(_country_name(constraints.country))
        if constraints.country_lock else ()
    )

    high_availability = constraints.availability == "high"
    durable = constraints.durability == "high"
    instances = _instances_for(load.peak_rps, high_availability=high_availability)
    requires_x86 = _requires_x86(description)
    aws_region = _aws_region(region)
    az_count = 2 if high_availability else 1

    # Computed early because the topology decision needs it: a sector
    # obligation tagged requires_network_isolation overrides everything
    # else public_simple would otherwise qualify for.
    compliance = compliance_notes(constraints.country, constraints.sector)
    topology = decide_topology(constraints, load, description, compliance)

    endpoints = _endpoint_plan(
        egress_gb=constraints.egress_gb or _default_egress_gb(constraints, load),
        az_count=az_count, aws_region=aws_region, dsn=dsn,
        nat_present=topology.value != PUBLIC_SIMPLE,
    )
    resource_count = instances + 1  # +1 for the database instance
    flow_logs, flow_logs_why = _flow_logs_wanted(constraints, compliance, description)
    if not flow_logs:
        load.excluded_with_reason.append(
            f"VPC flow logs: not added, {flow_logs_why} — they are an audit "
            "control billed per GB of traffic, not baseline infrastructure"
        )
    provisional_reasons = _provisional_reasons(constraints)

    plan = Plan(
        constraints=constraints, load=load, compliance=compliance,
        network_topology=topology.value, network_topology_reason=topology.reason,
        archetype=detected,
        archetype_state=archetype_module.PRICED,
        archetype_note=f"{detected}: {evidence}",
        priced=True,
        covered_archetypes=archetype_module.coverage(),
        coverage_summary=archetype_module.coverage_summary(),
        # Priced, but resting on an assumption that would change the
        # architecture rather than just its size -- so the number is
        # given with the caveat attached, not withheld and not implied
        # to be firmer than it is.
        provisional=bool(provisional_reasons),
        provisional_reasons=provisional_reasons,
        extraction_confidence=constraints.confidence_map(),
    )

    tier_meta = [
        ("tier_1", "Cheapest that meets your requirements", 1),
        ("tier_2", "Balanced — production-ready", 2),
        ("tier_3", "The architecture to grow into", 3),
    ]

    prev_spec: ArchitectureSpec | None = None
    capacity_3x = _instances_for(load.peak_rps * 3, high_availability=high_availability)

    for name, label, level in tier_meta:
        count = capacity_3x if level == 3 else instances
        spec = _spec_for(
            name=name, constraints=constraints, load=load, region=region,
            instances=count, tier_level=level, requires_x86=requires_x86,
            endpoints=endpoints, posture_resource_count=resource_count,
            topology=topology, flow_logs=flow_logs,
        )
        # FILTER BEFORE PRICE. A spec that fails here is never given a
        # number, because a cheap number attached to a rejected design is
        # the thing this module exists to stop producing.
        verdict = check(
            _architecture_from(spec, aws_region),
            availability=constraints.availability,
            durability=constraints.durability,
            country=_country_name(constraints.country),
            country_regions=_aws_regions(in_country),
        )
        _check_budget_allocation(spec, verdict.valid)
        if not verdict.valid:
            raise AssertionError(
                f"{name} was generated non-compliant: {verdict.violations}"
            )

        est = estimate(spec, provider, dsn=dsn)

        standby_added = False
        if level == 3 and durable and len(regions) > 1:
            standby_region = regions[1]
            standby_spec = _standby_spec(
                region=standby_region, constraints=constraints,
                requires_x86=requires_x86,
            )
            standby_est = estimate(standby_spec, provider, dsn=dsn)
            if standby_est.is_complete:
                est = _merge_standby(est, standby_est)
                standby_added = True

        obj = objectives(
            multi_instance=spec.compute_count >= 2 or spec.fargate_task_count >= 2,
            multi_az_database=spec.database_multi_az,
            cross_region_copy=bool(spec.backup_copy_gb),
            warm_standby=standby_added,
        )
        tier = Tier(
            name=name, label=label, philosophy=PHILOSOPHY[level],
            spec=spec, estimate=est,
            rto=obj["rto"], rpo=obj["rpo"],
            region_rto=obj["region_rto"], region_rpo=obj["region_rpo"],
        )
        tier.gives_up = _gives_up(spec, load, tier_level=level, topology=topology)
        tier.committed_use_note = _committed_use_note(spec)
        if level >= 2:
            tier.justifications.update(_tier_two_justifications(constraints))

        tier.pattern_diff = _pattern_diff(
            prev_spec, spec, standby_added=standby_added,
            capacity_before=instances, capacity_after=count,
            capacity_rps=load.peak_rps * 3,
        )
        if level > 1 and not tier.pattern_diff:
            tier.no_further_improvement = (
                "At this workload size there is no further improvement "
                "worth buying."
            )

        nat_warning = _nat_warning(name, est)
        if nat_warning:
            tier.warnings.append(nat_warning)

        plan.tiers.append(tier)
        prev_spec = spec

    plan.below_requirements = _below_panel(constraints, load, region, dsn, provider)

    budget = constraints.budget_monthly_usd
    cheapest = plan.tiers[0]
    if budget and cheapest.monthly_total > budget:
        plan.over_budget_note = (
            "Your requirements set a floor above your budget. Cheapest "
            "compliant design shown."
        )
    elif budget:
        reference = plan.tiers[-1]  # Tier 3 may spend up to 100% of budget
        spare = budget - reference.monthly_total
        if spare > 0:
            plan.unspent_budget = {
                "amount_usd": round(spare, 2),
                "note": (
                    f"${spare:,.2f} of your ${budget:,.0f} is unspent even "
                    "by the top tier. That is a correct result, not an "
                    f"error: every tier is sized from {load.peak_rps:.2f} "
                    "req/sec peak, and spending the remainder would buy "
                    "capacity this workload would not use."
                ),
            }
        else:
            plan.over_budget_note = (
                f"{reference.label} is over budget by "
                f"${-spare:,.2f}. It is shown anyway, flagged, rather than "
                "quietly downgraded to fit the number."
            )
    if plan.tiers:
        plan.storage_dominates, plan.storage_note = _storage_disclosure(
            constraints, plan.tiers[0]
        )
    _attach_extraction_meta(plan, meta)
    return plan


def _below_panel(constraints, load, region, dsn, provider) -> dict | None:
    """The design that fails the filter, shown apart and never priced as a tier."""
    if constraints.availability != "high" and constraints.durability != "high":
        return None

    naive = Architecture(
        compute_instance_count=1, availability_zones=1, load_balancer=False,
        database_multi_az=False, automated_backups=False, object_lock=False,
        regions=(_aws_region(region),), region_deny_guardrail=False,
    )
    in_country = (
        in_country_regions(_country_name(constraints.country))
        if constraints.country_lock else ()
    )
    verdict = check(
        naive,
        availability=constraints.availability,
        durability=constraints.durability,
        country=_country_name(constraints.country),
        country_regions=_aws_regions(in_country),
    )
    return {
        "label": "Below your stated requirements",
        "violations": verdict.violations,
        "note": (
            "Shown for comparison only. It is cheaper because it does less, "
            "not because it is better value, and it is not one of the three "
            "options above."
        ),
    }


#: Storage lines, for working out whether storage is what sets the bill.
_STORAGE_LABELS = (
    "Object storage", "Backup storage", "Cross-region backup copy",
    "Archived retention", "Database storage",
)


def _storage_disclosure(
    constraints: Constraints, tier: Tier,
) -> tuple[bool, str]:
    """Whether storage sets this bill, and whether anybody said so.

    The point is not the percentage. It is that a derived storage figure
    which happens to dominate deserves to be challenged, and a reader
    cannot challenge what the output never mentions.
    """
    total = float(tier.estimate.total_monthly)
    if total <= 0:
        return False, ""
    storage_cost = sum(
        float(i.monthly_usd) for i in tier.estimate.items
        if any(i.label.startswith(p) for p in _STORAGE_LABELS)
    )
    if storage_cost / total < 0.35:
        return False, ""

    stated = bool(
        constraints.storage_gb or constraints.content_storage_gb
        or constraints.user_data_gb
    )
    if stated:
        return False, ""
    share = 100.0 * storage_cost / total
    return True, (
        f"Storage is the largest line ({share:.0f}% of the total) and it was "
        "assumed, not stated. Tell us your library size and this number "
        f"changes. Current assumption: {_content_storage_gb(constraints):,.0f} GB "
        f"of shared content plus {_user_data_gb(constraints):,.0f} GB across "
        f"{constraints.users:,} users."
    )


def _committed_use_note(spec: ArchitectureSpec) -> str:
    """Advisory, not priced: the catalog carries on-demand rates only, so
    this is a labelled published-range caveat, never a figure looked up per
    SKU -- and it must never be added into monthly_total."""
    components = ["compute", "database"]
    if spec.cache_vcpu:
        components.append("cache")
    return (
        "available after usage stabilises: ~20-30% on "
        f"{', '.join(components)} with a 1-year AWS Savings Plan or "
        "Reserved Instance commitment (published list-price range, not "
        "looked up per SKU — not included in the total above)"
    )


def _gives_up(
    spec: ArchitectureSpec, load: Load, *, tier_level: int, topology: TopologyDecision,
) -> list[str]:
    gaps = []
    if tier_level == 1:
        gaps.append(
            "Patching, OS updates and dependency upgrades are manual — "
            "nothing here applies them for you."
        )
    if topology.value == PUBLIC_SIMPLE:
        gaps.append(
            "Application compute has a public IP. Access is controlled by "
            "security group rules rather than by network isolation. The "
            "database remains private."
        )
    if spec.database_read_replicas == 0:
        gaps.append(
            f"Reads and writes share one database; at {load.peak_rps:.2f} "
            "req/sec that is ample, but a reporting workload would contend."
        )
    if tier_level < 3:
        gaps.append(
            "Nothing here protects against a bad deployment — that needs a "
            "release process, not infrastructure."
        )
    return gaps


def _tier_two_justifications(constraints: Constraints) -> dict[str, str]:
    out = {
        "compute": (
            "moved to Fargate so patching a host is no longer a step "
            "someone has to remember"
        ),
        "secrets": (
            "credentials in environment variables leak through logs; you said "
            "the data is regulated"
        ),
        "tracing": "a slow lookup is otherwise diagnosed by guesswork",
    }
    if constraints.sector in ("healthcare", "fintech"):
        out["threat"] = (
            f"a {constraints.sector} record store is a target; detection bills "
            "per vCPU so it scales with the footprint"
        )
    return out


def _country_name(code: str) -> str:
    return {"IN": "India", "SG": "Singapore", "US": "United States",
            "IE": "Ireland", "GB": "United Kingdom"}.get(code, "")


def _aws_region(neutral: str) -> str:
    return provider_region(neutral, "aws")


def _aws_regions(neutral_keys: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(neutral_keys)
