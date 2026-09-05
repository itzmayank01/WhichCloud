"""HTTP API — the thin layer between the engine and a browser.

Everything here is a wrapper. The logic lives in `engine`, `estimator`,
`knowledge` and `pricing`; this module only translates HTTP to those calls and
back. If a route starts making decisions, it belongs in the engine instead.

Two things it deliberately exposes that a typical API would hide:

  * `fetched_at` on price data, so the frontend can show how fresh a number is
    rather than implying it is live.
  * `assumed` and `rejected` on recommendations, so the interface can show what
    was guessed and which techniques were skipped and why.

    uvicorn whichcloud.api:app --reload
"""

from __future__ import annotations

import hashlib
from decimal import Decimal
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import topology as topo
from .engine import (
    SIZING_BASIS,
    Option,
    diff_options,
    recommend,
    recommend_across_clouds,
    why_not,
)
from .knowledge import Technique, load_techniques
from .pricing import store
from .pricing.models import REGIONS
from .requirements import Requirement

app = FastAPI(
    title="WhichCloud",
    description=(
        "Cost-optimal cloud architecture from a plain-English description. "
        "Prices are fetched from provider catalogs and validated against a "
        "second source; sizing is heuristic and labelled as such."
    ),
    version="0.1.0",
)

# The frontend runs on a different port in development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


#: `parse_description` has no cache of its own -- unlike `extract_architecture`
#: and `llm_extract`'s Constraints reading, which measured that the same
#: model asked the same question twice does not reliably answer the same way.
#: Without this, `/describe/export.tf` re-reading the description could price
#: a different architecture than the one already on screen -- exactly the
#: drift this whole feature exists to rule out. In-process only: good enough
#: for one request's export to match its own display, not durable across a
#: restart.
_intake_cache: dict[str, object] = {}


def _cached_intake(description: str, reader: str | None):
    from .intake import parse_description

    key = hashlib.sha256(f"{description.strip()}|{reader or ''}".encode()).hexdigest()
    if key not in _intake_cache:
        _intake_cache[key] = parse_description(description, provider=reader)
    return _intake_cache[key]


# ── response shapes ─────────────────────────────────────────────────────


class LineItemOut(BaseModel):
    label: str
    sku: str
    unit: str
    unit_price: float
    quantity: float
    monthly_usd: float
    #: The diagram node this line belongs to, as a node KIND. The cost sheet
    #: groups by it -- "Cloud SQL" gathering its instance, standby, storage and
    #: backup rows rather than scattering them as four siblings -- and it is
    #: the same key the diagram uses, so clicking a node can find its lines and
    #: clicking a line can find its node without a second mapping to keep in
    #: step.
    group: str = ""
    #: What that node is called on this provider, so the sheet can head the
    #: group with "Cloud SQL" rather than the kind.
    group_label: str = ""


class TechniqueOut(BaseModel):
    id: str
    name: str
    category: str
    summary: str
    obviousness: str
    confidence: str
    tool: str
    tool_url: str | None
    tradeoffs: list[str]
    saved_monthly_usd: float | None = None
    versus_sku: str | None = None
    reasons: list[str] = Field(default_factory=list)
    priced: bool


class NodeOut(BaseModel):
    id: str
    label: str
    kind: str
    monthly_usd: float
    share: float  # fraction of the bill — drives visual weight
    sku: str
    detail: str
    priced: bool
    optimized_by: list[str]
    #: WHY this node is in the architecture, traced to what the description
    #: said. A role that cannot say why it is here is indistinguishable from
    #: a default that leaked in -- which is how an HR tool for eighty people
    #: acquired a web firewall. Empty only on baseline roles.
    because: str = ""
    #: Present by POLICY on every design -- identity, keys, observability,
    #: audit -- rather than derived from this workload.
    baseline: bool = False


class EdgeOut(BaseModel):
    source: str
    target: str
    label: str


class TopologyOut(BaseModel):
    nodes: list[NodeOut]
    edges: list[EdgeOut]


class ChangeOut(BaseModel):
    label: str
    kind: str  # added | removed | changed | unchanged
    delta_usd: float
    before_sku: str | None
    after_sku: str | None


class DiffOut(BaseModel):
    from_label: str
    to_label: str
    delta_monthly_usd: float
    changes: list[ChangeOut]


class OptionOut(BaseModel):
    label: str
    rationale: str
    provider: str
    region: str
    monthly_usd: float
    complete: bool
    within_budget: bool | None
    #: True when the workload saturated its capacity caps before spending the
    #: budget -- extra budget buys no more useful capacity. Lets the UI explain
    #: why a higher budget stops changing the number.
    budget_saturated: bool
    #: What this architecture costs with nothing committed -- the price the
    #: user pays today, without signing a one-year term. Null when no line had
    #: a committed rate to begin with, in which case `monthly_usd` is already
    #: the on-demand price.
    ondemand_monthly_usd: float | None = None
    #: The shape as labelled pairs rather than one middle-dot-joined string.
    #: A quotation sets its terms as a definition list with the labels aligned;
    #: "Most optimized · 3× 2 vCPU / 8 GB · regional (HA) db" is four facts
    #: run together, and the reader has to parse the punctuation to find the
    #: one they want.
    shape_parts: list[dict] = Field(default_factory=list)
    #: Which resources the committed price depends on, so the interface can
    #: name them rather than saying "1-year commitment" with no object.
    commitment_covers: list[str] = Field(default_factory=list)
    #: Steady-state monthly cost for spiky workloads (same architecture, spike
    #: headroom removed). None when traffic is not spiky or has no headroom.
    steady_monthly_usd: float | None
    shape: str
    items: list[LineItemOut]
    missing: list[str]
    measured_saving_usd: float
    saving_pct: float
    applied: list[TechniqueOut]
    advisory: list[TechniqueOut]
    tradeoffs: list[str]
    #: Does this shape meet what the requirement actually ASKED for? A
    #: tradeoff is a consequence to weigh; an unmet requirement is a promise
    #: broken. Without this the cheapest option arrives looking like a peer of
    #: the other two, when on an availability-critical workload it is the one
    #: that fails the brief.
    compliant: bool = True
    #: The specific promises this shape breaks, in the requirement's own
    #: terms. Empty when `compliant`.
    unmet: list[str] = Field(default_factory=list)
    topology: TopologyOut
    #: The option as a laid-out AWS architecture, priced. None on the other
    #: clouds until a service-equivalence table exists -- drawing a GCP option
    #: with an ECS box in it would be worse than not drawing it.
    drawn: dict | None = None


