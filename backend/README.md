# Backend — pricing layer

Phase 1 of the build: prove WhichCloud can get **real cloud prices with no cloud
account, no API key, and no paid service.** Everything else depends on this.

## Run the verification

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/python scripts/verify_pricing.py --region india --vcpu 2 --memory 4
```

First run downloads a ~300 MB EC2 catalog to `~/.cache/whichcloud/` and takes a
couple of minutes. After that it is instant.

### Verified output (2026-08-14)

```
1. Cheapest machine per provider
  AWS        t4g.medium      2vCPU  4GB  ARM   $16.35/mo
  Azure      Standard_B2s    2vCPU  4GB  x86   $32.70/mo
  → AWS wins at $16.35/mo — 50% less than Azure

2. Graviton / ARM saving, measured on AWS
  x86        t3a.medium      2vCPU  4GB  x86   $17.96/mo
  ARM        t4g.medium      2vCPU  4GB  ARM   $16.35/mo
  → ARM is $1.61/mo cheaper — 8.9% saving
```

## ⚠️ Why we are not using Infracost

The original plan was Infracost + a self-hosted `cloud-pricing-api`. Both changed:

| What we assumed | What is actually true (checked 2026-08-14) |
|---|---|
| `infracost breakdown` prices raw HCL with no credentials | `breakdown` is **deprecated** in v2. `infracost scan` **forces an interactive browser login** before doing anything |
| `infracost/cloud-pricing-api` can be self-hosted free | The repo returns **404**. Infracost moved self-hosting to a **paid plan**. Only stale third-party forks remain |

Infracost's hosted free tier (1,000 runs/month) still exists and is fine for a
student project — but it requires signing up for an account, and it makes the
project's core capability depend on someone else's pricing.

**Decision: build our own pricing layer from the providers' public APIs.** It
removes the dependency, has no run limits, costs nothing, and is a real
engineering contribution rather than a wrapper around someone else's tool.

## Where prices come from

| Source | Auth | Verified | Used for |
|---|---|---|---|
| [ec2instances.info](https://instances.vantage.sh/instances.json) (Vantage, open source) | none | ✅ 1,406 instances, specs + per-region prices | EC2 compute |
| [Azure Retail Prices API](https://prices.azure.com/api/retail/prices) | **none** | ✅ live, OData-filterable | Azure VMs |
| [AWS Price List Bulk API](https://pricing.us-east-1.amazonaws.com) | none | ✅ 106 regions | RDS, S3, everything else |
| GCP Cloud Billing Catalog API | API key | not yet wired | GCP (Phase 4) |

### Payload sizes (why we cache)

Measured for `ap-south-1`:

- `AmazonEC2` — **291 MB**
- `AmazonRDS` — 17.6 MB
- `AmazonS3` — 0.5 MB
- ec2instances.info full catalog — 298 MB

These are ingest-once-then-cache sources, never live lookups. That is what
Postgres and Redis in `infra/` are for.

## Layout

```
backend/
├── pyproject.toml
├── whichcloud/
│   └── pricing/
│       ├── models.py    # PricePoint, ComputeQuery, region mapping
│       ├── aws.py       # ec2instances.info + Price List Bulk API
│       └── azure.py     # Retail Prices API + VM spec table
└── scripts/
    └── verify_pricing.py
```

Every adapter returns a `PricePoint`, so the engine never learns a provider's
quirks and adding GCP touches no other file.

## Known gaps

- **Azure specs are hand-curated.** The Retail Prices API returns no vCPU/memory,
  so `AZURE_VM_SPECS` in `azure.py` maps the families we recommend. Unmapped SKUs
  are skipped, never guessed. Extend deliberately.
- **GCP is not wired up.** Its catalog API needs a (free) API key.
- **List prices only.** No committed-use, savings plans, or negotiated rates.
- **Nothing is in Postgres yet.** The adapters return objects; the ingest job that
  writes them to `price_points` is the next task.

## Next

1. Ingest job: adapters → `price_points` table
2. Redis-backed lookup so the engine queries the DB, not the internet
3. GCP adapter
4. Storage/network/database categories, not just compute
