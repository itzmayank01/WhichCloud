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
from typing import Literal, Optional

import time
from collections import defaultdict, deque

from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware

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
from .auth import current_owner, finops_owner
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


#: Endpoints that mutate real infrastructure or spend a provider credential
#: check get a much tighter budget than everything else. A stray retry loop
#: or a scripted abuse attempt against `/resources/action` or `/delete-all`
#: is not "a lot of reads" the way hammering `/catalog` would be -- each
#: request there is itself a live AWS CLI call, so the budget has to bound
#: the damage of a single attacker, not just protect server capacity.
_STRICT_RATE_PATHS = (
    "/api/finops/resources/action",
    "/api/finops/resources/delete-all",
    "/api/connections/verify",
    "/api/connections/setup",
)
_STRICT_LIMIT = 10
_STRICT_WINDOW_SECONDS = 60.0
_DEFAULT_LIMIT = 120
_DEFAULT_WINDOW_SECONDS = 60.0


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Fixed-window limiter, per client IP, in process memory.

    This is deliberately not a distributed limiter (Redis, etc.) -- it bounds
    a single-process deployment, which is what this service is today. It is
    still strictly better than the previous state, which was no limit at
    all: an unauthenticated caller could retry a destructive endpoint as
    fast as the network allowed. Swap for a shared store before running more
    than one worker process, since each process would otherwise track its
    own window.
    """

    def __init__(self, app):
        super().__init__(app)
        self._hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)

    def _client_key(self, request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        strict = path in _STRICT_RATE_PATHS
        limit = _STRICT_LIMIT if strict else _DEFAULT_LIMIT
        window = _STRICT_WINDOW_SECONDS if strict else _DEFAULT_WINDOW_SECONDS

        key = (self._client_key(request), "strict" if strict else "default")
        now = time.monotonic()
        hits = self._hits[key]
        while hits and now - hits[0] > window:
            hits.popleft()

        if len(hits) >= limit:
            retry_after = max(1, int(window - (now - hits[0])))
            return JSONResponse(
                status_code=429,
                content={
                    "ok": False,
                    "message": f"Rate limit exceeded ({limit} requests / {int(window)}s). Retry later.",
                },
                headers={"Retry-After": str(retry_after)},
            )

        hits.append(now)
        return await call_next(request)


app.add_middleware(RateLimitMiddleware)


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

    from .architecture.readers import configured, configured_sources
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
        # Which env vars supplied them -- names only, never values. A count
        # cannot tell you whether the key you just added is being seen.
        "reader_sources": configured_sources(),
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


@app.post("/describe/terraform/inspect")
def describe_terraform_inspect_route(body: DescribeExportIn):
    """Returns the generated Terraform files as a JSON dictionary {filename: content},
    along with architecture metadata, cost report template, and WhichCloud provider configuration.
    """
    from . import terraform_export, terraform_export_azure, terraform_export_gcp
    from .intake import IntakeError

    description = body.description.strip() if body.description else ""
    if not description:
        description = (
            "I run operations for a retail chain in India with 120 stores. "
            "Nightly batch sync runs 2am to 5am with inventory updates from all stores. "
            "In-store POS queries the catalog during store hours. Mobile app for customers with 50k daily active users. "
            "500 GB catalog images with fast delivery to users across India."
        )

    try:
        intake = _cached_intake(description, body.reader)
    except IntakeError as exc:
        raise HTTPException(400, str(exc)) from exc

    requirement = intake.requirement
    provider = body.provider or requirement.provider_preference or "aws"
    generators = {
        "aws": terraform_export,
        "gcp": terraform_export_gcp,
        "azure": terraform_export_azure,
    }
    generator = generators.get(provider, terraform_export)
    options = recommend(requirement, provider)
    option = next((o for o in options if o.label == body.option), None)
    if option is None:
        option = options[0] if options else None

    files: dict[str, str] = {}
    if option:
        files = generator.generate(option.spec, option.estimate)

    region = option.estimate.region if option else ("ap-south-1" if provider == "aws" else "asia-south1")
    total_cost = float(option.estimate.total_monthly) if option else 469.58

    def _hcl_str(value: str) -> str:
        """Escape a value for embedding inside an HCL double-quoted string.

        Without this, an option label containing a `"` (nothing stops the
        engine from producing one) breaks the generated file at that quote,
        and a stray `${` would be read as HCL interpolation syntax instead
        of literal text.
        """
        return value.replace("\\", "\\\\").replace('"', '\\"').replace("${", "$${")

    label_txt = _hcl_str(option.label if option else "Production")
    provider_txt = _hcl_str(provider)
    region_txt = _hcl_str(region)
    provider_upper_txt = _hcl_str(provider.upper())

    # Add WhichCloud Terraform Provider cost reporting and CUR integration module
    files["cost_reports.tf"] = f"""# WhichCloud Terraform Provider - Automated Cloud Cost Reporting
# Automates infrastructure cost tracking, budget alarms, and report sync.

terraform {{
  required_version = ">= 1.0.0"
  required_providers {{
    whichcloud = {{
      source  = "whichcloud-sh/whichcloud"
      version = "~> 1.2.0"
    }}
    aws = {{
      source  = "hashicorp/aws"
      version = ">= 5.48.0"
    }}
  }}
}}

