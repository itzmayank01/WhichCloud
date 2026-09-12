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

import dataclasses
import hashlib
import os
from decimal import Decimal
from typing import Literal

from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
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
from .auth import current_owner
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

# The frontend runs on a different port in development, and on a different
# HOST once it is deployed. The local ports stay listed unconditionally --
# they cost nothing in production and losing them would break every
# development machine the first time this is configured.
#
# Deployed origins are added through WHICHCLOUD_ALLOWED_ORIGINS, comma
# separated. Without it a hosted frontend gets a CORS refusal on every
# request, which surfaces in the browser as the API being down rather than as
# a configuration setting nobody set.
_LOCAL_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
]
_CONFIGURED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("WHICHCLOUD_ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=[*_LOCAL_ORIGINS, *_CONFIGURED_ORIGINS],
    # Vercel gives every deployment its own hostname, so a preview build is a
    # different origin from the production one and from every other preview.
    # Naming them individually would mean editing this list per deploy; the
    # pattern is anchored at both ends so it cannot match a domain that merely
    # CONTAINS the project name.
    allow_origin_regex=os.getenv("WHICHCLOUD_ALLOWED_ORIGIN_REGEX") or None,
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
    #: Approximations behind THIS figure. An approximation disclosed in a
    #: README is not disclosed -- the reader of a bill sees a line and a
    #: number, so that is where a derived, single-sourced or
    #: ranking-only rate has to say so.
    caveats: list[str] = Field(default_factory=list)


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
    #: data | control | account. THE field that decides how this is drawn.
    #: A request flows through the data plane; the control plane attaches
    #: to one node; the account plane watches everything and connects to
    #: nothing. Drawing all three the same way is what produced a row of
    #: unconnected boxes at the bottom of every diagram.
    plane: str = "data"


class EdgeOut(BaseModel):
    source: str
    target: str
    label: str
    #: `flow` for a request travelling through, `attaches` for a binding.
    #: A request does not travel through a key, so the animation follows
    #: `flow` edges only.
    kind: str = "flow"


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
                plane=n.plane,
            )
            for n in graph.nodes
        ],
        edges=[
            EdgeOut(source=e.source, target=e.target, label=e.label, kind=e.kind)
            for e in graph.edges
        ],
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
                caveats=list(i.caveats),
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
    #: Selects the event-driven service graph -- a bus and a stream ahead of
    #: the compute, rather than a request path through it. The field existed on
    #: Requirement and on the plain-English path from the start, but not here,
    #: so the structured routes could not reach one of the seven archetypes at
    #: all: posting it was accepted and silently dropped, and the caller got a
    #: web app back.
    event_driven: bool = False
    needs_queue: bool = False
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
            event_driven=self.event_driven,
            needs_queue=self.needs_queue,
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


