"""P3 AUDIT: a billing export in, a waste report out.

The PRD's third product, which did not exist. `backend/audit/` is an
internal scorecard grading the ENGINE against fixtures and reads no
billing data at all; the two were confused at the start of the session.

The property these hold above all others: THE HEADLINE MUST NOT ADD UP
ALTERNATIVES. The first sample bill I ran through this reported a 147.9%
saving, because every applicable technique per service was summed. You
cannot scale a fleet to zero off-peak, rightsize it, AND buy a one-year
commitment on it and collect all three — the second is measured against
the first, and the third against a fleet you have already shrunk.

That is not a new rule. The knowledge base states it: typical_pct values
"are neither independent nor additive, and adding them would invent a
number."
"""

from __future__ import annotations

import pytest

from whichcloud.billing_audit import BillingParseError, audit, parse

AWS_CUR = """lineItem/ProductCode,product/region,product/instanceType,lineItem/UsageAmount,lineItem/UnblendedCost
AmazonEC2,ap-south-1,m5.xlarge,2190,438.20
AmazonRDS,ap-south-1,db.m5.large,730,182.50
AmazonS3,ap-south-1,,4000,100.00
AWSDataTransfer,ap-south-1,,1200,131.16
AmazonQuickSight,ap-south-1,,3,54.00
"""

GCP_EXPORT = """service,location,sku_description,usage_amount,cost
Compute Engine,asia-south1,N2 Instance Core,2190,410.00
Cloud Storage,asia-south1,Standard Storage,4000,88.00
"""

DENSE_CUR = "".join(
    ["lineItem/ProductCode,product/region,product/instanceType,"
     "lineItem/UsageStartDate,lineItem/UsageAmount,lineItem/UnblendedCost\n"]
    + [f"Svc{i % 7},ap-south-1,t{i % 5},2024-03-{(i % 28) + 1:02d}T00:00:00Z,"
       f"10,{(i * 7.3331) % 100:.4f}\n" for i in range(400)]
)

AZURE_EXPORT = """MeterCategory,ResourceLocation,MeterSubCategory,Quantity,CostInBillingCurrency
Virtual Machines,centralindia,Dv3 Series,2190,395.00
Storage,centralindia,Blob Storage,4000,92.00
"""


# ── the honesty property ─────────────────────────────────────────────


def test_the_headline_never_exceeds_the_bill():
    """147.9% was the arithmetic saying the model was wrong."""
    report = audit(AWS_CUR)
    assert report.total_saving_usd <= report.total_monthly_usd
    assert 0 <= report.saving_pct <= 100


def test_techniques_against_one_service_are_alternatives_not_a_list():
    """Several techniques apply to EC2. The headline counts the best one,
    not their sum — they are competing options for the same spend."""
    report = audit(AWS_CUR)
    ec2 = [f for f in report.findings if f.service == "AmazonEC2"]
    assert len(ec2) > 1, "expected several EC2 techniques to compete"
    best = max(f.saved_monthly_usd for f in ec2)
    total_if_summed = sum(f.saved_monthly_usd for f in ec2)
    assert total_if_summed > best  # they really do overlap
    # ...and the headline used the best, not the sum.
    others = {f.service for f in report.findings} - {"AmazonEC2"}
    other_best = sum(
        max(f.saved_monthly_usd for f in report.findings if f.service == s)
        for s in others
    )
    assert report.total_saving_usd == pytest.approx(best + other_best, abs=0.02)


def test_no_finding_saves_more_than_the_service_costs():
    """Duty cycling claims 91%. A technique whose typical_pct exceeds the
    line must not be able to save more than the line spends."""
    report = audit(AWS_CUR)
    for finding in report.findings:
        assert finding.saved_monthly_usd <= finding.monthly_usd


def test_every_finding_says_what_a_bill_cannot_confirm():
    """A CUR gives a service and a total. It does not say whether the
    workload tolerates an interruption or whether downtime matters, and
    every one of those decides whether the technique applies at all."""
    report = audit(AWS_CUR)
    assert report.findings
    assert any(f.needs_confirmation for f in report.findings)