class RecommendationOut(BaseModel):
    goal: str
    region: str
    options: list[OptionOut]
    diffs: list[DiffOut]
    not_applied: list[dict]
    sizing_basis: str
    #: What the budget was read as. Without it the interface can say "within
    #: budget" but not against what, and cannot report what is left unspent --
    #: which is the difference between "this fits" and "this fits with $500
    #: to spare, here is what that would buy".
    budget_monthly_usd: float | None = None
    assumed: list[str] = Field(default_factory=list)
    clarifying_question: str | None = None
    read_by: str | None = None
    #: Which cloud these options were priced against. The caller may not have
    #: chosen it -- the description can state a preference, and the default is
    #: AWS -- so the answer has to say which cloud it is describing rather than
    #: leaving the interface to assume.
    provider: str = "aws"
    #: LOW | MEDIUM | HIGH | CRITICAL, derived from what the description SAYS
    #: rather than asked for as a field. It is the reason any option is marked
    #: non-compliant, and a warning without its reason is noise.
    criticality: str = "MEDIUM"
    #: Label of the cheapest option that actually meets the brief. Equal to
    #: the cheapest option's label when that one is compliant; different, and
    #: dearer, when it is not. Null when nothing on offer meets it -- which is
    #: a real answer, and the one a $500 budget on a must-not-go-down workload
    #: deserves.
    #:
    #: A LABEL rather than a relabelling: `label` is the key the export and
    #: diff routes look options up by, so renaming "Cheapest" to "Cheapest
    #: compliant" would break the download the user just asked for.
    cheapest_compliant: str | None = None


def _technique_out(
    technique: Technique,
    saved: Decimal | None = None,
    versus: str | None = None,
    reasons: tuple[str, ...] = (),
) -> TechniqueOut:
    tool = technique.tools[0] if technique.tools else {}
    return TechniqueOut(
        id=technique.id,
        name=technique.name,
        category=technique.category,
        summary=technique.summary,
        obviousness=technique.obviousness,
        confidence=technique.confidence,
        tool=tool.get("name", ""),
        tool_url=tool.get("url"),
        tradeoffs=list(technique.tradeoffs),
        saved_monthly_usd=float(saved) if saved is not None else None,
        versus_sku=versus,
        reasons=list(reasons),
        priced=technique.is_priceable,
    )


def _topology_out(option: Option) -> TopologyOut:
    graph = topo.build(option.spec, option.estimate, option.applied)
    total = graph.total_monthly
    return TopologyOut(
        nodes=[
            NodeOut(
                id=n.id,
                label=n.label,
                kind=n.kind,
                monthly_usd=float(n.monthly_usd),
                share=n.share_of(total),
                sku=n.sku,
                detail=n.detail,
                priced=n.priced,
                optimized_by=list(n.optimized_by),
                because=n.because,
                baseline=n.baseline,
            )
            for n in graph.nodes
        ],
        edges=[EdgeOut(source=e.source, target=e.target, label=e.label) for e in graph.edges],
    )


def _diff_out(before: Option, after: Option) -> DiffOut:
    d = diff_options(before, after)
    return DiffOut(
        from_label=d.from_label,
        to_label=d.to_label,
        delta_monthly_usd=float(d.delta_monthly),
        changes=[
            ChangeOut(
                label=c.label,
                kind=c.kind,
                delta_usd=float(c.delta),
                before_sku=c.before.sku if c.before else None,
                after_sku=c.after.sku if c.after else None,
            )
            for c in d.changes
        ],
    )


