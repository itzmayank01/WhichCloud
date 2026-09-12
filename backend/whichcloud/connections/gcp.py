"""GCP, connected by granting our service account a read.

The same shape as AWS and for the same reason: nothing of theirs is
stored. They add our service account as a reader on the BigQuery dataset
their billing export writes to, and revoke it by removing that binding.

GCP's costs do not come from an API the way AWS's and Azure's do. Billing
data is exported to BigQuery by the user, so this adapter is a SQL client
rather than a cost client -- and the shape of the export is fixed by
Google, which is what makes querying it safe to do generically.

Credits are an array on each row, not a column. A GCP bill read without
unnesting them overstates spend by whatever the customer negotiated,
which for a committed-use customer is the entire point of their discount.
"""

from __future__ import annotations

import json
import os
from datetime import date, timedelta
from decimal import Decimal
from typing import Iterator

import httpx

from .models import BillingFact, Setup, SetupStep, VerifyResult

#: Our service account's key, as the JSON Google hands out. The email
#: inside it is what the user grants -- so without it, the instructions
#: cannot even be written.
SA_JSON_ENV = "WHICHCLOUD_GCP_SA_JSON"

_SCOPE = "https://www.googleapis.com/auth/bigquery"
_TOKEN_URL = "https://oauth2.googleapis.com/token"


def _service_account() -> dict:
    raw = os.getenv(SA_JSON_ENV, "").strip()
    if not raw:
        raise ValueError(
            f"{SA_JSON_ENV} is not set, so this deployment has no identity "
            "for a customer to grant access to. GCP connections cannot be "
            "offered until it is."
        )
    # Either the JSON itself or a path to it: both are common in
    # deployment, and guessing wrong produces a confusing parse error.
    if raw.startswith("{"):
        return json.loads(raw)
    with open(raw) as handle:
        return json.load(handle)


def our_service_account_email() -> str:
    try:
        return _service_account().get("client_email", "")
    except Exception:
        return ""


def _access_token() -> str:
    """A bearer token, via the JWT grant.

    Signed here rather than through google-auth: the dependency exists to
    do exactly this one exchange, and pulling the whole client library in
    for it would be the largest thing in the image.
    """
    import time

    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding

    account = _service_account()
    now = int(time.time())
    header = {"alg": "RS256", "typ": "JWT", "kid": account.get("private_key_id", "")}
    claims = {
        "iss": account["client_email"],
        "scope": _SCOPE,
        "aud": _TOKEN_URL,
        "iat": now,
        "exp": now + 3600,
    }

    def segment(payload: dict) -> bytes:
        import base64

        return base64.urlsafe_b64encode(
            json.dumps(payload, separators=(",", ":")).encode()
        ).rstrip(b"=")

    signing_input = segment(header) + b"." + segment(claims)
    key = serialization.load_pem_private_key(
        account["private_key"].encode(), password=None
    )
    signature = key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())

    import base64

    assertion = (
        signing_input + b"." + base64.urlsafe_b64encode(signature).rstrip(b"=")
    ).decode()

    response = httpx.post(
        _TOKEN_URL,
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": assertion,
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["access_token"]


def setup(config: dict) -> Setup:
    email = our_service_account_email() or f"<{SA_JSON_ENV} not configured>"
    project = config.get("project_id") or "<your-project>"
    dataset = config.get("dataset") or "<your-billing-dataset>"
    return Setup(
        grants=(
            "Read-only access to the BigQuery dataset your billing export "
            "writes to. Nothing else in your project is reachable, and "
            "removing the IAM binding revokes it."
        ),
        stores_secret=False,
        steps=[
            SetupStep(
                title="Export billing to BigQuery, if you have not",
                body=(
                    "Billing → Billing export → BigQuery export → edit the "
                    "Detailed usage cost export. Detailed rather than "
                    "standard: the standard export has no resource-level "
                    "detail, so a report built on it cannot break a service "
                    "down. Data starts arriving within a few hours and is "
                    "not backfilled — history begins when you enable it."
                ),
            ),
            SetupStep(
                title="Grant our service account a read",
                body=(
                    "Run this against the project holding the export. It "
                    "grants read on that one dataset, not the project."
                ),
                snippet=(
                    f"bq add-iam-policy-binding \\\n"
                    f"  --member='serviceAccount:{email}' \\\n"
                    f"  --role='roles/bigquery.dataViewer' \\\n"
                    f"  {project}:{dataset}\n\n"
                    f"# BigQuery also needs permission to RUN a job in the\n"
                    f"# project it reads from:\n"
                    f"gcloud projects add-iam-policy-binding {project} \\\n"
                    f"  --member='serviceAccount:{email}' \\\n"
                    f"  --role='roles/bigquery.jobUser'"
                ),
                language="bash",
            ),
            SetupStep(
                title="Tell us where it landed",
                body=(
                    "The project id, the dataset, and the export table — "
                    "the detailed table is named gcp_billing_export_resource_v1_*."
                ),
            ),
        ],
    )


def _table(config: dict) -> str:
    project = (config.get("project_id") or "").strip()
    dataset = (config.get("dataset") or "").strip()
    table = (config.get("table") or "").strip()
    if not (project and dataset and table):
        raise ValueError(
            "A GCP connection needs a project id, a dataset and the export "
            "table name."
        )
    # Backticked and validated rather than interpolated raw: this string
    # goes into SQL, and a table name is the one part of this query a
    # caller influences.
    for part in (project, dataset, table):
        if not all(ch.isalnum() or ch in "-_:." for ch in part):
            raise ValueError(f"{part!r} is not a valid BigQuery identifier.")
    return f"`{project}.{dataset}.{table}`"


def _query(config: dict, sql: str, params: list | None = None) -> list[dict]:
    token = _access_token()
    project = config["project_id"]
    response = httpx.post(
        f"https://bigquery.googleapis.com/bigquery/v2/projects/{project}/queries",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "query": sql,
            "useLegacySql": False,
            "timeoutMs": 120000,
            "queryParameters": params or [],
        },
        timeout=180,
    )
    if response.status_code >= 400:
        raise ValueError(_explain(response))
    body = response.json()

    # A query that exceeds timeoutMs returns not-complete rather than
    # failing; treating that as "no rows" would silently report a zero
    # bill, which is the worst possible way to be wrong here.
    if not body.get("jobComplete", False):
        raise ValueError(
            "BigQuery did not finish this query within two minutes. The "
            "billing export may be very large; try a shorter window."
        )

    fields = [f["name"] for f in body.get("schema", {}).get("fields", [])]
    rows = []
    for row in body.get("rows", []):
        values = [cell.get("v") for cell in row.get("f", [])]
        rows.append(dict(zip(fields, values)))
    return rows


