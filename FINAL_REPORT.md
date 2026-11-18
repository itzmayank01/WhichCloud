WHICHCLOUD FULL QA & FIX — FINAL REPORT
=======================================
Branch: fix/full-qa -> merged to main
Date: 2026-11-18
Frontend (Vercel): https://whichcloud.vercel.app
Backend (Render): https://whichcloud-backend.onrender.com
Screenshots: docs/qa/ (12 desktop & mobile screenshots captured by Playwright)

1. WHAT WAS BROKEN AND WHAT WAS FIXED
-------------------------------------
- Stale-result bug on /terraform (and /estimate, /audit, /plan, /environments, /dashboard):
  * Root causes found: sessionStorage restored old architecture & hardcoded $519.04 fallback files;
    stale state merged over new state; no AbortController or request-ID guard; fetchThroughWake
    retried aborted requests; /describe/terraform/inspect wasted a separate LLM call via an
    unversioned intake cache; degraded heuristic fallback drafts were cached into Postgres;
    backend POST/dynamic routes lacked Cache-Control: no-store; DEFAULT_WORKLOAD was a composite
    workload rejected with 400.
  * Fixes: Added normalized, schema-versioned workload cache keys (build_workload_cache_key) and
    Cache-Control: no-store on all dynamic backend responses; routed /describe/terraform/inspect
    and /describe/export.tf directly through planning.build(); stopped caching degraded heuristic
    drafts into Postgres; added AbortController, request IDs, clear-on-submit, error+Retry banners,
    empty-input validation, dynamic engine-driven PICK badge, and "Generated for: <first 60 chars>
    at <time>" stamps across /terraform, /estimate, /audit, /plan, /dashboard.

- Engine & regression harness bugs:
  * retail-chain fixture crashed with KeyError: 'business_hours' (invalid peak_shape) and violated
    INV-4 with unstated storage/egress; run_harness.py crashed generating report.md when a fixture
    raised an exception. Fixed load_model.py fallback, run_harness.py guard, and retail-chain.yaml.
  * Added "visitors" / "customers" parsing to constraints.py with scoped monthly-to-daily regex
    (so static sites like "30,000 visitors a month" parse cleanly without breaking daily hospital
    prompts that mention a monthly budget).
  * Added canonical WORKLOAD_TYPE_TO_ARCHETYPE / archetype_from_workload_type() bridge in
    archetype.py so legacy workload_type paths map cleanly to the archetype planner.
  * Audited all 7 archetypes (web_app, event_driven, ml_inference, realtime, migration,
    static_site, batch_etl): all return priced 3-tier designs; Windows/x86 migrations emit 0
    ARM/Graviton SKUs; 40k-student coaching platform sizes ~2.39 TB (not 40 TB).
  * Audited & updated golden totals for justified resilience additions (Hyderabad DR standby on
    hospital-pune Tier 3 within $900 budget; RBI regulated_dr Multi-AZ on fintech-bengaluru).