def _drawn(option: Option, provider: str) -> dict | None:
    """The option as a laid-out AWS architecture, priced.

    Only AWS for now: the service names, the icons and the network
    conventions are all AWS's, and mapping a category to "the equivalent
    service" on another cloud is a table that does not exist yet. Drawing a
    GCP option with an ECS box in it would be worse than not drawing it.
    """
    if provider != "aws":
        return None

    from decimal import Decimal

    from .architecture.costed import PricedNode, architecture_from
    from .architecture.graph import attach_prices, build_graph, slug
    from .architecture.layout import badge_point, build_layout

    # Built the same way the topology output is, rather than read off the
    # option -- an Option carries a spec and an estimate, and the graph is
    # derived from those.
    graph_in = topo.build(option.spec, option.estimate, option.applied)
    nodes = [
        PricedNode(
            kind=n.kind,
            label=n.label,
            monthly_usd=float(n.monthly_usd) if n.priced else None,
            sku=n.sku,
        )
        for n in graph_in.nodes
        if n.kind != "client"
    ]
    if not nodes:
        return None

    # Zones come from the gateways the option is billed for -- one per zone
    # -- falling back to the Multi-AZ flag when there are none.
    zones = option.spec.nat_gateway_count or None
    arch, prices = architecture_from(
        nodes, option.spec.database_multi_az, zones, option.spec.serves_requests
    )
    graph = build_graph(arch)
    attach_prices(
        graph,
        {slug(name): (Decimal(str(cost)), sku) for name, (cost, sku) in prices.items()},
    )
    layout = build_layout(graph)

    return {
        "canvas": {"width": layout.width, "height": layout.height},
        "regions": graph.regions,
        "azs_per_region": graph.azs_per_region,
        "external": graph.external,
        "counts": {
            "services": len(layout.nodes),
            "edges": len(layout.edges),
            "groups": len(layout.groups),
            "priced": graph.priced_count,
        },
        "bands": [],
        "components": [],
        "cloud": (
            {"label": layout.cloud.label, "x": layout.cloud.x, "y": layout.cloud.y,
             "w": layout.cloud.w, "h": layout.cloud.h} if layout.cloud else None
        ),
        "actor": (
            {"label": layout.actor.label, "x": layout.actor.x, "y": layout.actor.y,
             "w": layout.actor.w, "h": layout.actor.h} if layout.actor else None
        ),
        "groups": [
            {"id": g.id, "kind": g.kind, "label": g.label, "depth": g.depth,
             "x": g.x, "y": g.y, "w": g.w, "h": g.h}
            for g in layout.groups
        ],
        "nodes": [
            {"id": n.id, "label": n.label, "tier": n.tier, "purpose": n.purpose,
             "priced": n.priced, "monthly_usd": n.monthly_usd, "sku": n.sku,
             "x": n.x, "y": n.y, "w": n.w, "h": n.h}
            for n in layout.nodes
        ],
        "edges": [
            {"source": e.source, "target": e.target, "flow": e.flow, "step": e.step,
             "badge": (dict(zip(("x", "y"), badge_point(e.points, layout.nodes)))
                       if e.step else None),
             "points": [{"x": x, "y": y} for x, y in e.points]}
            # The arrow from the people comes first and carries no number: it
            # is where traffic arrives, not a step between two services.
            for e in ([layout.actor_edge] if layout.actor_edge else []) + layout.edges
        ],
    }


def _compact(n: float) -> str:
    """1_200_000 -> "1.2M". Sizing lines are read at a glance, and a raw count
    with six digits in it is not."""
    for cutoff, suffix in ((1e9, "B"), (1e6, "M"), (1e3, "k")):
        if n >= cutoff:
            return f"{n / cutoff:.1f}".rstrip("0").rstrip(".") + suffix
    return f"{n:.0f}"


def _option_out(option: Option, provider: str) -> OptionOut:
    spec = option.spec
    # Describe the compute that IS there. A serverless shape has no instances,
    # and leading with "0× 2 vCPU / 4 GB" described a fleet of nothing at the
    # size it would have been -- the same class of mistake as the multi-AZ note
    # below, which used to appear on architectures with no database.
    if spec.compute_count:
        shape = f"{spec.compute_count}× {spec.compute_vcpu} vCPU / {spec.compute_memory_gb:g} GB"
        if spec.arch:
            shape += f" {spec.arch}"
        if spec.use_spot:
            shape += " spot"
        if spec.compute_duty_cycle < 1.0:
            shape += f" @{spec.compute_duty_cycle:.0%}"
    elif spec.fargate_task_count:
        shape = f"{spec.fargate_task_count}× containers"
        if spec.arch:
            shape += f" {spec.arch}"
    elif spec.lambda_invocations_per_month:
        # Volume is the only sizing a function has: there is no instance count
        # to state, and the invocation rate is what the bill turns on.
        shape = f"serverless · {_compact(spec.lambda_invocations_per_month)} calls/mo"
    else:
        shape = "serverless"
    # Only when there IS a database. The flag is set by the reliability
    # tiers regardless, so a batch job with no database was described as
    # "multi-AZ db" while its architecture contained no database at all.
    if spec.database_multi_az and spec.database_vcpu:
        # Each cloud has its own word for this and they are not synonyms.
        # "Multi-AZ" is an AWS product term; Google calls the same thing a
        # regional (HA) configuration, and Azure calls it zone-redundant.
        # Printing "multi-AZ db" on a Cloud SQL estimate describes AWS.
        shape += " · " + {
            "aws": "multi-AZ db",
            "gcp": "regional (HA) db",
            "azure": "zone-redundant db",
        }.get(provider, "multi-AZ db")

    # Group every line under the diagram node it pays for, using the same
    # kind mapping the topology uses. One key for both views is what makes the
    # node-to-line link exact rather than a best-effort match on labels.
    from . import topology as _topo

    _graph = _topo.build(option.spec, option.estimate, option.applied)
    node_label = {n.kind: n.label for n in _graph.nodes}

    parts: list[dict] = [{"label": "tier", "value": option.label}]
    if spec.compute_count:
        compute = f"{spec.compute_count} × {spec.compute_vcpu} vCPU / {spec.compute_memory_gb:g} GB"
        if spec.arch:
            compute += f" {spec.arch}"
        parts.append({"label": "compute", "value": compute})
    elif spec.lambda_invocations_per_month:
        parts.append(
            {"label": "compute", "value": f"serverless, {_compact(spec.lambda_invocations_per_month)} calls/mo"}
        )
    if spec.database_multi_az and spec.database_vcpu:
        parts.append({
            "label": "database",
            "value": {
                "aws": "multi-AZ",
                "gcp": "regional (HA)",
                "azure": "zone-redundant",
            }.get(provider, "multi-AZ"),
        })
    parts.append({"label": "region", "value": option.estimate.region})

    return OptionOut(
        shape_parts=parts,
        drawn=_drawn(option, provider),
        label=option.label,
        rationale=option.rationale,
        provider=provider,
        region=option.estimate.region,
        monthly_usd=float(option.monthly),
        complete=option.estimate.is_complete,
        within_budget=option.within_budget,
        budget_saturated=option.budget_saturated,
        ondemand_monthly_usd=(
            float(option.ondemand_monthly)
            if option.ondemand_monthly is not None
            else None
        ),
        commitment_covers=list(option.commitment_covers),
        steady_monthly_usd=(
            float(option.steady_monthly) if option.steady_monthly is not None else None
        ),
        shape=shape,
        items=[
            LineItemOut(
                label=i.label,
                sku=i.sku,
                unit=i.unit,
                unit_price=float(i.unit_price),
                quantity=float(i.quantity),
                monthly_usd=float(i.monthly_usd),
                group=_topo._kind_for(i),
                group_label=node_label.get(_topo._kind_for(i), i.label),
            )
            for i in option.estimate.items
        ],
        missing=list(option.estimate.missing),
        measured_saving_usd=float(option.measured_saving),
        saving_pct=option.saving_pct,
        applied=[
            _technique_out(a.technique, a.saved, a.counterfactual_sku, a.match.reasons)
            for a in option.applied
        ],
        advisory=[_technique_out(m.technique, reasons=m.reasons) for m in option.advisory],
        tradeoffs=list(option.tradeoffs),
        compliant=option.compliant,
        unmet=list(option.unmet),
        topology=_topology_out(option),
    )


