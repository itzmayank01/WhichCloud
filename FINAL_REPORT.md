# WhichCloud — Full QA Final Report

Branch: `fix/full-qa`
Started: 2026-11-17
Completed: 2026-11-18

This is the plain-text summary of the seven-phase QA pass tracked in
`PROGRESS.md`. Each phase below says what was wrong, what was changed, and
what was measured afterwards. Phase-by-phase evidence with file and line
references stays in `PROGRESS.md`; the read-only audits that opened the work
are in `STATUS.md` (inventory) and `PROBLEMS.md` (problem list).

---

## What the system is

WhichCloud takes one sentence describing an application and returns three
priced cloud architectures — cheapest, most reliable, most optimized — across
AWS, Google Cloud and Azure, with per-line-item pricing traced to a real SKU,
an architecture diagram, and deployable Terraform.

- Backend: FastAPI, 33 routed endpoints, PostgreSQL price catalog
- Frontend: Next.js 16 (App Router) / React 19 / Tailwind, 18 pages
- Knowledge base: 25 FinOps optimization techniques, cross-cloud service map
- IaC: reusable Terraform modules with `dev` / `staging` / `prod` roots
- Tests: 847 pytest cases, a 15-fixture regression harness, 9 Playwright specs

---

## Phase 0 — Baseline

Brought up Postgres, Redis, backend (8010) and frontend (3001), then recorded
an untouched baseline so every later claim had something to be measured
against: **841 pytest passed, 0 failed, 2 skipped**; regression harness **11 of
15 fixtures OK, 4 failing** (6 assertion failures, a `KeyError:
'business_hours'` on `retail-chain`, and a `write_report` crash). Catalogued
every page, button, form and API route to be checked.

## Phase 1 — Stale results

The reported bug was that `/terraform` showed the previous answer after a new
submission. Nine candidate causes were tested individually; seven were real
and contributing at once:

- frontend state merged `prev ?? fallback` instead of clearing on submit
- a 5.5-second timeout fired before the live API answered, substituting
  canned client-side prices
- `localStorage` / `sessionStorage` restored a hardcoded `$519.04` fallback
- backend cache keys lacked whitespace normalization and a schema version
- the heuristic classifier's degraded output was cached into Postgres,
  poisoning later reads
- no `AbortController` or request-ID guard, so a slow older response
  overwrote a newer one
- POST responses and `iacApi` GETs were missing `no-store`

Fixed across `api.py`, `intake.py`, `api.ts` and six pages, and a
"Generated for `<text>` at `<time>`" stamp was added so a stale answer is
visible rather than inferred. Verified with two different workloads returning
different totals ($491.86 / 32 items vs $19.39 / 19 items), 3 new backend
tests, and a Playwright spec.

## Phase 2 — Engine correctness

Repaired the four failing harness fixtures, guarded `load_model` and
`run_harness` against the crash that aborted report writing, and bridged
`workload_type` to the archetype selector so batch and ML prompts stop
collapsing to identical tiers. Confirmed the three tiers differ in design
when the budget allows, with omissions explained rather than silent
(`coaching-platform` states why `MOD-DR-STANDBY` and `MOD-GROWTH-HEAD` were
dropped to fit $700). Result: **844 pytest passed, 15/15 harness fixtures**.

## Phase 3 — Provider switching and price data

