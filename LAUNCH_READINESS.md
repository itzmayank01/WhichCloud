# Launch readiness — what to fix before charging money

Written 2026-11-20. Every item marked **[verified]** was reproduced against
the live deployment or the code in this repo during the session that wrote
this; items marked **[judgment]** are opinion and should be argued with.

The organising question is not "is it finished" but **"if a stranger pays
$29 and the first number they see is wrong, do we find out before they
do?"** Today the answer is no, and that is what P0 is about.

---

## P0 — Blocks taking money at all

### 1. The deploy pipeline is not deploying [verified]

Two backend commits (`ec2fe00`, `f131d7e`) sat unpublished for 25+ minutes.
Production still answers `read_by: groq (cached)` under draft schema
version 1, which proves it is running pre-fix code — the fix bumps that to 2.

Nothing else on this list can be shipped until this is fixed. Check
**Render → whichcloud-backend → Events** for a failed or queued deploy, or
auto-deploy being disabled.

**Why it is P0 and not P2:** a product that takes money needs a working
path from "bug found" to "bug fixed in production". Right now there isn't
one.

### 2. A stated figure is read 37× too large [verified, fixed, undeployed]

"We keep about 2 TB of history" priced **75,000 GB** of object storage
($1,875) plus 15,000 GB of backup ($825) — **97% of a $2,783 estimate**,
against the **$600 budget stated in the same sentence**. Confirmed
proportional: 3 TB → 112,500 GB.

It was also cached by description, so the wrong answer was served instantly,
forever, to anyone who had already asked.

Fixed in `ec2fe00` (deterministic unit-aware reader overrides the model;
schema bump evicts poisoned rows; 20 tests). **Undeployed — see item 1.**

**This is the single most dangerous class of bug in the product**, because
the output looks completely normal. There is no visual tell that the number
is 37× wrong.

### 3. There is no way to pay [verified]

`frontend/app/pricing/page.tsx` sells a **$29/month Pro plan**. There is
**no Stripe, Razorpay, Paddle or Lemon Squeezy integration anywhere in the
repo**. "Upgrade to Pro" gates nothing. A `clerk-billing` skill exists in
`.agents/skills/` but is not wired in.

Decide and implement one:
- **Clerk Billing** — least work, you are already on Clerk for auth.
- **Stripe Checkout + webhook** — more control, more work, standard.
- **Razorpay** — if the market is India-first and you want UPI/local cards.

Then: a `plan` on the user record, server-side entitlement checks on every
paid route (never client-side only), and a webhook that survives replay.

### 4. The price catalog is 65 days stale [verified]

`/health` reports `last_updated: 2026-09-15`, **65 days old**, and the
landing page says so in orange: *"refreshed 65 days ago"*.

The product's entire claim is *"Every price is fetched, not estimated"* and
*"0 hardcoded prices in the source"*. Charging for a price-accuracy tool
whose prices are two months old is the kind of thing that ends in a refund
request and a bad tweet.

Needs a **scheduled re-ingest** (Render cron / GitHub Action calling
`scripts/ingest_prices.py`) and an **alert when age > N days**. The freshness
badge already exists — make it a monitored SLO, not decoration.

### 5. `/describe` returns HTTP 500 on a real description [verified]