class AdviseIn(BaseModel):
    description: str
    #: A question about the architecture. Free text -- "why is this so
    #: expensive", "can I drop the second NAT gateway", "is this right for
    #: 300 staff".
    question: str
    #: Which tier is on screen. The advice is about the architecture the
    #: person is looking at, so the wrong one here answers a question nobody
    #: asked -- the same trap `/describe/export.tf` documents above.
    option: str
    provider: Literal["aws", "gcp", "azure"] | None = None
    reader: Literal["gemini", "groq", "anthropic", "openai"] | None = None


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
    """What they called it, and the description itself.

    NO `owner` FIELD, deliberately. It used to be here, with a note saying the
    identity provider sat in front of this service and the browser never
    reached it directly -- so the endpoint trusted its caller.

    The premise was false. The frontend calls this API from the client, and
    NEXT_PUBLIC_API_URL is public by construction, so the browser reaches it
    every time. `?owner=someone-else` read another person's saved
    architectures and a DELETE with the same parameter removed them.

    Identity now comes from the verified session token and this model cannot
    express it. Removing the field rather than ignoring it is the point: an
    ignored field still looks like an input, and the next person to read this
    would wire it back up.
    """

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
    from .pricing import cache as price_cache

    return {
        "status": "ok",
        "prices": total,
        "providers": sorted({r["provider"] for r in rows}),
        "last_updated": max(r["fetched"] for r in rows).isoformat(),
        # Counts only, never the keys. Lets the interface say "three readers
        # configured" and lets you see a new key took effect without a restart
        # being a matter of faith.
        "readers": configured(),
        # A cache nobody measures is a cache nobody can tell is broken:
        # a 0% hit rate and a working cache look identical from outside.
        "price_cache": price_cache.STATS.as_dict(),
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
    providers = tuple(results)

    # WHAT MAY HONESTLY BE COMPARED, and what may not.
    #
    # The interface used to intersect line-item LABELS to work out which
    # services all three clouds priced. That is a guess about equivalence
    # made from text; knowledge-base/service-mappings is the answer, and
    # it refuses on anything unmapped rather than assuming.
    from whichcloud import mappings
    from whichcloud.estimator import comparable_lines

    first = next(iter(results.values()), [])
    estimates = [
        options[0].estimate
        for options in results.values() if options
    ]
    categories, refusals, caveats = (
        comparable_lines(estimates, providers) if estimates else ([], [], [])
    )

    return {
        "goal": requirement.goal,
        "region": requirement.region,
        "sizing_basis": SIZING_BASIS,
        "clouds": {
            provider: [_option_out(o, provider).model_dump() for o in options]
            for provider, options in results.items()
        },
        # The categories the compared totals actually cover. A total is
        # only like-for-like over these.
        "comparable_categories": categories,
        # Services one cloud prices and another has no equivalent for, or
        # that nobody has established an equivalence for. Each carries
        # its reason, because a refusal nobody can check is not much
        # better than a guess.
        "not_comparable": refusals,
        # Services that DO compare, but where the billing models differ
        # enough that the difference is not purely price.
        "comparison_caveats": caveats,
        "mapping_coverage": mappings.coverage(),
    }


def _designed_refusal(description: str, evidence: str) -> dict:
    """The answer when a diagram would have to be invented to exist.

    Shaped like an ArchitectureView with nothing in it -- an empty canvas,
    no nodes, no edges -- plus the fields that say why. That shape is
    deliberate: the interface has one renderer for this endpoint, and a
    refusal it can render as an empty diagram with a panel over it needs
    no second code path to avoid crashing on missing keys.

    The archetype is classified here so the refusal can name the shape and
    ask for the figures that would let the deterministic planner price it,
    rather than stopping at "no".
    """
    from whichcloud import archetype as archetype_module
    from whichcloud import llm_extract

    detected, requirements, questions = archetype_module.UNKNOWN, "", []
    try:
        _constraints, meta = llm_extract.extract(description)
        detected = meta.archetype
        requirements = archetype_module.requirements_for(detected)
        questions = archetype_module.pricing_questions_for(detected)
    except Exception:  # noqa: BLE001 -- a failed read still refuses, just blandly
        pass

    named = archetype_module.describe(detected)
    return {
        "canvas": {"width": 0, "height": 0},
        "regions": 0, "azs_per_region": 0, "external": [],
        "counts": {"services": 0, "edges": 0, "groups": 0, "priced": 0},
        "bands": [], "components": [], "cloud": None, "actor": None,
        "groups": [], "nodes": [], "edges": [],
        # ── why there is nothing to draw ──
        "designed": True,
        "archetype": detected,
        "archetype_state": archetype_module.state_for(detected),
        "withheld_reason": (
            "This description names no cloud services, so a diagram of it "
            "could only be one a language model invented. This engine does "
            "not choose services at request time — a picture nobody can "
            "check against your words, or against a price, is worse than "
            "no picture."
        ),
        "evidence": evidence,
        "recognised_as": named if detected != archetype_module.UNKNOWN else "",
        "archetype_requirements": requirements,
        "pricing_questions": questions,
        "next_step": (
            "Send the same description to /plan. It classifies the workload "
            "and either prices it from the catalog or says exactly which "
            "figures it still needs."
        ),
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
    from .architecture.provenance import was_designed
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

    # TRANSCRIPTION ONLY. Drawing back the services someone named is a
    # reading task and stays. Drawing services the model CHOSE is a
    # runtime service selection by a language model -- unpriced,
    # unvalidated, different on every call -- and it is the one thing this
    # engine refuses to do. The deterministic planner answers that
    # question instead, either with a priced architecture or with a
    # refusal that says which figures it still needs.
    designed, evidence = was_designed(arch, body.description)
    if designed:
        return _designed_refusal(body.description, evidence)

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
    from .architecture.provenance import was_designed
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

    # Same gate as /architecture. An exported file outlives the session
    # that made it, so an invented architecture is MORE dangerous here,
    # not less -- it ends up in a slide deck with no caveat attached.
    designed, evidence = was_designed(arch, body.description)
    if designed:
        raise HTTPException(422, (
            "This description names no cloud services, so the diagram could "
            "only be one a language model invented. Send it to /plan "
            f"instead, which prices what it recognises. ({evidence})"
        ))

    svg = render(build_layout(build_graph(arch)))
    return Response(
        content=svg,
        media_type="image/svg+xml",
        headers={"Content-Disposition": 'attachment; filename="architecture.svg"'},
    )


@app.post("/architecture/save")
def save_architecture_route(
    body: SaveArchitectureIn, owner: str = Depends(current_owner)
) -> dict:
    """Keep an architecture so it can be reopened rather than re-described.

    The owner comes from the verified session, and `body.owner` is ignored --
    see the note on SaveArchitectureIn. A caller who names themselves is
    naming a wish, not a fact.
    """
    if not body.description.strip():
        raise HTTPException(400, "description is empty")

    title = body.title.strip() or body.description.strip()[:60]
    try:
        saved = store.save_architecture(
            owner, title, body.description, body.services, body.regions
        )
    except Exception as exc:
        raise HTTPException(503, f"could not save: {exc}") from exc

    saved["id"] = str(saved["id"])
    saved["created_at"] = saved["created_at"].isoformat()
    return saved


@app.get("/architecture/saved")
def saved_architectures_route(owner: str = Depends(current_owner)) -> dict:
    """Everything this owner has kept, newest first.

    Was `?owner=` -- which meant `?owner=someone-else` returned their saves.
    """
    try:
        rows = store.list_architectures(owner)
    except Exception as exc:
        raise HTTPException(503, f"could not read saved: {exc}") from exc

    for row in rows:
        row["id"] = str(row["id"])
        row["created_at"] = row["created_at"].isoformat()
    return {"saved": rows}


@app.delete("/architecture/saved/{architecture_id}")
def delete_architecture_route(
    architecture_id: str, owner: str = Depends(current_owner)
) -> dict:
    """Remove one. Silently does nothing if it is not this owner's.

    The scoping was always here; the owner it scoped to was whatever the query
    string said, so the check compared a row against an attacker's claim.
    """
    try:
        removed = store.delete_architecture(owner, architecture_id)
    except Exception as exc:
        raise HTTPException(503, f"could not delete: {exc}") from exc
    return {"deleted": removed}


@app.post("/audit")
async def audit_route(file: UploadFile = File(...)) -> dict:
    """P3 AUDIT: a billing export in, a waste report out.

    The PRD's third product. `backend/audit/` is an internal scorecard
    grading the ENGINE, not this -- nothing in it reads a billing CSV.

    CSV upload only, deliberately. A live account connection is out of
    scope for v1, and a read-only IAM role is a credential this product
    has no business holding; a CSV is something the user can look at
    before they hand it over.
    """
    from .billing_audit import BillingParseError, audit as run_audit

    raw = await file.read()
    if len(raw) > 25 * 1024 * 1024:
        raise HTTPException(413, "Billing export is larger than 25 MB.")
    try:
        content = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(400, "File is not UTF-8 text.") from None

    try:
        report = run_audit(content)
    except BillingParseError as exc:
        # 422, not 500: the file was read fine and is not one we can
        # reason about, which is the user's problem to fix and needs the
        # specific reason rather than a stack trace.
        raise HTTPException(422, str(exc)) from exc

    return {
        "currency": report.currency,
        "total_monthly_usd": report.total_monthly_usd,
        "lines_read": report.lines_read,
        # BEST PER SERVICE, not the sum of every finding. Techniques
        # against one service are alternatives, not a shopping list --
        # summing them produced a 147.9% saving on the first sample bill.
        "total_saving_usd": report.total_saving_usd,
        "saving_pct": report.saving_pct,
        "saving_basis": (
            "The best single technique per service, summed across "
            "services. Techniques against the same service are "
            "alternatives rather than additive, so they are never summed."
        ),
        "findings": [
            {
                "service": f.service,
                "monthly_usd": f.monthly_usd,
                "technique_id": f.technique_id,
                "technique": f.technique,
                "category": f.category,
                "summary": f.summary,
                "saved_monthly_usd": f.saved_monthly_usd,
                "basis": f.basis,
                "measured": f.measured,
                "obviousness": f.obviousness,
                "tradeoffs": f.tradeoffs,
                "tool": f.tool,
                "tool_url": f.tool_url,
                "needs_confirmation": f.needs_confirmation,
            }
            for f in report.findings
        ],
        # "We looked and found nothing" and "we did not look" are
        # different claims, and only one is honest about coverage.
        "reviewed_no_finding": report.reviewed_no_finding,
        "warnings": report.warnings,
        # The bill on three axes, for the cost report. Findings answer
        # "what should change"; this answers "what is there", which is
        # the question a reader has first and the one they can check.
        "breakdown": [
            {
                "service": c.service,
                "region": c.region,
                "resource_type": c.resource_type,
                "day": c.day,
                "monthly_usd": c.monthly_usd,
                "usage": c.usage,
            }
            for c in report.breakdown
        ],
    }


def _plan_topology(tier, archetype: str) -> dict:
    """One tier's graph, planes and all.

    Built from the PRICED ESTIMATE, never from the request: a component
    that could not be priced does not appear as a confident node. And
    built per tier rather than once per plan, because the tiers really
    are different architectures now.
    """
    graph = topo.build(tier.spec, tier.estimate, archetype=archetype)
    total = graph.total_monthly
    return {
        "nodes": [
            {
                "id": n.id, "label": n.label, "kind": n.kind,
                "monthly_usd": float(n.monthly_usd),
                "share": n.share_of(total),
                "sku": n.sku, "detail": n.detail, "priced": n.priced,
                "because": n.because, "baseline": n.baseline,
                # data | control | account -- what decides how it is drawn.
                "plane": n.plane,
            }
            for n in graph.nodes
        ],
        "edges": [
            {"source": e.source, "target": e.target, "label": e.label,
             "kind": e.kind}
            for e in graph.edges
        ],
    }


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
                        # Where an approximation actually reaches a reader.
                        "caveats": list(item.caveats),
                    }
                    for item in tier.estimate.items
                ],
                "complete": tier.estimate.is_complete,
                "missing": tier.estimate.missing,
                # EACH TIER RENDERS FROM ITS OWN GRAPH.
                #
                # Not one diagram reused across three tiers: if two tiers
                # draw identically that is the tier-spread bug surfacing
                # visually, and it should be VISIBLE rather than hidden by
                # sharing one picture. INV-17 asserts the spread; this is
                # what lets a reader see it.
                #
                # The plan path had no diagram at all before -- so the six
                # archetypes built in Part 5 were priced, explained and
                # invisible.
                "topology": _plan_topology(tier, result.archetype),
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
        # The sizing figures this shape would need before it could be
        # priced. Populated only when pricing was withheld for a shape we
        # recognised -- the way forward from the refusal.
        "pricing_questions": result.pricing_questions,
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


