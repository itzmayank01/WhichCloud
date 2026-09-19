# WhichCloud

**A Constraint-Driven, LLM-Augmented Framework for Multi-Objective Cloud Architecture Synthesis and Cost Optimization**

Describe your app in plain English and get three costed cloud architectures across
AWS, Google Cloud and Azure: real line-item pricing, the optimizations that apply,
an architecture diagram, and deployable Terraform.

**Live app:** https://whichcloud.vercel.app

![WhichCloud architecture view (AWS, ap-south-1)](docs/screenshots/whichcloud-aws-architecture.png)

---

## How it works

```
Plain English requirement
   → LLM extracts a structured Requirement (or pass it directly, no LLM needed)
   → Engine + Knowledge Base picks services, sizing and optimizations
   → Pricing engine costs every line item from provider price catalogs (Postgres)
   → Three options: Cheapest / Balanced (most reliable) / Most optimized
   → Architecture diagram + Terraform for AWS, GCP and Azure
```

Prices come from the providers' own pricing APIs, ingested into Postgres. They are
computed, not guessed by an LLM.

## Features

| Area | What you get |
|---|---|
| **Price your app** | Three costed architectures per cloud, with a cost breakdown and cost sheet |
| **Architecture** | Region, VPC, subnet and route-table diagram with per-service cost badges |
| **Terraform IaC** | Terraform output for the chosen architecture (AWS, GCP, Azure) |
| **Optimizations** | Knowledge-base techniques (Graviton, spot, scale-to-zero, commitments...) with measured savings |
| **Cost analytics** | Engine output analysed with Amazon Athena and an interactive QuickSight dashboard (below) |
| **FinOps workspace** | Resource inventory, utilization and right-sizing views (UI preview, sample data) |

## Cost analytics: S3 + Athena + QuickSight

The engine's priced output for 13 benchmark workloads (841 line items) is exported to
Amazon S3, queried with SQL in Amazon Athena, and explored in an interactive
Amazon QuickSight dashboard with workload and tier filters and click-to-filter charts.

![QuickSight dashboard overview](analytics/screenshots/quicksight-dashboard-overview.png)
![QuickSight dashboard detail](analytics/screenshots/quicksight-dashboard-details.png)

Key findings:

- Average monthly cost per workload rises from $546 (Cheapest) to $657 (Balanced)
  to $827 (Grow-into): reliability adds about 51% end to end.
- Compute and backups are the two biggest cost drivers.
- 164 of 841 line items cost $0 (free tier or included in another service).

Pipeline, SQL and the dashboard-as-code scripts: [`analytics/`](analytics/README.md)

## FinOps workspace (UI preview)

![FinOps active resources view, sample data](docs/screenshots/finops-resources-sample-data.png)

*The resources shown are built-in sample data used to demonstrate the FinOps views.*

## Testing

- Pytest unit tests across the engine, pricing and generators (`backend/tests/`)
- A regression harness (`backend/tests/run_harness.py`) runs 13 benchmark workloads and
  checks every architecture decision, invariant and cost total against recorded
  golden totals

## Tech stack

- **Backend:** Python, FastAPI, PostgreSQL, Redis, Pytest
- **Frontend:** Next.js, React
- **Cloud & IaC:** AWS, Google Cloud, Azure, Terraform
- **Analytics:** Amazon S3, Amazon Athena, Amazon QuickSight

## Repo structure

```
WhichCloud/
├── backend/          # FastAPI: engine, pricing, generators, tests
├── frontend/         # Next.js: app, results, diagrams, FinOps views
├── knowledge-base/   # Curated optimization techniques and service mappings
├── analytics/        # S3 + Athena + QuickSight cost analytics
├── diagrams/         # Generated reference architecture diagrams
├── infra/            # docker-compose: Postgres, Redis
└── docs/             # PRD, resource map, screenshots
```

## Run locally

See [`backend/README.md`](backend/README.md) for starting Postgres/Redis, ingesting
prices and running the engine.

## Docs

- [Product Requirements (PRD)](docs/PRD.md)
- [Resource Map](docs/RESOURCES.md)
- [Knowledge Base schema](knowledge-base/README.md)
- [Cost analytics](analytics/README.md)