def _cheapest_compliant(options: list[Option]) -> str | None:
    """Label of the cheapest option that actually meets the brief.

    Cheapest by PRICE, not by position: the tiers are ordered by posture and
    a budget ladder can reorder them by cost, so picking the first compliant
    one in the list would sometimes name a dearer option than necessary.
    """
    meets = [o for o in options if o.compliant]
    return min(meets, key=lambda o: o.monthly).label if meets else None


# ── requests ────────────────────────────────────────────────────────────


class RecommendIn(BaseModel):
    """A structured requirement. Every field optional but `goal`."""

    goal: str = "a web application"
    workload_type: Literal["web", "api", "batch", "ml", "storage", "mixed"] = "web"
    traffic_pattern: Literal["steady", "spiky", "unknown"] = "unknown"
    traffic_scale: Literal["low", "medium", "high"] = "medium"
    region: str = "india"
    budget_monthly_usd: float | None = None
    storage_gb: float = 50.0
    egress_gb: float = 100.0
    interruptible: bool = False
    high_availability: bool = False
    arm_compatible: bool = True
    provider_preference: Literal["aws", "azure", "gcp"] | None = None

    # Functional signals. Without these the form path could not express a
    # single capability the engine gained -- streaming, analytics, search,
    # protection -- and a stated transaction volume was dropped before it
    # reached sizing, so ten times the load produced the same shape.
    needs_waf: bool = False
    needs_event_streaming: bool = False
    needs_analytics: bool = False
    needs_search: bool = False
    daily_transactions: int | None = None
    latency_target_ms: int | None = None

    def to_requirement(self) -> Requirement:
        return Requirement(
            goal=self.goal,
            workload_type=self.workload_type,
            traffic_pattern=self.traffic_pattern,
            traffic_scale=self.traffic_scale,
            region=self.region,
            budget_monthly_usd=self.budget_monthly_usd,
            storage_gb=self.storage_gb,
            egress_gb=self.egress_gb,
            interruptible=self.interruptible,
            high_availability=self.high_availability,
            arm_compatible=self.arm_compatible,
            provider_preference=self.provider_preference,
            needs_waf=self.needs_waf,
            needs_event_streaming=self.needs_event_streaming,
            needs_analytics=self.needs_analytics,
            needs_search=self.needs_search,
            daily_transactions=self.daily_transactions,
            latency_target_ms=self.latency_target_ms,
        )


class DescribeIn(BaseModel):
    description: str
    reader: Literal["gemini", "groq", "anthropic", "openai"] | None = None
    #: Which cloud to price against. Omitted, the description decides -- a
    #: stated preference wins, and failing that AWS. The interface needs to be
    #: able to override that so the same requirement can be compared across
    #: providers without rewriting the description to say "on GCP".
    provider: Literal["aws", "gcp", "azure"] | None = None


class PlanExportIn(BaseModel):
    description: str
    tier: Literal["tier_1", "tier_2", "tier_3"] = "tier_2"
    #: Which cloud to price AND to generate for. One field, because the two
    #: cannot disagree: exporting a cloud the tier was not priced on would
    #: hand out resources nobody costed.
    provider: Literal["aws", "gcp", "azure"] = "aws"


class DescribeExportIn(BaseModel):
    description: str
    reader: Literal["gemini", "groq", "anthropic", "openai"] | None = None
    #: One of the labels `/describe` returned, e.g. "Cheapest".
    option: str
    #: Which cloud the caller is looking at. WITHOUT THIS the route fell back
    #: to the description's stated preference, which is almost always unset,
    #: so it resolved to AWS and handed out AWS resources to someone viewing a
    #: Google Cloud or Azure architecture. The guard below existed the whole
    #: time; it simply never fired, because nothing told it what was on screen.
    #: That is worse than an unsupported-export error: a plausible-looking
    #: main.tf full of aws_instance and aws_db_instance is something a person
    #: can run.
    provider: Literal["aws", "gcp", "azure"] | None = None