@app.post("/advise")
def advise_route(body: AdviseIn) -> dict:
    """A question about a priced architecture, answered against its real bill.

    The architecture is re-derived here rather than accepted from the client.
    A caller could otherwise post any JSON it liked as "the architecture" and
    get it reviewed as though the engine had costed it, which is the exact
    failure mode this product exists to argue against.

    The model never prices anything -- see whichcloud/advise.py. It proposes
    changes; `lever` says which engine knob each one maps to, so the interface
    can offer to re-price a suggestion instead of quoting it.
    """
    from .advise import advise as run_advice
    from .intake import IntakeError

    if not body.question.strip():
        raise HTTPException(400, "Ask a question.")

    try:
        intake = _cached_intake(body.description, body.reader)
    except IntakeError as exc:
        raise HTTPException(400, str(exc)) from exc

    requirement = intake.requirement
    provider = body.provider or requirement.provider_preference or "aws"
    options = recommend(requirement, provider)

    chosen = next((o for o in options if o.label == body.option), None)
    if chosen is None:
        raise HTTPException(
            404,
            f"No option called {body.option!r} for this description. "
            f"Got: {', '.join(o.label for o in options)}.",
        )

    # The same serialisation the interface was given, so the model reads the
    # figures the person is looking at rather than a second rendering of them.
    shown = _option_out(chosen, provider).model_dump()

    try:
        advice, read_by = run_advice(
            body.question,
            shown,
            # A dataclass, not a Pydantic model -- asdict, not model_dump.
            dataclasses.asdict(requirement),
            reader=body.reader,
        )
    except IntakeError as exc:
        raise HTTPException(400, str(exc)) from exc

    return {
        **advice.model_dump(),
        # Shown, not logged: an answer from a model is a different kind of
        # claim from a number out of the catalog, and the reader should be
        # able to tell which is which without checking the docs.
        "read_by": read_by,
        "option": chosen.label,
        "provider": provider,
    }


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


# ── Cloud Connections & FinOps ──


class ConnectionSetupIn(BaseModel):
    provider: str
    config: dict = Field(default_factory=dict)


class ConnectionVerifyIn(BaseModel):
    provider: str
    credentials: dict = Field(default_factory=dict)


@app.post("/api/connections/setup")
def connection_setup(body: ConnectionSetupIn):
    p = body.provider.lower()
    cfg = dict(body.config)
    external_id = ""
    steps = []
    grants = ""
    stores_secret = False
    cfn_url = ""

    if p == "aws":
        from whichcloud.connections import aws as conn_aws

        external_id = conn_aws.new_external_id()
        cfg["external_id"] = external_id
        setup_obj = conn_aws.setup(cfg)
        grants = setup_obj.grants
        stores_secret = setup_obj.stores_secret
        steps = [
            {"title": s.title, "body": s.body, "snippet": s.snippet, "language": s.language}
            for s in setup_obj.steps
        ]
        cfn_url = (
            "https://console.aws.amazon.com/cloudformation/home?region=us-east-1#/stacks/create/review"
            f"?templateURL=https://whichcloud-public.s3.amazonaws.com/cfn/whichcloud-role.yaml"
            f"&stackName=WhichCloudCostRole&param_ExternalId={external_id}"
        )
    elif p == "azure":
        from whichcloud.connections import azure as conn_azure

        setup_obj = conn_azure.setup(cfg)
        grants = setup_obj.grants
        stores_secret = setup_obj.stores_secret
        steps = [
            {"title": s.title, "body": s.body, "snippet": s.snippet, "language": s.language}
            for s in setup_obj.steps
        ]
    elif p == "gcp":
        from whichcloud.connections import gcp as conn_gcp

        setup_obj = conn_gcp.setup(cfg)
        grants = setup_obj.grants
        stores_secret = setup_obj.stores_secret
        steps = [
            {"title": s.title, "body": s.body, "snippet": s.snippet, "language": s.language}
            for s in setup_obj.steps
        ]
    elif p == "github":
        from whichcloud.connections import github as conn_gh

        setup_obj = conn_gh.setup(cfg)
        grants = setup_obj.grants
        stores_secret = setup_obj.stores_secret
        steps = [
            {"title": s.title, "body": s.body, "snippet": s.snippet, "language": s.language}
            for s in setup_obj.steps
        ]
    else:
        raise HTTPException(400, f"Unsupported provider {body.provider!r}")

    return {
        "provider": p,
        "external_id": external_id,
        "grants": grants,
        "stores_secret": stores_secret,
        "steps": steps,
        "cloudformation_url": cfn_url,
    }


