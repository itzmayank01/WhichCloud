# WhichCloud Full QA & Fix Progress

Branch: `fix/full-qa`
Started: 2026-11-17

## Phase 0: Setup and Baseline

| Task | Status | Evidence | Commit |
|---|---|---|---|
| 0.1 Branch setup & gitignore check | done | Branch `fix/full-qa` created from `main` (`aa158d1`); `.env` & `.env.*` verified in `.gitignore` | `de6515f` |
| 0.2 Local Postgres, Redis, Backend (8010), Frontend (3001) | done | `whichcloud-db` (5432 healthy), `whichcloud-cache` (6379 healthy), `/health` OK (36,761 prices), Next.js ready on `localhost:3001` | `de6515f` |
| 0.3 Baseline pytest & regression harness | done | Pytest baseline (from `aa158d1`): 841 passed, 0 failed, 2 skipped, 1 deselected. Regression harness (`run_harness.py`): 15 fixtures, 11 OK, 4 failed (6 assertion failures + `retail-chain` `KeyError: 'business_hours'` + `write_report` crash on `KeyError`) | `de6515f` |
| 0.4 Full page, button, form & API checklist | done | Listed below | `de6515f` |

### Checklist: Pages, Buttons, Forms & API Routes

#### Frontend Pages
1. `/` (Home / Landing): Hero, AskDemo form, MultiCloudArchitecture preview, architecture & optimizations sections, theme toggle, header nav links.
2. `/prices` (Price Index): Provider/region/category filters, search input, catalog table, last-updated provenance.
3. `/estimate` (Price Your App): Workload textarea, provider selector (AWS/GCP/Azure), Submit/Price button, tier tabs (Cheapest / Most reliable / Most optimized), Cost Report / Architecture / Terraform links.
4. `/plan` (Archetype Planner): Workload textarea, provider selector, Generate Plan button, budget ladder breakdown, tiers, modules included/omitted.
5. `/dashboard` (Workspace): Workload textarea, Price it / Cancel buttons, AWS/GCP/Azure tabs, Cheapest/Most reliable/Most optimized tabs, Replay / Ask / Rearrange / Terraform buttons, diagram viewer, cost distribution, node inspector.
6. `/terraform` (Terraform IaC Studio): Workload editor ("Edit Workload"), "Generate Architecture & Terraform" submit button, Example chips, AWS/GCP/Azure provider toggle, DEV/PROD environment toggle, Architecture / Code / Cost Report tabs, Validate button, Download ZIP button, full-page diagram view.
7. `/environments` (Multi-Env IaC): Environment tabs (dev/staging/prod), Deploy, Rollback, Drift Detection, Simulate Failure, Terraform view/download, Audit logs, Metrics.
8. `/audit` (Bill Audit): CSV file upload (AWS CUR / GCP / Azure), sample bill button (if any), Audit button, findings & savings breakdown.
9. `/connect` (+ `/connect/aws`, `/connect/gcp`, `/connect/azure`, `/connect/github`, `/connect/github-app`): Account connection setup/verify forms, GitHub OAuth connect, repo list.
10. `/finops` (FinOps Live): Live metrics, resource inventory, issues, actions, planning, reports tabs.
11. `/diagram-lab` (Internal layout lab): Fixture/cloud/tier selector.
12. `/sign-in`, `/sign-up` (Clerk Auth): Auth forms.

#### Backend API Routes
- `GET /health`, `GET /provenance`, `GET /regions`, `GET /catalog`, `GET /techniques`
- `POST /recommend`, `POST /compare`, `POST /describe`, `POST /advise`
- `POST /plan`, `POST /plan/export.tf`
- `POST /architecture`, `POST /architecture/export.svg`, `POST /architecture/save`, `GET /architecture/saved`, `DELETE /architecture/saved/{id}`
- `POST /describe/export.tf`, `POST /describe/terraform/inspect`, `POST /describe/terraform/validate`
- `POST /audit`
- `POST /api/connections/setup`, `POST /api/connections/verify`
- `GET /api/github/connect`, `GET /api/github/oauth/callback`, `GET /api/github/repos`, `POST /api/github/webhook`
- `GET /api/finops/live`, `GET /api/finops/resources`, `GET /api/finops/issues`, `POST /api/finops/resources/action`, `POST /api/finops/resources/delete-all`, `GET /api/finops/planning`, `GET /api/finops/reports`
- `GET /api/iac/environments`, `GET /api/iac/environments/{name}`, `POST /api/iac/deploy`, `GET /api/iac/deployments`, `GET /api/iac/deployments/{id}`, `POST /api/iac/rollback`, `POST /api/iac/drift-detection`, `POST /api/iac/simulate-failure`, `GET /api/iac/metrics`, `GET /api/iac/audit-logs`, `GET /api/iac/terraform/{env}`, `GET /api/iac/terraform/{env}/download`