class SaveArchitectureIn(BaseModel):
    """Who is saving, what they called it, and the description itself.

    `owner` arrives from the caller rather than being derived from a token.
    The identity provider sits in front of this service, and the browser never
    reaches it directly -- but that means this endpoint trusts its caller, so
    it must not be exposed publicly without a check in front of it.
    """

    owner: str
    #: Optional, because the route names an untitled save after its own
    #: description. Requiring it here would reject the case that behaviour
    #: exists to handle.
    title: str = ""
    description: str
    services: int = 0
    regions: int = 1


class ArchitectureIn(BaseModel):
    description: str
    reader: Literal["gemini", "groq", "anthropic", "openai"] | None = None
    #: Re-read rather than reuse the stored answer. Off by default, because
    #: the stored answer is the one the user has already seen.
    refresh: bool = False


# ── routes ──────────────────────────────────────────────────────────────


@app.get("/health")
def health() -> dict:
    """Is the catalog loaded and usable?"""
    try:
        rows = store.stats()
    except Exception as exc:
        raise HTTPException(503, f"price catalog unreachable: {exc}") from exc

    total = sum(r["n"] for r in rows)
    if not total:
        raise HTTPException(503, "price catalog is empty — run ingest_prices.py")

    from .architecture.readers import configured

    return {
        "status": "ok",
        "prices": total,
        "providers": sorted({r["provider"] for r in rows}),
        "last_updated": max(r["fetched"] for r in rows).isoformat(),
        # Counts only, never the keys. Lets the interface say "three readers
        # configured" and lets you see a new key took effect without a restart
        # being a matter of faith.
        "readers": configured(),
    }


@app.get("/provenance")
def provenance() -> dict:
    """Where the catalog's numbers came from.

    Exists so the site can show its working rather than assert it. The split
    is counted from the catalog on every call, so it cannot drift away from
    what is actually stored the way a figure typed into a page would.
    """
    try:
        rows = store.provenance()
    except Exception as exc:
        raise HTTPException(503, f"price catalog unreachable: {exc}") from exc

    total = sum(r["n"] for r in rows)
    if not total:
        raise HTTPException(503, "price catalog is empty — run ingest_prices.py")

    return {
        "total": total,
        "split": {r["kind"]: r["n"] for r in rows},
    }


@app.get("/regions")
def regions() -> dict:
    """Regions the catalog can actually price, and their provider mappings.

    Only regions with prices in the catalog are returned. REGIONS is the set
    this service knows how to map; it is not the set it can answer for, and
    the difference matters: the landing page offers these as choices and
    counts them as a capability, so advertising a region with no rows behind
    it produces a comparison of zeros and a claim that is not true.
    """
    from .pricing.store import priced_regions

    try:
        available = priced_regions()
    except Exception:
        # No catalog reachable means no region can be priced. Returning the
        # configured map here would put choices in front of a reader that
        # answer with zeros, which is worse than offering none.
        return {}

    return {k: v for k, v in REGIONS.items() if any(r in available for r in v.values())}


@app.get("/catalog")
def catalog(
    region: str = "india",
    category: str = "compute",
    min_vcpu: int = 0,
    min_memory_gb: float = 0,
    arch: str | None = None,
    purchase: str = "ondemand",
    provider: str | None = None,
    limit: int = Query(100, le=500),
) -> dict:
    """Browse the price catalog. Powers the comparison table.

    Returns `fetched_at` per row so the interface can show how fresh a price
    is rather than implying it is live.
    """
    if region not in REGIONS:
        raise HTTPException(400, f"unknown region {region!r}; try {sorted(REGIONS)}")

    from .pricing.models import provider_region

    regions_wanted = []
    for prov in ([provider] if provider else ["aws", "azure", "gcp"]):
        try:
            regions_wanted.append(provider_region(region, prov))
        except ValueError:
            continue

    sql = """
        SELECT provider, region, sku, name, vcpu, memory_gb, arch, unit,
               price_usd, attributes, fetched_at
        FROM price_points
        WHERE category = %(category)s AND region = ANY(%(regions)s)
    """
    params: dict = {
        "category": category,
        "regions": regions_wanted,
        "limit": limit,
    }
    if category == "compute":
        sql += """ AND coalesce(vcpu, 0) >= %(vcpu)s
                   AND coalesce(memory_gb, 0) >= %(memory)s
                   AND attributes->>'purchase' = %(purchase)s"""
        params |= {"vcpu": min_vcpu, "memory": min_memory_gb, "purchase": purchase}
    if arch:
        sql += " AND arch = %(arch)s"
        params["arch"] = arch
    sql += " ORDER BY price_usd ASC LIMIT %(limit)s"

    with store.connect() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()

    return {
        "region": region,
        "category": category,
        "count": len(rows),
        "rows": [
            {
                "provider": r["provider"],
                "region": r["region"],
                "sku": r["sku"],
                "name": r["name"],
                "vcpu": r["vcpu"],
                "memory_gb": r["memory_gb"],
                "arch": r["arch"],
                "unit": r["unit"],
                "hourly_usd": float(r["price_usd"]),
                "monthly_usd": float(r["price_usd"]) * (730 if r["unit"] == "hour" else 1),
                "fetched_at": r["fetched_at"].isoformat(),
            }
            for r in rows
        ],
    }


@app.get("/techniques")
def techniques() -> dict:
    """The optimization knowledge base."""
    return {
        "count": len(load_techniques()),
        "techniques": [
            _technique_out(t).model_dump() for t in load_techniques()
        ],
    }