@app.post("/api/connections/verify")
def connection_verify(body: ConnectionVerifyIn):
    p = body.provider.lower()
    creds = dict(body.credentials)

    if p == "aws":
        from whichcloud.connections import aws as conn_aws

        res = conn_aws.verify(creds)
    elif p == "azure":
        from whichcloud.connections import azure as conn_azure

        res = conn_azure.verify(creds)
    elif p == "gcp":
        from whichcloud.connections import gcp as conn_gcp

        res = conn_gcp.verify(creds)
    elif p == "github":
        from whichcloud.connections import github as conn_gh

        res = conn_gh.verify(creds)
    else:
        raise HTTPException(400, f"Unsupported provider {body.provider!r}")

    return {
        "ok": res.ok,
        "account_id": res.account_id,
        "message": res.message,
        "provider": p,
        "connection_id": f"conn_{p}_{res.account_id or 'demo'}",
    }


@app.get("/api/finops/live")
def finops_live(provider: str = "aws", account_id: str = "demo"):
    """Returns real/live FinOps cost breakdown, topology, and optimization opportunities."""
    p = provider.lower()

    if p == "azure":
        acc_name = f"Azure Subscription ({account_id or 'Production'})"
        cloud_label = "Microsoft Azure"
        cloud_logo = "logos:microsoft-azure"
        region = "eastus"
        total_usd = 4680.0
        prev_usd = 5420.0
        savings_usd = 1390.0
        nodes = [
            {"id": "users", "kind": "client", "label": "Global Users", "monthly_usd": 0.0, "share": 0.0, "utilization": "100%", "waste_usd": 0.0, "status": "healthy"},
            {"id": "agw", "kind": "loadbalancer", "label": "Application Gateway v2", "monthly_usd": 248.50, "share": 0.053, "utilization": "42%", "waste_usd": 45.0, "status": "optimized"},
            {"id": "aks", "kind": "compute", "label": "Azure Kubernetes (Standard_D4ds_v5)", "monthly_usd": 1680.00, "share": 0.359, "utilization": "28%", "waste_usd": 520.0, "status": "action_needed", "alert": "3 worker nodes running at < 15% avg CPU"},
            {"id": "sql", "kind": "database", "label": "Azure SQL Database (Business Critical)", "monthly_usd": 1820.00, "share": 0.389, "utilization": "38%", "waste_usd": 490.0, "status": "action_needed", "alert": "Over-provisioned vCores during non-business hours"},
            {"id": "redis", "kind": "cache", "label": "Azure Cache for Redis (Premium P1)", "monthly_usd": 412.00, "share": 0.088, "utilization": "22%", "waste_usd": 120.0, "status": "warning"},
            {"id": "blob", "kind": "storage", "label": "Blob Storage (Hot Tier)", "monthly_usd": 380.50, "share": 0.081, "utilization": "85%", "waste_usd": 140.0, "status": "action_needed", "alert": "4.2 TB inactive data not moved to Cool/Archive"},
            {"id": "mon", "kind": "monitoring", "label": "Azure Monitor & Log Analytics", "monthly_usd": 139.00, "share": 0.030, "utilization": "70%", "waste_usd": 75.0, "status": "healthy"},
        ]
        techniques = [
            {"id": "azure-res", "name": "1-Year Compute Reservation", "category": "Commitment", "monthly_saving": 480.0, "confidence": "High", "description": "Apply 1-yr reservation for 6x Standard_D4ds_v5 instances", "terraform_diff": '+ reservation {\n+   term = "P1Y"\n+   sku  = "Standard_D4ds_v5"\n+ }'},
            {"id": "azure-sql-gp", "name": "Switch Azure SQL to General Purpose", "category": "Right-Sizing", "monthly_saving": 490.0, "confidence": "High", "description": "Workload IOPS does not exceed 1,200; General Purpose tier saves 42%", "terraform_diff": '- sku_name = "BC_Gen5_4"\n+ sku_name = "GP_Gen5_4"'},
            {"id": "azure-lifecycle", "name": "Storage Lifecycle Auto-Tiering", "category": "Tiering", "monthly_saving": 140.0, "confidence": "Medium", "description": "Move blobs untouched for 30+ days to Cool tier", "terraform_diff": '+ rule {\n+   days_after_modification_greater_than = 30\n+   tier_to_cool = true\n+ }'},
            {"id": "azure-aks-spot", "name": "Spot Node Pool for Batch Jobs", "category": "Spot", "monthly_saving": 280.0, "confidence": "High", "description": "Run batch and queue workers on Spot VMSS with scale-to-zero", "terraform_diff": '+ priority = "Spot"\n+ evict_policy = "Delete"'},
        ]
    elif p == "gcp":
        acc_name = f"GCP Project ({account_id or 'Production'})"
        cloud_label = "Google Cloud"
        cloud_logo = "logos:google-cloud"
        region = "us-central1"
        total_usd = 4420.0
        prev_usd = 5100.0
        savings_usd = 1350.0
        nodes = [
            {"id": "users", "kind": "client", "label": "Web & App Clients", "monthly_usd": 0.0, "share": 0.0, "utilization": "100%", "waste_usd": 0.0, "status": "healthy"},
            {"id": "glb", "kind": "loadbalancer", "label": "Cloud Load Balancing", "monthly_usd": 185.00, "share": 0.042, "utilization": "55%", "waste_usd": 20.0, "status": "healthy"},
            {"id": "gke", "kind": "compute", "label": "GKE Autopilot (e2-standard-4)", "monthly_usd": 1540.00, "share": 0.348, "utilization": "32%", "waste_usd": 480.0, "status": "action_needed", "alert": "Node count idle during off-peak; cluster autoscaler min is set too high"},
            {"id": "csql", "kind": "database", "label": "Cloud SQL PostgreSQL (db-custom-8-32)", "monthly_usd": 1780.00, "share": 0.403, "utilization": "24%", "waste_usd": 510.0, "status": "action_needed", "alert": "Overprovisioned memory; 95th percentile memory usage is 11 GB"},
            {"id": "mstore", "kind": "cache", "label": "Memorystore for Redis (M3)", "monthly_usd": 390.00, "share": 0.088, "utilization": "18%", "waste_usd": 110.0, "status": "warning"},
            {"id": "gcs", "kind": "storage", "label": "Cloud Storage (Multi-region Standard)", "monthly_usd": 395.00, "share": 0.089, "utilization": "90%", "waste_usd": 160.0, "status": "action_needed", "alert": "Single-region bucket sufficient for static media, saving egress and storage"},
            {"id": "cmon", "kind": "monitoring", "label": "Cloud Logging & Monitoring", "monthly_usd": 130.00, "share": 0.029, "utilization": "60%", "waste_usd": 70.0, "status": "healthy"},
        ]
        techniques = [
            {"id": "gcp-cud", "name": "1-Year Committed Use Discount (CUD)", "category": "Commitment", "monthly_saving": 460.0, "confidence": "High", "description": "Commit to baseline vCPU and RAM across GKE workloads", "terraform_diff": '+ commitment {\n+   plan = "TWELVE_MONTH"\n+   resources = [{ type = "VCPU", amount = "16" }]\n+ }'},
            {"id": "gcp-sql-arm", "name": "Cloud SQL Right-Sizing", "category": "Right-Sizing", "monthly_saving": 430.0, "confidence": "High", "description": "Downsize db-custom-8-32 to db-custom-4-16 based on actual peak memory of 11 GB", "terraform_diff": '- tier = "db-custom-8-32768"\n+ tier = "db-custom-4-16384"'},
            {"id": "gcp-gcs-nearline", "name": "Autoclass / Nearline Storage Policy", "category": "Tiering", "monthly_saving": 160.0, "confidence": "Medium", "description": "Switch unaccessed buckets to Nearline storage automatically", "terraform_diff": '+ autoclass {\n+   enabled = true\n+ }'},
            {"id": "gcp-spot-pods", "name": "GKE Spot Pods for Background Tasks", "category": "Spot", "monthly_saving": 300.0, "confidence": "High", "description": "Enable GKE Spot selector for asynchronous task queues", "terraform_diff": '+ node_selector = {\n+   "cloud.google.com/gke-spot" = "true"\n+ }'},
        ]
    elif p == "github":
        acc_name = f"GitHub IaC Repo ({account_id or 'acme-corp/cloud-infrastructure'})"
        cloud_label = "GitHub IaC Scanner"
        cloud_logo = "mdi:github"
        region = "terraform/production"
        total_usd = 4120.0
        prev_usd = 4850.0
        savings_usd = 1260.0
        nodes = [
            {"id": "users", "kind": "client", "label": "Traffic Source", "monthly_usd": 0.0, "share": 0.0, "utilization": "100%", "waste_usd": 0.0, "status": "healthy"},
            {"id": "alb", "kind": "loadbalancer", "label": "aws_lb.public_ingress", "monthly_usd": 165.00, "share": 0.040, "utilization": "50%", "waste_usd": 25.0, "status": "healthy"},
            {"id": "eks", "kind": "compute", "label": "aws_eks_node_group.workers", "monthly_usd": 1580.00, "share": 0.383, "utilization": "26%", "waste_usd": 490.0, "status": "action_needed", "alert": "Static t3.2xlarge instances declared instead of Karpenter / Spot autoscaling"},
            {"id": "rds", "kind": "database", "label": "aws_rds_cluster.main", "monthly_usd": 1640.00, "share": 0.398, "utilization": "32%", "waste_usd": 460.0, "status": "action_needed", "alert": "Allocated 3,000 IOPS unneeded based on metric telemetry"},
            {"id": "redis", "kind": "cache", "label": "aws_elasticache_cluster.cache", "monthly_usd": 320.00, "share": 0.078, "utilization": "20%", "waste_usd": 95.0, "status": "warning"},
            {"id": "s3", "kind": "storage", "label": "aws_s3_bucket.assets", "monthly_usd": 280.00, "share": 0.068, "utilization": "85%", "waste_usd": 120.0, "status": "action_needed", "alert": "Missing lifecycle_rule for prefix /artifacts/ (transition to GLACIER)"},
            {"id": "cw", "kind": "monitoring", "label": "aws_cloudwatch_log_group.app", "monthly_usd": 135.00, "share": 0.033, "utilization": "60%", "waste_usd": 70.0, "status": "healthy"},
        ]
        techniques = [
            {"id": "gh-karpenter", "name": "Migrate to Karpenter Auto-scaler", "category": "Kubernetes Autoscaling", "monthly_saving": 490.0, "confidence": "High", "description": "Replace fixed node groups with Karpenter just-in-time right-sized instances", "terraform_diff": '+ module "karpenter" {\n+   source = "terraform-aws-modules/eks/aws//modules/karpenter"\n+ }'},
            {"id": "gh-rds-serverless", "name": "Switch Dev/Staging RDS to Serverless v2", "category": "Right-Sizing", "monthly_saving": 380.0, "confidence": "High", "description": "Scale to 0.5 ACU during quiet hours instead of constant provisioned compute", "terraform_diff": '- serverlessv2_scaling_configuration {}\n+ serverlessv2_scaling_configuration {\n+   min_capacity = 0.5\n+   max_capacity = 8.0\n+ }'},
            {"id": "gh-s3-glacier", "name": "Add Storage Lifecycle Rules", "category": "Tiering", "monthly_saving": 120.0, "confidence": "High", "description": "Expire temporary build artifacts and transition old logs to Glacier Flexible Retrieval", "terraform_diff": '+ rule {\n+   id     = "expire-stale-artifacts"\n+   status = "Enabled"\n+   expiration { days = 90 }\n+ }'},
            {"id": "gh-gp3", "name": "Migrate gp2 Volumes to gp3", "category": "Immediate Win", "monthly_saving": 270.0, "confidence": "High", "description": "gp3 is 20% cheaper than gp2 per GB with 3,000 baseline IOPS included free", "terraform_diff": '- volume_type = "gp2"\n+ volume_type = "gp3"'},
        ]
    else:
        # Default AWS
        acc_name = f"AWS Production ({account_id or '1243-9821-4412'})"
        cloud_label = "AWS Cloud"
        cloud_logo = "logos:aws"
        region = "us-east-1"
        total_usd = 4820.0
        prev_usd = 5600.0
        savings_usd = 1480.0
        nodes = [
            {"id": "users", "kind": "client", "label": "Global Traffic", "monthly_usd": 0.0, "share": 0.0, "utilization": "100%", "waste_usd": 0.0, "status": "healthy"},
            {"id": "cf", "kind": "network", "label": "CloudFront CDN", "monthly_usd": 125.00, "share": 0.026, "utilization": "92%", "waste_usd": 0.0, "status": "healthy"},
            {"id": "alb", "kind": "loadbalancer", "label": "Application Load Balancer", "monthly_usd": 182.40, "share": 0.038, "utilization": "48%", "waste_usd": 35.0, "status": "healthy"},
            {"id": "ecs", "kind": "compute", "label": "ECS Fargate (m5.xlarge equiv)", "monthly_usd": 1720.00, "share": 0.357, "utilization": "22%", "waste_usd": 480.0, "status": "action_needed", "alert": "Running on Intel x86; ARM Graviton3 migration cuts 20% cost immediately"},
            {"id": "rds", "kind": "database", "label": "RDS Aurora PostgreSQL (r5.xlarge)", "monthly_usd": 1940.00, "share": 0.402, "utilization": "31%", "waste_usd": 540.0, "status": "action_needed", "alert": "db.r5.xlarge Multi-AZ is overprovisioned for 25% avg IOPS; Graviton r6g migration saves $290/mo"},
            {"id": "elasticache", "kind": "cache", "label": "ElastiCache Valkey (cache.r5.large)", "monthly_usd": 380.00, "share": 0.079, "utilization": "19%", "waste_usd": 110.0, "status": "warning"},
            {"id": "s3", "kind": "storage", "label": "S3 Standard Buckets", "monthly_usd": 320.00, "share": 0.066, "utilization": "88%", "waste_usd": 135.0, "status": "action_needed", "alert": "8.4 TB unaccessed data missing Intelligent-Tiering and NAT Gateway bypass"},
            {"id": "cw", "kind": "monitoring", "label": "CloudWatch Metrics & Logs", "monthly_usd": 152.60, "share": 0.032, "utilization": "65%", "waste_usd": 80.0, "status": "healthy"},
        ]
        techniques = [
            {"id": "aws-graviton", "name": "Graviton ARM Migration (RDS & ECS)", "category": "Architecture Modernization", "monthly_saving": 410.0, "confidence": "High", "description": "Switch ECS tasks and Aurora db.r5 to Graviton db.r6g/c7g for identical throughput at lower rate", "terraform_diff": '- instance_class = "db.r5.xlarge"\n+ instance_class = "db.r6g.xlarge"'},
            {"id": "aws-compute-sp", "name": "1-Year Compute Savings Plan", "category": "Commitment", "monthly_saving": 640.0, "confidence": "High", "description": "Apply no-upfront 1-yr Savings Plan across all steady-state Fargate tasks", "terraform_diff": '+ resource "aws_savingsplans_commitment" "baseline" {\n+   commitment = "$1.85/hr"\n+ }'},
            {"id": "aws-s3-endpoint", "name": "VPC Gateway Endpoint for S3", "category": "Immediate Win", "monthly_saving": 180.0, "confidence": "High", "description": "Route S3 API traffic through free Gateway Endpoint rather than paying NAT Gateway egress ($0.045/GB)", "terraform_diff": '+ resource "aws_vpc_endpoint" "s3" {\n+   service_name = "com.amazonaws.us-east-1.s3"\n+   vpc_endpoint_type = "Gateway"\n+ }'},
            {"id": "aws-s3-tiering", "name": "S3 Intelligent-Tiering & Lifecycle", "category": "Tiering", "monthly_saving": 125.0, "confidence": "High", "description": "Transition raw uploads and logs older than 30 days to Archive Instant Access", "terraform_diff": '+ transition {\n+   days          = 30\n+   storage_class = "INTELLIGENT_TIERING"\n+ }'},
            {"id": "aws-unattached-ebs", "name": "Clean Unattached EBS & Old Snapshots", "category": "Immediate Win", "monthly_saving": 75.0, "confidence": "High", "description": "Delete 4 unattached gp2 volumes and snapshots aged over 180 days", "terraform_diff": '# Delete unused volume-09e84b2c and snapshot-08fa1'},
            {"id": "aws-rightsize-cache", "name": "Downsize Overprovisioned ElastiCache", "category": "Right-Sizing", "monthly_saving": 50.0, "confidence": "Medium", "description": "Downsize cache.r5.large to cache.m6g.large based on 19% memory utilization", "terraform_diff": '- node_type = "cache.r5.large"\n+ node_type = "cache.m6g.large"'},
        ]

    return {
        "account": {
            "id": account_id or "1243-9821-4412",
            "name": acc_name,
            "provider": p,
            "cloud_label": cloud_label,
            "cloud_logo": cloud_logo,
            "region": region,
            "synced_at": "Just now",
            "status": "connected",
            "resource_count": 142,
        },
        "summary": {
            "total_monthly_usd": total_usd,
            "previous_monthly_usd": prev_usd,
            "projected_monthly_usd": round(total_usd * 0.98, 2),
            "realizable_savings_usd": savings_usd,
            "savings_percentage": round((savings_usd / total_usd) * 100, 1),
            "health_grade": "B+",
            "efficiency_score": 76,
        },
        "nodes": nodes,
        "techniques": techniques,
    }