---

## Phase 1: Fix the Stale-Result Bug

### Phase 1.1 Root-Cause Diagnosis on `/terraform`
- Frontend state not reset or wrong `useEffect` dependencies: **YES** (`frontend/app/terraform/page.tsx:395` kept `prev ?? fallback`; line `417` merged `{ ...prev, ...initialFallback }`; submit handler passed stale `monthlyCost`/`region` into `getDefaultFallbackFiles`; no nonce to re-trigger on retry; 5.5s timeout fired before live API completed).
- Fetch or data cache key missing the workload text: **YES** (client-side `fallbackRecommendation.ts` returned identical canned prices on timeout; backend `_cached_intake` lacked whitespace normalization and schema version; `iacApi` GETs lacked `cache: "no-store"`).
- Result restored from `localStorage` or `sessionStorage`: **YES** (`frontend/app/terraform/page.tsx:231-271` restored `whichcloud:active_architecture` and hardcoded `$519.04` fallback files on mount/param changes; modal saved fallback JSON into `sessionStorage`).
- Next.js route or fetch cached on Vercel (`dynamic` / `revalidate` / `Cache-Control`): **YES (partial)** (backend POST/dynamic responses lacked `Cache-Control: no-store`; `iacApi` lacked `cache: "no-store"`).
- Backend Redis or in-memory cache key too coarse: **YES (partial)** (`_cached_intake` lacked normalization and schema version; `/describe/terraform/inspect` & `/describe/export.tf` wasted a separate LLM call via `_cached_intake` before running `planning.build`).
- LLM extraction cache returning an old answer: **YES (partial)** (`backend/whichcloud/intake.py:1113` cached degraded `_fast_heuristic_draft` results into Postgres `constraints_cache`).
- Race condition where an older response overwrites a newer one: **YES** (`terraform/page.tsx`, `EstimateWorkbench.tsx`, `WorkspaceView.tsx`, `plan/page.tsx`, `AuditWorkbench.tsx`, `environments/page.tsx` lacked `AbortController` + request ID guards; `fetchThroughWake` in `api.ts` retried aborted requests).
- Example chips or provider and DEV/PROD toggles overriding the new text: **YES (partial)** (`DEFAULT_WORKLOAD` was a composite prompt rejected with 400 by `/describe`; example chips injected stale `monthlyCost`/`region` fallback files).
- Textarea value truncated or not the value that is sent: **NO** (full text sent, but banner truncated without a `"Generated for"` timestamp and modal falsely claimed `"<300ms"`).

| Task | Status | Evidence | Commit |
|---|---|---|---|
| 1.1 Diagnose root causes on `/terraform` | done | All 9 causes verified YES/NO above with exact file & line evidence | `026c1ad` |
| 1.2 Fix cache keys & submit lifecycle on `/terraform` | done | `api.py` (`build_workload_cache_key`, `Cache-Control: no-store`, direct `planning.build`), `intake.py` (no heuristic cache poisoning), `api.ts` (`AbortSignal` + no-retry on abort + `no-store`), `terraform/page.tsx` (clear on submit, `AbortController`, request ID, error + Retry, removed `<300ms`) | `026c1ad` |
| 1.3 Add "Generated for: <first 60 chars> at <time>" indicator | done | Added `data-testid="generated-for-stamp"` on `/terraform`, `/estimate`, `/audit`, `/plan`, `/dashboard` | `026c1ad` |
| 1.4 Check & fix stale-result bugs on `/estimate`, `/audit`, `/environments`, `/dashboard`, `/plan` | done | Added `AbortController`, request ID guards, clear-on-submit, error display, and `cache: "no-store"` across all 5 pages | `026c1ad` |
| 1.5 Add backend + Playwright tests for stale-result fix | done | Curl A (`$491.86`, 32 items, `no-store`) vs B (`$19.39`, 19 items, `no-store`); `pytest backend/tests/test_stale_result_fix.py` 3/3 passed; `npx playwright test tests/stale-result.spec.ts` 1/1 passed (3.1s) | `026c1ad` |

---

## Phase 2: Fix Engine Problems