A migration-shaped description ("we have an order system in our own server
room and we want to move it to the cloud") returns **500 Internal Server
Error** — a crash with no message, not a graceful refusal.

By contrast the `realtime` refusal (400, "a quantity we could not read")
is correct behaviour and should be left alone. The 500 is a genuine
unhandled path.

### 6. Budget overrun is reported as "fine" [verified]

Budget $600, cost $5,145, and the panel says
**"Uses most of your budget ($0/mo left)"** — clamped at zero instead of
reporting a **$4,545 overrun**.

A costing tool that cannot say "this is over your budget" is failing at its
one job, and it is a two-line fix.

---

## P1 — The numbers are not yet trustworthy enough to sell

These do not crash. They quietly undermine the claim the product is sold on.

### 7. "Totals are floors rather than answers" [verified]

Live, on an Azure estimate: *"Every option here is missing components the
catalog cannot price in this region, so these totals are floors rather than
answers"* and *"1 component could not be priced"*.

The honesty is genuinely excellent — it is the best thing about this
codebase. But **you cannot charge $29/month for a floor.** Either close the
catalog gaps for your launch regions, or restrict the paid product to
region/provider combinations where coverage is complete and say so.

**Recommendation [judgment]:** pick **AWS + ap-south-1** as the one
"complete" paid path for launch, verify every component prices there, and
market GCP/Azure as comparison-only until their coverage lands.

### 8. GCP is compute-only, and unvalidated [verified, documented]

From `backend/README.md`: storage, egress and Cloud SQL need a Catalog API
key; no second source exists to cross-check GCP against. The three-cloud
comparison is the headline feature, and one of the three clouds is a stub
with correct disclaimers.

### 9. Budget does not buy anything, and the UI does not explain it [verified]

$500 budget → $244/mo design. $5,000 budget → $387/mo, leaving **$4,612
unallocated**, reported as *"Well within budget"*.

The engine refuses to spend to a budget **on purpose** and documents the
reasoning well ("a tier that grew until it consumed a percentage of whatever
figure was typed would recommend the same architecture to a blog and to a
bank"). The *behaviour* is defensible. The *presentation* is not: a user
who types $5,000 and gets $387 with no explanation concludes the tool
ignored them.

**Still open — needs your decision.** Three options, in preference order:
- **A.** Keep sizing honest; replace "well within budget" with what the
  budget *could* buy as explicit opt-in upgrades ("multi-region
  active-active +$420/mo"). Recommended.
- **B.** Let a high budget unlock resilience only (extends what already
  happens — $5k added cross-region DR).
- **C.** Re-enable budget-driven growth. Reverses a decision the engine
  documents as a bug it was built to prevent.

### 10. Known pricing caveats that a paying customer will eventually hit [verified, documented]

Already listed in `backend/README.md` and surfaced honestly in the UI, but
worth knowing they are revenue-relevant:

| Gap | Why it matters commercially |
|---|---|
| List prices only — no committed-use, savings plans or reserved rates | The customers with the biggest bills are exactly the ones on committed pricing |
| Azure HA is derived (standby billed as 2×) | Azure publishes no HA meter; the figure is a model, not a rate |
| Spot feed undated | Fine for ranking, not for billing-grade claims |
| Sizing is heuristic | Stated clearly in the UI; still the biggest source of "that's not what I'd run" |

---

## P2 — Operations you need before strangers depend on it

11. **Render free tier sleeps after 15 min** [verified] — 30–60s cold start.
    A paying user's first click should never take a minute. Move the backend
    to a paid instance; this is the cheapest credibility you can buy.
12. **Redis container runs but the lookup path does not use it** [verified,
    documented] — free latency win already half-built.
13. **Rate limiting is per-process, in memory** [verified] — fine for one
    worker, wrong the moment you scale out. The code says so itself.
14. **No error monitoring** [judgment] — Sentry or equivalent. Right now a
    500 in production is invisible unless someone reports it (see item 5 —
    which I found by accident, not by alert).
15. **No backup/restore story for Neon** [judgment] — saved architectures and
    connections are customer data now.

---

## P3 — Polish that affects perceived quality

16. **AWS diagrams have 32 of 51 total edge crossings** [verified] — Azure
    has 10 on the same shapes. Root cause found and documented in
    `elkLayout.ts`: replication edges are withheld from ELK and hand-routed,
    and ~78% of AWS crossings involve them. Two viable fixes recorded there.
17. **4 of 38 service kinds have no vendor icon** [verified, mitigated] —
    now a neutral glyph rather than a broken-looking dot.

---

## What actually makes money

Ranked by willingness-to-pay, not by how finished it is.

### Tier 1 — recurring revenue lives here

**Connected-account FinOps (`/finops`, `/connect`).** "Here is $340/month of
waste in your actual bill" is the thing people pay for every month. It is
what Vantage, CloudZero and nOps charge for. Everything else in this product
is a one-shot utility.

The pricing page already argues this: *"a single unattached EBS gp2 volume
costs $10–$40/month; an idle NAT gateway costs $35/month."* That argument is
correct and it is your best one — **but it only works if the connect flow is
reliable and the findings are real.** Per-tenant AssumeRole has landed. This
is where to spend the next month of effort.

**Why it beats the estimator commercially:** "price my app" is used once
before a project starts. A connected account is a reason to log in every
month, which is the difference between a $29 one-off and $29 recurring.

### Tier 2 — strong retention features, partially built

- **PR cost comments** ("this PR adds Redis, +$24/month"). Designed in the
  GitHub plan, not built. This is Infracost's entire wedge and it is sticky:
  once it is in CI, removing it is a decision someone has to defend.
- **Terraform / Multi-Env IaC export.** Already built. Converts an estimate
  into something you can run, which is what makes the estimate worth paying
  for. Fix the ZIP download reliability permanently and make this prominent.
- **Saved projects + history.** Shipped (`/projects`). Add "what changed
  since last month" and it becomes a reason to return.

### Tier 3 — pricing and packaging [judgment]

- **$29/month is probably underpriced for the FinOps value and overpriced
  for the estimator alone.** Consider: free estimator (lead generation),
  paid connected-account FinOps.
- **Annual billing at ~2 months free.** Single biggest lever on cash and
  churn, costs one Stripe price object.
- **Seats/teams.** Cloud cost is a team conversation; today everything is
  single-user.
- **The "pays for itself in 48 hours" claim** needs to be *demonstrable* —
  ideally the product shows the user their own first finding before asking
  for a card. That is the highest-converting onboarding you can build.

---

## Suggested order of work

1. Unblock Render (item 1) — nothing ships otherwise.
2. Deploy the storage fix (item 2) and re-verify live.
3. Fix the budget-overrun display (item 6) and the `/describe` 500 (item 5).
4. Schedule price re-ingest + staleness alert (item 4).
5. Pick one complete paid path (item 7) and verify every component prices.
6. Wire payments (item 3) — pointless before 1–5, essential immediately after.
7. Move off the free Render tier (item 11).
8. Then: PR cost comments, and the budget-presentation decision (item 9).

**Do not wire payments first.** The moment money changes hands, every item
above becomes a support ticket instead of a task.