def test_findings_are_marked_estimated_rather_than_measured():
    """The Design path prices a swap against the catalog. This one
    estimates from a cited figure, and blurring the two would be the
    dishonesty the whole project is against."""
    report = audit(AWS_CUR)
    assert all(not f.measured for f in report.findings)
    assert all(f.basis for f in report.findings)


def test_every_finding_carries_its_trade_off():
    report = audit(AWS_CUR)
    for finding in report.findings:
        assert finding.tradeoffs, finding.technique


# ── coverage is reported, not implied ────────────────────────────────


def test_a_service_with_no_technique_is_reported_not_dropped():
    """"We looked and found nothing" and "we did not look" are different
    claims, and dropping the second implies a completeness this does not
    have."""
    report = audit(AWS_CUR)
    reviewed = {r["service"] for r in report.reviewed_no_finding}
    assert "AmazonQuickSight" in reviewed
    for entry in report.reviewed_no_finding:
        assert entry["why"]


# ── reading real exports ─────────────────────────────────────────────


@pytest.mark.parametrize(
    "content", [AWS_CUR, GCP_EXPORT, AZURE_EXPORT],
    ids=["aws-cur", "gcp-export", "azure-export"],
)
def test_all_three_providers_export_formats_are_read(content):
    """A tool that only reads one cloud's column names is a tool for one
    cloud."""
    lines, _warnings = parse(content)
    assert lines
    assert all(line.service for line in lines)
    assert sum(line.monthly_usd for line in lines) > 0


def test_credits_are_skipped_and_the_skip_is_reported():
    """A refund is not spend. Counting it would understate the base the
    savings are measured against -- and silently dropping rows is how a
    total stops reconciling with the file somebody uploaded."""
    with_credit = AWS_CUR + "AmazonEC2,ap-south-1,m5.xlarge,-50,-12.00\n"
    lines, warnings = parse(with_credit)
    assert all(line.monthly_usd >= 0 for line in lines)
    assert any("negative" in w for w in warnings)


def test_a_file_we_cannot_read_refuses_with_a_reason():
    """A report built from misread columns is worse than a refusal,
    because it looks like an answer."""
    with pytest.raises(BillingParseError) as exc:
        parse("colour,animal\nred,fox\n")
    assert "service column" in str(exc.value)
    # The refusal names what it looked for AND what it found.
    assert "colour" in str(exc.value) or "Found:" in str(exc.value)


def test_an_empty_file_refuses():
    with pytest.raises(BillingParseError):
        parse("")


def test_rows_for_one_service_are_folded_into_one_finding():
    """A CUR has thousands of rows for one service. A finding per row is
    noise, not a report."""
    many = "lineItem/ProductCode,lineItem/UnblendedCost\n" + "".join(
        "AmazonEC2,10.00\n" for _ in range(50)
    )
    report = audit(many)
    assert report.lines_read == 50
    assert report.total_monthly_usd == pytest.approx(500.0)
    assert len({f.service for f in report.findings}) == 1


# ── the cost report's axes ───────────────────────────────────────────
#
# The audit collapses the bill to one row per service, because a finding
# per CUR row would be noise. A cost report needs the other axes back,
# and the property that matters is that regrouping NEVER MOVES MONEY:
# whatever you group by, the parts still add up to the bill.


def test_the_breakdown_adds_up_to_the_bill():
    """Exactly, to the cent -- not within a tolerance. Cells rounded
    independently drifted ten cents from the headline on a 1,165-cell
    export, and a report whose rows do not add up to its own total is one
    a reader is right to stop believing."""
    report = audit(AWS_CUR)
    assert round(sum(c.monthly_usd for c in report.breakdown), 2) == report.total_monthly_usd


def test_the_breakdown_adds_up_on_a_bill_wide_enough_to_drift():
    import random

    random.seed(3)
    rows = [
        "lineItem/ProductCode,product/region,product/instanceType,"
        "lineItem/UsageStartDate,lineItem/UsageAmount,lineItem/UnblendedCost"
    ]
    for day in range(1, 29):
        for service in ("AmazonEC2", "AmazonRDS", "AmazonS3", "AWSLambda"):
            for region in ("ap-south-1", "us-east-1", "eu-west-1"):
                rows.append(
                    f"{service},{region},x,2024-03-{day:02d}T00:00:00Z,10,"
                    f"{random.uniform(1, 99):.4f}"
                )
    report = audit("\n".join(rows) + "\n")
    assert len(report.breakdown) > 300
    assert round(sum(c.monthly_usd for c in report.breakdown), 2) == report.total_monthly_usd


