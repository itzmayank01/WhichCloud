# WhichCloud / CloudForge — Product Requirements (v1)

**Owner:** Mayank Thakur · **Status:** Draft v1

---

## 1. Summary

WhichCloud takes a user's **goal and constraints as input** and returns cost-optimal cloud
architecture recommendations — including the non-obvious optimization techniques and the
tools that implement them — with real pricing and deployable Terraform.

v1 proves the **core brain** (knowledge base + reasoning + pricing) through three tightly
scoped products built on one shared engine.

## 2. Goal-as-Input

The user never fills a 40-field infra spec. They state a **goal + constraints** in natural
language; the system infers the rest and asks only what's missing — one question at a time.

### Requirement Object (canonical schema v1)

```json
{
  "goal": "string",
  "workload_type": "web | api | batch | ml | storage | mixed",
  "traffic": { "pattern": "steady | spiky | unknown", "scale": "low | medium | high" },
  "budget_monthly_usd": "number | null",
  "latency_target_ms": "number | null",
  "region": "string | null",
  "compliance": ["GDPR" | "HIPAA" | "none"],
  "lock_in_tolerance": "low | medium | high",
  "team_skill": "beginner | intermediate | expert",
  "provider_preference": "aws | gcp | azure | none"
}
```

`provider_preference: none` is the **default and hero path** — it's what makes this
"WhichCloud" rather than an AWS calculator.

## 3. The three products

### P1 — Design (greenfield)
- **In:** Requirement Object
- **Out:** 2–3 ranked architectures (*Cheapest / Balanced / Most Reliable*), each with diagram,
  service list, monthly cost, embedded optimization techniques + tools, Terraform
- **Acceptance:** for 10 seed goals, produces valid priced diagrammed architectures,
  each including ≥1 non-obvious optimization

### P2 — Advise (conversational)
- **In:** free-form questions ("Should I use spot instances for this?")
- **Out:** grounded, explainable answers citing knowledge-base entries and current pricing
- **Acceptance:** every answer references ≥1 KB entry with a concrete savings figure;
  can escalate into a full Design run

### P3 — Audit (brownfield)
- **In:** uploaded billing CSV / cost export (**no live account connection in v1**)
- **Out:** top waste items + technique-level fixes, each with estimated `$ saved / month`
- **Acceptance:** flags ≥5 concrete savings opportunities on a sample bill

## 4. Shared engine

- **Knowledge Base** — curated optimization techniques with applicability, savings,
  tradeoffs, and implementing tool
- **Pricing Layer** — self-hosted `cloud-pricing-api` fed by AWS/GCP/Azure public pricing APIs
- **Reasoning Layer** — Claude + RAG over the knowledge base + pricing
- **Output Generators** — `mingrammer/diagrams` renderer + Terraform templater

## 5. v1 scope — what we WILL build

| Area | In v1 |
|---|---|
| Interaction | Goal-as-input via chat + guided form |
| Products | P1 Design, P2 Advise, P3 Audit (CSV upload) |
| Clouds priced | AWS + GCP + Azure (compute, storage, DB, network core) |
| Knowledge base | 20–30 hand-curated high-value techniques |
| Cost | Static per-architecture estimate + basic what-if (traffic / spot / Graviton toggles) |
| Output | Diagram + service list + cost + techniques + Terraform (common patterns) |
| Persistence | Save/re-open a project; export report |
| Auth | Basic email login |

## 6. Explicit OUT list — NOT in v1

- ❌ Live cloud account connection (read-only IAM roles, OAuth) — audit is **CSV upload only**
- ❌ Automatic deployment / `terraform apply` — we generate IaC, we never provision
- ❌ Continuous monitoring / drift detection / alerts
- ❌ Billing, payment, %-of-savings charging, subscriptions
- ❌ Every cloud SKU — core categories only, not niche/managed-AI/edge exotica
- ❌ Multi-cloud deployment orchestration — we *compare* clouds, we don't manage them
- ❌ Team/org features — no roles, sharing, RBAC, workspaces
- ❌ Custom/enterprise pricing (EDPs, committed-use discounts) — public list/spot pricing only
- ❌ Exact-to-the-cent billing — estimates are directional and labeled as such
- ❌ Guaranteed-correct Terraform for arbitrary designs — curated common patterns only

## 7. Success metrics

- Goal → 3 priced architectures in **< 3 minutes**
- Each Design output contains **≥1 optimization the user didn't know** (user survey)
- Audit produces **≥5 quantified savings items** on a sample bill
- Cost estimates within **±20%** of provider calculators

## 8. Risks

| Risk | Mitigation |
|---|---|
| Pricing freshness | Scheduled refresh + label outputs "estimate, not quote" |
| P2 not clearly better than ChatGPT | Always ground in KB + live pricing; cite sources |
| Knowledge base is the real work | Treat curation as a first-class ongoing task, not a one-time load |
| `cloud-pricing-api` self-host terms | **Verify 2026 licensing before building on it** — load-bearing dependency |