- Provider switching, price validation & honest site copy:
  * Verified AWS (ap-south-1), GCP (asia-south1), and Azure (centralindia) return provider-native
    services and regions; expanded frontend ServiceIcon.tsx to map all 34 vendored GCP and 27
    vendored Azure icons.
  * Fixed real price validation causes without altering real prices: separated C4D highmem RAM/CPU
    rates in validate_gcp_compute.py; excluded "promo" and "expired" VM meters in pricing/azure.py.
  * Added a visible "Last updated: <date> UTC" badge at the top of /prices.
  * Removed inaccurate site claims ("<300ms", "GCP covers compute only", "0 hardcoded prices in
    the source", "Every price is fetched, not estimated").
  * Marked GCP and Azure live cloud-account connections as "Coming Soon" on /connect, /connect/gcp,
    and /connect/azure (matching the backend's 501 status).

- Architecture diagram viewer:
  * Grouped account-plane governance, security, and observability services inside a labelled
    "Security, Governance & Observability" container inside the Cloud boundary (elkLayout.ts),
    dropping containerless orphan nodes from 3-6 down to 0 across all 63/63 diagram fixtures.
  * Removed tinted subnet boxes and AccountNode tint for crisp AWS-style white containers.
  * Made the "Click to expand" button always discoverable and replaced Iconify CDN icons on the
    expand and full-page close buttons with inline SVGs so they never render blank.

- Whole-site UI & deployment fixes caught by Playwright:
  * Fixed 467px horizontal overflow on /terraform at 390px mobile viewport and removed an invalid
    nested <main> landmark inside /terraform.
  * Fixed Vercel preview deployments falling back to http://127.0.0.1:8010 (which caused Chrome
    Private Network Access CORS errors): unified API_BASE across lib/api.ts, BackendWarmup.tsx,
    and EstimateWorkbench.tsx to automatically use https://whichcloud-backend.onrender.com on
    *.vercel.app when NEXT_PUBLIC_API_URL is unset.
  * Guarded frontend/proxy.ts when Clerk env vars are unset (preventing 500 errors on /connect in
    CI and unconfigured preview environments).
  * Fixed ESLint errors in environments/page.tsx (unescaped quotes) and PricedDiagram.tsx
    (module-scoped useIsomorphicLayoutEffect) and added .github/workflows/ci.yml.

2. BEFORE AND AFTER TEST COUNTS
-------------------------------
- Backend pytest suite:
  * Before (early audit): 808 passed, 13 failed, 2 skipped
  * Baseline on main (aa158d1): 841 passed, 0 failed, 2 skipped, 1 deselected
  * After (fix/full-qa): 844 passed, 0 failed, 2 skipped, 1 deselected (added 3 stale-result API tests)
- Backend regression harness (backend/tests/run_harness.py):
  * Before: 15 fixtures — 11 OK, 4 failed (6 assertion failures + retail-chain KeyError + report crash)
  * After: 15/15 fixtures passed — 1,917 assertions passed, 0 failed
- Frontend diagram layout quality harness (npm run diagram:check):
  * Before: 63 fixtures passed with 3-6 containerless orphan nodes per AWS fixture
  * After: 63/63 fixtures passed (AWS, GCP, Azure) — 0 overlaps, 0 edge-node hits, 0 label overlaps, 0 orphans
- Frontend cost report harness (npm run report:check):
  * After: 282 cells passed, 0 failed
- Frontend TypeScript, ESLint & production build:
  * Before: 56 ESLint errors
  * After: 0 TypeScript errors, 0 ESLint errors (93 legacy warnings), 21/21 Next.js routes build cleanly
- Playwright end-to-end UI suite (frontend/tests/stale-result.spec.ts + full-site-qa.spec.ts):
  * Before: 0 Playwright tests
  * After (local full stack): 9/9 passed (11.0s), including ZIP download + HCL2 validation of every .tf file,
    full-page diagram expand/Escape, mobile 390px overflow <= 4px, 0 console errors, 0 5xx responses
  * After (live Vercel preview https://whichcloud-m1ua7hkd2-team-which-cloud.vercel.app):
    7/7 passed — Home (/), Price index (/prices), Estimate (/estimate form+describe), Plan (/plan),
    Audit (/audit valid+invalid CSV), Environments (/environments), Connect (/connect), and FinOps
    Live Demo (/finops?provider=aws&account_id=demo) all passed with 0 console errors and 0 5xx responses

3. STILL NOT WORKING OR MARKED "COMING SOON"
--------------------------------------------
- Live cloud account connections for GCP (/connect/gcp) and Azure (/connect/azure): backend
  /api/connections/verify returns 501; both are now honestly labelled "Coming Soon" in the UI.
- Third-party FinOps integrations on /connect (Fastly, Snowflake, Datadog, PlanetScale, New Relic):
  marked "Soon" / disabled.
- Multi-environment Terraform toggles (DEV / PROD): supported on AWS only; intentionally hidden on
  GCP and Azure because their Terraform exporters do not yet emit separate environment tfvars.
- Full 36,761-row catalog tests in GitHub Actions CI: CI seeds the 115-row fallback_catalog.json
  into Postgres and runs fast unit + stale-result + Playwright checks on every push; the full
  844-test suite & 15-fixture golden harness run locally (or in CI when repo variable
  WHICHCLOUD_FULL_CATALOG_CI=true is enabled with a provisioned catalog).

4. MANUAL STEPS YOU NEED TO DO
------------------------------
1. Vercel Dashboard -> Project Settings -> Environment Variables:
   - Ensure NEXT_PUBLIC_API_URL=https://whichcloud-backend.onrender.com is set for BOTH
     Production and Preview environments (Preview now falls back cleanly in code too, but
     setting it explicitly keeps server-side ISR builds consistent).
   - Ensure NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY and CLERK_SECRET_KEY are set for Preview if you
     want Clerk sign-in active on preview branches (Production already has them).
   - Confirm Vercel switches Production from development Clerk keys to production Clerk keys
     before public launch (Clerk logs a dev-key warning in console).
2. Render Backend (https://whichcloud-backend.onrender.com):
   - Render auto-deploys from main; after this merge to main, verify the Render deploy completes
     so /describe/terraform/inspect, Cache-Control: no-store, and normalized cache keys go live
     in production.
   - Flush old unversioned Redis / constraints_cache entries (or let the new v2 key prefix
     naturally bypass them — v2 keys already isolate all new requests from stale cache entries).
   - Run backend/scripts/ingest_prices.py on a schedule so the catalog's Last Updated date stays
     fresh (production Render currently reports last_updated: 2026-09-15).
3. GitHub Repository Settings (optional):
   - Check Actions tab to confirm WhichCloud CI passes on main after merge.

5. TOP 10 MOST IMPORTANT NEXT IMPROVEMENTS
------------------------------------------
1. Schedule automated weekly price catalog ingestion (GitHub Action or Render Cron Job) so
   AWS/GCP/Azure prices stay current instead of aging months behind.
2. Switch Clerk on Vercel Production from development keys to a production Clerk instance with
   custom domain.
3. Implement live GCP (BigQuery billing export) and Azure (Cost Management Service Principal)
   account verification so /connect/gcp and /connect/azure graduate from "Coming Soon".
4. Add DEV/PROD environment tfvars support to GCP and Azure Terraform exporters to match AWS.
5. Upgrade Render backend from free/sleep tier (or keep-warm with shorter interval) to eliminate
   20-40s cold-start latency on first /describe calls.
6. Run real `terraform validate` (with cached provider plugin bundle) in CI on generated ZIP
   exports in addition to HCL2 grammar parsing.
7. Clean up the remaining 93 legacy ESLint warnings (`@typescript-eslint/no-explicit-any` in
   api.ts/elkLayout.ts and `react-hooks/set-state-in-effect`) and promote both rules back to error.
8. Add authenticated Playwright E2E tests for /dashboard and /connect/aws using Clerk testing
   tokens.
9. Provision a seeded test catalog snapshot artifact for GitHub Actions so the full 844-test
   pytest suite and 15-fixture golden harness run on every PR without live provider scraping.
10. Expand multi-region / multi-cloud side-by-side comparison mode on /terraform so users can
    diff AWS vs GCP vs Azure monthly costs and service counts in one view.