@app.post("/recommend", response_model=RecommendationOut)
def recommend_route(body: RecommendIn) -> RecommendationOut:
    """Three priced architectures for a structured requirement."""
    try:
        requirement = body.to_requirement()
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    provider = requirement.provider_preference or "aws"
    try:
        options = recommend(requirement, provider)
    except Exception as exc:
        raise HTTPException(500, f"recommendation failed: {exc}") from exc

    return RecommendationOut(
        goal=requirement.goal,
        region=requirement.region,
        options=[_option_out(o, provider) for o in options],
        criticality=options[0].criticality if options else "MEDIUM",
        cheapest_compliant=_cheapest_compliant(options),
        diffs=[_diff_out(a, b) for a, b in zip(options, options[1:])],
        not_applied=[
            {"id": t.id, "name": t.name, "reason": why}
            for t, why in why_not(requirement, provider)
        ],
        sizing_basis=SIZING_BASIS,
        provider=provider,
    )


@app.post("/compare")
def compare_route(body: RecommendIn) -> dict:
    """The same requirement priced on every cloud.

    Incomplete estimates are flagged rather than filtered: a total missing its
    database is not cheaper, it is wrong, and the interface should say so.
    """
    try:
        requirement = body.to_requirement()
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    results = recommend_across_clouds(requirement)
    return {
        "goal": requirement.goal,
        "region": requirement.region,
        "sizing_basis": SIZING_BASIS,
        "clouds": {
            provider: [_option_out(o, provider).model_dump() for o in options]
            for provider, options in results.items()
        },
    }


@app.post("/architecture")
def architecture_route(body: ArchitectureIn) -> dict:
    """A description, drawn.

    Separate from /describe, which answers "what would this cost" and keeps
    only what it can price -- six nodes out of a twenty six service
    description. This answers "what did you describe", so it keeps everything
    named whether or not the catalog can price it.

    The coordinates are computed here rather than in the browser. Layout is
    deterministic and depends on nothing the client knows, so doing it once on
    the server means every viewer of the same architecture sees the same
    picture, and the interface is left with drawing rather than deciding.
    """
    from .architecture.extract import extract_architecture
    from .architecture.graph import build_graph
    from .architecture.layout import badge_point, build_layout
    from .intake import IntakeError

    if not body.description.strip():
        raise HTTPException(400, "description is empty")

    try:
        arch = extract_architecture(
            body.description,
            reader=body.reader or "gemini",
            refresh=body.refresh,
        )
    except IntakeError as exc:
        raise HTTPException(503, str(exc)) from exc

    graph = build_graph(arch)
    layout = build_layout(graph)

    return {
        "canvas": {"width": layout.width, "height": layout.height},
        "regions": graph.regions,
        "azs_per_region": graph.azs_per_region,
        "external": graph.external,
        "counts": {
            "services": len(layout.nodes),
            "edges": len(layout.edges),
            "groups": len(layout.groups),
            "priced": graph.priced_count,
        },
        "bands": [{"tier": b.tier, "y": b.y, "h": b.h} for b in layout.bands],
        # Functional groups -- "Web UI component", "Data component" -- which
        # are what organise an AWS reference diagram. Drawn behind everything.
        "components": [
            {"name": c.name, "x": c.x, "y": c.y, "w": c.w, "h": c.h}
            for c in layout.components
        ],
        # The provider boundary and the people outside it. Every reference
        # architecture is framed this way, and without it a diagram is a pile
        # of services with no edge to the system.
        "cloud": (
            {
                "label": layout.cloud.label, "x": layout.cloud.x,
                "y": layout.cloud.y, "w": layout.cloud.w, "h": layout.cloud.h,
            }
            if layout.cloud
            else None
        ),
        "actor": (
            {
                "label": layout.actor.label, "x": layout.actor.x,
                "y": layout.actor.y, "w": layout.actor.w, "h": layout.actor.h,
            }
            if layout.actor
            else None
        ),
        # Outermost first: the interface paints them in order so nesting lands
        # on top without having to sort anything itself.
        "groups": [
            {
                "id": g.id, "kind": g.kind, "label": g.label, "depth": g.depth,
                "x": g.x, "y": g.y, "w": g.w, "h": g.h,
            }
            for g in layout.groups
        ],
        "nodes": [
            {
                "id": n.id, "label": n.label, "tier": n.tier,
                "purpose": n.purpose, "priced": n.priced,
                "monthly_usd": n.monthly_usd, "sku": n.sku,
                "x": n.x, "y": n.y, "w": n.w, "h": n.h,
            }
            for n in layout.nodes
        ],
        # Already routed. A polyline, not two endpoints, so the client does not
        # have to work out where an arrow should meet a box.
        "edges": [
            {
                "source": e.source, "target": e.target, "flow": e.flow,
                # Where on this arrow its number goes, worked out here so both
                # renderers put it in the same place.
                "step": e.step,
                "badge": (
                    dict(zip(("x", "y"), badge_point(e.points, layout.nodes)))
                    if e.step
                    else None
                ),
                "points": [{"x": x, "y": y} for x, y in e.points],
            }
            for e in layout.edges
        ],
    }