def _explain(response: httpx.Response) -> str:
    try:
        error = response.json().get("error", {})
        message = error.get("message", "")
    except Exception:
        message = response.text[:200]
    if response.status_code in (401, 403):
        return (
            "GCP refused the read. Usually the IAM binding has not been "
            "added yet, was added to the project instead of the dataset, "
            f"or is missing roles/bigquery.jobUser. ({message})"
        )
    if response.status_code == 404:
        return (
            "That project, dataset or table does not exist. The detailed "
            f"export table is named gcp_billing_export_resource_v1_*. ({message})"
        )
    return f"BigQuery refused: {message}"


def verify(config: dict, secret: str = "") -> VerifyResult:
    try:
        table = _table(config)
        rows = _query(
            config,
            f"SELECT COUNT(*) AS n, MAX(DATE(usage_start_time)) AS latest FROM {table}",
        )
    except ValueError as exc:
        return VerifyResult(ok=False, message=str(exc))
    except Exception as exc:
        return VerifyResult(ok=False, message=f"Could not reach BigQuery: {exc}")

    if not rows:
        return VerifyResult(ok=False, message="The export table is empty.")
    latest = rows[0].get("latest") or "no rows yet"
    return VerifyResult(
        ok=True,
        account_id=config.get("project_id", ""),
        message=f"Read the export. Latest usage date: {latest}.",
    )


#: Credits are an array per row. Unnesting and summing them is the
#: difference between a list price and what the customer actually pays.
_SQL = """
SELECT
  DATE(usage_start_time)                        AS usage_date,
  service.description                           AS service,
  IFNULL(location.region, '')                   AS region,
  IFNULL(sku.description, '')                   AS resource_type,
  IFNULL(project.id, '')                        AS account_id,
  SUM(cost)                                     AS cost,
  SUM(IFNULL((SELECT SUM(c.amount) FROM UNNEST(credits) c), 0)) AS credits,
  SUM(IFNULL(usage.amount, 0))                  AS usage_amount,
  ANY_VALUE(IFNULL(usage.unit, ''))             AS usage_unit
FROM {table}
WHERE DATE(usage_start_time) >= @start
  AND DATE(usage_start_time) <  @end
GROUP BY usage_date, service, region, resource_type, account_id
HAVING cost != 0 OR credits != 0
"""


def fetch(config: dict, secret: str, start: date, end: date) -> Iterator[BillingFact]:
    sql = _SQL.format(table=_table(config))
    params = [
        {"name": "start", "parameterType": {"type": "DATE"},
         "parameterValue": {"value": start.isoformat()}},
        {"name": "end", "parameterType": {"type": "DATE"},
         "parameterValue": {"value": end.isoformat()}},
    ]
    for row in _query(config, sql, params):
        cost = _decimal(row.get("cost"))
        credits = _decimal(row.get("credits"))
        yield BillingFact(
            usage_date=date.fromisoformat(row["usage_date"]),
            service=row.get("service") or "",
            region=row.get("region") or "",
            resource_type=row.get("resource_type") or "",
            account_id=row.get("account_id") or "",
            unblended_usd=cost,
            # GCP has no separate amortised figure: a committed-use
            # discount already arrives as a credit on the line rather
            # than as an up-front charge to spread. So amortised is cost
            # net of credits, which is what the customer actually pays.
            amortized_usd=cost + credits,
            blended_usd=cost,
            # Credits arrive negative from GCP; stored positive, because
            # "credits: -$400" reads as a charge in a report.
            credit_usd=-credits,
            usage_amount=_decimal(row.get("usage_amount")),
            usage_unit=row.get("usage_unit") or "",
        )


def _decimal(value) -> Decimal:
    if value in (None, ""):
        return Decimal(0)
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal(0)


def default_window() -> tuple[date, date]:
    today = date.today()
    return today - timedelta(days=90), today + timedelta(days=1)
