"""AWS, connected by a role we are trusted to assume.

No access keys. The user creates a role in their own account whose trust
policy names our account as principal and requires an external id we
generated; we call AssumeRole and get credentials that expire in an hour.
They can revoke it from their side at any moment, and there is nothing of
theirs sitting in our database to leak.

THE EXTERNAL ID IS NOT DECORATION. Without it, any customer of ours could
give us the ARN of a role belonging to somebody else who had trusted us,
and we would dutifully assume it and read a stranger's bill -- the
confused deputy problem, which is exactly what AWS documents external ids
to prevent. So it is generated HERE, per connection, from a CSPRNG, and
never accepted from the caller.

Costs are read through Cost Explorer rather than a CUR export in S3. A
CUR means the user configures an export, waits up to 24 hours for the
first file, and grants us bucket access; Cost Explorer is one API call
against data they already have, and it returns amortized and blended
alongside unblended, which is precisely what a CUR would have been parsed
for. It bills $0.01 per request, which is disclosed rather than hidden.
"""

from __future__ import annotations

import secrets as _random
from datetime import date, timedelta
from decimal import Decimal
from typing import Iterator

from .models import BillingFact, Setup, SetupStep, VerifyResult

#: The AWS account this service runs as. The user's trust policy has to
#: name it, so it has to be configured for the instructions to be
#: correct -- and instructions containing a placeholder are worse than no
#: instructions, because they look complete and fail at the last step.
import os

OUR_ACCOUNT_ID = os.getenv("WHICHCLOUD_AWS_ACCOUNT_ID", "")

#: What we ask for. Read-only, and narrow: Cost Explorer and the identity
#: call used to prove the role works. Nothing that can see a resource,
#: read an object, or change anything.
POLICY_ACTIONS = ["ce:GetCostAndUsage", "ce:GetDimensionValues"]


def new_external_id() -> str:
    """A per-connection secret the user pastes into their trust policy.

    Generated here and never accepted from the caller: an external id the
    caller chooses is one an attacker chooses, which defeats the entire
    point of having one.
    """
    return f"whichcloud-{_random.token_urlsafe(24)}"


def trust_policy(external_id: str) -> str:
    import json

    account = OUR_ACCOUNT_ID or "<WHICHCLOUD_AWS_ACCOUNT_ID not configured>"
    return json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"AWS": f"arn:aws:iam::{account}:root"},
                    "Action": "sts:AssumeRole",
                    "Condition": {"StringEquals": {"sts:ExternalId": external_id}},
                }
            ],
        },
        indent=2,
    )


def permission_policy() -> str:
    import json

    return json.dumps(
        {
            "Version": "2012-10-17",
            "Statement": [
                {"Effect": "Allow", "Action": POLICY_ACTIONS, "Resource": "*"}
            ],
        },
        indent=2,
    )


def setup(config: dict) -> Setup:
    external_id = config.get("external_id", "")
    return Setup(
        grants=(
            "Read-only access to your AWS Cost Explorer totals. It cannot "
            "see your resources, read your data, or change anything, and "
            "you can revoke it by deleting the role."
        ),
        stores_secret=False,
        steps=[
            SetupStep(
                title="Create a role in your AWS account",
                body=(
                    "IAM → Roles → Create role → Custom trust policy. Paste "
                    "this as the trust policy. The external id is unique to "
                    "this connection and is what stops anyone else's role "
                    "ARN from being used against your account."
                ),
                snippet=trust_policy(external_id),
                language="json",
            ),
            SetupStep(
                title="Attach these permissions",
                body=(
                    "Create an inline policy on the role. This is everything "
                    "we ask for — Cost Explorer reads, nothing else."
                ),
                snippet=permission_policy(),
                language="json",
            ),
            SetupStep(
                title="Turn Cost Explorer on, if it is not already",
                body=(
                    "Billing → Cost Explorer → Enable. The first enablement "
                    "can take up to 24 hours to backfill history. Queries "
                    "cost $0.01 each; we make one per sync."
                ),
            ),
            SetupStep(
                title="Paste the role ARN back here",
                body="Copy it from the role's summary page.",
                snippet="arn:aws:iam::<your-account-id>:role/WhichCloudCostRole",
            ),
        ],
    )


def _session(config: dict):
    """Short-lived credentials from the user's role, or a clear failure."""
    import boto3
    from botocore.exceptions import ClientError

    role_arn = (config.get("role_arn") or "").strip()
    external_id = (config.get("external_id") or "").strip()
    if not role_arn:
        raise ValueError("No role ARN has been set for this connection.")
    if not external_id:
        raise ValueError("This connection has no external id, so it cannot be assumed.")

    sts = boto3.client("sts")
    try:
        assumed = sts.assume_role(
            RoleArn=role_arn,
            RoleSessionName="whichcloud-cost-sync",
            ExternalId=external_id,
            DurationSeconds=3600,
        )
    except ClientError as exc:
        raise ValueError(_explain(exc)) from exc

    creds = assumed["Credentials"]
    return boto3.Session(
        aws_access_key_id=creds["AccessKeyId"],
        aws_secret_access_key=creds["SecretAccessKey"],
        aws_session_token=creds["SessionToken"],
    )


