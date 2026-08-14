# Resource Map

Every implementation part → the exact resource we use and why.

---

## 1. Frontend

| Part | Resource | Why |
|---|---|---|
| Web app | Next.js (React) + TypeScript | Chat + form + results in one; easy Vercel deploy |
| Styling | Tailwind CSS + shadcn/ui | Fast, professional look with zero design work |
| Cost charts / what-if sliders | Recharts | Simple React charting for cost comparison |
| Diagram display | React Flow (interactive) or static PNG | React Flow if drag/edit needed; static fine for v1 |

## 2. Requirement Intake (plain English → structured JSON)

| Part | Resource | Why |
|---|---|---|
| Reasoning LLM | Claude API (`claude-sonnet-5`) | Best structured-output + tool use; fast, cheap enough for v1 |
| Structured extraction | Claude tool-use / JSON schema output | Guarantees a valid Requirement Object |
| Validation | Pydantic | Enforces schema server-side before it hits the engine |

## 3. Knowledge Base ⭐ THE MOAT

| Part | Resource | Why |
|---|---|---|
| Storage format | YAML files in Git | Human-curated, version-controlled, reviewable |
| Database | PostgreSQL + `pgvector` | Structured data *and* embeddings in one DB |
| Retrieval (RAG) | pgvector + embeddings | Simpler than Pinecone/Chroma; one less service |
| Source material | Karpenter, KEDA, Valkey, zram/zswap, Firecracker, Cloudflare R2, `awesome-finops` | Mine these to build 20–30 technique entries |

## 4. Architecture Synthesis Engine

| Part | Resource | Why |
|---|---|---|
| Reasoning | Claude API + RAG over knowledge base | Grounded recommendations, not hallucinations |
| Service mapping (AWS↔GCP↔Azure) | Our own YAML mapping table | Small, high-value, hand-built |
| Multi-objective ranking | Custom Python scoring (cost/latency/reliability) | Weighted Pareto filter — no heavy solver needed for v1 |

## 5. Terraform / IaC Generation

| Part | Resource | Why |
|---|---|---|
| Vetted modules | `terraform-aws-modules` (+ GCP/Azure equivalents) | LLM fills proven modules instead of raw HCL — fewer broken outputs |
| Templating | Jinja2 | Standard Python templating |
| Validation | `terraform validate` / `tflint` | Catch broken output before showing the user |

## 6. Cost Engine ⭐ CREDIBILITY

| Part | Resource | Why |
|---|---|---|
| **Pricing a design** | [Infracost](https://github.com/infracost/infracost) (Apache-2.0) | Parses HCL directly — **no cloud credentials, no `terraform plan` needed**. Critical: our users have no cloud account |
| **Pricing database** | [infracost/cloud-pricing-api](https://github.com/infracost/cloud-pricing-api) self-hosted | 3M+ prices AWS/GCP/Azure, auto-updates weekly, unlimited runs (hosted free tier caps at 1,000/mo) |
| **Cross-cloud comparison** | [vantage-sh/ec2instances.info](https://github.com/vantage-sh/ec2instances.info) | Instance specs + prices across all 3 clouds — the "which cloud is cheapest" dataset |
| Raw price sources | Azure Retail Prices API (free, no auth) · AWS Price List Bulk API (needs IAM) · GCP Cloud Billing Catalog API (needs key) | Feed the self-hosted pricing DB |
| Backup engine | [OpenInfraQuote](https://github.com/terrateamio/openinfraquote) (MPL) | Fully offline CSV pricing, no limits — AWS-only today |
| Caching | Redis | Price lookups are repetitive |

> **Pipeline:** `LLM → Terraform → Infracost → real $` — not an LLM guess.

⚠️ **TO VERIFY:** confirm 2026 terms for self-hosting `cloud-pricing-api` for free.
It is a load-bearing dependency. Active forks (IBM-Cloud) suggest it's fine — confirm before building on it.

## 7. Diagram Generation

| Part | Resource | Why |
|---|---|---|
| Diagram engine | [mingrammer/diagrams](https://github.com/mingrammer/diagrams) | Python (matches backend), AWS/GCP/Azure/K8s, **icons bundled**, code→PNG |
| Renderer dependency | Graphviz | Required by `diagrams` |
| Icon packs (if custom renderer) | [tf2d2/icons](https://github.com/tf2d2/icons) · [weibeld/aws-icons-svg](https://github.com/weibeld/aws-icons-svg) · [az-icons.com](https://az-icons.com/) | ⚠️ AWS icons **CC-BY-ND** (no modification), Azure MIT, GCP Apache-2.0 |
| Optional AWS-native look | [awslabs/diagram-as-code](https://github.com/awslabs/diagram-as-code) | Only if official AWS-guideline diagrams wanted later |

## 8. Bill Audit (P3)

| Part | Resource | Why |
|---|---|---|
| Bill parsing | pandas + AWS CUR / GCP / Azure cost export CSV | v1 is **upload only** — no live account connection |
| Waste rules | Our own rules engine + knowledge base | "Idle resource", "egress bleed", "x86 → Graviton" |
| Reference tools to study | Komiser, Cloud Custodian, OpenCost | Mine their rule sets for waste patterns |

## 9. Backend & Infrastructure

| Part | Resource | Why |
|---|---|---|
| API server | Python + FastAPI | Best ecosystem for LLM + data work; async; auto OpenAPI docs |
| Database | PostgreSQL + pgvector | App data + pricing + embeddings in one |
| Cache / queue | Redis | Price cache + job queue |
| Background jobs | Celery or APScheduler | Weekly pricing refresh |
| Containers | Docker + docker-compose | Infracost, pricing-api, Postgres, Redis |

## 10. Hosting (eat our own dog food)

| Part | Resource | Why |
|---|---|---|
| Frontend | Vercel or Cloudflare Pages | Free tier, zero config |
| Backend + DB | Hetzner / Railway / Render small VM | The cheap option — proves our own thesis |
| Object storage | Cloudflare R2 | No egress fees — a technique we literally recommend |

---

## Reference repos (study, don't ship)

| Repo | What to learn |
|---|---|
| [Siddhant-K-code/cloud-architect-ai](https://github.com/Siddhant-K-code/cloud-architect-ai) | ⚠️ Closest existing product — steal UX flow, **beat it on real pricing + optimizations** |
| [carlosmgv02/diagram-ai-generator](https://github.com/carlosmgv02/diagram-ai-generator) | How to prompt an LLM to emit valid `diagrams` Python code |
| [Azure-Samples/agent-architecture-review-sample](https://github.com/Azure-Samples/agent-architecture-review-sample) | Agent pattern for *critiquing* an architecture → explainability feature |
| ailinestudio.com | UX benchmark for the diagram step — but don't compete on diagrams |

## Evaluated and dropped

`vidanov/aws-architecture-diagram-skill` · `n0531m/gcp_diagram_tools` · `cmb211087/azure-diagrams-skill` · `Arturo-Quiroga-MSFT/azure-architecture-diagram-builder`

**Why:** all single-cloud diagram wrappers. `mingrammer/diagrams` covers all three in one library.

---

## The five that decide the project

1. **Infracost** → real cost, not guesses *(credibility)*
2. **cloud-pricing-api** self-hosted → unlimited pricing data *(independence)*
3. **mingrammer/diagrams** → diagrams for free *(table stakes)*
4. **Claude API + pgvector** → the reasoning *(intelligence)*
5. **Our own knowledge base** → optimization techniques *(the moat)*

> Four of these install in a day. **#5 is the project.**
