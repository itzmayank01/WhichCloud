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


# ── response shapes ─────────────────────────────────────────────────────


class LineItemOut(BaseModel):
    label: str
    sku: str
    unit: str
    unit_price: float
    quantity: float
    monthly_usd: float


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
    shape: str
    items: list[LineItemOut]
    missing: list[str]
    measured_saving_usd: float
    saving_pct: float
    applied: list[TechniqueOut]
    advisory: list[TechniqueOut]
    tradeoffs: list[str]
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


def _option_out(option: Option, provider: str) -> OptionOut:
    spec = option.spec
    shape = f"{spec.compute_count}× {spec.compute_vcpu} vCPU / {spec.compute_memory_gb:g} GB"
    if spec.arch:
        shape += f" {spec.arch}"
    if spec.use_spot:
        shape += " spot"
    if spec.compute_duty_cycle < 1.0:
        shape += f" @{spec.compute_duty_cycle:.0%}"
    # Only when there IS a database. The flag is set by the reliability
    # tiers regardless, so a batch job with no database was described as
    # "multi-AZ db" while its architecture contained no database at all.
    if spec.database_multi_az and spec.database_vcpu:
        shape += " · multi-AZ db"

    return OptionOut(
        drawn=_drawn(option, provider),
        label=option.label,
        rationale=option.rationale,
        provider=provider,
        region=option.estimate.region,
        monthly_usd=float(option.monthly),
        complete=option.estimate.is_complete,
        within_budget=option.within_budget,
        shape=shape,
        items=[
            LineItemOut(
                label=i.label,
                sku=i.sku,
                unit=i.unit,
                unit_price=float(i.unit_price),
                quantity=float(i.quantity),
                monthly_usd=float(i.monthly_usd),
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
        topology=_topology_out(option),
    )


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
        diffs=[_diff_out(a, b) for a, b in zip(options, options[1:])],
        not_applied=[
            {"id": t.id, "name": t.name, "reason": why}
            for t, why in why_not(requirement, provider)
        ],
        sizing_basis=SIZING_BASIS,
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
                "monthly_total": round(tier.monthly_total, 2),
                "within_budget": tier.within_budget(constraints.budget_monthly_usd),
                "rto": tier.rto,
                "rpo": tier.rpo,
                "region_rto": tier.region_rto,
                "region_rpo": tier.region_rpo,
                "gives_up": tier.gives_up,
                "justifications": tier.justifications,
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
    }


@app.post("/describe", response_model=RecommendationOut)
def describe_route(body: DescribeIn) -> RecommendationOut:
    """Plain English straight through to three priced architectures.

    The only route that needs a model API key. It reports what the model
    assumed and what it would ask next, so the interface can surface guesses
    as guesses.
    """
    from .intake import IntakeError, parse_description

    try:
        intake = parse_description(body.description, provider=body.reader)
    except IntakeError as exc:
        raise HTTPException(400, str(exc)) from exc

    requirement = intake.requirement
    provider = requirement.provider_preference or "aws"
    options = recommend(requirement, provider)

    return RecommendationOut(
        goal=requirement.goal,
        region=requirement.region,
        options=[_option_out(o, provider) for o in options],
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
    )