def test_apportioning_moves_no_cell_by_more_than_a_cent():
    """The leftover cents have to land somewhere. They may not land in a
    heap: a cell shifted by more than a cent is a misstated line, however
    well the column adds up."""
    from whichcloud.billing_audit import _breakdown, parse

    lines, _ = parse(DENSE_CUR)
    rows, _ = _breakdown(lines)
    exact: dict[tuple, float] = {}
    for line in lines:
        key = (line.service, line.region, line.resource_type, line.day)
        exact[key] = exact.get(key, 0.0) + float(line.monthly_usd)
    for row in rows:
        key = (row.service, row.region, row.resource_type, row.day)
        assert abs(row.monthly_usd - exact[key]) <= 0.0101


def test_one_service_in_two_regions_stays_two_rows():
    """The service rollup kept the FIRST region it saw and added the rest
    of the money to it. That silently relocates spend -- a report grouped
    by region would have shown us-east-1 at zero while it was being
    billed."""
    report = audit(
        "lineItem/ProductCode,product/region,product/instanceType,"
        "lineItem/UsageAmount,lineItem/UnblendedCost\n"
        "AmazonEC2,ap-south-1,m5.xlarge,100,400.00\n"
        "AmazonEC2,us-east-1,m5.xlarge,100,100.00\n"
    )
    by_region = {c.region: c.monthly_usd for c in report.breakdown}
    assert by_region == {"ap-south-1": 400.00, "us-east-1": 100.00}


def test_the_breakdown_is_largest_first():
    costs = [c.monthly_usd for c in audit(AWS_CUR).breakdown]
    assert costs == sorted(costs, reverse=True)


@pytest.mark.parametrize("content", [AWS_CUR, GCP_EXPORT, AZURE_EXPORT])
def test_every_provider_export_yields_a_breakdown(content):
    report = audit(content)
    assert report.breakdown
    assert all(c.service for c in report.breakdown)


# ── the time axis ────────────────────────────────────────────────────

DATED_CUR = """lineItem/ProductCode,product/region,lineItem/UsageStartDate,lineItem/UsageAmount,lineItem/UnblendedCost
AmazonEC2,ap-south-1,2024-03-01T00:00:00Z,100,400.00
AmazonEC2,ap-south-1,2024-03-02T00:00:00Z,100,300.00
AmazonRDS,ap-south-1,2024-03-01T00:00:00Z,100,100.00
"""


def test_costs_are_split_by_day():
    by_day: dict[str, float] = {}
    for cell in audit(DATED_CUR).breakdown:
        by_day[cell.day] = by_day.get(cell.day, 0) + cell.monthly_usd
    assert by_day == {"2024-03-01": 500.00, "2024-03-02": 300.00}


def test_splitting_by_day_still_adds_up_to_the_bill():
    report = audit(DATED_CUR)
    assert round(sum(c.monthly_usd for c in report.breakdown), 2) == pytest.approx(
        report.total_monthly_usd, abs=0.01
    )


def test_an_undated_bill_says_so_rather_than_inventing_a_date():
    """A row dated to today because the export did not say would draw a
    trend that never happened. Empty, and a warning that names the column
    to look for."""
    report = audit(AWS_CUR)
    assert all(c.day == "" for c in report.breakdown)
    assert any("single snapshot" in w for w in report.warnings)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("2024-03-01T00:00:00Z", "2024-03-01"),   # AWS
        ("2024-03-01 00:00:00 UTC", "2024-03-01"),  # GCP
        ("03/01/2024", "2024-03-01"),             # Azure, US-style
        ("3/7/2024", "2024-03-07"),
        ("", ""),
        ("not a date", ""),                       # guessed dates move money
    ],
)
def test_each_provider_writes_the_date_differently(raw, expected):
    from whichcloud.billing_audit import _day

    assert _day(raw) == expected
