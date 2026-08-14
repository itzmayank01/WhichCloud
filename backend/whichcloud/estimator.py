"""Turn an architecture into a monthly bill.

This is what separates WhichCloud from a diagram tool. The engine describes a
shape — three app servers, a Postgres, 200 GB of assets, 500 GB of egress — and
this module prices every line from the catalog and adds it up.

Rules it follows:
  * Never invent a price. If a component cannot be priced, it is reported in
    `missing`, not silently dropped or guessed.
  * Every line shows its unit price and quantity, so a user can check the maths.
  * Totals are labelled estimates, because list pricing ignores committed-use
    discounts and real traffic never matches a projection exactly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from .pricing.models import HOURS_PER_MONTH, ComputeQuery, PricePoint, provider_region
from .pricing import store


@dataclass(frozen=True, slots=True)
class ArchitectureSpec:
    """A provider-neutral description of what needs to run."""

    name: str
    region: str  # our neutral key, e.g. "india"

    compute_count: int = 1
    compute_vcpu: int = 2
    compute_memory_gb: float = 4.0
    arch: str | None = None  # "arm64" to force ARM

    database_vcpu: int | None = None
    database_memory_gb: float | None = None
    database_multi_az: bool = False
    database_arch: str | None = None  # "arm64" to force ARM database instances

    storage_gb: float = 0.0
    egress_gb: float = 0.0
    load_balancer: bool = False

    # Spot capacity can be reclaimed at short notice, so it is opt-in and only
    # ever appropriate for interruptible work.
    use_spot: bool = False

    # Fraction of the month compute actually runs. 1.0 = always on. Scale-to-
    # zero lowers this. The hourly RATE stays real; only the hours change.
    compute_duty_cycle: float = 1.0


@dataclass(frozen=True, slots=True)
class LineItem:
    label: str
    sku: str
    unit: str
    unit_price: Decimal
    quantity: Decimal
    monthly_usd: Decimal

    @property
    def detail(self) -> str:
        return f"{self.quantity:g} × ${self.unit_price:.4f}/{self.unit}"


@dataclass(slots=True)
class Estimate:
    provider: str
    region: str
    spec: ArchitectureSpec
    items: list[LineItem] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)

    @property
    def total_monthly(self) -> Decimal:
        return sum((i.monthly_usd for i in self.items), Decimal(0))

    @property
    def is_complete(self) -> bool:
        return not self.missing


# For metered categories, "cheapest in category" is the wrong default: S3
# archive tiers undercut Standard by 5x but are not where a web app's assets
# live. Naming the sensible default keeps estimates honest, and we fall back to
# cheapest only when the preferred SKU is absent.
DEFAULT_SKUS: dict[tuple[str, str], str] = {
    ("aws", "storage"): "s3:general-purpose",
    ("azure", "storage"): "blob:hot-lrs",
    ("aws", "loadbalancer"): "alb",
    ("azure", "loadbalancer"): "lb:standard",
    ("aws", "network"): "egress:internet",
    ("azure", "network"): "egress:internet",
}


def _preferred(
    provider: str, region: str, category: str, dsn: str | None
) -> PricePoint | None:
    sku = DEFAULT_SKUS.get((provider, category))
    if sku:
        point = store.get_price(provider, region, category, sku, dsn=dsn)
        if point:
            return point
    return store.cheapest_in_category(provider, region, category, dsn=dsn)


def _hourly_line(
    label: str, point: PricePoint, count: int, duty_cycle: float = 1.0
) -> LineItem:
    quantity = Decimal(count) * HOURS_PER_MONTH * Decimal(str(duty_cycle))
    return LineItem(
        label=label,
        sku=point.sku,
        unit=point.unit,
        unit_price=point.price_usd,
        quantity=quantity,
        monthly_usd=point.price_usd * quantity,
    )


def _metered_line(label: str, point: PricePoint, amount: float) -> LineItem:
    quantity = Decimal(str(amount))
    return LineItem(
        label=label,
        sku=point.sku,
        unit=point.unit,
        unit_price=point.price_usd,
        quantity=quantity,
        monthly_usd=point.price_usd * quantity,
    )


def estimate(spec: ArchitectureSpec, provider: str, dsn: str | None = None) -> Estimate:
    """Price one architecture on one provider."""
    region = provider_region(spec.region, provider)
    result = Estimate(provider=provider, region=region, spec=spec)

    # ---- compute ----
    if spec.compute_count > 0:
        query = ComputeQuery(
            min_vcpu=spec.compute_vcpu,
            min_memory_gb=spec.compute_memory_gb,
            region=spec.region,
            arch=spec.arch,
        )
        purchase = "spot" if spec.use_spot else "ondemand"
        point = store.cheapest_compute(
            query, provider=provider, purchase=purchase, dsn=dsn
        )
        if point:
            label = f"Compute × {spec.compute_count}"
            if spec.use_spot:
                label += " (spot)"
            result.items.append(
                _hourly_line(
                    label, point, spec.compute_count, spec.compute_duty_cycle
                )
            )
        else:
            result.missing.append(
                f"{purchase} compute {spec.compute_vcpu}vCPU/"
                f"{spec.compute_memory_gb:g}GB"
                + (f" {spec.arch}" if spec.arch else "")
            )

    # ---- database ----
    if spec.database_vcpu:
        point = store.cheapest_database(
            provider=provider,
            region=region,
            min_vcpu=spec.database_vcpu,
            min_memory_gb=spec.database_memory_gb or 0.0,
            multi_az=spec.database_multi_az,
            arch=spec.database_arch,
            dsn=dsn,
        )
        if point:
            label = "Database" + (" (Multi-AZ)" if spec.database_multi_az else "")
            result.items.append(_hourly_line(label, point, 1))
        else:
            result.missing.append(
                f"database {spec.database_vcpu}vCPU/"
                f"{(spec.database_memory_gb or 0):g}GB"
                + (f" {spec.database_arch}" if spec.database_arch else "")
                + (" multi-az" if spec.database_multi_az else "")
            )

    # ---- storage ----
    if spec.storage_gb > 0:
        point = _preferred(provider, region, "storage", dsn)
        if point:
            result.items.append(_metered_line("Object storage", point, spec.storage_gb))
        else:
            result.missing.append("object storage")

    # ---- egress ----
    if spec.egress_gb > 0:
        point = _preferred(provider, region, "network", dsn)
        if point:
            result.items.append(_metered_line("Egress", point, spec.egress_gb))
        else:
            result.missing.append("egress")

    # ---- load balancer ----
    if spec.load_balancer:
        point = _preferred(provider, region, "loadbalancer", dsn)
        if point:
            result.items.append(_hourly_line("Load balancer", point, 1))
        else:
            result.missing.append("load balancer")

    return result


def compare(
    spec: ArchitectureSpec,
    providers: tuple[str, ...] = ("aws", "azure", "gcp"),
    dsn: str | None = None,
) -> list[Estimate]:
    """Price the same architecture on each provider, cheapest first.

    Incomplete estimates sort last regardless of price — a total that is missing
    a database is not cheaper, it is wrong, and ranking it first would be a lie.
    """
    results = [estimate(spec, p, dsn=dsn) for p in providers]
    return sorted(results, key=lambda e: (not e.is_complete, e.total_monthly))