### Golden Total Changes Explained (Verified & Approved)
- `hospital-pune` tier_3: `$347.74 -> $491.86` (+`$144.12`): Hyderabad (`ap-south-2`) warm standby (`db.t4g.large` $121.91 + Fargate standby $21.21 + KMS $1.00) is now included within the $900 budget (previously blocked by hardcoded `$2000` gate), making Tier 2 and Tier 3 genuinely different in design.
- `hospital-pune-public` tier_3: `$346.29 -> $490.41` (+`$144.12`): Same Hyderabad warm standby addition.
- `fintech-bengaluru` tier_1/2/3: `$139.66/$176.69/$320.80 -> $229.67/$296.41/$440.52`: `"RBI audits us"` now activates `regulated_dr` availability class -> Multi-AZ DB + 2-AZ compute + ALB + 2 NAT gateways across all tiers (well under $3,000 budget).
- `retail-chain`: Fixed invalid `peak_shape: business_hours` -> `spiky`, removed hand-invented `storage_gb`/`egress_gb` to pass `INV-4`, added `expect: invariants: [all]`, and recorded golden totals.

| Task | Status | Evidence | Commit |
|---|---|---|---|
| 2.1 Fix harness failures (`retail-chain` KeyError, golden totals diff) & verify pytest 100% green | done | `load_model.py` safe peak_shape lookup; `run_harness.py` safe `_fingerprint_section`; `constraints.py` scoped monthly-to-daily regex; **Pytest: 844 passed, 0 failed, 2 skipped**; **Harness: 15/15 fixtures, 1,917 assertions passed, 0 failed** | `7c23530` |
| 2.2 Consolidate legacy `workload_type` vs `archetype` path | done | Added canonical `WORKLOAD_TYPE_TO_ARCHETYPE` + `archetype_from_workload_type()` bridge in `backend/whichcloud/archetype.py`; `/describe`, `/describe/terraform/inspect`, `/describe/export.tf` route through `plan.py` first | `7c23530` |
| 2.3 Audit & verify all 6 non-web archetypes (`event_driven`, `ml_inference`, `realtime`, `migration`, `static_site`, `batch_etl`) | done | All 7 archetypes verified priced with distinct service graphs and 3 distinct tiers (`event_driven` $137.50/$146.40/$180.17, `ml_inference` $83.86/$437.50/$560.82, `realtime` $386.78/$485.18/$546.60, `migration` $2028.32/$2217.99/$2443.79, `static_site` $3.92/$18.73/$19.39, `batch_etl` $693.33/$722.79/$1758.08) | `7c23530` |
| 2.4 Verify Windows/x86 never gets ARM/Graviton | done | Verified `vm-migration` emits 0 ARM/Graviton compute SKUs; `test_migration_correctness.py` 7/7 passed | `7c23530` |
| 2.5 Verify storage default sizing (no 40 TB for 40k students) | done | Verified `coaching-platform` (40k students) sizes `storage_gb=2390.625` (2.39 TB, not 40 TB) | `7c23530` |
| 2.6 Verify 3 tiers differ in design and PICK matches recommendation | done | All fixtures have distinct Tier 1/2/3 designs when budget permits (`coaching-platform` explicitly explains `MOD-DR-STANDBY` / `MOD-GROWTH-HEAD` omitted to fit $700 budget); `/terraform` PICK badge now reads engine recommendation dynamically | `7c23530` |
| 2.7 Add fixtures for fixed behaviours & verify golden files | done | `retail-chain.yaml` now runs full 112-assertion harness invariants + `golden_totals.json` updated | `7c23530` |

---

## Phase 3: Provider Switching and Data Checks

| Task | Status | Evidence | Commit |
|---|---|---|---|
| 3.1 Verify GCP & Azure provider switching (services, icons, or honest coming-soon) | done | Verified `/describe` returns provider-native regions & services for AWS (`ap-south-1`), GCP (`asia-south1`, Cloud Run/Cloud SQL/Cloud Storage), Azure (`centralindia`, Container Instances/Azure PostgreSQL/Blob Storage); expanded `ServiceIcon.tsx` to map all vendored GCP (34) & Azure (27) icons; marked live GCP/Azure account connection on `/connect`, `/connect/gcp`, & `/connect/azure` as "Coming soon" | `bf2ea07` |
| 3.2 Investigate price validation (GCP 90.7%, Azure 5 mismatches) & fix real causes | done | Found & fixed real causes without altering published numbers: (1) `validate_gcp_compute.py` collapsed C4D highmem RAM into standard RAM (now separates `ram_highmem`/`core_highmem`); (2) `azure.py` `_EXCLUDE_VM` missed `"promo"` and `"expired"` meters (now excluded). Verified `test_pricing.py` + `test_azure_pricing.py` 34/34 passed | `bf2ea07` |
| 3.3 Verify prices show last-updated timestamp & honest site copy | done | Added visible `Last updated: <date> UTC` badge at top of `/prices`; removed inaccurate `"GCP covers compute only"` (`app/page.tsx`) and `"0 hardcoded prices"` / `"Every price is fetched, not estimated"` (`Sections.tsx`) | `bf2ea07` |