def _explain(exc) -> str:
    """AWS's errors, turned into the thing to go and fix.

    `AccessDenied` on AssumeRole has four common causes that need four
    different fixes, and the raw message distinguishes none of them.
    """
    code = exc.response.get("Error", {}).get("Code", "")
    if code == "AccessDenied":
        return (
            "AWS refused the role. Usually one of: the trust policy does "
            "not name our account, the external id does not match, the "
            "role was created in a different account than the ARN says, "
            "or the role was only just created and has not propagated "
            "yet — that one clears within a minute."
        )
    if code in ("InvalidClientTokenId", "SignatureDoesNotMatch"):
        return (
            "This deployment's own AWS credentials are missing or wrong, "
            "so it cannot assume anyone's role. That is our side, not "
            "yours."
        )
    if code == "DataUnavailableException":
        return (
            "Cost Explorer has no data for this account yet. It takes up "
            "to 24 hours after first enabling it."
        )
    return f"AWS refused: {exc.response.get('Error', {}).get('Message', code)}"


def verify(config: dict, secret: str = "") -> VerifyResult:
    try:
        session = _session(config)
        who = session.client("sts").get_caller_identity()
    except ValueError as exc:
        return VerifyResult(ok=False, message=str(exc))
    except Exception as exc:                      # network, clock skew, bad ARN shape
        return VerifyResult(ok=False, message=f"Could not reach AWS: {exc}")

    return VerifyResult(
        ok=True,
        account_id=who.get("Account", ""),
        message=f"Assumed {who.get('Arn', 'the role')} successfully.",
    )


#: Cost Explorer groups by at most two dimensions per call, so this is
#: the pair worth spending them on: what, and where.
_GROUPS = [
    {"Type": "DIMENSION", "Key": "SERVICE"},
    {"Type": "DIMENSION", "Key": "REGION"},
]

#: Cost Explorer's own name for a line's purchase type.
_PURCHASE = {
    "On Demand": "on_demand", "OnDemand": "on_demand",
    "Reserved": "reserved", "Standard Reserved Instances": "reserved",
    "Savings Plan": "savings_plan", "SavingsPlans": "savings_plan",
    "Spot": "spot", "Spot Instances": "spot",
}


def fetch(config: dict, secret: str, start: date, end: date) -> Iterator[BillingFact]:
    """Daily costs between start and end, end exclusive.

    Asks for all three cost metrics in one call. Cost Explorer returns
    them per group, which is what makes the amortised/unblended toggle in
    the report a read rather than an estimate.
    """
    client = _session(config).client("ce")

    token = None
    while True:
        request = {
            "TimePeriod": {"Start": start.isoformat(), "End": end.isoformat()},
            "Granularity": "DAILY",
            "Metrics": ["UnblendedCost", "AmortizedCost", "BlendedCost", "UsageQuantity"],
            "GroupBy": _GROUPS,
        }
        if token:
            request["NextPageToken"] = token
        page = client.get_cost_and_usage(**request)

        for period in page.get("ResultsByTime", []):
            day = date.fromisoformat(period["TimePeriod"]["Start"])
            for cell in period.get("Groups", []):
                service, region = (cell.get("Keys", []) + ["", ""])[:2]
                metrics = cell.get("Metrics", {})
                fact = BillingFact(
                    usage_date=day,
                    service=service,
                    region=region,
                    unblended_usd=_amount(metrics.get("UnblendedCost")),
                    amortized_usd=_amount(metrics.get("AmortizedCost")),
                    blended_usd=_amount(metrics.get("BlendedCost")),
                    usage_amount=_amount(metrics.get("UsageQuantity")),
                    usage_unit=(metrics.get("UsageQuantity") or {}).get("Unit", ""),
                )
                # A day with no spend in a service is a row Cost Explorer
                # still returns. Keeping them would triple the table for
                # no added truth.
                if fact.unblended_usd or fact.amortized_usd:
                    yield fact

        token = page.get("NextPageToken")
        if not token:
            break


def _amount(metric: dict | None) -> Decimal:
    if not metric:
        return Decimal(0)
    try:
        return Decimal(str(metric.get("Amount", "0")))
    except Exception:
        return Decimal(0)


def default_window() -> tuple[date, date]:
    """The last 90 days. Cost Explorer keeps 12 months of daily data, but
    a first sync that pulls all of it is slow and mostly unread; the
    report's own range control asks for more when it needs it."""
    today = date.today()
    return today - timedelta(days=90), today + timedelta(days=1)