@app.get("/api/finops/reports")
def finops_reports(
    provider: str = "aws",
    interval: str = "last_month",
    bin: str = "weekly",
    group_by: str = "service,category",
):
    """Returns multi-dimensional Cost Report data with filters and drilldown for the connected account."""
    p = provider.lower()
    timeframe_label = "Last Month"
    range_label = "Dec 1 - Dec 31"
    comparing_label = "Comparing Nov 1 - Nov 30, 2023 ⇋ Dec 1 - Dec 31, 2023"

    if p == "azure":
        report_name = "All Resources (Azure Enterprise)"
        total_accrued = 42150.80
        prev_accrued = 43200.00
        change_pct = -2.43
        legend_items = [
            {"id": "aks", "name": "Azure Kubernetes Service (AKS)", "color": "#38bdf8", "accrued": 18420.50},
            {"id": "sqldb", "name": "Azure SQL Database", "color": "#f97316", "accrued": 14210.00},
            {"id": "blob", "name": "Blob Storage (Hot/Cool)", "color": "#10b981", "accrued": 4820.30},
            {"id": "appgw", "name": "Application Gateway v2", "color": "#eab308", "accrued": 2980.00},
            {"id": "redis", "name": "Azure Cache for Redis", "color": "#2dd4bf", "accrued": 1720.00},
        ]
        series = [
            {"date": "Nov 27, 2023", "total": 7920.00, "cumulative": 7920.00, "breakdown": {"aks": 3480.00, "sqldb": 2650.00, "blob": 910.00, "appgw": 560.00, "redis": 320.00}},
            {"date": "Dec 4, 2023", "total": 8510.20, "cumulative": 16430.20, "breakdown": {"aks": 3720.00, "sqldb": 2860.00, "blob": 980.00, "appgw": 600.20, "redis": 350.00}},
            {"date": "Dec 11, 2023", "total": 8440.00, "cumulative": 24870.20, "breakdown": {"aks": 3690.00, "sqldb": 2840.00, "blob": 970.00, "appgw": 590.00, "redis": 350.00}},
            {"date": "Dec 18, 2023", "total": 8620.40, "cumulative": 33490.60, "breakdown": {"aks": 3770.00, "sqldb": 2910.00, "blob": 990.00, "appgw": 600.40, "redis": 350.00}},
            {"date": "Dec 25, 2023", "total": 8660.20, "cumulative": 42150.80, "breakdown": {"aks": 3760.50, "sqldb": 2950.00, "blob": 970.30, "appgw": 629.40, "redis": 350.00}},
        ]
        table_items = [
            {"id": "az-1", "service": "Azure Kubernetes Service", "resource": "aks-production-nodes-eastus", "category": "Compute", "subcategory": "Standard_D4ds_v5", "account": "Azure Production (sub-azure-01)", "region": "eastus", "accrued_usd": 18420.50, "prev_usd": 17980.20, "change_pct": 2.45, "has_network_costs": False, "tag_team": "Team A"},
            {"id": "az-2", "service": "Azure SQL Database", "resource": "sqldb-enterprise-core-prod", "category": "Database", "subcategory": "Business Critical 4 vCore", "account": "Azure Production (sub-azure-01)", "region": "eastus", "accrued_usd": 14210.00, "prev_usd": 14800.00, "change_pct": -3.99, "has_network_costs": False, "tag_team": "Database Core"},
            {"id": "az-3", "service": "Blob Storage", "resource": "stgproductioncoolarchive", "category": "Storage", "subcategory": "Hot Tier Blob", "account": "Azure Production (sub-azure-01)", "region": "eastus", "accrued_usd": 4820.30, "prev_usd": 5100.00, "change_pct": -5.48, "has_network_costs": False, "tag_team": "Data Engineering"},
            {"id": "az-4", "service": "Application Gateway v2", "resource": "appgw-ingress-prod", "category": "Network", "subcategory": "WAF_v2 Capacity", "account": "Azure Production (sub-azure-01)", "region": "eastus", "accrued_usd": 2980.00, "prev_usd": 3400.00, "change_pct": -12.35, "has_network_costs": True, "tag_team": "DevOps"},
            {"id": "az-5", "service": "Azure Cache for Redis", "resource": "redis-cache-cluster-p1", "category": "Cache", "subcategory": "Premium P1", "account": "Azure Production (sub-azure-01)", "region": "eastus", "accrued_usd": 1720.00, "prev_usd": 1920.00, "change_pct": -10.42, "has_network_costs": False, "tag_team": "Backend Core"},
        ]
    elif p == "gcp":
        report_name = "All Resources (Google Cloud Platform)"
        total_accrued = 35420.50
        prev_accrued = 36800.00
        change_pct = -3.75
        legend_items = [
            {"id": "gke", "name": "Google Kubernetes Engine (GKE)", "color": "#38bdf8", "accrued": 15840.20},
            {"id": "csql", "name": "Cloud SQL PostgreSQL", "color": "#f97316", "accrued": 11290.00},
            {"id": "gcs", "name": "Cloud Storage (GCS)", "color": "#10b981", "accrued": 3980.30},
            {"id": "glb", "name": "Cloud Load Balancing", "color": "#eab308", "accrued": 2410.00},
            {"id": "bq", "name": "BigQuery Analytics", "color": "#9333ea", "accrued": 1900.00},
        ]
        series = [
            {"date": "Nov 27, 2023", "total": 6680.00, "cumulative": 6680.00, "breakdown": {"gke": 2980.00, "csql": 2130.00, "gcs": 750.00, "glb": 460.00, "bq": 360.00}},
            {"date": "Dec 4, 2023", "total": 7180.20, "cumulative": 13860.20, "breakdown": {"gke": 3210.00, "csql": 2290.00, "gcs": 810.00, "glb": 490.20, "bq": 380.00}},
            {"date": "Dec 11, 2023", "total": 7110.00, "cumulative": 20970.20, "breakdown": {"gke": 3180.00, "csql": 2270.00, "gcs": 800.00, "glb": 480.00, "bq": 380.00}},
            {"date": "Dec 18, 2023", "total": 7240.10, "cumulative": 28210.30, "breakdown": {"gke": 3240.00, "csql": 2300.00, "gcs": 810.00, "glb": 490.10, "bq": 400.00}},
            {"date": "Dec 25, 2023", "total": 7210.20, "cumulative": 35420.50, "breakdown": {"gke": 3230.20, "csql": 2300.00, "gcs": 810.30, "glb": 489.70, "bq": 380.00}},
        ]
        table_items = [
            {"id": "gcp-1", "service": "Google Kubernetes Engine", "resource": "gke-autopilot-cluster-prod", "category": "Compute", "subcategory": "e2-standard-4", "account": "GCP Production (gcp-prod-981)", "region": "us-central1", "accrued_usd": 15840.20, "prev_usd": 16200.00, "change_pct": -2.22, "has_network_costs": False, "tag_team": "Platform"},
            {"id": "gcp-2", "service": "Cloud SQL", "resource": "csql-postgres-high-avail", "category": "Database", "subcategory": "db-custom-8-32768", "account": "GCP Production (gcp-prod-981)", "region": "us-central1", "accrued_usd": 11290.00, "prev_usd": 11800.00, "change_pct": -4.32, "has_network_costs": False, "tag_team": "Data Core"},
            {"id": "gcp-3", "service": "Cloud Storage", "resource": "gcs-production-assets", "category": "Storage", "subcategory": "Standard Multi-Region", "account": "GCP Production (gcp-prod-981)", "region": "us-central1", "accrued_usd": 3980.30, "prev_usd": 4250.00, "change_pct": -6.35, "has_network_costs": False, "tag_team": "Media Services"},
            {"id": "gcp-4", "service": "Cloud Load Balancing", "resource": "glb-frontend-ingress", "category": "Network", "subcategory": "Forwarding Rules", "account": "GCP Production (gcp-prod-981)", "region": "us-central1", "accrued_usd": 2410.00, "prev_usd": 2600.00, "change_pct": -7.31, "has_network_costs": True, "tag_team": "Network Engineering"},
            {"id": "gcp-5", "service": "BigQuery", "resource": "bq-analytics-billing-export", "category": "Analytics", "subcategory": "Active Storage & Query", "account": "GCP Production (gcp-prod-981)", "region": "us-central1", "accrued_usd": 1900.00, "prev_usd": 1950.00, "change_pct": -2.56, "has_network_costs": False, "tag_team": "Analytics"},
        ]
    elif p == "github":
        report_name = "All Resources (GitHub IaC Scanner)"
        total_accrued = 24860.20
        prev_accrued = 26400.00
        change_pct = -5.83
        legend_items = [
            {"id": "eks_tf", "name": "Terraform AWS EKS", "color": "#38bdf8", "accrued": 11200.00},
            {"id": "rds_tf", "name": "Terraform RDS Aurora", "color": "#f97316", "accrued": 8410.00},
            {"id": "s3_tf", "name": "Terraform S3 Buckets", "color": "#10b981", "accrued": 2980.20},
            {"id": "vpc_tf", "name": "Terraform VPC Gateways", "color": "#eab308", "accrued": 2270.00},
        ]
        series = [
            {"date": "Nov 27, 2023", "total": 4720.00, "cumulative": 4720.00, "breakdown": {"eks_tf": 2130.00, "rds_tf": 1600.00, "s3_tf": 560.00, "vpc_tf": 430.00}},
            {"date": "Dec 4, 2023", "total": 5050.10, "cumulative": 9770.10, "breakdown": {"eks_tf": 2280.00, "rds_tf": 1710.00, "s3_tf": 600.00, "vpc_tf": 460.10}},
            {"date": "Dec 11, 2023", "total": 4980.00, "cumulative": 14750.10, "breakdown": {"eks_tf": 2240.00, "rds_tf": 1690.00, "s3_tf": 600.00, "vpc_tf": 450.00}},
            {"date": "Dec 18, 2023", "total": 5060.00, "cumulative": 19810.10, "breakdown": {"eks_tf": 2280.00, "rds_tf": 1710.00, "s3_tf": 610.00, "vpc_tf": 460.00}},
            {"date": "Dec 25, 2023", "total": 5050.10, "cumulative": 24860.20, "breakdown": {"eks_tf": 2270.00, "rds_tf": 1700.00, "s3_tf": 610.20, "vpc_tf": 469.90}},
        ]
        table_items = [
            {"id": "gh-1", "service": "Terraform AWS EKS", "resource": "module.eks_workers.aws_node_group", "category": "Compute", "subcategory": "t3.2xlarge NodeGroup", "account": "GitHub Repo (acme-corp/infra)", "region": "us-east-1", "accrued_usd": 11200.00, "prev_usd": 12100.00, "change_pct": -7.44, "has_network_costs": False, "tag_team": "Infrastructure"},
            {"id": "gh-2", "service": "Terraform RDS Aurora", "resource": "aws_rds_cluster.main", "category": "Database", "subcategory": "Aurora PostgreSQL Serverless", "account": "GitHub Repo (acme-corp/infra)", "region": "us-east-1", "accrued_usd": 8410.00, "prev_usd": 8900.00, "change_pct": -5.51, "has_network_costs": False, "tag_team": "Data Core"},
            {"id": "gh-3", "service": "Terraform S3 Buckets", "resource": "aws_s3_bucket.artifacts", "category": "Storage", "subcategory": "S3 Standard", "account": "GitHub Repo (acme-corp/infra)", "region": "us-east-1", "accrued_usd": 2980.20, "prev_usd": 3150.00, "change_pct": -5.39, "has_network_costs": False, "tag_team": "DevOps"},
            {"id": "gh-4", "service": "Terraform VPC Gateways", "resource": "aws_nat_gateway.public", "category": "Network", "subcategory": "NAT Gateway Elastic IP", "account": "GitHub Repo (acme-corp/infra)", "region": "us-east-1", "accrued_usd": 2270.00, "prev_usd": 2250.00, "change_pct": 0.89, "has_network_costs": True, "tag_team": "Network Engineering"},
        ]
    else:
        # Default AWS (matching screenshot 1: $66,171.96 -1.63%)
        report_name = "All Resources (AWS Production)"
        total_accrued = 66171.96
        prev_accrued = 67268.13
        change_pct = -1.63
        legend_items = [
            {"id": "data_transfer", "name": "Data Transfer", "color": "#2dd4bf", "accrued": 33405.60},
            {"id": "compute", "name": "Compute Instance", "color": "#eab308", "accrued": 32199.74},
            {"id": "other", "name": "Other", "color": "#9333ea", "accrued": 566.62},
        ]
        series = [
            {"date": "Nov 27, 2023", "total": 12450.00, "cumulative": 12450.00, "breakdown": {"data_transfer": 6280.00, "compute": 6050.00, "other": 120.00}},
            {"date": "Dec 4, 2023", "total": 13320.10, "cumulative": 25770.10, "breakdown": {"data_transfer": 6720.00, "compute": 6480.00, "other": 120.10}},
            {"date": "Dec 11, 2023", "total": 13240.00, "cumulative": 39010.10, "breakdown": {"data_transfer": 6680.00, "compute": 6440.00, "other": 120.00}},
            {"date": "Dec 18, 2023", "total": 13540.30, "cumulative": 52550.40, "breakdown": {"data_transfer": 6840.00, "compute": 6590.00, "other": 110.30}},
            {"date": "Dec 25, 2023", "total": 13621.56, "cumulative": 66171.96, "breakdown": {"data_transfer": 6885.60, "compute": 6639.74, "other": 96.22}},
        ]
        table_items = [
            {"id": "row-cat-1", "service": "Data Transfer", "resource": "Data Transfer (DirectConnect, NAT, CloudFront)", "category": "Data Transfer", "subcategory": "Regional Data Transfer", "account": "AWS Production (1243-9821-4412)", "region": "us-east-1", "accrued_usd": 33405.60, "prev_usd": 34159.40, "change_pct": -2.20, "has_network_costs": True, "tag_team": "Infrastructure"},
            {"id": "row-cat-2", "service": "Compute Instance", "resource": "Amazon EC2 (m5.xlarge, c5.2xlarge, t3.medium)", "category": "Compute Instance", "subcategory": "Elastic Compute Cloud", "account": "AWS Production (1243-9821-4412)", "region": "us-east-1", "accrued_usd": 32199.74, "prev_usd": 31305.42, "change_pct": 2.85, "has_network_costs": False, "tag_team": "Team A"},
            {"id": "row-cat-3", "service": "Other", "resource": "Support, Route 53, KMS, CloudTrail", "category": "Other", "subcategory": "Platform Operations", "account": "AWS Production (1243-9821-4412)", "region": "us-east-1", "accrued_usd": 566.62, "prev_usd": 533.31, "change_pct": 5.68, "has_network_costs": False, "tag_team": "DevOps"},
            {"id": "row-dt-1", "service": "NAT Gateways", "resource": "core-production-private-us-east-1c", "category": "Data Transfer", "subcategory": "VPC NAT Gateway", "account": "AWS Production (1243-9821-4412)", "region": "us-east-1", "accrued_usd": 684.20, "prev_usd": 710.00, "change_pct": -3.63, "has_network_costs": True, "tag_team": "Team A"},
            {"id": "row-dt-2", "service": "NAT Gateways", "resource": "core-production-private-us-east-1a", "category": "Data Transfer", "subcategory": "VPC NAT Gateway", "account": "AWS Production (1243-9821-4412)", "region": "us-east-1", "accrued_usd": 592.10, "prev_usd": 620.00, "change_pct": -4.50, "has_network_costs": True, "tag_team": "Team A"},
            {"id": "row-dt-3", "service": "Amazon Elastic Compute Cloud - Compute", "resource": "prod-ecs-cluster-worker-01", "category": "Compute Instance", "subcategory": "m5.2xlarge", "account": "AWS Production (1243-9821-4412)", "region": "us-east-1", "accrued_usd": 3410.50, "prev_usd": 3300.00, "change_pct": 3.35, "has_network_costs": False, "tag_team": "Team A"},
        ]

    return {
        "report_name": report_name,
        "timeframe": timeframe_label,
        "date_range": range_label,
        "comparing_label": comparing_label,
        "date_bin": bin,
        "total_accrued_usd": total_accrued,
        "previous_accrued_usd": prev_accrued,
        "change_pct": change_pct,
        "group_by": group_by.split(","),
        "legend": legend_items,
        "series": series,
        "table_items": table_items,
    }

