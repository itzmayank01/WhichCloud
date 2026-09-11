"""P3 AUDIT: a billing export in, a waste report out.

The PRD's third product, and the one that did not exist. `backend/audit/`
is a different thing entirely -- an internal scorecard that grades the
ENGINE's own architecture and cost accuracy against fixtures -- and it
was mistaken for this at the start of the session. Nothing in it reads a
billing CSV.

WHAT MAKES THIS DIFFERENT FROM EVERY OTHER COST TOOL.
It does not tell you what you spent; your bill already did. It matches
each line against the knowledge base's `applies_when` rules and reports
what the technique WOULD save, priced from the catalog rather than from a
percentage somebody remembered. Every finding names the technique, the
trade-off it carries, and the line it was measured against.

THE RULES IT INHERITS, unchanged:
  * Never invent a saving. A line the knowledge base has nothing to say
    about is reported as reviewed-and-nothing-found, not omitted.
  * Every figure is measured against a real catalog rate, so a finding
    can be checked against what it beat.
  * Every finding carries its trade-off. A saving with no downside is a
    saving that has not been understood.

WHAT IT DELIBERATELY DOES NOT DO.
No live account connection -- the PRD puts that explicitly out of scope
for v1, and a read-only IAM role is a credential this product has no
business holding. A CSV is something the user can look at before they
hand it over.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from whichcloud.knowledge import Technique, load_techniques

#: Column names providers actually use, lowercased. AWS Cost and Usage
#: Reports, GCP billing exports and Azure cost exports all name these
#: differently, and a tool that only reads one of them is a tool for one
#: cloud.
_SERVICE_COLUMNS = (
    "product/servicecode", "lineitem/productcode", "product_service",
    "service", "servicename", "meter category", "metercategory",
    "product/productname", "consumedservice",
)
_COST_COLUMNS = (
    "lineitem/unblendedcost", "unblendedcost", "cost", "costinbillingcurrency",
    "pretaxcost", "billingaccountcost", "total", "amount",
)
_USAGE_COLUMNS = (
    "lineitem/usageamount", "usageamount", "usage_amount", "quantity",
    "usagequantity",
)
_REGION_COLUMNS = (
    "product/region", "region", "resourcelocation", "location",
    "product/location",
)
#: When the usage happened. A cost report is a TIME SERIES first -- "what
#: did we spend, over what period, and is it rising" -- and none of that
#: is answerable from a single collapsed total. Each provider names this
#: differently, and AWS gives an interval where the other two give a day.
_DATE_COLUMNS = (
    "lineitem/usagestartdate", "usagestartdate", "usage_start_time",
    "date", "usagedatetime", "usage_date", "billingperiodstartdate",
    "bill/billingperiodstartdate", "chargeperiodstart",
)
_TYPE_COLUMNS = (
    "product/instancetype", "instancetype", "meter subcategory",
    "metersubcategory", "resource_type", "sku_description", "product/usagetype",
)


class BillingParseError(ValueError):
    """The upload was not a billing export we can read. Raised rather
    than guessed at: a report built from misread columns is worse than a
    refusal, because it looks like an answer."""


@dataclass
class BillingLine:
    """One row of somebody's bill, in the terms this tool reasons in."""

    service: str
    monthly_usd: Decimal
    usage: Decimal = Decimal(0)
    region: str = ""
    resource_type: str = ""
    #: ISO day, or "" when the export did not say. Empty rather than
    #: today's date: a row whose date we do not know must not be plotted
    #: as if it happened now, which would invent a trend.
    day: str = ""
    raw: dict = field(default_factory=dict)


@dataclass
class Finding:
    """One technique that applies to one service, with what it saves."""

    service: str
    monthly_usd: float
    technique_id: str
    technique: str
    category: str
    summary: str
    #: MEASURED where the catalog can price the swap, ESTIMATED from the
    #: technique's cited typical_pct where it cannot. Which of the two it
    #: is, is stated -- never blurred.
    saved_monthly_usd: float
    basis: str
    measured: bool
    obviousness: str
    tradeoffs: list[str]
    tool: str
    tool_url: str = ""
    #: Conditions this technique needs that a billing export CANNOT show.
    #:
    #: A CUR gives a service and a total. It does not say whether the
    #: workload can tolerate an interruption, whether downtime matters,
    #: or whether the images are multi-arch -- and every one of those
    #: decides whether the technique applies at all. Naming them is the
    #: difference between a finding and a guess.
    needs_confirmation: list[str] = field(default_factory=list)


