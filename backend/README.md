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

# 3. THE ENGINE — plain English in, three priced architectures out
export ANTHROPIC_API_KEY=...          # only this step needs a key
.venv/bin/python scripts/recommend.py --describe "an e-commerce site for 50k users, spiky weekend traffic, \$400/mo"

#    ...or skip Claude and pass the requirement directly
.venv/bin/python scripts/recommend.py --goal "e-commerce site" --scale medium --spiky --budget 400
.venv/bin/python scripts/recommend.py --workload batch --interruptible --scale high

# 4. price a hand-written architecture directly
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
├── intake.py               # plain English → Requirement (Claude, structured output)
├── requirements.py         # Requirement — the contract with the front end
├── knowledge.py            # loads knowledge-base/*.yaml, matches techniques
├── engine.py               # requirements → sized shapes → techniques → priced
├── estimator.py            # architecture → itemised monthly bill, cross-cloud compare
└── pricing/
    ├── models.py           # PricePoint, ComputeQuery, neutral region mapping
    ├── aws.py              # EC2, RDS, S3, egress, ALB
    ├── azure.py            # VMs, PostgreSQL, Blob, egress, Load Balancer
    └── store.py            # Postgres catalog: upsert, query, prune
scripts/
├── recommend.py            # the engine, end to end (--describe for plain English)
├── eval_intake.py          # scores intake extraction against hand-written fixtures
├── ingest_prices.py        # provider APIs → price_points table
├── estimate_architecture.py
├── validate_pricing.py     # cross-source validation
├── show.py                 # inspect the catalog and its provenance
└── verify_pricing.py
```

## How the engine reports savings

A technique never asserts a saving. It declares an `effect` (use arm64) and a
`counterfactual` (use x86_64). The engine prices **both** against the real
catalog and reports the difference:

```
✓ ARM-based compute            −$6.57/mo   vs t3a.xlarge
✓ Spot / preemptible capacity −$36.21/mo   vs t4g.xlarge
  measured saving              $42.78      (32% vs untuned)
```

Nothing sums the `typical_pct` values from the knowledge base — those are
neither independent nor additive, and adding them would invent a number.
Techniques that cannot be modelled (zram, whose benefit depends on how
compressible a workload's memory is) are surfaced as advice and explicitly
excluded from the total.

**Sizing is the one heuristic part.** Prices are fetched and validated; the
rules turning "medium, spiky" into "3 × 2 vCPU" are conventional judgement,
collected in `BASE_SIZING`/`DB_SIZING` so they can be argued with and tuned.
Every output says so.

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
- **No hand-written data.** Specs come from real machine catalogs
  (`specs.py`), never from a table typed from memory. A SKU absent from the
  catalog is skipped, never guessed.
- **Allow-lists, not deny-lists**, when selecting provider meters. One SKU can
  carry a dozen meters; naming rules miss the odd one out.
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
| **GCP is compute-only** | Storage, egress and Cloud SQL need a Catalog API key. GCP estimates are correctly reported incomplete |
| **GCP is unvalidated** | No second credential-free source exists to cross-check against |
| **GCP architecture is inferred** | From Google's documented family naming (`t2a`/`c4a` = Arm). The only inference left in the layer; asserted by tests |
| **Spot feed is undated** | AWS's public spot feed carries no timestamp. Fine for ranking spot vs on-demand, not billing-grade |
| **Azure HA is derived** | Azure publishes no HA meter; we bill the standby as a second instance (2x) and label it derived |
| **List prices only** | No committed-use, savings plans, or reserved rates |
| **No Redis caching yet** | Container runs; the lookup path does not use it |

## Validation

`scripts/validate_pricing.py` checks each provider against an **independent
second source** — not against itself.

```
AWS — our catalog (ec2instances.info) vs AWS Price List CSV
  compared        807 types      exact match  807   100.0%   ✓

Azure — our catalog (Retail Prices API) vs Vantage catalog
  compared        928 types      exact match  923    99.5%   ✓
```

AWS agrees **exactly**, with no coverage gap in either direction. Azure agrees
on 923 of 928; the five outliers are legacy families (`m64`, `f2`, `f4`, `f8`,
`m128`) where the two feeds genuinely differ.

The PRD's ±20% accuracy target is met at **0% drift on AWS and 0.5% on Azure**.

GCP has no second credential-free source, so it is **not validated** — stated
plainly rather than implied.

### What validation caught

Cross-checking is not ceremony. It found a live bug: a single Azure `armSkuName`
carries up to a dozen meters, and the Windows-priced **"Cloud Services"** meter
contains no distinguishing word. Selecting it made 36 machine types read
**2.65× too expensive** ($0.148 vs $0.0556 for `D2as_v5`). Agreement went from
96.3% to 99.5% once the selector became an allow-list. There is a regression
test for it.

## Plain-English intake

`intake.py` is a thin adapter: Claude reads a description and fills the same
`Requirement` the CLI flags build. Nothing downstream knows which one happened.

Two things make it safe to trust:

- **The model reports what it guessed.** Every draft carries an `assumed` list
  and one `clarifying_question`, so an inferred budget is visibly inferred
  rather than presented as fact.
- **Validation is ours, not the model's.** Structured outputs guarantee the
  shape; `Requirement` rejects the values. A hallucinated field fails at the
  boundary instead of becoming a confidently wrong architecture.

It is the only component that needs an API key, and the only one that costs
money per call. Everything else runs offline.

```bash
.venv/bin/python scripts/eval_intake.py          # score extraction, field by field
```

## Tests

```bash
.venv/bin/python -m pytest tests/ -q     # 82 passed
```

No test calls the Anthropic API — the model's judgement is measured by
`eval_intake.py`; the suite covers the mapping, validation, and failure paths
around it.

They assert the rules above: no hand-written spec tables, incomplete estimates
never win a comparison, undescribed machines never match a requirement, and the
Cloud Services meter stays rejected.

## Next

1. GCP Catalog API for storage/egress/Cloud SQL (needs a key)
2. Redis on the lookup path
3. Feed the estimator from the optimization knowledge base
4. The engine: requirements -> architecture selection
