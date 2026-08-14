# Backend — pricing engine

Phase 1: prove WhichCloud can price real cloud architectures with **no cloud
account, no API key, and no paid service.** Everything else depends on this.

**Status: working.** Prices are ingested into Postgres and a complete
architecture can be costed and compared across clouds.

## Run it

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -e .

# 1. start Postgres + Redis
docker compose -f ../infra/docker-compose.yml up -d

# 2. pull provider prices into the catalog (idempotent, re-run anytime)
.venv/bin/python scripts/ingest_prices.py --region india

# 3. price three architectures and compare clouds
.venv/bin/python scripts/estimate_architecture.py

# (optional) single-machine cross-cloud check
.venv/bin/python scripts/verify_pricing.py --region india --vcpu 2 --memory 4
```

First run downloads a ~300 MB EC2 catalog to `~/.cache/whichcloud/`. After that
it is seconds.

### Verified output (2026-08-14)

```
Balanced   3× 2vCPU/8GB arm64

  AWS    ap-south-1
    Compute × 3        t4g.large           $98.11   2190 × $0.0448/hour
    Database           db.t4g.large       $121.91    730 × $0.1670/hour
    Object storage     s3:general-purpose   $5.00    200 × $0.0250/GB-month
    Egress             egress:internet     $54.65    500 × $0.1093/GB
    Load balancer      alb                 $17.45    730 × $0.0239/hour
    Total                                 $297.12

  AZURE  centralindia                     $338.14
  → AWS is cheaper by $41.02/mo (12%)
```

## What exists

```
whichcloud/
├── estimator.py            # architecture → itemised monthly bill, cross-cloud compare
└── pricing/
    ├── models.py           # PricePoint, ComputeQuery, neutral region mapping
    ├── aws.py              # EC2, RDS, S3, egress, ALB
    ├── azure.py            # VMs, PostgreSQL, Blob, egress, Load Balancer
    └── store.py            # Postgres catalog: upsert, query, prune
scripts/
├── ingest_prices.py        # provider APIs → price_points table
├── estimate_architecture.py
└── verify_pricing.py
```

Every adapter returns a `PricePoint`, so the engine never learns a provider's
quirks and adding GCP touches no other file.

## Design rules the code enforces

- **Never invent a price.** Anything unpriceable lands in `Estimate.missing` and
  the estimate is marked incomplete.
- **Incomplete estimates never win a comparison.** A total missing its database
  is not cheaper, it is wrong — `compare()` sorts incomplete last regardless of
  price.
- **Sensible defaults, not cheapest.** S3 archive tiers undercut Standard 5×,
  but a web app's assets do not live there. `DEFAULT_SKUS` names the honest
  default per category.
- **Unmapped SKUs are skipped, never guessed.** Azure publishes no vCPU/memory,
  so `AZURE_VM_SPECS` / `AZURE_DB_SPECS` carry curated specs.
- **Stale rows are pruned.** Every ingest deletes rows it did not refresh, so a
  retired SKU cannot be quoted later.
- **Multi-AZ is a real SKU**, not a multiplier — the reliable option gets a
  published price.

## Where prices come from

| Source | Auth | Used for |
|---|---|---|
| [ec2instances.info](https://instances.vantage.sh/instances.json) | none | EC2 compute (1,406 instances, specs + prices) |
| [Azure Retail Prices API](https://prices.azure.com/api/retail/prices) | **none** | Azure VMs, PostgreSQL, Blob, egress, LB |
| [AWS Price List Bulk API](https://pricing.us-east-1.amazonaws.com) | none | RDS, S3, data transfer, ALB |
| GCP Cloud Billing Catalog API | API key | not yet wired |

Payload sizes for `ap-south-1`: EC2 291 MB, RDS 17.6 MB, S3 0.5 MB, instances
catalog 298 MB. Ingest-once-then-cache, never live lookups — which is what
Postgres and Redis are for.

## ⚠️ Why not Infracost

The original plan was Infracost + a self-hosted `cloud-pricing-api`. Both changed:

| What we assumed | What is actually true (checked 2026-08-14) |
|---|---|
| `infracost breakdown` prices raw HCL with no credentials | `breakdown` is **deprecated** in v2.16; `infracost scan` **forces an interactive browser login** |
| `infracost/cloud-pricing-api` can be self-hosted free | Repo returns **404**; self-hosting moved to a **paid plan** |

Its hosted free tier (1,000 runs/month) still works but needs an account and
makes our core capability depend on someone else's pricing.

## Known gaps

| Gap | Impact |
|---|---|
| **GCP not wired** | Two of three clouds. Needs a free API key |
| **No spot pricing** | ec2instances.info has no spot rates; AWS's spot feed needs credentials. The engine must not claim a spot saving it cannot price |
| **Azure HA Postgres unpriced** | Zone-redundant HA is a separate meter. "Most reliable" on Azure is correctly reported incomplete |
| **Azure specs hand-curated** | 25 VM + 13 DB SKUs mapped. Unmapped SKUs are skipped |
| **List prices only** | No committed-use, savings plans, or reserved rates |
| **Not validated** | The PRD's ±20% accuracy target is unproven against provider calculators |
| **No Redis caching yet** | Container runs; the lookup path does not use it |

## Next

1. GCP adapter
2. Validate totals against the AWS and Azure calculators
3. Redis on the lookup path
4. Feed the estimator from the optimization knowledge base