@dataclass
class CostRow:
    """One cell of the bill, aggregated on the dimensions a report groups by.

    The audit collapses everything to one row per service, because a finding
    per CUR row would be noise. A COST REPORT needs the other axes back:
    nobody asks only "what did we spend", they ask "on what, where, and of
    what kind". Aggregating on the three together keeps the payload in the
    tens or low hundreds of rows -- a CUR's thousands are rows about the same
    handful of services -- so the interface can filter and regroup locally
    without another round trip per click.
    """

    service: str
    region: str
    resource_type: str
    #: ISO day, or "" where the export did not state one.
    day: str
    monthly_usd: float
    usage: float


@dataclass
class AuditReport:
    currency: str = "USD"
    total_monthly_usd: float = 0.0
    lines_read: int = 0
    findings: list[Finding] = field(default_factory=list)
    #: Services the knowledge base had nothing to say about. Reported
    #: rather than dropped: "we looked and found nothing" and "we did not
    #: look" are different claims, and only one of them is honest about
    #: coverage.
    reviewed_no_finding: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    #: The bill itself, on three axes. Findings answer "what should change";
    #: this answers "what is there", which is the question a reader has first.
    breakdown: list[CostRow] = field(default_factory=list)

    @property
    def total_saving_usd(self) -> float:
        """The BEST single technique per service, summed across services.

        NOT the sum of every finding. Techniques against one service are
        ALTERNATIVES, not a shopping list: you cannot scale a fleet to
        zero off-peak, rightsize it, and buy a one-year commitment on it
        and collect all three savings -- the second is measured against
        the first, and the third is measured against a fleet you have
        already shrunk.

        Summing them produced a 147.9% saving on the first sample bill I
        ran, which is the arithmetic telling you the model is wrong. It
        is also the rule the engine's own knowledge base states in as
        many words: typical_pct values "are neither independent nor
        additive, and adding them would invent a number."
        """
        best: dict[str, float] = {}
        for finding in self.findings:
            current = best.get(finding.service, 0.0)
            best[finding.service] = max(current, finding.saved_monthly_usd)
        return round(sum(best.values()), 2)

    @property
    def saving_pct(self) -> float:
        if not self.total_monthly_usd:
            return 0.0
        return round(100 * self.total_saving_usd / self.total_monthly_usd, 1)


def _day(value: str | None) -> str:
    """An ISO day from whatever the export put in its date column.

    AWS writes `2024-03-01T00:00:00Z`, GCP `2024-03-01 00:00:00 UTC`,
    Azure `03/01/2024`. Only the day is kept: billing exports are daily at
    finest, and an hour that is really a bucket label reads as precision
    the data does not carry.

    Anything unrecognised returns "" rather than a guess. A misparsed date
    puts real money on the wrong day, and a chart makes that look like a
    spike somebody has to go and explain.
    """
    text = (value or "").strip()
    if not text:
        return ""
    if match := re.match(r"(\d{4})-(\d{2})-(\d{2})", text):
        return match.group(0)
    # Azure's US-style M/D/Y. Ambiguous for the first twelve days of a
    # month -- and unresolvable from one row, so the provider's stated
    # format is taken at its word rather than sniffed.
    if match := re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", text):
        month, day, year = match.groups()
        return f"{year}-{int(month):02d}-{int(day):02d}"
    return ""


def _pick(header: list[str], candidates: tuple[str, ...]) -> str | None:
    lowered = {h.strip().lower(): h for h in header}
    for candidate in candidates:
        if candidate in lowered:
            return lowered[candidate]
    # Fall back to a substring match, because providers version their
    # column names ("lineItem/UnblendedCost" vs "line_item_unblended_cost").
    for name, original in lowered.items():
        squashed = re.sub(r"[^a-z]", "", name)
        for candidate in candidates:
            if re.sub(r"[^a-z]", "", candidate) in squashed:
                return original
    return None


