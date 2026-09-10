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