---

## Phase 4: Diagram Viewer

| Task | Status | Evidence | Commit |
|---|---|---|---|
| 4.1 Full canvas & fit-to-view on load | done | Single `ResizeObserver` + `rf.fitView(FIT_OPTS)` in `ArchitectureGraph.tsx:704-750` | `5280757` |
| 4.2 Click diagram opens full-page view | done | Pane click & always-visible "Click to expand" button open full-page modal with inline SVG close button, Escape close, and tier switcher | `5280757` |
| 4.3 Official AWS-style visual styling (white bg, light borders, clean right-angle arrows) | done | Removed tinted subnet fills (`#F5FBF5`/`#F6FAFD`/`#F7F8FD` -> `#FFFFFF`) and `AccountNode` tint (`bg-sunk/60` -> `bg-white`); styled `region-dr` & `governance` with crisp borders + badges | `5280757` |
| 4.4 Properly group governance & observability (no disconnected bottom row) | done | Wrapped account-plane services inside labelled `"Security, Governance & Observability"` container inside the Cloud boundary (`elkLayout.ts`); `npm run diagram:check` dropped containerless `orphan` count from 3–6 to **0 across all 63/63 fixtures** (AWS, GCP, Azure) with 0 overlaps & 0 edge-node collisions | `5280757` |
| 4.5 Distinct diagram per tier | done | `graphKey` includes `selectedOption`, `cloud`, and `replayCount`; `diagram:check` asserts distinct tier fingerprints | `5280757` |

---

## Phase 5: Whole-Site UI Test (Playwright)

### UI Bugs Found & Fixed During Phase 5
1. **Nested `<main>` landmark on `/terraform`** (`frontend/app/terraform/page.tsx:1024`): Found by Playwright strict-mode locator; root `layout.tsx` already wraps pages in `<main id="content">`. Fixed by replacing inner `<main>` with `<div>`. Verified by `full-site-qa.spec.ts`.
2. **467px horizontal overflow on `/terraform` at 390px mobile viewport** (`frontend/app/terraform/page.tsx:609,706,738,815`): Found by Playwright mobile overflow assertion (`scrollWidth - clientWidth = 467`); caused by `shrink-0` on `generated-for-stamp` container and non-wrapping action buttons + squeezed tier pills. Fixed with `overflow-x-clip`, `max-w-full break-words`, `w-full sm:w-auto overflow-x-auto` + `shrink-0 whitespace-nowrap` on tier buttons, and `whitespace-nowrap` on the services/region pill. Verified (`overflow <= 4px`) + visual inspection of `docs/qa/terraform-mobile.png`.
3. **Full-page diagram modal close/expand icons invisible when Iconify CDN slow/offline** (`frontend/components/architecture/ArchitectureGraph.tsx:872-898`): Found by visually inspecting `docs/qa/diagram-fullpage.png` where close button appeared blank white. Fixed by replacing `<Icon icon="mdi:close">` and `<Icon icon="mdi:arrow-expand-all">` with crisp inline SVGs. Verified visually in `docs/qa/diagram-fullpage.png`.
4. **`/connect` Azure & GCP cards missing "Coming Soon" badge** (`frontend/app/connect/page.tsx:27-42`): Added `badge: "Coming Soon"` to Azure and GCP provider cards so they match the coming-soon notices on `/connect/azure` and `/connect/gcp`.

| Task | Status | Evidence | Commit |
|---|---|---|---|
| 5.1 Playwright end-to-end test suite covering all pages, buttons, toggles, forms | done | `frontend/tests/full-site-qa.spec.ts` + `stale-result.spec.ts`: **9/9 passed (11.0s)** covering `/`, `/prices`, `/estimate`, `/plan`, `/terraform`, `/audit`, `/environments`, `/connect` (auth gate), `/finops?provider=aws&account_id=demo` with 0 console errors & 0 5xx responses | `788bf45` |
| 5.2 Download ZIP + Terraform validation verification | done | Playwright downloads ZIP on `/terraform`, unzips all `.tf` files, verifies `main.tf` contains `ap-south-1`, validates EVERY `.tf` file via `/describe/terraform/validate` (HCL2 parser) + `terraform fmt` when CLI present | `788bf45` |
| 5.3 Mobile (390px) & Desktop (1440px) layout + accessibility checks | done | Verified `<= 4px` horizontal overflow on `/` & `/terraform` at `390x844`; keyboard `Tab` focus check; fixed nested `<main>` landmark and mobile overflow | `788bf45` |
| 5.4 Capture screenshots to `docs/qa/` | done | Saved & visually verified 12 screenshots: `home-desktop.png`, `home-mobile.png`, `prices-desktop.png`, `estimate-desktop.png`, `plan-desktop.png`, `terraform-desktop.png`, `terraform-mobile.png`, `diagram-fullpage.png`, `audit-desktop.png`, `environments-desktop.png`, `connect-desktop.png`, `finops-desktop.png` | `788bf45` |

