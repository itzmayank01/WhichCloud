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

from .engine import SIZING_BASIS, Option, recommend, recommend_across_clouds, why_not
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
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
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


class RecommendationOut(BaseModel):
    goal: str
    region: str
    options: list[OptionOut]
    not_applied: list[dict]
    sizing_basis: str
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


def _option_out(option: Option, provider: str) -> OptionOut:
    spec = option.spec
    shape = f"{spec.compute_count}× {spec.compute_vcpu} vCPU / {spec.compute_memory_gb:g} GB"
    if spec.arch:
        shape += f" {spec.arch}"
    if spec.use_spot:
        shape += " spot"
    if spec.compute_duty_cycle < 1.0:
        shape += f" @{spec.compute_duty_cycle:.0%}"
    if spec.database_multi_az:
        shape += " · multi-AZ db"

    return OptionOut(
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
        )


class DescribeIn(BaseModel):
    description: str
    reader: Literal["gemini", "anthropic"] | None = None


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

    return {
        "status": "ok",
        "prices": total,
        "providers": sorted({r["provider"] for r in rows}),
        "last_updated": max(r["fetched"] for r in rows).isoformat(),
    }


@app.get("/regions")
def regions() -> dict:
    """Region keys and how they map to each provider."""
    return REGIONS


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
        not_applied=[
            {"id": t.id, "name": t.name, "reason": why}
            for t, why in why_not(requirement, provider)
        ],
        sizing_basis=SIZING_BASIS,
        assumed=list(intake.assumed),
        clarifying_question=intake.clarifying_question,
        read_by=intake.provider,
    )
