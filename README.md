# WhichCloud (CloudForge)

**A Constraint-Driven, LLM-Augmented Framework for Multi-Objective Cloud Architecture Synthesis and Cost Optimization**

---

## What it does

Describe your app in plain English → get 2–3 cost-optimal cloud architectures, with **real** pricing, the money-saving optimization techniques most people don't know about, a diagram, and deployable Terraform.

```
Plain English
   → LLM extracts Requirement JSON
   → Engine + Knowledge Base picks services & optimizations
   → Generate Terraform (from vetted modules)
   → Infracost prices it            ← REAL numbers, not LLM guesses
   → mingrammer/diagrams renders it
   → 3 options: Cheapest / Balanced / Most Reliable + cross-cloud comparison
```

## The three products (v1)

| Mode | Entry point | Output |
|---|---|---|
| **Design** | "I'm building something new" | 2–3 priced architectures + diagram + Terraform |
| **Advise** | "I have a question" | Grounded answers citing real pricing + techniques |
| **Audit** | "I'm overpaying" | Upload billing CSV → waste report with `$ saved/month` |

## Why this is different

Existing tools either draw pretty diagrams (no cost) or calculate prices (no reasoning).
Competitors' cost numbers come from an LLM guessing. **Ours are computed by a real pricing engine.**

The moat is `knowledge-base/` — the curated catalog of optimization techniques
(Graviton, zram, spot+checkpointing, scale-to-zero, egress-free storage…),
each mapped to when it applies, what it saves, and the tool that implements it.

## Repo structure

```
WhichCloud/
├── docs/                       # PRD, resource map
├── knowledge-base/             # ⭐ THE MOAT — curated optimization techniques
│   ├── techniques/             #   one YAML per technique
│   └── service-mappings/       #   AWS ↔ GCP ↔ Azure equivalents
├── backend/                    # FastAPI — engine, RAG, cost, generators
├── frontend/                   # Next.js — chat, results, diagrams
└── infra/                      # docker-compose: Postgres, Redis, cloud-pricing-api
```

## Docs

- [Product Requirements (PRD)](docs/PRD.md)
- [Resource Map — every tool/repo we use and why](docs/RESOURCES.md)
- [Knowledge Base schema](knowledge-base/README.md)

## Status

🚧 **Pre-v1.** Scaffolding stage. Next step: verify the cost pipeline
(self-host `cloud-pricing-api`, run `infracost breakdown` on sample Terraform with no cloud credentials).