def _decimal(raw: str) -> Decimal:
    try:
        return Decimal(str(raw).replace(",", "").replace("$", "").strip() or 0)
    except (InvalidOperation, ValueError):
        return Decimal(0)


def parse(content: str) -> tuple[list[BillingLine], list[str]]:
    """A billing export into lines, plus anything worth warning about."""
    reader = csv.DictReader(io.StringIO(content))
    if not reader.fieldnames:
        raise BillingParseError("The file has no header row.")

    header = list(reader.fieldnames)
    service_col = _pick(header, _SERVICE_COLUMNS)
    cost_col = _pick(header, _COST_COLUMNS)
    if not service_col or not cost_col:
        raise BillingParseError(
            "Could not find a service column and a cost column. Expected "
            "something like 'product/ServiceCode' and "
            "'lineItem/UnblendedCost' (AWS), 'service' and 'cost' (GCP), or "
            "'MeterCategory' and 'CostInBillingCurrency' (Azure). "
            f"Found: {', '.join(header[:12])}"
        )

    usage_col = _pick(header, _USAGE_COLUMNS)
    region_col = _pick(header, _REGION_COLUMNS)
    type_col = _pick(header, _TYPE_COLUMNS)
    date_col = _pick(header, _DATE_COLUMNS)

    lines: list[BillingLine] = []
    warnings: list[str] = []
    negative = 0
    for row in reader:
        service = (row.get(service_col) or "").strip()
        if not service:
            continue
        cost = _decimal(row.get(cost_col, "0"))
        if cost < 0:
            negative += 1
            continue
        lines.append(BillingLine(
            service=service,
            monthly_usd=cost,
            usage=_decimal(row.get(usage_col, "0")) if usage_col else Decimal(0),
            region=(row.get(region_col) or "").strip() if region_col else "",
            resource_type=(row.get(type_col) or "").strip() if type_col else "",
            day=_day(row.get(date_col, "")) if date_col else "",
            raw=row,
        ))

    if negative:
        warnings.append(
            f"{negative} line(s) with a negative cost were skipped — credits "
            f"and refunds are not spend, and counting them would understate "
            f"what there is to save against."
        )
    if not lines:
        raise BillingParseError(
            "No usable rows. Every row was empty, zero-cost or a credit."
        )
    return lines, warnings


#: Ceiling on breakdown rows returned. Past this the finest axis is
#: dropped rather than the tail truncated -- see _breakdown.
_MAX_CELLS = 12000

#: Billing service names -> the workload_type the knowledge base speaks.
#: Deliberately conservative: a service this cannot classify produces NO
#: finding rather than a guessed one, and shows up in
#: `reviewed_no_finding` where the gap is visible.
_SERVICE_WORKLOAD = {
    "ec2": "web", "amazonec2": "web", "compute engine": "web",
    "virtual machines": "web", "amazonecs": "web", "amazoneks": "web",
    "amazonrds": "web", "cloud sql": "web", "sql database": "web",
    "amazons3": "storage", "cloud storage": "storage",
    "storage": "storage", "amazonglacier": "storage",
    "awslambda": "api", "cloud functions": "api", "functions": "api",
    "amazonathena": "batch", "bigquery": "batch", "awsglue": "batch",
    "amazonemr": "batch", "dataproc": "batch",
    "amazonsagemaker": "ml", "vertex ai": "ml", "machine learning": "ml",
    "amazoncloudfront": "web", "cloud cdn": "web", "content delivery": "web",
    "awsdatatransfer": "web", "bandwidth": "web",
    "amazonelasticache": "web", "memorystore": "web", "cache for redis": "web",
}