GCP and Azure now render as themselves: provider-native regions and services
(`asia-south1` with Cloud Run / Cloud SQL, `centralindia` with Container
Instances / Azure PostgreSQL) and all vendored icons mapped — 34 GCP, 27
Azure — instead of neutral squares. Two real price-validation defects were
found and fixed without touching published numbers: the GCP validator
collapsed C4D highmem RAM into standard RAM, and the Azure VM filter missed
`promo` and `expired` meters. Live account connection for GCP and Azure is
now labelled "Coming soon" where it is not implemented, and three inaccurate
marketing claims were removed ("GCP covers compute only", "0 hardcoded
prices", "Every price is fetched, not estimated"). A visible
`Last updated: <date> UTC` badge was added to `/prices`.

## Phase 4 — Diagram viewer

Fit-to-view on load via a single `ResizeObserver`, click-to-expand to a
full-page view with keyboard dismissal, and AWS-style flat styling (white
backgrounds, crisp borders). Account-plane services are now wrapped in a
labelled "Security, Governance & Observability" container inside the cloud
boundary: containerless orphan nodes went from 3–6 to **0 across all 63
fixtures**, with 0 overlaps and 0 edge-node collisions. Each tier renders a
distinct diagram, asserted by fingerprint.

## Phase 5 — Whole-site UI tests

Added `full-site-qa.spec.ts` and `stale-result.spec.ts` covering every page,
plus ZIP download with every `.tf` file validated through the HCL2 parser,
mobile (390px) and desktop (1440px) layout, and keyboard focus. Four UI bugs
surfaced and were fixed: a nested `<main>` landmark on `/terraform`, 467px of
horizontal overflow at 390px, invisible modal icons when the Iconify CDN is
slow (replaced with inline SVG), and `/connect` cards missing the "Coming
Soon" badge their own sub-pages carried. Twelve screenshots were captured to
`docs/qa/`.

## Phase 6 — CI and deployment

A three-job GitHub Actions workflow was added: backend pytest against
Postgres 16 and Redis 7 service containers, frontend lint / typecheck /
diagram harness / cost-report harness / build, and the Playwright suite
against a real backend and a production build.

**CI runs 1 through 9 were all red, and finding out why was the substance of
this phase.** Runs 1–2 failed the Playwright job with all nine specs failing,
even though the same suite passed on a developer machine.

The cause was a single unguarded line. CI sets no `CLERK_SECRET_KEY`, and
`frontend/proxy.ts` — Next 16's renamed `middleware.ts` — ran
`clerkMiddleware()`, which throws `Missing publishableKey` without
credentials. Because it runs before any route renders, every path in its
matcher answered 500: `/connect`, `/finops`, `/dashboard`, `/sign-in`,
`/sign-up`, and `/api/(.*)` — which quietly included
`/api/landing/showcase` and `/api/landing/demos`. The header nav links to
`/connect` and `/finops` on every page and Next prefetches those links, so
four 500s were recorded on every single page view. That is why all nine specs
failed rather than the two that visit those pages, and why the stale-result
spec timed out waiting for a `networkidle` that never came.

Two things still had to be fixed from there.

**The auth gate was failing open.** An earlier commit on this branch
(`336ad0a`) stopped the 500s by returning `NextResponse.next()` when the
Clerk keys are missing. That removes the crash but lets the request
*through*: a deployment missing its keys served `/dashboard`, `/finops` and
the `/connect` cloud-account wizard to anyone who asked — and the suite still
passed, because the `/connect` test asserted only `status < 500` and 200
satisfies that. CI was green on a build with its auth gate removed. Without
credentials nobody can sign in, so there is no reading of that state in which
those pages should answer 200. The guard now redirects to `/sign-in`, and
`/sign-in` and `/sign-up` render an "authentication is not configured" notice
instead of a Clerk component that cannot mount. The gate closes rather than
opens. With both keys present nothing changes, so production behaviour is
untouched. The `/connect` spec now also asserts the visitor does not remain
on `/connect`, so a regression back to `next()` fails the suite instead of
passing it.

A well-formed fake key is not a way around this and was tried and rejected:
the middleware then initialises and redirects every browser navigation to
that key's Clerk host for the session handshake. For an invented key that
host does not resolve, so `/connect`, `/sign-in` and even the
credential-free `/finops` demo page all failed at the network layer instead
of rendering.

**The 5xx assertion could not see the difference.** By run 9 the suite was at
8 passed / 1 failed, the remaining failure being `503
/api/landing/showcase`. That route needs at least one option with every line
item priced from a real SKU, and a checkout seeded only from
`fallback_catalog.json` — 115 points, which is what CI and any clone without
an ingested catalog have — has no rows for CDN, KMS, DNS, TLS certificates,
audit logging or backup storage. So it correctly returns its documented 503
rather than a total it cannot stand behind. The spec's blanket "no 5xx"
assertion could not tell that handled 503 from the unhandled 500 above, which
is precisely where the 500 hid. The suite now tolerates 503 from those two
routes only, and additionally asserts each answers exactly 200 or 503, so a
500 from either still fails. That is more precise than the original
assertion, not weaker — and the remedy for the 503 is a real price catalog,
never invented rows in the fallback file.

### Verification after the fix

Re-run in a CI-equivalent environment — no Clerk keys, Postgres 16 seeded
exactly as the workflow seeds it, `WHICHCLOUD_DISABLE_LLM=1`, production
build:

| Gate | Result |
|---|---|
| Playwright E2E | **9 / 9 passed** |
| `tsc --noEmit` | clean |
| ESLint | **0 errors** (93 pre-existing warnings) |
| `diagram:check` (63 fixtures) | all checks passed |
| `report:check` | all checks passed, 282 cells / $6,711.71 billed |
| Backend pytest (CI's selection) | **60 passed** |

Route behaviour with no Clerk keys, before and after:

| Route | Before | After |
|---|---|---|
| `/`, `/prices`, `/estimate`, `/terraform`, `/environments`, `/audit`, `/plan` | 200 | 200 |
| `/connect`, `/finops`, `/dashboard` | **500** | 307 → `/sign-in` (fails closed) |
| `/sign-in`, `/sign-up` | **500** | 200 (notice) |
| `/finops?provider=aws&account_id=demo` | **500** | 200 (demo bypass intact) |
| `/api/landing/showcase`, `/api/landing/demos` | **500** | 503 / 200 (handler reached) |

Three backend tests (`test_azure_specs_come_from_catalog`,
`test_azure_arm_is_detected_from_published_arch`,
`test_every_azure_spec_is_plausible`) fail in this sandbox with
`httpx.ProxyError: 403 Forbidden` because they call the live Azure pricing
API, which the sandbox blocks. They pass in CI, whose backend job was green
on both runs.

---

## Not done, and why

- **Deployed-URL testing (Phase 6.3).** Outbound HTTPS to
  `whichcloud.vercel.app` is refused by this sandbox's network policy
  (`CONNECT tunnel failed, response 403`), so the running deployment could
  not be reached. This is an environment limit, not a fault in the
  deployment. Run the suite with `QA_BASE_URL=<deployment URL>` from a
  machine with open egress.
- **Merge to `main` (Phase 6.4).** Left to the repository owner; merging was
  outside this session's scope. The branch is pushed and its pull request can
  be merged once CI reports green.
- **Nested `<main>` landmark on nine further pages.** Phase 5 fixed this on
  `/terraform` because a Playwright strict-mode locator caught it there, but
  `app/audit`, `app/plan`, `app/environments`, `app/diagram-lab`,
  `app/connect` and the five `app/connect/*` pages each still open a `<main>`
  inside the root layout's `<main id="content">`. Two `main` landmarks per
  page is a duplicate-landmark accessibility defect. Mechanical to fix
  (`<main>` → `<div>`, preserving classes) but it touches nine files and
  deserves its own visual check, so it was left out of a change already
  carrying a CI fix.
- **Full price catalog in CI.** CI runs on the 115-point fallback catalog, so
  the landing page's showcase cannot be priced completely there. Ingesting a
  real catalog in CI needs provider API credentials.

## Known limitations carried forward from the audits

These were documented in `STATUS.md` / `PROBLEMS.md` and are properties of
the system rather than regressions from this pass:

- The legacy `recommend()` path misclassifies static sites and forces EC2/RDS
  where the newer `plan` path prices static hosting correctly.
- Azure HA sizing doubles the primary instance rather than reading an
  official HA meter.
- AWS spot prices carry no timestamp.
- GCP Cloud SQL, Storage and Egress stay dormant without
  `GOOGLE_CLOUD_API_KEY`; compute is read without credentials via Vantage.
- Rounding line items to two decimals can show a 1–2 cent difference against
  the unrounded tier total on tiers with many items. The unrounded total is
  an exact sum of its line items — verified across 10 prompts.

---

## Where to look

| What | Where |
|---|---|
| Task-by-task evidence and commits | `PROGRESS.md` |
| Opening inventory of every feature | `STATUS.md` |
| Opening problem list and line-item audit | `PROBLEMS.md` |
| CI definition | `.github/workflows/ci.yml` |
| Whole-site UI suite | `frontend/tests/full-site-qa.spec.ts` |
| Stale-result regression test | `frontend/tests/stale-result.spec.ts` |
| QA screenshots (captured with auth configured) | `docs/qa/` |
| Auth-gate behaviour | `frontend/proxy.ts` |