@app.post("/architecture/export.svg")
def export_architecture_route(body: ArchitectureIn):
    """The same diagram as a file someone can keep.

    SVG rather than an image, because it opens in draw.io, Figma and
    Illustrator as editable shapes -- the export is a starting point rather
    than a picture of one.
    """
    from fastapi.responses import Response

    from .architecture.extract import extract_architecture
    from .architecture.graph import build_graph
    from .architecture.layout import build_layout
    from .architecture.svg import render
    from .intake import IntakeError

    if not body.description.strip():
        raise HTTPException(400, "description is empty")

    try:
        arch = extract_architecture(
            body.description, reader=body.reader or "gemini", refresh=body.refresh
        )
    except IntakeError as exc:
        raise HTTPException(503, str(exc)) from exc

    svg = render(build_layout(build_graph(arch)))
    return Response(
        content=svg,
        media_type="image/svg+xml",
        headers={"Content-Disposition": 'attachment; filename="architecture.svg"'},
    )


@app.post("/architecture/save")
def save_architecture_route(body: SaveArchitectureIn) -> dict:
    """Keep an architecture so it can be reopened rather than re-described."""
    if not body.owner.strip():
        raise HTTPException(400, "owner is required")
    if not body.description.strip():
        raise HTTPException(400, "description is empty")

    title = body.title.strip() or body.description.strip()[:60]
    try:
        saved = store.save_architecture(
            body.owner, title, body.description, body.services, body.regions
        )
    except Exception as exc:
        raise HTTPException(503, f"could not save: {exc}") from exc

    saved["id"] = str(saved["id"])
    saved["created_at"] = saved["created_at"].isoformat()
    return saved


@app.get("/architecture/saved")
def saved_architectures_route(owner: str = Query(...)) -> dict:
    """Everything this owner has kept, newest first."""
    try:
        rows = store.list_architectures(owner)
    except Exception as exc:
        raise HTTPException(503, f"could not read saved: {exc}") from exc

    for row in rows:
        row["id"] = str(row["id"])
        row["created_at"] = row["created_at"].isoformat()
    return {"saved": rows}


@app.delete("/architecture/saved/{architecture_id}")
def delete_architecture_route(architecture_id: str, owner: str = Query(...)) -> dict:
    """Remove one. Silently does nothing if it is not this owner's."""
    try:
        removed = store.delete_architecture(owner, architecture_id)
    except Exception as exc:
        raise HTTPException(503, f"could not delete: {exc}") from exc
    return {"deleted": removed}


@app.post("/plan")
def plan_endpoint(body: DescribeIn) -> dict:
    """The reasoning-layer contract: a description in, three compliant tiers out.

    Separate from /describe rather than replacing it. /describe still
    answers "what would this cost", which is a fair question and the one
    the price index is built around. This answers "what should I build,
    given what I told you" -- and it refuses to price anything that fails
    a stated requirement, which is a different promise.
    """
    from whichcloud import plan as planning

    try:
        result = planning.build(body.description)
    except AssertionError as exc:  # a tier was generated non-compliant
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    constraints = result.constraints
    return {
        "sizing_basis": result.load.sizing_basis(),
        "excluded_with_reason": result.load.excluded_with_reason,
        "tiers": [
            {
                "name": tier.name,
                "label": tier.label,
                "philosophy": tier.philosophy,
                "monthly_total": round(tier.monthly_total, 2),
                "within_budget": tier.within_budget(constraints.budget_monthly_usd),
                "rto": tier.rto,
                "rpo": tier.rpo,
                "region_rto": tier.region_rto,
                "region_rpo": tier.region_rpo,
                "gives_up": tier.gives_up,
                "justifications": tier.justifications,
                "pattern_diff_vs_previous_tier": tier.pattern_diff,
                "no_further_improvement": tier.no_further_improvement,
                "warnings": tier.warnings,
                "committed_use_note": tier.committed_use_note,
                "components": [
                    {
                        "label": item.label,
                        "sku": item.sku,
                        "unit": item.unit,
                        "monthly_usd": float(item.monthly_usd),
                    }
                    for item in tier.estimate.items
                ],
                "complete": tier.estimate.is_complete,
                "missing": tier.estimate.missing,
            }
            for tier in result.tiers
        ],
        # The default view is the recommended tier, not the cheapest --
        # showing the cheapest first makes price the frame for every
        # comparison that follows.
        "default_tier": "tier_2",
        "below_requirements_panel": result.below_requirements,
        "compliance_notes": result.compliance,
        "assumed_fields": constraints.assumed_fields(),
        "stated_fields": {
            name: constraints.evidence.get(name, "")
            for name in sorted(constraints.stated)
        },
        "unspent_budget": result.unspent_budget,
        "over_budget_note": result.over_budget_note,
        "network_topology": result.network_topology,
        "network_topology_reason": result.network_topology_reason,
        "archetype": result.archetype,
        "archetype_note": result.archetype_note,
        # One of: priced | recognised_unpriced | unknown. The latter two
        # both withhold pricing, but for different reasons and with
        # different copy -- see whichcloud.archetype.
        "archetype_state": result.archetype_state,
        "archetype_requirements": result.archetype_requirements,
        "coverage_summary": result.coverage_summary,
        # False means the engine declined to price this shape. `tiers` is
        # then empty by decision, not by failure -- the interface must say
        # so rather than rendering an empty result as a broken one.
        "priced": result.priced,
        "withheld_reason": result.withheld_reason,
        "covered_archetypes": result.covered_archetypes,
        "clarifying_questions": result.clarifying_questions,
        "provisional": result.provisional,
        "provisional_reasons": result.provisional_reasons,
        "extraction_confidence": result.extraction_confidence,
        # How the Constraints were read. `degraded` means the phrase-table
        # fallback answered because no model was reachable -- it reads far
        # fewer phrasings, so a plan built on it must say so.
        "extraction_reader": result.extraction_reader,
        "extraction_model": result.extraction_model,
        "extraction_cached": result.extraction_cached,
        "degraded": result.degraded,
        "degraded_reason": result.degraded_reason,
        "extraction_failover": result.extraction_failover,
        "extraction_failover_note": result.extraction_failover_note,
        "archetype_evidence_verdict": result.archetype_evidence_verdict,
        # STEP 1: the assumption that moves the bill most, at the top.
        "dominant_driver_note": result.dominant_driver_note,
        "cost_drivers": result.cost_drivers,
        "total_low": result.total_low,
        "total_high": result.total_high,
        "storage_dominates": result.storage_dominates,
        "storage_note": result.storage_note,
        # STEP 3: order-of-magnitude smoke alarms, warnings not failures.
        "guards": result.guards,
        "extraction_spans": result.extraction_spans,
    }