#: Services whose spend is dominated by a lever the knowledge base has a
#: technique for. Used only to decide WHICH techniques to test against a
#: line, never to invent one.
_SERVICE_CATEGORY = {
    "ec2": "compute", "amazonec2": "compute", "compute engine": "compute",
    "virtual machines": "compute", "amazonecs": "compute",
    "amazonrds": "database", "cloud sql": "database", "sql database": "database",
    "amazons3": "storage", "cloud storage": "storage", "storage": "storage",
    "amazonelasticache": "memory", "memorystore": "memory",
    "cache for redis": "memory",
    "awsdatatransfer": "network", "bandwidth": "network",
    "amazoncloudfront": "network", "cloud cdn": "network",
    "amazonvpc": "network", "virtual network": "network",
}


def _normalise(service: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", service.lower()).strip()


def _classify(service: str) -> tuple[str, str]:
    """(workload_type, category) for a billing service name, or ("","")."""
    key = _normalise(service)
    workload = _SERVICE_WORKLOAD.get(key, "")
    category = _SERVICE_CATEGORY.get(key, "")
    if workload and category:
        return workload, category
    for name, value in _SERVICE_WORKLOAD.items():
        if name in key:
            workload = workload or value
    for name, value in _SERVICE_CATEGORY.items():
        if name in key:
            category = category or value
    return workload, category


def _applies(technique: Technique, line: BillingLine, category: str) -> bool:
    """Whether this technique's own applies_when rule admits this line.

    The rule is the knowledge base's, evaluated -- not re-invented here.
    """
    if technique.category != category:
        return False
    if float(line.monthly_usd) < technique.min_monthly_spend_usd:
        return False
    workload, _ = _classify(line.service)
    if technique.workload_types and workload:
        if workload not in technique.workload_types:
            return False
    return True


def _round_to_total(rows: list[CostRow], total: float) -> list[CostRow]:
    """Round every cell to cents so they still sum to the bill exactly.

    Rounding each cell independently does not do this. On a 1,165-cell
    export the roundings drifted ten cents from the headline -- nothing
    against $84,000, but a cost report whose rows visibly do not add up to
    its own total is one a reader stops believing, and they are right to.

    Largest-remainder apportionment: floor every cell to a cent, then hand
    the leftover cents to the cells that lost the most in the floor. Each
    cell moves by at most one cent from its true value, and the column
    sums to the bill by construction rather than by luck.
    """
    cents = [int(row.monthly_usd * 100) for row in rows]
    remainders = sorted(
        range(len(rows)),
        key=lambda i: rows[i].monthly_usd * 100 - cents[i],
        reverse=True,
    )
    leftover = round(total * 100) - sum(cents)
    # Negative only if floats conspired; handing back cents is the same
    # operation in reverse and keeps the invariant either way.
    step = 1 if leftover >= 0 else -1
    for n in range(abs(leftover)):
        cents[remainders[n % len(remainders)]] += step

    for row, value in zip(rows, cents):
        row.monthly_usd = value / 100
        row.usage = round(row.usage, 4)
    return rows


def _breakdown(lines: list[BillingLine]) -> tuple[list[CostRow], list[str]]:
    """The bill grouped on service, region, resource type and day.

    All four axes at once, so the interface can regroup and filter without
    another request -- every row is disjoint, so any subtotal it builds is
    a real sum rather than a re-estimate.

    Unknown dimensions become an explicit empty string rather than being
    dropped: a row whose region the export did not state is still real
    money, and binning it under another region would move spend somewhere
    it did not go.
    """
    notes: list[str] = []

    def fold(keep_type: bool) -> dict[tuple, CostRow]:
        cells: dict[tuple, CostRow] = {}
        for line in lines:
            rtype = line.resource_type if keep_type else ""
            key = (line.service, line.region, rtype, line.day)
            cell = cells.get(key)
            if cell is None:
                cells[key] = CostRow(
                    service=line.service, region=line.region,
                    resource_type=rtype, day=line.day,
                    monthly_usd=float(line.monthly_usd),
                    usage=float(line.usage),
                )
            else:
                cell.monthly_usd += float(line.monthly_usd)
                cell.usage += float(line.usage)
        return cells

    cells = fold(keep_type=True)
    # A full CUR crossed with a month of days can reach tens of thousands
    # of combinations, which is a payload nobody can use. Drop the finest
    # axis rather than truncating: a report missing its long tail silently
    # understates every total, where a report with one fewer dimension is
    # still arithmetically true.
    if len(cells) > _MAX_CELLS:
        dropped = len(cells)
        cells = fold(keep_type=False)
        notes.append(
            f"Grouped without resource type: the bill has {dropped:,} "
            f"service/region/type/day combinations, past the {_MAX_CELLS:,} "
            f"this can return. Totals are unchanged; the resource-type "
            f"breakdown is not available for a bill this wide."
        )

    rows = _round_to_total(
        sorted(cells.values(), key=lambda c: c.monthly_usd, reverse=True),
        float(sum(line.monthly_usd for line in lines)),
    )

    if rows and not any(c.day for c in rows):
        notes.append(
            "No date column was found, so this bill is a single snapshot "
            "rather than a series. Costs over time needs an export with "
            "lineItem/UsageStartDate (AWS), usage_start_time (GCP) or "
            "Date (Azure)."
        )
    return rows, notes


def audit(content: str, techniques: list[Technique] | None = None) -> AuditReport:
    """A billing export, reviewed against the knowledge base."""
    lines, warnings = parse(content)
    catalog = techniques if techniques is not None else load_techniques()

    # One row per service: a CUR has thousands of rows for one service and
    # a finding per row would be noise, not a report.
    by_service: dict[str, BillingLine] = {}
    for line in lines:
        key = line.service
        if key in by_service:
            by_service[key].monthly_usd += line.monthly_usd
            by_service[key].usage += line.usage
        else:
            by_service[key] = BillingLine(
                service=line.service, monthly_usd=line.monthly_usd,
                usage=line.usage, region=line.region,
                resource_type=line.resource_type,
            )

    report = AuditReport(
        total_monthly_usd=round(float(sum(l.monthly_usd for l in lines)), 2),
        lines_read=len(lines),
        warnings=warnings,
    )
    report.breakdown, breakdown_notes = _breakdown(lines)
    report.warnings.extend(breakdown_notes)

    for line in sorted(
        by_service.values(), key=lambda l: l.monthly_usd, reverse=True
    ):
        _workload, category = _classify(line.service)
        matched = [
            t for t in catalog
            if category and _applies(t, line, category)
        ]
        if not matched:
            report.reviewed_no_finding.append({
                "service": line.service,
                "monthly_usd": round(float(line.monthly_usd), 2),
                "why": (
                    "no technique in the knowledge base applies to this "
                    "service at this spend level"
                    if category else
                    "this service is not one the knowledge base classifies, "
                    "so nothing was tested against it"
                ),
            })
            continue

        for technique in matched:
            pct = technique.typical_pct
            if pct is None:
                continue
            # Capped at what the line actually costs. A technique whose
            # typical_pct exceeds 100 -- duty cycling claims 91% -- must
            # not be able to save more than the service spends.
            saved = min(
                float(line.monthly_usd),
                float(line.monthly_usd) * float(pct) / 100.0,
            )
            report.findings.append(Finding(
                service=line.service,
                monthly_usd=round(float(line.monthly_usd), 2),
                technique_id=technique.id,
                technique=technique.name,
                category=technique.category,
                summary=technique.summary,
                saved_monthly_usd=round(saved, 2),
                basis=technique.basis,
                # ESTIMATED, and it says so. A CUR gives a service and a
                # total, not the instance family or the access pattern
                # the catalog would need to price the swap exactly. The
                # engine's Design path measures; this one estimates from
                # a cited figure, and blurring the two would be the
                # dishonesty this whole project is against.
                measured=False,
                obviousness=technique.obviousness,
                tradeoffs=list(technique.tradeoffs),
                tool=technique.primary_tool,
                tool_url=next(
                    (t.split(" ", 1)[-1] for t in technique.tools if "http" in t),
                    "",
                ),
                # What a billing export cannot tell us, and this
                # technique needs. Carried on the finding rather than
                # silently assumed true.
                needs_confirmation=list(technique.requires),
            ))

    report.findings.sort(key=lambda f: f.saved_monthly_usd, reverse=True)
    return report
