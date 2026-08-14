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

**Status: BUILT and verified 2026-08-14.** See `backend/README.md`.

The original plan (Infracost + self-hosted `cloud-pricing-api`) **did not survive
verification** — see the correction below. We build the pricing layer ourselves.

| Part | Resource | Why |
|---|---|---|
| **EC2 compute prices** | [ec2instances.info](https://github.com/vantage-sh/ec2instances.info) (Vantage, open source) | ✅ 1,406 instances with specs *and* per-region prices in one file. No auth |
| **Azure prices** | [Azure Retail Prices API](https://prices.azure.com/api/retail/prices) | ✅ **No authentication at all.** OData-filterable, live |
| **Everything else AWS** | [AWS Price List Bulk API](https://pricing.us-east-1.amazonaws.com) | ✅ Public, no credentials. 106 regions |
| **GCP prices** | Cloud Billing Catalog API | Needs a free API key. Phase 4 |
| **Store** | PostgreSQL + pgvector | Prices are 300 MB per catalog — ingest once, query locally |
| **Cache** | Redis | Price lookups are repetitive |

> **Pipeline:** `provider APIs → our price_points table → engine → real $`

### ⚠️ Correction: why not Infracost

| What we assumed | What is actually true (checked 2026-08-14) |
|---|---|
| `infracost breakdown` prices raw HCL with no credentials | `breakdown` is **deprecated** in v2.16. `infracost scan` **forces an interactive browser login** |
| `infracost/cloud-pricing-api` can be self-hosted free | Repo returns **404**. Infracost moved self-hosting to a **paid plan**. Only stale forks remain |

Its hosted free tier (1,000 runs/mo) still works but needs an account and makes our
core capability depend on someone else's pricing. Building our own removes the
dependency, has no limits, and is a real contribution rather than a wrapper.

[OpenInfraQuote](https://github.com/terrateamio/openinfraquote) (MPL, offline, no
account, AWS-only) remains a good **cross-check** for Terraform-based estimates.

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