@app.post("/plan/export.tf")
def plan_export_terraform_route(body: PlanExportIn):
    """One tier of `/plan`, as a downloadable Terraform project.

    Re-runs the same planner rather than accepting a spec from the client,
    for the same reason `/architecture/export.svg` re-runs extraction: the
    server is the only thing that has actually priced anything, so it is
    the only thing that gets to decide what the SKUs were.
    """
    from fastapi.responses import Response

    from . import plan as planning
    from . import terraform_export, terraform_export_azure, terraform_export_gcp

    if not body.description.strip():
        raise HTTPException(400, "description is empty")

    try:
        result = planning.build(body.description, provider=body.provider)
    except AssertionError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    tier = next((t for t in result.tiers if t.name == body.tier), None)
    if tier is None:
        raise HTTPException(404, f"no priced tier named {body.tier!r}")

    generator = {
        "aws": terraform_export,
        "gcp": terraform_export_gcp,
        "azure": terraform_export_azure,
    }[body.provider]
    files = generator.generate(tier.spec, tier.estimate)
    archive = terraform_export.zip_bytes(files)
    return Response(
        content=archive,
        media_type="application/zip",
        headers={
            "Content-Disposition": 'attachment; filename="whichcloud-terraform.zip"'
        },
    )


@app.post("/describe", response_model=RecommendationOut)
def describe_route(body: DescribeIn) -> RecommendationOut:
    """Plain English straight through to three priced architectures.

    The only route that needs a model API key. It reports what the model
    assumed and what it would ask next, so the interface can surface guesses
    as guesses.
    """
    from .intake import IntakeError

    try:
        intake = _cached_intake(body.description, body.reader)
    except IntakeError as exc:
        raise HTTPException(400, str(exc)) from exc

    requirement = intake.requirement
    # An explicit request wins over the description's stated preference, which
    # in turn wins over the default. Comparing providers is the product's whole
    # job, so the caller has to be able to ask for one.
    provider = body.provider or requirement.provider_preference or "aws"
    options = recommend(requirement, provider)

    return RecommendationOut(
        goal=requirement.goal,
        region=requirement.region,
        options=[_option_out(o, provider) for o in options],
        criticality=options[0].criticality if options else "MEDIUM",
        cheapest_compliant=_cheapest_compliant(options),
        diffs=[_diff_out(a, b) for a, b in zip(options, options[1:])],
        not_applied=[
            {"id": t.id, "name": t.name, "reason": why}
            for t, why in why_not(requirement, provider)
        ],
        sizing_basis=SIZING_BASIS,
        budget_monthly_usd=(
            float(intake.requirement.budget_monthly_usd)
            if intake.requirement.budget_monthly_usd
            else None
        ),
        assumed=list(intake.assumed),
        clarifying_question=intake.clarifying_question,
        read_by=intake.provider,
        provider=provider,
    )


@app.post("/describe/export.tf")
def describe_export_terraform_route(body: DescribeExportIn):
    """One option from `/describe`, as a downloadable Terraform project.

    Reads through `_cached_intake` rather than `parse_description` directly:
    `/describe` already cached this description's extraction (or is about to
    cache it, if this export request comes first), and reusing it is the only
    way to guarantee this matches what `/describe` showed. `parse_description`
    has no cache of its own -- re-running it here would risk a different
    priced architecture than the one already on screen.
    """
    from fastapi.responses import Response

    from . import terraform_export, terraform_export_azure, terraform_export_gcp
    from .intake import IntakeError

    try:
        intake = _cached_intake(body.description, body.reader)
    except IntakeError as exc:
        raise HTTPException(400, str(exc)) from exc

    requirement = intake.requirement
    provider = body.provider or requirement.provider_preference or "aws"
    # One generator per cloud, because the resource graphs differ in shape and
    # not merely in resource names -- a global network, one regional Cloud NAT
    # and an anycast load balancer are different FILES, not renamed ones.
    generators = {
        "aws": terraform_export,
        "gcp": terraform_export_gcp,
        "azure": terraform_export_azure,
    }
    generator = generators.get(provider)
    if generator is None:
        raise HTTPException(
            400,
            f"No Terraform generator for {provider!r}. Emitting another "
            f"cloud's resources for it would produce a plan that applies "
            f"cleanly and builds the wrong thing.",
        )
    options = recommend(requirement, provider)

    option = next((o for o in options if o.label == body.option), None)
    if option is None:
        raise HTTPException(404, f"no priced option named {body.option!r}")

    files = generator.generate(option.spec, option.estimate)
    archive = terraform_export.zip_bytes(files)
    return Response(
        content=archive,
        media_type="application/zip",
        headers={
            "Content-Disposition": 'attachment; filename="whichcloud-terraform.zip"'
        },
    )