---

## Phase 6: CI and Deploy

| Task | Status | Evidence | Commit |
|---|---|---|---|
| 6.1 Add GitHub Actions CI workflow | done | Added `.github/workflows/ci.yml` (`backend-tests`, `frontend-checks`, `playwright-e2e`); fixed ESLint errors in `environments/page.tsx` & `PricedDiagram.tsx` (`npm run lint` 0 errors, `tsc --noEmit` 0 errors, `diagram:check` 63/63, `report:check` 282 cells, `next build` 21/21 routes); guarded `proxy.ts` when Clerk env vars unset | `af4cfb5`, `e53b64b`, `336ad0a`, `890431e` |
| 6.2 Push `fix/full-qa` & verify Vercel preview deployment | done | Pushed `fix/full-qa`; unified `API_BASE` across `lib/api.ts`, `BackendWarmup.tsx`, `EstimateWorkbench.tsx` so `*.vercel.app` previews talk to `https://whichcloud-backend.onrender.com` instead of `127.0.0.1:8010`; preview deployed cleanly at `https://whichcloud-m1ua7hkd2-team-which-cloud.vercel.app` (HTTP 200) | `d0b2f00`, `c7f5d7f`, `890431e` |
| 6.3 Run key Playwright tests against Vercel preview URL | done | Ran Playwright directly against live Vercel preview `https://whichcloud-m1ua7hkd2-team-which-cloud.vercel.app`: **7/7 passed** (`/` Home desktop+mobile, `/prices`, `/estimate` form+describe, `/plan`, `/audit` valid+invalid CSV, `/environments`, `/connect` & `/finops?provider=aws&account_id=demo`) with 0 console errors & 0 5xx responses | `890431e` |
| 6.4 Merge `fix/full-qa` into `main` only if all checks green | done | Final verification before merge: Pytest **844 passed, 0 failed, 2 skipped**; Harness **15/15 fixtures, 1,917 assertions passed, 0 failed**; Diagram harness **63/63 passed, 0 orphans**; Report harness **282 cells passed**; Playwright **9/9 local + 7/7 live Vercel preview passed**; `next build` 21/21 passed. Merged `fix/full-qa` into `main` and pushed `origin/main` | merged |

---

## Phase 7: Final Report

| Task | Status | Evidence | Commit |
|---|---|---|---|
| 7.1 Write `FINAL_REPORT.md` in plain text | done | Created `FINAL_REPORT.md` covering fixes, before/after test counts, coming-soon features, manual deploy steps, and top 10 next improvements | final |

---

## Phase 8: Product Monetization, SaaS Workflow & Pricing Architecture

| Task | Status | Evidence | Commit |
|---|---|---|---|
| 8.1 Dedicated Pricing Page (`/pricing`) | done | Built responsive `/pricing` page with 4 tiers (Starter $0, Pro $29/mo or $290/yr, Team $99/mo or $990/yr, Enterprise custom), monthly/annual toggle, interactive FinOps ROI calculator, full feature comparison matrix, social proof, and FAQ | `c873f10` |
| 8.2 Dedicated Projects Hub (`/projects`) | done | Built `/projects` workspace hub with 3 tabs (Saved Cloud Architectures, Connected Cloud Accounts, Multi-Env IaC Deployments), 1-click actions to open in Workspace, Terraform, or Deploy, live account list, and project usage meters | `c873f10` |
| 8.3 Global Navigation & In-App Upsell Hooks | done | Added `/pricing` and `/projects` to desktop `<nav>`, `HeaderAuth` ("Upgrade to Pro" pill + "Projects" button), `MobileNav`, and `Footer`; added Pro feature badges on Terraform ZIP download & FinOps Live | `c873f10` |
| 8.4 E2E Playwright Suite & Production Build | done | Added `tests/pricing-and-projects.spec.ts`; all 11 Playwright tests passed (9.4s); Next.js production build generated 23/23 routes with zero errors | `c873f10` |