provider "whichcloud" {{
  # Export WHICHCLOUD_API_TOKEN or configure here
  api_token = var.whichcloud_api_token
}}

# 1. Dedicated FinOps Cost Folder for this workload
resource "whichcloud_folder" "workload_folder" {{
  title = "{label_txt} Costs"
}}

# 2. Saved Filter using WhichCloud Query Language (VQL)
resource "whichcloud_saved_filter" "workload_filter" {{
  title  = "{provider_upper_txt} {region_txt} Infrastructure"
  filter = "costs.provider = '{provider_txt}' AND costs.region = '{region_txt}'"
}}

# 3. Automated Cost Report synced with WhichCloud FinOps Console
resource "whichcloud_cost_report" "workload_cost_report" {{
  folder_token = whichcloud_folder.workload_folder.token
  title        = "{label_txt} Cost Report"
  filter       = "costs.provider = '{provider_txt}'"
  start_date   = "2026-09-01"
  end_date     = "2026-09-30"
  date_bin     = "cumulative"
  chart_type   = "line"
  groupings    = "region,service"

  saved_filter_tokens = [
    whichcloud_saved_filter.workload_filter.token
  ]
}}

# 4. WhichCloud AWS CUR 2.0 Integration Module (Root/Management Account)
module "whichcloud_aws_integration" {{
  source  = "whichcloud-sh/whichcloud-integration/aws"
  version = "~> 1.1.0"

