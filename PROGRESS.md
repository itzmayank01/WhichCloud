# WhichCloud Full QA & Fix Progress

Branch: `fix/full-qa`
Started: 2026-11-17

## Phase 0: Setup and Baseline

| Task | Status | Evidence | Commit |
|---|---|---|---|
| 0.1 Branch setup & gitignore check | done | Branch `fix/full-qa` created from `main` (`aa158d1`); `.env` & `.env.*` verified in `.gitignore` | pending |
| 0.2 Local Postgres, Redis, Backend (8010), Frontend (3001) | done | `whichcloud-db` (5432 healthy), `whichcloud-cache` (6379 healthy), `/health` OK (36,761 prices), Next.js ready on `127.0.0.1:3001` | pending |
| 0.3 Baseline pytest & regression harness | done | Pytest baseline (from `aa158d1`): 841 passed, 0 failed, 2 skipped, 1 deselected. Regression harness (`run_harness.py`): 15 fixtures, 11 OK, 4 failed (6 assertion failures + `retail-chain` `KeyError: 'business_hours'` + `write_report` crash on `KeyError`) | pending |
| 0.4 Full page, button, form & API checklist | done | Listed below | pending |

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

| Task | Status | Evidence | Commit |
|---|---|---|---|
| 1.1 Diagnose root causes on `/terraform` | doing | Checking frontend state, caches, storage, backend cache keys, race conditions | - |
| 1.2 Fix cache keys & submit lifecycle on `/terraform` | todo | - | - |
| 1.3 Add "Generated for: <first 60 chars> at <time>" indicator | todo | - | - |
| 1.4 Check & fix stale-result bugs on `/estimate`, `/audit`, `/environments`, `/dashboard`, `/plan` | todo | - | - |
| 1.5 Add backend + Playwright tests for stale-result fix | todo | - | - |

---

## Phase 2: Fix Engine Problems

| Task | Status | Evidence | Commit |
|---|---|---|---|
| 2.1 Fix harness failures (`retail-chain` KeyError, golden totals diff) & verify pytest 100% green | todo | - | - |
| 2.2 Consolidate legacy `workload_type` vs `archetype` path | todo | - | - |
| 2.3 Audit & verify all 6 non-web archetypes (`event_driven`, `ml_inference`, `realtime`, `migration`, `static_site`, `batch_etl`) | todo | - | - |
| 2.4 Verify Windows/x86 never gets ARM/Graviton | todo | - | - |
| 2.5 Verify storage default sizing (no 40 TB for 40k students) | todo | - | - |
| 2.6 Verify 3 tiers differ in design and PICK matches recommendation | todo | - | - |
| 2.7 Add fixtures for fixed behaviours & verify golden files | todo | - | - |

---

## Phase 3: Provider Switching and Data Checks

| Task | Status | Evidence | Commit |
|---|---|---|---|
| 3.1 Verify GCP & Azure provider switching (services, icons, or honest coming-soon) | todo | - | - |
| 3.2 Investigate price validation (GCP 90.7%, Azure 5 mismatches) & fix real causes | todo | - | - |
| 3.3 Verify prices show last-updated timestamp & honest site copy | todo | - | - |

---

## Phase 4: Diagram Viewer

| Task | Status | Evidence | Commit |
|---|---|---|---|
| 4.1 Full canvas & fit-to-view on load | todo | - | - |
| 4.2 Click diagram opens full-page view | todo | - | - |
| 4.3 Official AWS-style visual styling (white bg, light borders, clean right-angle arrows) | todo | - | - |
| 4.4 Properly group governance & observability (no disconnected bottom row) | todo | - | - |
| 4.5 Distinct diagram per tier | todo | - | - |

---

## Phase 5: Whole-Site UI Test (Playwright)

| Task | Status | Evidence | Commit |
|---|---|---|---|
| 5.1 Playwright end-to-end test suite covering all pages, buttons, toggles, forms | todo | - | - |
| 5.2 Download ZIP + `terraform validate` verification | todo | - | - |
| 5.3 Mobile (390px) & Desktop (1440px) layout + accessibility checks | todo | - | - |
| 5.4 Capture screenshots to `docs/qa/` | todo | - | - |

---

## Phase 6: CI and Deploy

| Task | Status | Evidence | Commit |
|---|---|---|---|
| 6.1 Add GitHub Actions CI workflow | todo | - | - |
| 6.2 Push `fix/full-qa` & verify Vercel preview deployment | todo | - | - |
| 6.3 Run key Playwright tests against Vercel preview URL | todo | - | - |
| 6.4 Merge `fix/full-qa` into `main` only if all checks green | todo | - | - |

---

## Phase 7: Final Report

| Task | Status | Evidence | Commit |
|---|---|---|---|
| 7.1 Write `FINAL_REPORT.md` in plain text | todo | - | - |