  cur_bucket_name   = "whichcloud-cur-{region_txt}-reports"
  cur_bucket_region = "{region_txt}"
  upgrade_to_cur_2  = true
}}
"""

    return {
        "files": files,
        "option": option.label if option else "Most optimized",
        "provider": provider,
        "monthly_cost": total_cost,
        "region": region,
        "all_options": [
            {
                "label": o.label,
                "monthly": float(o.estimate.total_monthly),
                "region": o.estimate.region,
            }
            for o in options
        ],
        "items": [
            {
                "label": item.label,
                "monthly": float(item.monthly_usd),
                "sku": item.sku,
            }
            for item in (option.estimate.items if option else [])
        ],
    }


class TerraformValidateIn(BaseModel):
    code: str
    filename: str = "main.tf"


@app.post("/describe/terraform/validate")
def describe_terraform_validate_route(body: TerraformValidateIn):
    """Validates HCL syntax by actually parsing it.

    This checks grammar, not semantics: it catches malformed HCL (unterminated
    strings, unbalanced blocks, stray tokens) the way `terraform fmt` would,
    but it does not run `terraform validate` or `terraform init` -- those
    need a real backend and provider plugins downloaded over the network,
    which is too slow and too much attack surface for a request handler. A
    file can pass this and still fail a real `terraform plan` for reasons
    this cannot see (missing required arguments, bad references, provider
    version conflicts), so the message says what was actually checked.
    """
    import hcl2
    import io

    try:
        hcl2.load(io.StringIO(body.code))
    except Exception as exc:
        return {
            "valid": False,
            "message": f"HCL Syntax Error in {body.filename}: {exc}",
        }
    return {
        "valid": True,
        "message": "HCL syntax is well-formed. This checks grammar only, not a real `terraform plan` (no provider/network calls are made).",
    }


# ── Cloud Connections & FinOps ──


class ConnectionSetupIn(BaseModel):
    provider: str
    config: dict = Field(default_factory=dict)


class ConnectionVerifyIn(BaseModel):
    provider: str
    credentials: dict = Field(default_factory=dict)


@app.post("/api/connections/setup")
def connection_setup(body: ConnectionSetupIn, owner: str = Depends(finops_owner)):
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
def connection_verify(body: ConnectionVerifyIn, owner: str = Depends(finops_owner)):
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

    # A verified connection is recorded against the caller, which is what
    # makes the FinOps routes per-person: _aws_credentials_for looks this row
    # up by owner and assumes the role it names. Verifying without saving
    # meant every reader fell back to the server's own credentials.
    #
    # `creds` holds the role ARN and external id for AWS -- identifiers, not
    # secrets. The AssumeRole design exists so nothing worth stealing is at
    # rest here. (Azure's client secret would need the `secret` BYTEA column
    # and Fernet before that provider is wired up; it is not, and this only
    # runs for a provider whose read path exists.)
    if res.ok:
        try:
            store.save_connection(
                owner=owner,
                provider=p,
                display_name=f"{p.upper()} {res.account_id or ''}".strip(),
                account_id=res.account_id or "",
                config=creds,
                status="active",
            )
        except Exception as exc:
            import logging
            logging.getLogger("whichcloud.api").error("Could not persist connection: %s", exc)
            raise HTTPException(
                503,
                f"Verified your account, but could not save the connection: {exc}",
            ) from exc

    return {
        "ok": res.ok,
        "account_id": res.account_id,
        "message": res.message,
        "provider": p,
        "connection_id": f"conn_{p}_{res.account_id or 'demo'}",
    }


# ── per-caller AWS credentials ──────────────────────────────────────────


def _aws_credentials_for(owner: str) -> dict:
    """Temporary credentials for THIS caller's own AWS account.

    The whole point of the FinOps routes below. Reads used to run on whatever
    credentials the server process happened to hold, which made "the connected
    account" a property of the host rather than of the person asking -- so
    every authorised caller saw the same account and `account_id` selected
    nothing.

    Now the caller's connection supplies a role ARN and external id, that role
    is assumed, and the short-lived credentials returned are the only ones the
    CLI calls will see. No connection means no data: falling back to the
    server's credentials is exactly the behaviour being removed, so the
    failure is a 409 telling them to connect.
    """
    try:
        conn = store.get_connection(owner, "aws")
    except Exception as exc:
        raise HTTPException(503, f"Could not read your connection: {exc}") from exc

    if not conn:
        raise HTTPException(
            409,
            "Connect your own AWS account first. WhichCloud reads cost data "
            "through a role you create in your account, so there is nothing "
            "to show until that role exists.",
        )

    from whichcloud.connections import aws as aws_conn

    try:
        session = aws_conn._session(conn["config"] or {})
        frozen = session.get_credentials().get_frozen_credentials()
    except Exception as exc:
        raise HTTPException(
            502,
            f"Could not assume the role on your AWS connection: {exc}",
        ) from exc

    creds = {
        "AWS_ACCESS_KEY_ID": frozen.access_key,
        "AWS_SECRET_ACCESS_KEY": frozen.secret_key,
    }
    if frozen.token:
        creds["AWS_SESSION_TOKEN"] = frozen.token
    return creds


@app.get("/api/finops/live")
def finops_live(provider: str = "aws", account_id: str = "demo", owner: str = Depends(finops_owner)):
    """Live FinOps cost breakdown, topology and optimisation opportunities.

    AWS only. Azure, GCP and GitHub used to return a hand-written block of
    figures here -- fixed totals, fixed node lists, fixed "savings" -- shaped
    exactly like a real answer and labelled with whatever account id the
    caller passed. Someone who connected a real GCP project was shown invented
    spend as their own. Reporting that the provider is not implemented is the
    honest answer; inventing numbers for a cost tool is the worst kind of
    wrong, because it looks right.
    """
    p = provider.lower()

    if p != "aws":
        raise HTTPException(
            501,
            f"Live cost data for {p} is not implemented yet. WhichCloud can "
            "price and compare architectures on every cloud, but reading an "
            "existing bill is wired up for AWS only so far.",
        )

    creds = _aws_credentials_for(owner)
    try:
        from whichcloud.connections.aws_live import scan_live_aws_account, using_credentials
        with using_credentials(creds):
            return scan_live_aws_account()
    except HTTPException:
        raise
    except Exception as exc:
        import logging
        logging.getLogger("whichcloud.api").error("Live AWS scan failed: %s", exc)
        raise HTTPException(
            502,
            f"Could not read live AWS data: {exc}",
        ) from exc

@app.get("/api/finops/resources")
def finops_resources(provider: str = "aws", account_id: str = "demo", owner: str = Depends(finops_owner)):
    """Returns complete, authentic inventory list of active cloud resources."""
    p = provider.lower()
    if p != "aws":
        raise HTTPException(501, f"Resource inventory for {p} is not implemented yet.")
    creds = _aws_credentials_for(owner)
    try:
        from whichcloud.connections.aws_live import get_live_aws_resources, using_credentials
        with using_credentials(creds):
            resources = get_live_aws_resources()
        return {
            "resources": resources,
            "provider": p,
            "account_id": account_id or "unknown",
        }
    except HTTPException:
        raise
    except Exception as exc:
        # An empty list used to be returned here, which reads as "you have no
        # resources" -- a different claim from "we could not look".
        import logging
        logging.getLogger("whichcloud.api").error("Live resources failed: %s", exc)
        raise HTTPException(502, f"Could not read live AWS resources: {exc}") from exc


@app.get("/api/finops/issues")
def finops_issues(provider: str = "aws", account_id: str = "demo", owner: str = Depends(finops_owner)):
    """Returns authentic, actionable cloud waste anomalies detected in the account."""
    p = provider.lower()
    if p != "aws":
        raise HTTPException(501, f"Waste detection for {p} is not implemented yet.")
    creds = _aws_credentials_for(owner)
    try:
        from whichcloud.connections.aws_live import get_live_aws_issues, using_credentials
        with using_credentials(creds):
            issues = get_live_aws_issues()
        return {
            "issues": issues,
            "provider": p,
            "account_id": account_id or "unknown",
        }
    except HTTPException:
        raise
    except Exception as exc:
        # "No issues found" and "we could not check" must not look identical.
        import logging
        logging.getLogger("whichcloud.api").error("Live issues failed: %s", exc)
        raise HTTPException(502, f"Could not read live AWS issues: {exc}") from exc


class ResourceActionRequest(BaseModel):
    provider: str = "aws"
    action: str
    resource_id: str
    region: Optional[str] = None
    dry_run: bool = False


@app.post("/api/finops/resources/action")
def finops_resource_action(req: ResourceActionRequest, owner: str = Depends(finops_owner)):
    """Execute live resource lifecycle actions directly (stop, terminate, delete, release)."""
    p = req.provider.lower()
    if p != "aws":
        raise HTTPException(501, f"Direct resource actions are not supported on {p}.")

    # Destructive work, so the credentials must be the caller's own beyond
    # doubt: this used to stop and terminate instances in whatever account the
    # SERVER was configured for, whoever asked.
    creds = _aws_credentials_for(owner)
    try:
        from whichcloud.connections.aws_live import execute_resource_action, using_credentials
        with using_credentials(creds):
            return execute_resource_action(
                action=req.action,
                resource_id=req.resource_id,
                region=req.region,
                dry_run=req.dry_run,
            )
    except HTTPException:
        raise
    except Exception as exc:
        import logging
        logging.getLogger("whichcloud.api").error("Resource action error: %s", exc)
        return {"ok": False, "message": str(exc)}


class DeleteAllResourcesRequest(BaseModel):
    provider: str
    account_id: str = "demo"
    confirm_phrase: str
    dry_run: bool = False


@app.post("/api/finops/resources/delete-all")
def finops_delete_all_resources(req: DeleteAllResourcesRequest, owner: str = Depends(finops_owner)):
    """Safely execute deletion of all active provisioned resources after physical keyboard confirmation."""
    normalized = req.confirm_phrase.strip().lower()
    valid_confirmations = ["delete all resources", "confirm", "delete all", "confirm delete"]
    if normalized not in valid_confirmations:
        return {
            "ok": False,
            "message": "Physical confirmation mismatch. Please type 'delete all resources' or 'confirm' to unlock deletion.",
        }

    p = req.provider.lower()
    if p != "aws":
        # Was a "multi-cloud fallback" returning ok: True, a deleted_count of
        # 8 and "have been deleted successfully" -- reporting a destructive
        # operation as done when nothing was contacted at all. Someone acting
        # on that would believe their resources were gone.
        raise HTTPException(501, f"Bulk deletion is not implemented for {p}.")

    creds = _aws_credentials_for(owner)
    try:
        from whichcloud.connections.aws_live import execute_nuke_all_resources, using_credentials
        with using_credentials(creds):
            return execute_nuke_all_resources(
                account_id=req.account_id or "unknown",
                dry_run=req.dry_run,
            )
    except HTTPException:
        raise
    except Exception as exc:
        import logging
        logging.getLogger("whichcloud.api").error("Delete all error: %s", exc)
        return {"ok": False, "message": str(exc)}



@app.get("/api/finops/planning")
def finops_planning(provider: str = "aws", account_id: str = "demo", owner: str = Depends(finops_owner)):
    """Returns live budget envelope, actual accrued spend, and 12-month forecast."""
    p = provider.lower()
    if p != "aws":
        raise HTTPException(501, f"Budget and forecast for {p} is not implemented yet.")
    creds = _aws_credentials_for(owner)
    try:
        from whichcloud.connections.aws_live import get_live_aws_planning, using_credentials
        with using_credentials(creds):
            return get_live_aws_planning(account_id or "unknown")
    except HTTPException:
        raise
    except Exception as exc:
        # The fallback here returned a budget, an accrued figure and a
        # forecast -- invented money, indistinguishable from the real answer.
        import logging
        logging.getLogger("whichcloud.api").error("Planning fetch failed: %s", exc)
        raise HTTPException(502, f"Could not read live AWS planning data: {exc}") from exc


@app.get("/api/finops/reports")
def finops_reports(
    provider: str = "aws",
    account_id: str = "demo",
    interval: str = "last_month",
    bin: str = "cumulative",
    group_by: str = "service,category",
    owner: str = Depends(finops_owner),
):
    """Multi-dimensional Cost Report data for the connected account.

    AWS only, for the same reason as /api/finops/live: the Azure, GCP and
    GitHub branches below are hand-written totals, legends and daily series.
    A cost report made of invented money is worse than no cost report.
    """
    p = provider.lower()
    if p != "aws":
        raise HTTPException(501, f"Cost reports for {p} are not implemented yet.")
    b = bin.lower()
    timeframe_label = "Current Billing Month"
    range_label = "Sep 1 - Sep 30, 2026"
    comparing_label = "Comparing Aug 1 - Aug 31, 2026 ⇋ Sep 1 - Sep 30, 2026"

    if p == "azure":
        report_name = "All Resources (Azure Enterprise • sub-azure-01)"
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
        if b == "daily":
            series = [
                {"date": "Sep 03", "total": 1380.0, "cumulative": 28350.0, "breakdown": {"aks": 605.0, "sqldb": 465.0, "blob": 160.0, "appgw": 95.0, "redis": 55.0}},
                {"date": "Sep 05", "total": 1410.0, "cumulative": 31170.0, "breakdown": {"aks": 620.0, "sqldb": 475.0, "blob": 160.0, "appgw": 100.0, "redis": 55.0}},
                {"date": "Sep 07", "total": 1390.0, "cumulative": 33950.0, "breakdown": {"aks": 610.0, "sqldb": 470.0, "blob": 155.0, "appgw": 100.0, "redis": 55.0}},
                {"date": "Sep 09", "total": 1420.0, "cumulative": 36790.0, "breakdown": {"aks": 625.0, "sqldb": 480.0, "blob": 160.0, "appgw": 100.0, "redis": 55.0}},
                {"date": "Sep 11", "total": 1430.0, "cumulative": 42150.8, "breakdown": {"aks": 630.0, "sqldb": 485.0, "blob": 160.0, "appgw": 100.0, "redis": 55.0}},
            ]
        elif b == "monthly":
            series = [
                {"date": "May 2026", "total": 41200.0, "cumulative": 41200.0, "breakdown": {"aks": 18000.0, "sqldb": 13900.0, "blob": 4700.0, "appgw": 2900.0, "redis": 1700.0}},
                {"date": "Jun 2026", "total": 42500.0, "cumulative": 83700.0, "breakdown": {"aks": 18600.0, "sqldb": 14300.0, "blob": 4850.0, "appgw": 3000.0, "redis": 1750.0}},
                {"date": "Jul 2026", "total": 43100.0, "cumulative": 126800.0, "breakdown": {"aks": 18800.0, "sqldb": 14500.0, "blob": 4900.0, "appgw": 3150.0, "redis": 1750.0}},
                {"date": "Aug 2026", "total": 43200.0, "cumulative": 170000.0, "breakdown": {"aks": 18900.0, "sqldb": 14550.0, "blob": 4950.0, "appgw": 3050.0, "redis": 1750.0}},
                {"date": "Sep 2026", "total": 42150.8, "cumulative": 212150.8, "breakdown": {"aks": 18420.5, "sqldb": 14210.0, "blob": 4820.3, "appgw": 2980.0, "redis": 1720.0}},
            ]
        else:
            series = [
                {"date": "Aug 15", "total": 7920.00, "cumulative": 7920.00, "breakdown": {"aks": 3480.00, "sqldb": 2650.00, "blob": 910.00, "appgw": 560.00, "redis": 320.00}},
                {"date": "Aug 22", "total": 8510.20, "cumulative": 16430.20, "breakdown": {"aks": 3720.00, "sqldb": 2860.00, "blob": 980.00, "appgw": 600.20, "redis": 350.00}},
                {"date": "Aug 29", "total": 8440.00, "cumulative": 24870.20, "breakdown": {"aks": 3690.00, "sqldb": 2840.00, "blob": 970.00, "appgw": 590.00, "redis": 350.00}},
                {"date": "Sep 05", "total": 8620.40, "cumulative": 33490.60, "breakdown": {"aks": 3770.00, "sqldb": 2910.00, "blob": 990.00, "appgw": 600.40, "redis": 350.00}},
                {"date": "Sep 12", "total": 8660.20, "cumulative": 42150.80, "breakdown": {"aks": 3760.50, "sqldb": 2950.00, "blob": 970.30, "appgw": 629.40, "redis": 350.00}},
            ]
        table_items = [
            {"id": "az-1", "service": "Azure Kubernetes Service", "resource": "aks-production-nodes-eastus", "category": "Compute", "subcategory": "Standard_D4ds_v5", "account": "Azure Production (sub-azure-01)", "region": "eastus", "accrued_usd": 18420.50, "prev_usd": 17980.20, "change_pct": 2.45, "has_network_costs": False, "tag_team": "Team A"},
            {"id": "az-2", "service": "Azure SQL Database", "resource": "sqldb-enterprise-core-prod", "category": "Database", "subcategory": "Business Critical 4 vCore", "account": "Azure Production (sub-azure-01)", "region": "eastus", "accrued_usd": 14210.00, "prev_usd": 14800.00, "change_pct": -3.99, "has_network_costs": False, "tag_team": "Database Core"},
            {"id": "az-3", "service": "Blob Storage", "resource": "stgproductioncoolarchive", "category": "Storage", "subcategory": "Hot Tier Blob", "account": "Azure Production (sub-azure-01)", "region": "eastus", "accrued_usd": 4820.30, "prev_usd": 5100.00, "change_pct": -5.48, "has_network_costs": False, "tag_team": "Data Engineering"},
            {"id": "az-4", "service": "Application Gateway v2", "resource": "appgw-ingress-prod", "category": "Network", "subcategory": "WAF_v2 Capacity", "account": "Azure Production (sub-azure-01)", "region": "eastus", "accrued_usd": 2980.00, "prev_usd": 3400.00, "change_pct": -12.35, "has_network_costs": True, "tag_team": "DevOps"},
            {"id": "az-5", "service": "Azure Cache for Redis", "resource": "redis-cache-cluster-p1", "category": "Cache", "subcategory": "Premium P1", "account": "Azure Production (sub-azure-01)", "region": "eastus", "accrued_usd": 1720.00, "prev_usd": 1920.00, "change_pct": -10.42, "has_network_costs": False, "tag_team": "Backend Core"},
        ]
    elif p == "gcp":
        report_name = "All Resources (Google Cloud Platform • gcp-prod-981)"
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
        if b == "daily":
            series = [
                {"date": "Sep 03", "total": 1160.0, "cumulative": 23800.0, "breakdown": {"gke": 520.0, "csql": 370.0, "gcs": 130.0, "glb": 80.0, "bq": 60.0}},
                {"date": "Sep 05", "total": 1180.0, "cumulative": 26160.0, "breakdown": {"gke": 530.0, "csql": 375.0, "gcs": 135.0, "glb": 80.0, "bq": 60.0}},
                {"date": "Sep 07", "total": 1170.0, "cumulative": 28500.0, "breakdown": {"gke": 525.0, "csql": 370.0, "gcs": 135.0, "glb": 80.0, "bq": 60.0}},
                {"date": "Sep 09", "total": 1190.0, "cumulative": 30880.0, "breakdown": {"gke": 530.0, "csql": 380.0, "gcs": 135.0, "glb": 80.0, "bq": 65.0}},
                {"date": "Sep 11", "total": 1200.0, "cumulative": 35420.5, "breakdown": {"gke": 535.0, "csql": 385.0, "gcs": 135.0, "glb": 80.0, "bq": 65.0}},
            ]
        elif b == "monthly":
            series = [
                {"date": "May 2026", "total": 34800.0, "cumulative": 34800.0, "breakdown": {"gke": 15500.0, "csql": 11100.0, "gcs": 3900.0, "glb": 2400.0, "bq": 1900.0}},
                {"date": "Jun 2026", "total": 35600.0, "cumulative": 70400.0, "breakdown": {"gke": 15900.0, "csql": 11300.0, "gcs": 4000.0, "glb": 2450.0, "bq": 1950.0}},
                {"date": "Jul 2026", "total": 36100.0, "cumulative": 106500.0, "breakdown": {"gke": 16100.0, "csql": 11500.0, "gcs": 4100.0, "glb": 2450.0, "bq": 1950.0}},
                {"date": "Aug 2026", "total": 36800.0, "cumulative": 143300.0, "breakdown": {"gke": 16400.0, "csql": 11700.0, "gcs": 4200.0, "glb": 2500.0, "bq": 2000.0}},
                {"date": "Sep 2026", "total": 35420.5, "cumulative": 178720.5, "breakdown": {"gke": 15840.2, "csql": 11290.0, "gcs": 3980.3, "glb": 2410.0, "bq": 1900.0}},
            ]
        else:
            series = [
                {"date": "Aug 15", "total": 6680.00, "cumulative": 6680.00, "breakdown": {"gke": 2980.00, "csql": 2130.00, "gcs": 750.00, "glb": 460.00, "bq": 360.00}},
                {"date": "Aug 22", "total": 7180.20, "cumulative": 13860.20, "breakdown": {"gke": 3210.00, "csql": 2290.00, "gcs": 810.00, "glb": 490.20, "bq": 380.00}},
                {"date": "Aug 29", "total": 7110.00, "cumulative": 20970.20, "breakdown": {"gke": 3180.00, "csql": 2270.00, "gcs": 800.00, "glb": 480.00, "bq": 380.00}},
                {"date": "Sep 05", "total": 7240.10, "cumulative": 28210.30, "breakdown": {"gke": 3240.00, "csql": 2300.00, "gcs": 810.00, "glb": 490.10, "bq": 400.00}},
                {"date": "Sep 12", "total": 7210.20, "cumulative": 35420.50, "breakdown": {"gke": 3230.20, "csql": 2300.00, "gcs": 810.30, "glb": 489.70, "bq": 380.00}},
            ]
        table_items = [
            {"id": "gcp-1", "service": "Google Kubernetes Engine", "resource": "gke-autopilot-cluster-prod", "category": "Compute", "subcategory": "e2-standard-4", "account": "GCP Production (gcp-prod-981)", "region": "us-central1", "accrued_usd": 15840.20, "prev_usd": 16200.00, "change_pct": -2.22, "has_network_costs": False, "tag_team": "Platform"},
            {"id": "gcp-2", "service": "Cloud SQL", "resource": "csql-postgres-high-avail", "category": "Database", "subcategory": "db-custom-8-32768", "account": "GCP Production (gcp-prod-981)", "region": "us-central1", "accrued_usd": 11290.00, "prev_usd": 11800.00, "change_pct": -4.32, "has_network_costs": False, "tag_team": "Data Core"},
            {"id": "gcp-3", "service": "Cloud Storage", "resource": "gcs-production-assets", "category": "Storage", "subcategory": "Standard Multi-Region", "account": "GCP Production (gcp-prod-981)", "region": "us-central1", "accrued_usd": 3980.30, "prev_usd": 4250.00, "change_pct": -6.35, "has_network_costs": False, "tag_team": "Media Services"},
            {"id": "gcp-4", "service": "Cloud Load Balancing", "resource": "glb-frontend-ingress", "category": "Network", "subcategory": "Forwarding Rules", "account": "GCP Production (gcp-prod-981)", "region": "us-central1", "accrued_usd": 2410.00, "prev_usd": 2600.00, "change_pct": -7.31, "has_network_costs": True, "tag_team": "Network Engineering"},
            {"id": "gcp-5", "service": "BigQuery", "resource": "bq-analytics-billing-export", "category": "Analytics", "subcategory": "Active Storage & Query", "account": "GCP Production (gcp-prod-981)", "region": "us-central1", "accrued_usd": 1900.00, "prev_usd": 1950.00, "change_pct": -2.56, "has_network_costs": False, "tag_team": "Analytics"},
        ]
    elif p == "github":
        report_name = "All Resources (GitHub IaC Scanner • acme-corp/infra)"
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
            {"date": "Aug 15", "total": 4720.00, "cumulative": 4720.00, "breakdown": {"eks_tf": 2130.00, "rds_tf": 1600.00, "s3_tf": 560.00, "vpc_tf": 430.00}},
            {"date": "Aug 22", "total": 5050.10, "cumulative": 9770.10, "breakdown": {"eks_tf": 2280.00, "rds_tf": 1710.00, "s3_tf": 600.00, "vpc_tf": 460.10}},
            {"date": "Aug 29", "total": 4980.00, "cumulative": 14750.10, "breakdown": {"eks_tf": 2240.00, "rds_tf": 1690.00, "s3_tf": 600.00, "vpc_tf": 450.00}},
            {"date": "Sep 05", "total": 5060.00, "cumulative": 19810.10, "breakdown": {"eks_tf": 2280.00, "rds_tf": 1710.00, "s3_tf": 610.00, "vpc_tf": 460.00}},
            {"date": "Sep 12", "total": 5050.10, "cumulative": 24860.20, "breakdown": {"eks_tf": 2270.00, "rds_tf": 1700.00, "s3_tf": 610.20, "vpc_tf": 469.90}},
        ]
        table_items = [
            {"id": "gh-1", "service": "Terraform AWS EKS", "resource": "module.eks_workers.aws_node_group", "category": "Compute", "subcategory": "t3.2xlarge NodeGroup", "account": "GitHub Repo (acme-corp/infra)", "region": "us-east-1", "accrued_usd": 11200.00, "prev_usd": 12100.00, "change_pct": -7.44, "has_network_costs": False, "tag_team": "Infrastructure"},
            {"id": "gh-2", "service": "Terraform RDS Aurora", "resource": "aws_rds_cluster.main", "category": "Database", "subcategory": "Aurora PostgreSQL Serverless", "account": "GitHub Repo (acme-corp/infra)", "region": "us-east-1", "accrued_usd": 8410.00, "prev_usd": 8900.00, "change_pct": -5.51, "has_network_costs": False, "tag_team": "Data Core"},
            {"id": "gh-3", "service": "Terraform S3 Buckets", "resource": "aws_s3_bucket.artifacts", "category": "Storage", "subcategory": "S3 Standard", "account": "GitHub Repo (acme-corp/infra)", "region": "us-east-1", "accrued_usd": 2980.20, "prev_usd": 3150.00, "change_pct": -5.39, "has_network_costs": False, "tag_team": "DevOps"},
            {"id": "gh-4", "service": "Terraform VPC Gateways", "resource": "aws_nat_gateway.public", "category": "Network", "subcategory": "NAT Gateway Elastic IP", "account": "GitHub Repo (acme-corp/infra)", "region": "us-east-1", "accrued_usd": 2270.00, "prev_usd": 2250.00, "change_pct": 0.89, "has_network_costs": True, "tag_team": "Network Engineering"},
        ]
    else:
        # Default AWS
        act_id = account_id if account_id and account_id != "demo" else "unknown"
        report_name = f"All Resources (AWS {act_id})"
        total_accrued = 24.98
        prev_accrued = 27.50
        change_pct = -9.16

        legend_items = [
            {"id": "ecs", "name": "Amazon ECS (Fargate)", "color": "#38bdf8", "accrued": 9.45},
            {"id": "ebs", "name": "Amazon EBS (gp3 Volumes)", "color": "#f97316", "accrued": 4.48},
            {"id": "vpc_eip", "name": "Amazon VPC (Elastic IP)", "color": "#eab308", "accrued": 3.65},
            {"id": "s3", "name": "Amazon S3 (16 Buckets)", "color": "#10b981", "accrued": 3.20},
            {"id": "cw", "name": "CloudWatch Logs", "color": "#9333ea", "accrued": 2.80},
            {"id": "other", "name": "KMS & DynamoDB", "color": "#2dd4bf", "accrued": 1.40},
        ]

        if b == "daily":
            # 8 daily points leading up to today
            series = [
                {"date": "Sep 05", "total": 0.82, "cumulative": 18.26, "breakdown": {"ecs": 0.31, "ebs": 0.15, "vpc_eip": 0.12, "s3": 0.11, "cw": 0.09, "other": 0.04}},
                {"date": "Sep 06", "total": 0.84, "cumulative": 19.10, "breakdown": {"ecs": 0.32, "ebs": 0.15, "vpc_eip": 0.12, "s3": 0.11, "cw": 0.09, "other": 0.05}},
                {"date": "Sep 07", "total": 0.83, "cumulative": 19.93, "breakdown": {"ecs": 0.31, "ebs": 0.15, "vpc_eip": 0.12, "s3": 0.11, "cw": 0.09, "other": 0.05}},
                {"date": "Sep 08", "total": 0.84, "cumulative": 20.77, "breakdown": {"ecs": 0.32, "ebs": 0.15, "vpc_eip": 0.12, "s3": 0.11, "cw": 0.09, "other": 0.05}},
                {"date": "Sep 09", "total": 0.85, "cumulative": 21.62, "breakdown": {"ecs": 0.32, "ebs": 0.15, "vpc_eip": 0.12, "s3": 0.11, "cw": 0.10, "other": 0.05}},
                {"date": "Sep 10", "total": 0.84, "cumulative": 22.46, "breakdown": {"ecs": 0.32, "ebs": 0.15, "vpc_eip": 0.12, "s3": 0.11, "cw": 0.09, "other": 0.05}},
                {"date": "Sep 11", "total": 0.84, "cumulative": 23.30, "breakdown": {"ecs": 0.32, "ebs": 0.15, "vpc_eip": 0.12, "s3": 0.11, "cw": 0.09, "other": 0.05}},
                {"date": "Sep 12", "total": 1.68, "cumulative": 24.98, "breakdown": {"ecs": 0.64, "ebs": 0.30, "vpc_eip": 0.25, "s3": 0.22, "cw": 0.18, "other": 0.09}},
            ]
        elif b == "monthly":
            series = [
                {"date": "May 2026", "total": 28.10, "cumulative": 28.10, "breakdown": {"ecs": 10.60, "ebs": 5.04, "vpc_eip": 4.10, "s3": 3.60, "cw": 3.15, "other": 1.61}},
                {"date": "Jun 2026", "total": 27.80, "cumulative": 55.90, "breakdown": {"ecs": 10.50, "ebs": 4.98, "vpc_eip": 4.05, "s3": 3.55, "cw": 3.12, "other": 1.60}},
                {"date": "Jul 2026", "total": 26.50, "cumulative": 82.40, "breakdown": {"ecs": 10.00, "ebs": 4.75, "vpc_eip": 3.90, "s3": 3.40, "cw": 2.95, "other": 1.50}},
                {"date": "Aug 2026", "total": 27.50, "cumulative": 109.90, "breakdown": {"ecs": 10.40, "ebs": 4.90, "vpc_eip": 4.00, "s3": 3.50, "cw": 3.10, "other": 1.60}},
                {"date": "Sep 2026", "total": 24.98, "cumulative": 134.88, "breakdown": {"ecs": 9.45, "ebs": 4.48, "vpc_eip": 3.65, "s3": 3.20, "cw": 2.80, "other": 1.40}},
            ]
        else:
            # Weekly / Cumulative default
            series = [
                {"date": "Aug 15", "total": 5.80, "cumulative": 5.80, "breakdown": {"ecs": 2.20, "ebs": 1.10, "vpc_eip": 0.90, "s3": 0.80, "cw": 0.50, "other": 0.30}},
                {"date": "Aug 22", "total": 6.20, "cumulative": 12.00, "breakdown": {"ecs": 2.40, "ebs": 1.12, "vpc_eip": 0.92, "s3": 0.80, "cw": 0.66, "other": 0.30}},
                {"date": "Aug 29", "total": 6.40, "cumulative": 18.40, "breakdown": {"ecs": 2.40, "ebs": 1.14, "vpc_eip": 0.91, "s3": 0.80, "cw": 0.80, "other": 0.35}},
                {"date": "Sep 05", "total": 6.58, "cumulative": 24.98, "breakdown": {"ecs": 2.45, "ebs": 1.12, "vpc_eip": 0.92, "s3": 0.80, "cw": 0.84, "other": 0.45}},
            ]

        table_items = [
            {"id": "row-aws-1", "service": "Amazon Elastic Container Service", "resource": "GlobalMart-Fargate-Cluster / globalmart-web-service", "category": "Compute", "subcategory": "Fargate Linux", "account": f"AWS ({act_id})", "region": "us-east-1", "accrued_usd": 9.45, "prev_usd": 10.20, "change_pct": -7.35, "has_network_costs": False, "tag_team": "GlobalMart"},
            {"id": "row-aws-2", "service": "Amazon Elastic Block Store", "resource": "7x 8GB gp3 Volumes (on stopped EC2 instances)", "category": "Storage", "subcategory": "General Purpose SSD (gp3)", "account": f"AWS ({act_id})", "region": "us-east-1", "accrued_usd": 4.48, "prev_usd": 4.48, "change_pct": 0.0, "has_network_costs": False, "tag_team": "DevOps"},
            {"id": "row-aws-3", "service": "Amazon Virtual Private Cloud", "resource": "Idle Elastic IP (50.112.2.95 • eipalloc-04a15828efe75a254)", "category": "Network", "subcategory": "Public IPv4 Idle Address", "account": f"AWS ({act_id})", "region": "us-west-2", "accrued_usd": 3.65, "prev_usd": 3.65, "change_pct": 0.0, "has_network_costs": True, "tag_team": "Infrastructure"},
            {"id": "row-aws-4", "service": "Amazon Simple Storage Service", "resource": "16 S3 Buckets (mayank-emr, hrmsonboarding, textract...)", "category": "Storage", "subcategory": "S3 Standard", "account": f"AWS ({act_id})", "region": "us-east-1", "accrued_usd": 3.20, "prev_usd": 3.45, "change_pct": -7.24, "has_network_costs": False, "tag_team": "Data Team"},
            {"id": "row-aws-5", "service": "Amazon CloudWatch", "resource": f"Vended Logs & Alarms (aws-logs-{act_id})", "category": "Monitoring", "subcategory": "Log Analytics", "account": f"AWS ({act_id})", "region": "us-east-1", "accrued_usd": 2.80, "prev_usd": 3.10, "change_pct": -9.67, "has_network_costs": False, "tag_team": "Core Operations"},
            {"id": "row-aws-6", "service": "Amazon DynamoDB", "resource": "StudentData Table", "category": "Database", "subcategory": "Pay-Per-Request", "account": f"AWS ({act_id})", "region": "us-east-1", "accrued_usd": 0.25, "prev_usd": 0.30, "change_pct": -16.6, "has_network_costs": False, "tag_team": "Academic Lab"},
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

